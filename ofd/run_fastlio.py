"""Convert ROS1 bag -> ROS2, run FAST-LIO, play bag, record /Odometry -> common run format."""
import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, fastlio_bag, se3, tracks
from ofd.matching import match_monotonic

ROS = "source /opt/ros/jazzy/setup.bash && source ros2_ws/install/setup.bash && "


def assemble(raw_ts, raw_Ts, end_ns, tol_ms=5.0, min_match=0.9):
    order = np.argsort(raw_ts, kind="stable")
    raw_ts, raw_Ts = np.asarray(raw_ts, np.int64)[order], raw_Ts[order]
    end_ns = np.sort(np.asarray(end_ns, np.int64))
    m = match_monotonic(end_ns, raw_ts, int(tol_ms * 1e6))
    frac = float((m >= 0).mean()) if len(m) else 0.0
    if frac < min_match:
        near = [int(raw_ts[np.argmin(np.abs(raw_ts - e))] - e) for e in end_ns] if len(raw_ts) else [0]
        raise RuntimeError(f"só {frac:.1%} dos scans casaram com poses; mediana(pose - scan) = "
                           f"{np.median(near) / 1e6:.1f} ms — conferir timestamp_unit/end_ns")
    ok = (m >= 0).astype(int)
    state = pd.DataFrame({"ts_ns": end_ns, "ok": ok, "map_id": 0})
    return end_ns[ok == 1], raw_Ts[m[ok == 1]], state, {"matched_frac": frac, "tol_ms": tol_ms}


def _promote(staging, out_dir):
    """Troca out_dir por staging com renomeações (sem estado misturado de execuções diferentes)."""
    out_dir = Path(out_dir)
    old = out_dir.with_name(out_dir.name + f".old-{os.getpid()}")
    if out_dir.exists():
        os.rename(out_dir, old)
    os.rename(staging, out_dir)
    if old.exists():
        shutil.rmtree(old)


def finalize(attempt_dir, out_dir, end_ns, meta):
    """Monta o formato comum a partir dos artefatos de UMA tentativa e promove atomicamente.
    Em falha, levanta e não toca em out_dir; a tentativa fica preservada para comparação."""
    attempt_dir, out_dir = Path(attempt_dir), Path(out_dir)
    raw_ts, raw_Ts = se3.load_tum(attempt_dir / "raw_odom.tum")
    ts, Ts, state, info = assemble(raw_ts, raw_Ts, end_ns)
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


def run(bag1, ds_cfg, cfg_yaml, seq_dir, out_dir, rate=0.5, start=None, duration=None):
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
    with open(attempt / "log.txt", "w") as log:
        node = subprocess.Popen(["bash", "-c", ROS + f"exec ros2 launch fast_lio mapping.launch.py rviz:=false "
                                 f"config_path:={cfg_yaml.parent} config_file:={cfg_yaml.name}"], stdout=log, stderr=log)
        rec = subprocess.Popen(["bash", "-c", ROS + f"exec /usr/bin/python3 tools/fastlio_recorder.py "
                                f"{attempt / 'raw_odom.tum'} 30"], stdout=log, stderr=log)
        try:
            time.sleep(5)
            subprocess.run(["bash", "-c", ROS + f"ros2 bag play {ros2_bag_dir} --rate {rate}"],
                           check=True, stdout=log, stderr=log)
            rec.wait(timeout=600)
        finally:
            for p in (rec, node):
                if p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        p.kill()
    end_ns = pd.read_csv(Path(seq_dir) / "lidar_stamps.csv")["end_ns"].to_numpy(np.int64)
    commit = Path("third_party_fastlio_commit.txt").read_text().strip() if Path("third_party_fastlio_commit.txt").exists() else "unknown"
    meta = {"method": "fastlio", "uses_imu": True, "sensor_frame": "imu", "deskew": True, "continuous_frame": True,
            "fastlio_commit": commit, "config": cfg_yaml.read_text(), "rate": rate,
            "start": start, "duration": duration, "ros2_bag": str(ros2_bag_dir),
            "point_time": ds_cfg.point_time}
    finalize(attempt, out_dir, end_ns, meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--config", required=True, help="dataset.yaml (tópicos e semântica do tempo por ponto)")
    ap.add_argument("--fastlio-config", required=True)
    ap.add_argument("--seq-dir", required=True, help="extração correspondente (para lidar_stamps.csv)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rate", type=float, default=0.5)
    ap.add_argument("--start", type=float)
    ap.add_argument("--duration", type=float)
    a = ap.parse_args()
    run(a.bag, config.load(a.config), a.fastlio_config, a.seq_dir, a.out, a.rate, a.start, a.duration)


if __name__ == "__main__":
    main()
