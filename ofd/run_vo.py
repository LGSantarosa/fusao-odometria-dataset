"""Run VO binaries over extracted stereo and convert frames.csv -> common run format."""
import argparse
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import se3, tracks

BIN = {"orbslam3": "third_party/bin/orbslam3_stereo_log", "stella": "third_party/bin/stella_stereo_log"}
VOCAB = {"orbslam3": "third_party/ORB_SLAM3/Vocabulary/ORBvoc.txt", "stella": "third_party/orb_vocab.fbow"}


def convert(frames_csv, out_dir, method, meta):
    f = pd.read_csv(frames_csv)
    ok = f[f["ok"] == 1]
    Ts = np.stack([se3.to_mat(r[["x", "y", "z"]].to_numpy(float), r[["qx", "qy", "qz", "qw"]].to_numpy(float))
                   for _, r in ok.iterrows()]) if len(ok) else np.zeros((0, 4, 4))
    ind = f[["ts_ns", "inliers", "n_features", "reproj_err", "tracked_ratio"]].copy()
    ind.loc[ind["reproj_err"] < 0, "reproj_err"] = np.nan
    tracks.write_run(out_dir, ok["ts_ns"].to_numpy(np.int64), Ts, f[["ts_ns", "ok", "map_id"]], ind,
                     {"method": method, "uses_imu": False, "sensor_frame": "cam_left", "loop_closure": False, **meta})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True, choices=list(BIN))
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--settings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rate", type=float, default=1.0, help="1.0 = tempo real; 0 = sem espera (só debug)")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "VO_RATE": str(a.rate)}
    with open(out / "log.txt", "w") as log:
        subprocess.run([BIN[a.method], VOCAB[a.method], a.settings, a.seq_dir, str(out)],
                       check=True, stdout=log, stderr=log, env=env)
    commit = {"orbslam3": "4452a3c4ab75", "stella": "e445b5452535"}[a.method]
    convert(out / "frames.csv", out, a.method,
            {"settings": Path(a.settings).read_text(), "rate": a.rate, "commit": commit})


if __name__ == "__main__":
    main()
