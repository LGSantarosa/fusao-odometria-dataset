"""Uniform LiDAR indicators from a method's own consecutive ΔT (causal: uses scans k-1, k only)."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, indicators, se3, tracks


def compute(seq_dir, run_dir, T_L_S):
    seq_dir, run_dir = Path(seq_dir), Path(run_dir)
    tr, ind, _ = tracks.load_run(run_dir)
    st = pd.read_csv(seq_dir / "lidar_stamps.csv")
    cloud_of = dict(zip(st["end_ns"].astype(np.int64), st["ts_ns"].astype(np.int64)))  # end_ns -> arquivo
    rows = []
    for k in range(1, len(tr.ts_ns)):
        a, b = int(tr.ts_ns[k - 1]), int(tr.ts_ns[k])
        if tr.segment[k] != tr.segment[k - 1] or a not in cloud_of or b not in cloud_of:
            continue
        dT = se3.conjugate(se3.delta(tr.Ts[k - 1], tr.Ts[k]), T_L_S)
        src = np.load(seq_dir / "clouds" / f"{cloud_of[b]}.npz")["xyz"]
        tgt = np.load(seq_dir / "clouds" / f"{cloud_of[a]}.npz")["xyz"]
        rows.append({"ts_ns": b, **indicators.registration_quality(src, tgt, dT)})
    new = pd.DataFrame(rows, columns=["ts_ns", "fitness", "inlier_rmse", "unmatched_ratio", "n_points"])
    base = ind.drop(columns=[c for c in new.columns if c in ind.columns], errors="ignore").reset_index()
    merged = base.merge(new, on="ts_ns", how="outer").sort_values("ts_ns")
    merged.to_csv(run_dir / "indicators.csv", index=False)
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--method", required=True, choices=["fastlio", "kissicp"])
    a = ap.parse_args()
    compute(a.seq_dir, a.run_dir, config.load(a.config).T_L_S[a.method])


if __name__ == "__main__":
    main()
