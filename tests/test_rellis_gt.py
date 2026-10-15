import numpy as np
import pytest
from ofd import rellis_gt, se3

MS = 1_000_000


def kitti_lines(n):
    return "\n".join(" ".join(f"{v:g}" for v in [1, 0, 0, i, 0, 1, 0, 2 * i, 0, 0, 1, 0]) for i in range(n)) + "\n"


def test_kth_line_is_kth_scan(tmp_path):
    (tmp_path / "poses.txt").write_text(kitti_lines(5))
    Ts = rellis_gt.load_kitti(tmp_path / "poses.txt")
    stamps = 1_000 * 10**9 + np.arange(5) * 100 * MS
    ts, out = rellis_gt.align(stamps, Ts)
    assert ts.tolist() == stamps.tolist()
    assert np.allclose(out[:, 0, 3], np.arange(5)) and np.allclose(out[:, 1, 3], 2 * np.arange(5))
    se3.save_tum(tmp_path / "gt.tum", ts, out)
    ts2, Ts2 = se3.load_tum(tmp_path / "gt.tum")
    assert ts2.tolist() == stamps.tolist() and np.allclose(Ts2, out)


def test_count_mismatch_refuses():
    with pytest.raises(ValueError, match="scans"):
        rellis_gt.align(np.arange(4) * 100 * MS, np.stack([np.eye(4)] * 5))


def test_gap_refuses():
    stamps = np.array([0, 100, 200, 400, 500]) * MS                  # lacuna de 200 ms
    with pytest.raises(ValueError, match="lacuna"):
        rellis_gt.align(stamps, np.stack([np.eye(4)] * 5))


def test_scan_stamps_keep_bag_order_so_disorder_is_refused(tmp_path):
    from rosbags.rosbag1 import Writer
    from tests.test_extract import TS, PC2, cloud
    p = tmp_path / "s.bag"
    with Writer(p) as w:
        c = w.add_connection("/os1_cloud_node/points", PC2.__msgtype__, typestore=TS)
        for k, h in enumerate([100, 300, 200]):                      # header fora de ordem; gravação em ordem
            w.write(c, (k + 1) * 100 * MS, TS.serialize_ros1(cloud(h * MS, n=4), PC2.__msgtype__))
    stamps = rellis_gt.scan_stamps_in_bag_order(p)
    assert stamps.tolist() == [100 * MS, 300 * MS, 200 * MS]
    with pytest.raises(ValueError, match="lacuna"):
        rellis_gt.align(stamps, np.stack([np.eye(4)] * 3))
