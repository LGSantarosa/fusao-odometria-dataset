"""KISS-ICP (pure LiDAR odometry) over extracted clouds -> common run format."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from kiss_icp.config import load_config
from kiss_icp.kiss_icp import KissICP

from ofd import config, tracks


def resolve_deskew(extract_meta, override="auto"):
    """Deskew só com tempo por ponto validado na extração; o dataset pode desligá-lo (config kissicp_deskew)."""
    valid = bool(extract_meta.get("deskew", False))
    return valid if override == "auto" else (valid and bool(override))


def run(seq_dir, out_dir, deskew):
    seq_dir = Path(seq_dir)
    cfg = load_config(None)  # kiss-icp 1.3: load_config só recebe o arquivo; ajustes via campos
    cfg.data.deskew = bool(deskew)
    cfg.data.max_range = 100.0
    odom = KissICP(config=cfg)
    stamps = pd.read_csv(seq_dir / "lidar_stamps.csv")
    Ts, ok = [], []
    for t in stamps["ts_ns"].to_numpy(np.int64):
        z = np.load(seq_dir / "clouds" / f"{t}.npz")
        pts = z["xyz"].astype(np.float64)
        if deskew:
            if "t_norm" not in z.files:
                raise RuntimeError(f"deskew=True mas scan {t} sem t_norm")
            times = z["t_norm"].astype(np.float64)
        else:
            times = np.zeros(len(pts))
        odom.register_frame(pts, times)
        Ts.append(odom.last_pose.copy())
        ok.append(1)
    end = stamps["end_ns"].to_numpy(np.int64)
    state = pd.DataFrame({"ts_ns": end, "ok": ok, "map_id": 0})
    meta = {"method": "kissicp", "uses_imu": False, "sensor_frame": "lidar", "deskew": bool(deskew),
            "kiss_icp_version": __import__("kiss_icp").__version__,
            "config": json.loads(cfg.model_dump_json()) if hasattr(cfg, "model_dump_json") else str(cfg)}
    tracks.write_run(out_dir, end, np.stack(Ts), state, pd.DataFrame({"ts_ns": end}), meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", help="dataset.yaml (lê kissicp_deskew: auto|true|false)")
    a = ap.parse_args()
    override = config.load(a.config).kissicp_deskew if a.config else "auto"
    meta = json.loads((Path(a.seq_dir) / "meta.json").read_text())
    run(a.seq_dir, a.out, resolve_deskew(meta, override))


if __name__ == "__main__":
    main()
