"""Convert ROS1 bag -> ROS2, run FAST-LIO, play bag, record /Odometry -> common run format."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, fastlio_bag, proc, se3, tracks
from ofd.matching import match_monotonic

ROS = "source /opt/ros/jazzy/setup.bash && source ros2_ws/install/setup.bash && "


TOL_MS = 20.0


def assemble(raw_ts, raw_Ts, end_ns, tol_ms=TOL_MS, min_match=0.9, imu_window=None):
    """imu_window=(t0, t1): um LIO não pode estimar fora da cobertura da IMU; a fração mínima é exigida só
    sobre os scans dentro dela (os de fora ficam ok=0 e são contados à parte).

    tol_ms: o FAST-LIO carimba a pose no último ponto que sobra após o próprio pré-processamento (distância mínima,
    subamostragem); end_ns é o último ponto válido da nuvem inteira. Os dois "fins da varredura" diferem em até
    ~7 ms (1018-13). As janelas de ±tol_ms ficam centradas no end_ns de cada scan, e o menor intervalo entre scans
    é 98,3 ms (1018-13): 2 x 20 < 98 -> janelas de scans vizinhos não se sobrepõem. O menor intervalo entre poses
    (>= 96 ms) é só uma verificação adicional de unicidade. O desvio observado vai para o run.json."""
    order = np.argsort(raw_ts, kind="stable")
    raw_ts, raw_Ts = np.asarray(raw_ts, np.int64)[order], raw_Ts[order]
    end_ns = np.sort(np.asarray(end_ns, np.int64))
    m = match_monotonic(end_ns, raw_ts, int(tol_ms * 1e6))
    cov = np.ones(len(end_ns), bool) if imu_window is None else (end_ns >= imu_window[0]) & (end_ns <= imu_window[1])
    frac = float((m[cov] >= 0).mean()) if cov.any() else 0.0
    frac_all = float((m >= 0).mean()) if len(m) else 0.0
    if frac < min_match:
        near = [int(raw_ts[np.argmin(np.abs(raw_ts - e))] - e) for e in end_ns] if len(raw_ts) else [0]
        raise RuntimeError(f"só {frac:.1%} dos scans casaram com poses; mediana(pose - scan) = "
                           f"{np.median(near) / 1e6:.1f} ms — conferir timestamp_unit/end_ns")
    ok = ((m >= 0) & cov).astype(int)
    state = pd.DataFrame({"ts_ns": end_ns, "ok": ok, "map_id": 0})
    off = (raw_ts[m[m >= 0]] - end_ns[m >= 0]) / 1e6          # desvio assinado pose - fim do scan (ms)
    gap = np.diff(raw_ts) / 1e6
    stats = {"offset_ms_min": float(off.min()), "offset_ms_max": float(off.max()),
             "offset_ms_median": float(np.median(off)), "offset_abs_ms_p95": float(np.percentile(np.abs(off), 95)),
             "offset_abs_ms_max": float(np.abs(off).max())} if len(off) else {}
    return end_ns[ok == 1], raw_Ts[m[ok == 1]], state, {
        "matched_frac": frac, "matched_frac_all": frac_all, "n_scans_without_imu": int((~cov).sum()),
        "tol_ms": tol_ms, **stats, "min_pose_spacing_ms": float(gap.min()) if len(gap) else None}


def _promote(staging, out_dir):
    """Troca out_dir por staging com renomeações (sem estado misturado de execuções diferentes)."""
    out_dir = Path(out_dir)
    old = out_dir.with_name(out_dir.name + f".old-{os.getpid()}")
    if out_dir.exists():
        os.rename(out_dir, old)
    os.rename(staging, out_dir)
    if old.exists():
        shutil.rmtree(old)


def imu_window(ros2_bag, imu_topic):
    from rosbags.highlevel import AnyReader
    with AnyReader([Path(ros2_bag)]) as r:
        ts = [t for c, t, _ in r.messages(connections=[c for c in r.connections if c.topic == imu_topic])]
    return (int(min(ts)), int(max(ts))) if ts else None


def finalize(attempt_dir, out_dir, end_ns, meta, imu_win=None, tol_ms=TOL_MS):
    """Monta o formato comum a partir dos artefatos de UMA tentativa e promove atomicamente.
    Em falha, levanta e não toca em out_dir; a tentativa fica preservada para comparação."""
    attempt_dir, out_dir = Path(attempt_dir), Path(out_dir)
    raw_ts, raw_Ts = se3.load_tum(attempt_dir / "raw_odom.tum")
    ts, Ts, state, info = assemble(raw_ts, raw_Ts, end_ns, tol_ms=tol_ms, imu_window=imu_win)
    staging = out_dir.with_name(out_dir.name + f".staging-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    try:
        tracks.write_run(staging, ts, Ts, state, pd.DataFrame({"ts_ns": ts}),
                         {**meta, **info, "attempt_dir": str(attempt_dir)})
        for f in ("log.txt", "raw_odom.tum"):
            if (attempt_dir / f).exists():
                shutil.copy2(attempt_dir / f, staging / f)
        _promote(staging, out_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def run(bag1, ds_cfg, cfg_yaml, seq_dir, out_dir, rate=0.5, start=None, duration=None, tol_ms=TOL_MS):
    out_dir = Path(out_dir)
    attempt = out_dir.with_name(out_dir.name + ".attempts") / time.strftime("%Y%m%dT%H%M%S")
    attempt.mkdir(parents=True, exist_ok=False)
    win = f"_s{start}_d{duration}" if start is not None or duration else ""
    ros2_bag_dir = Path(bag1).with_name(Path(bag1).stem + f"_fastlio{win}_ros2")
    if not ros2_bag_dir.exists():   # só LiDAR + IMU, na convenção de tempo do FAST-LIO, já recortado na janela
        tmp = ros2_bag_dir.with_name(ros2_bag_dir.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        fastlio_bag.convert(bag1, tmp, ds_cfg.topics["lidar"], ds_cfg.topics["imu"], ds_cfg.point_time, start, duration)
        os.rename(tmp, ros2_bag_dir)
    cfg_yaml = Path(cfg_yaml).resolve()
    shutil.copy2(cfg_yaml, attempt / "fastlio_config.yaml")   # configuração efetiva desta tentativa
    proc.assert_not_running("fastlio_mapping")   # nó órfão de outra execução contaminaria esta
    with open(attempt / "log.txt", "w") as log:
        node = proc.spawn(["bash", "-c", ROS + f"exec ros2 launch fast_lio mapping.launch.py rviz:=false "
                                 f"config_path:={cfg_yaml.parent} config_file:={cfg_yaml.name}"], stdout=log, stderr=log)
        rec = proc.spawn(["bash", "-c", ROS + f"exec /usr/bin/python3 tools/fastlio_recorder.py "
                                f"{attempt / 'raw_odom.tum'} 30"], stdout=log, stderr=log)
        try:
            time.sleep(5)
            subprocess.run(["bash", "-c", ROS + f"ros2 bag play {ros2_bag_dir} --rate {rate}"],
                           check=True, stdout=log, stderr=log)
            rec.wait(timeout=600)
        finally:
            for p in (rec, node):
                proc.stop_group(p)
    proc.assert_not_running("fastlio_mapping")      # garante que nada sobreviveu à tentativa
    end_ns = pd.read_csv(Path(seq_dir) / "lidar_stamps.csv")["end_ns"].to_numpy(np.int64)
    commit = Path("third_party_fastlio_commit.txt").read_text().strip() if Path("third_party_fastlio_commit.txt").exists() else "unknown"
    meta = {"method": "fastlio", "uses_imu": True, "sensor_frame": "imu", "deskew": True, "continuous_frame": True,
            "fastlio_commit": commit, "fastlio_patches": sorted(p.name for p in Path("patches/fastlio").glob("*.patch")),
            "config": cfg_yaml.read_text(), "rate": rate,
            "start": start, "duration": duration, "ros2_bag": str(ros2_bag_dir),
            "point_time": ds_cfg.point_time}
    finalize(attempt, out_dir, end_ns, meta, imu_window(ros2_bag_dir, ds_cfg.topics["imu"]), tol_ms)


ASSEMBLE_KEYS = {"matched_frac", "matched_frac_all", "n_scans_without_imu", "tol_ms", "offset_ms_min",
                 "offset_ms_max", "offset_ms_median", "offset_abs_ms_p95", "offset_abs_ms_max",
                 "min_pose_spacing_ms", "attempt_dir"}


def reassemble(ds_cfg, seq_dir, out_dir, tol_ms=TOL_MS):
    """Remonta out_dir a partir do raw_odom.tum da tentativa registrada no run.json, sem reexecutar o FAST-LIO."""
    out_dir = Path(out_dir)
    old = json.loads((out_dir / "run.json").read_text())
    meta = {k: v for k, v in old.items() if k not in ASSEMBLE_KEYS}
    end_ns = pd.read_csv(Path(seq_dir) / "lidar_stamps.csv")["end_ns"].to_numpy(np.int64)
    finalize(old["attempt_dir"], out_dir, end_ns, {**meta, "reassembled_from": old["attempt_dir"]},
             imu_window(old["ros2_bag"], ds_cfg.topics["imu"]), tol_ms)
    print(f"{out_dir}: remontado com tol_ms={tol_ms}. indicators.csv voltou ao esboço: refazer ofd.lidar_indicators, "
          "ofd.build_dataset e ofd.evaluate.", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", help="obrigatório, exceto com --reassemble")
    ap.add_argument("--config", required=True, help="dataset.yaml (tópicos e semântica do tempo por ponto)")
    ap.add_argument("--fastlio-config", help="obrigatório, exceto com --reassemble")
    ap.add_argument("--seq-dir", required=True, help="extração correspondente (para lidar_stamps.csv)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rate", type=float, default=0.5)
    ap.add_argument("--start", type=float)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--tol-ms", type=float, default=TOL_MS, help="tolerância do casamento pose <-> fim do scan")
    ap.add_argument("--reassemble", action="store_true",
                    help="só remonta --out a partir do raw_odom.tum já gravado (não executa o FAST-LIO); "
                         "depois, refazer lidar_indicators, build_dataset e evaluate")
    a = ap.parse_args()
    if a.reassemble:
        reassemble(config.load(a.config), a.seq_dir, a.out, a.tol_ms)
        return
    if not (a.bag and a.fastlio_config):
        ap.error("--bag e --fastlio-config são obrigatórios sem --reassemble")
    run(a.bag, config.load(a.config), a.fastlio_config, a.seq_dir, a.out, a.rate, a.start, a.duration, a.tol_ms)


if __name__ == "__main__":
    main()
