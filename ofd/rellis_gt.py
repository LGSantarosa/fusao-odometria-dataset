"""RELLIS-3D poses.txt (KITTI 3x4, sem timestamps) -> gt.tum: a k-ésima linha é a pose do k-ésimo scan do bag
(veredito B de docs/preflight_rellis.md). Recusa se a contagem divergir ou houver lacuna entre scans."""
import argparse
from pathlib import Path

import numpy as np

from ofd import se3
from ofd.preflight_rellis import bag_scan_stamps


def load_kitti(path):
    rows = np.loadtxt(path, ndmin=2).reshape(-1, 3, 4)
    Ts = np.tile(np.eye(4), (len(rows), 1, 1))
    Ts[:, :3, :] = rows
    return Ts


def scan_stamps_in_bag_order(bag, topic="/os1_cloud_node/points"):
    return bag_scan_stamps(bag, topic, sort=False)


def align(stamps_ns, Ts, max_gap_ms=150.0):
    stamps_ns = np.asarray(stamps_ns, np.int64)
    if len(stamps_ns) != len(Ts):
        raise ValueError(f"{len(stamps_ns)} scans no bag != {len(Ts)} linhas no poses.txt (veredito C)")
    gaps = np.diff(stamps_ns) / 1e6
    if len(gaps) and (gaps.max() > max_gap_ms or gaps.min() <= 0):
        raise ValueError(f"ordem/lacuna entre scans fora de (0, {max_gap_ms}] ms: min {gaps.min():.1f}, max {gaps.max():.1f}")
    return stamps_ns, Ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--poses", required=True, help="Rellis-3D/<seq>/poses.txt")
    ap.add_argument("--out", required=True, help="gt.tum (frame ouster1/os1_lidar, o mesmo das nuvens do bag)")
    ap.add_argument("--topic", default="/os1_cloud_node/points")
    ap.add_argument("--max-gap-ms", type=float, default=150.0)
    a = ap.parse_args()
    ts, Ts = align(scan_stamps_in_bag_order(a.bag, a.topic), load_kitti(a.poses), a.max_gap_ms)
    se3.save_tum(Path(a.out), ts, Ts)
    print(f"{len(ts)} poses -> {a.out}")


if __name__ == "__main__":
    main()
