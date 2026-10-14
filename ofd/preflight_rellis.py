"""Prove (or refute) the mapping RELLIS-3D bag scans -> poses.txt entries (monotonic, one-to-one)."""
import argparse
from pathlib import Path

import numpy as np
from rosbags.highlevel import AnyReader

from ofd.matching import match_monotonic


def bag_scan_stamps(bag, topic="/os1_cloud_node/points"):
    with AnyReader([Path(bag)]) as r:
        conns = [c for c in r.connections if c.topic == topic]
        out = []
        for c, _, raw in r.messages(connections=conns):
            h = r.deserialize(raw, c.msgtype).header.stamp
            out.append(h.sec * 1_000_000_000 + h.nanosec)
    return np.sort(np.array(out, dtype=np.int64))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--pose-times", required=True, help="1 timestamp (s) por linha, alinhado linha a linha ao poses.txt")
    ap.add_argument("--tol-ms", type=float, default=5.0)
    a = ap.parse_args()
    b = bag_scan_stamps(a.bag)
    p = np.sort((np.loadtxt(a.pose_times) * 1e9).astype(np.int64))
    m = match_monotonic(b, p, int(a.tol_ms * 1e6))
    frac = float((m >= 0).mean()) if len(m) else 0.0
    print(f"scans no bag: {len(b)}  casados: {(m >= 0).sum()} ({frac:.1%})  idx poses: {m[m >= 0][:1]}..{m[m >= 0][-1:]}")


if __name__ == "__main__":
    main()
