"""KISS-ICP (pure LiDAR odometry) over extracted clouds -> common run format."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from kiss_icp.config import load_config
from kiss_icp.kiss_icp import KissICP

from ofd import config, se3, tracks
from ofd.kissicp_conditions import CONDITIONS, ROTATION_DIRECTIONS, prepare_scan


def resolve_deskew(extract_meta, override="auto"):
    """Deskew só com tempo por ponto validado na extração; o dataset pode desligá-lo (config kissicp_deskew)."""
    valid = bool(extract_meta.get("deskew", False))
    return valid if override == "auto" else (valid and bool(override))


def _scan_table(seq_dir):
    seq_dir = Path(seq_dir)
    if (seq_dir / "scans.csv").exists():
        return pd.read_csv(seq_dir / "scans.csv")
    st = pd.read_csv(seq_dir / "lidar_stamps.csv")
    st["t_min_s"] = 0.0
    st["span_s"] = (st["end_ns"] - st["ts_ns"]) / 1e9
    return st


def run(seq_dir, out_dir, deskew=None, condition=None, rotation_direction=None, gt_tum=None):
    seq_dir = Path(seq_dir)
    condition = condition or ("D1" if deskew else "D0")
    if condition not in CONDITIONS:
        raise ValueError(f"condition deve ser um de {CONDITIONS}")
    if condition in ("D3", "D4prime") and rotation_direction not in ROTATION_DIRECTIONS:
        raise ValueError(f"{condition} exige rotation_direction em {ROTATION_DIRECTIONS}")
    gt = se3.load_tum(gt_tum or seq_dir / "gt.tum") if condition in ("D4", "D4prime") else None
    cfg = load_config(None)  # kiss-icp 1.3: load_config só recebe o arquivo; ajustes via campos
    cfg.data.deskew = condition in ("D1", "D2", "D3")
    cfg.data.max_range = 100.0
    odom = KissICP(config=cfg)
    stamps = _scan_table(seq_dir)
    Ts, ok = [], []
    diagnostics, n_external, n_external_missing = [], 0, 0
    for _, row in stamps.iterrows():
        t = int(row["ts_ns"])
        z = np.load(seq_dir / "clouds" / f"{t}.npz")
        prepared = prepare_scan(z["xyz"], z, row, condition, rotation_direction, gt)
        odom.register_frame(prepared.points, prepared.times)
        if prepared.diagnostic:
            diagnostics.append(prepared.diagnostic)
        if condition in ("D4", "D4prime"):
            n_external += int(prepared.externally_compensated)
            n_external_missing += int(not prepared.externally_compensated)
        Ts.append(odom.last_pose.copy())
        ok.append(1)
    end = stamps["end_ns"].to_numpy(np.int64)
    state = pd.DataFrame({"ts_ns": end, "ok": ok, "map_id": 0})
    diag = ({"time_geo_corr_median": float(np.nanmedian([d["time_geo_corr"] for d in diagnostics])),
             "time_geo_abs_ms_median": float(np.median([d["time_geo_abs_ms_median"] for d in diagnostics])),
             "time_geo_n_scans": len(diagnostics)} if diagnostics else {})
    meta = {"method": "kissicp", "uses_imu": False, "sensor_frame": "lidar",
            "deskew": condition != "D0", "deskew_internal": condition in ("D1", "D2", "D3"),
            "deskew_external": condition in ("D4", "D4prime"), "condition": condition,
            "rotation_direction": rotation_direction, "external_compensated_scans": n_external,
            "external_uncompensated_scans": n_external_missing, "continuous_frame": True,
            "kiss_icp_version": __import__("kiss_icp").__version__,
            "config": json.loads(cfg.model_dump_json()) if hasattr(cfg, "model_dump_json") else str(cfg), **diag}
    tracks.write_run(out_dir, end, np.stack(Ts), state, pd.DataFrame({"ts_ns": end}), meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", help="dataset.yaml (lê kissicp_deskew: auto|true|false)")
    ap.add_argument("--condition", choices=CONDITIONS, help="condição pré-registrada D0--D4prime")
    ap.add_argument("--rotation-direction", choices=ROTATION_DIRECTIONS,
                    help="obrigatório para D3/D4prime; sentido visto de cima")
    ap.add_argument("--gt-tum", help="GT TUM para D4/D4prime (padrão: <seq-dir>/gt.tum)")
    a = ap.parse_args()
    ds_cfg = config.load(a.config) if a.config else None
    override = ds_cfg.kissicp_deskew if ds_cfg else "auto"
    meta = json.loads((Path(a.seq_dir) / "meta.json").read_text())
    default_condition = "D1" if resolve_deskew(meta, override) else "D0"
    run(a.seq_dir, a.out, condition=a.condition or default_condition,
        rotation_direction=a.rotation_direction or (ds_cfg.lidar_rotation_direction if ds_cfg else None),
        gt_tum=a.gt_tum)


if __name__ == "__main__":
    main()
