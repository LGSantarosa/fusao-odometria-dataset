import numpy as np
from pathlib import Path
from rosbags.rosbag1 import Writer
from rosbags.typesys import Stores, get_typestore
from ofd import extract, config

TS = get_typestore(Stores.ROS1_NOETIC)
Image = TS.types["sensor_msgs/msg/Image"]
PC2 = TS.types["sensor_msgs/msg/PointCloud2"]
PF = TS.types["sensor_msgs/msg/PointField"]
Header = TS.types["std_msgs/msg/Header"]
Time = TS.types["builtin_interfaces/msg/Time"]


def hdr(ns):
    return Header(seq=0, stamp=Time(sec=ns // 10**9, nanosec=ns % 10**9), frame_id="x")


def cloud(ns, n=200):
    pts = np.zeros(n, dtype=[("x", "f4"), ("y", "f4"), ("z", "f4"), ("intensity", "f4"), ("time", "f4")])
    pts["x"] = np.linspace(1, 10, n); pts["time"] = np.linspace(0, 0.1, n)
    fields = [PF(name=k, offset=o, datatype=7, count=1) for k, o in
              [("x", 0), ("y", 4), ("z", 8), ("intensity", 12), ("time", 16)]]
    return PC2(header=hdr(ns), height=1, width=n, fields=fields, is_bigendian=False,
               point_step=20, row_step=20 * n, data=np.frombuffer(pts.tobytes(), np.uint8), is_dense=True)


def img(ns):
    return Image(header=hdr(ns), height=4, width=6, encoding="mono8", is_bigendian=0, step=6,
                 data=np.arange(24, dtype=np.uint8))


def make_bag(p):
    base = 1_700_000_000 * 10**9
    with Writer(p) as w:
        cl = w.add_connection("/l", Image.__msgtype__, typestore=TS)
        cr = w.add_connection("/r", Image.__msgtype__, typestore=TS)
        cp = w.add_connection("/p", PC2.__msgtype__, typestore=TS)
        for k in range(3):
            t = base + k * 100_000_000
            w.write(cp, t, TS.serialize_ros1(cloud(t), PC2.__msgtype__))
            w.write(cl, t, TS.serialize_ros1(img(t), Image.__msgtype__))
            w.write(cr, t, TS.serialize_ros1(img(t), Image.__msgtype__))
    return base


def test_extract(tmp_path):
    bag = tmp_path / "x.bag"; make_bag(bag)
    cfg = config.DatasetConfig("x", "survey", {"left": "/l", "right": "/r", "lidar": "/p", "imu": "/i", "gt": "/g"},
                               {"field": "time", "unit": "s", "ref": "scan_start"},
                               {m: np.eye(4) for m in ["orbslam3", "stella", "fastlio", "kissicp"]})
    meta = extract.extract(bag, cfg, tmp_path / "out", None, None, None)
    assert len(list((tmp_path / "out/images/left").glob("*.png"))) == 3
    z = np.load(sorted((tmp_path / "out/clouds").glob("*.npz"))[0])
    assert {"xyz", "intensity", "t_norm"} <= set(z.files)
    assert meta["deskew"] is True and meta["n_scans"] == 3
    st = __import__("pandas").read_csv(tmp_path / "out/lidar_stamps.csv")
    assert ((st["end_ns"] - st["ts_ns"]) > 90_000_000).all()  # end = header + ~0.1 s (ref scan_start)
    assert (tmp_path / "out/scans.csv").exists()


def test_extract_one_bad_scan_disables_deskew(tmp_path, monkeypatch):
    bag = tmp_path / "x.bag"; make_bag(bag)
    calls = {"n": 0}
    real = extract.pointtime.normalize

    def flaky(*a, **k):
        calls["n"] += 1
        return (None, {"t_min_s": 0, "t_max_s": 0, "span_s": 0, "monotonic_frac": 0, "valid": False}) \
            if calls["n"] == 2 else real(*a, **k)
    monkeypatch.setattr(extract.pointtime, "normalize", flaky)
    cfg = config.DatasetConfig("x", "survey", {"left": "/l", "right": "/r", "lidar": "/p", "imu": "/i", "gt": "/g"},
                               {"field": "time", "unit": "s", "ref": "scan_start"},
                               {m: np.eye(4) for m in ["orbslam3", "stella", "fastlio", "kissicp"]})
    meta = extract.extract(bag, cfg, tmp_path / "out", None, None, None)
    assert meta["deskew"] is False and meta["deskew_valid_frac"] < 1.0


PoseStamped = TS.types["geometry_msgs/msg/PoseStamped"]
Pose = TS.types["geometry_msgs/msg/Pose"]
Point = TS.types["geometry_msgs/msg/Point"]
Quaternion = TS.types["geometry_msgs/msg/Quaternion"]


def make_gt_bag(p, base, n=3):
    with Writer(p) as w:
        c = w.add_connection("/gt_poses", PoseStamped.__msgtype__, typestore=TS)
        for k in range(n):
            t = base + k * 100_000_000
            m = PoseStamped(header=hdr(t), pose=Pose(position=Point(x=float(k), y=0.0, z=0.0),
                                                     orientation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)))
            w.write(c, t, TS.serialize_ros1(m, PoseStamped.__msgtype__))


def _cfg(stereo=None):
    return config.DatasetConfig("x", "survey", {"left": "/l", "right": "/r", "lidar": "/p", "imu": "/i", "gt": "/gt_poses"},
                                {"field": "time", "unit": "s", "ref": "scan_start"},
                                {m: np.eye(4) for m in ["orbslam3", "stella", "fastlio", "kissicp"]}, stereo=stereo)


def test_extract_gt_from_separate_bag(tmp_path):
    bag = tmp_path / "x.bag"; base = make_bag(bag)
    make_gt_bag(tmp_path / "gt.bag", base)
    extract.extract(bag, _cfg(), tmp_path / "out", None, None, None, gt_bag=tmp_path / "gt.bag")
    from ofd import se3
    ts, Ts = se3.load_tum(tmp_path / "out/gt.tum")
    assert len(ts) == 3 and ts[0] == base and abs(Ts[2][0, 3] - 2.0) < 1e-9


def test_extract_rectifies_when_stereo_calib_given(tmp_path):
    bag = tmp_path / "x.bag"; make_bag(bag)
    K = [[5.0, 0, 3.0], [0, 5.0, 2.0], [0, 0, 1]]
    T01 = np.eye(4); T01[0, 3] = 0.2
    stereo = {"K0": K, "D0": [0, 0, 0, 0, 0], "K1": K, "D1": [0, 0, 0, 0, 0],
              "T_c0_c1": T01.ravel().tolist(), "size": [6, 4]}
    meta = extract.extract(bag, _cfg(stereo), tmp_path / "out", None, None, None)
    r = meta["rectified"]
    assert abs(r["baseline"] - 0.2) < 1e-9 and r["width"] == 6 and len(r["T_cam0_rect"]) == 16


def test_gt_bag_drops_nonfinite_poses(tmp_path):
    p = tmp_path / "gt.bag"; base = 1_700_000_000 * 10**9
    with Writer(p) as w:
        c = w.add_connection("/gt_poses", PoseStamped.__msgtype__, typestore=TS)
        for k in range(4):
            t = base + k * 100_000_000
            q = Quaternion(x=float("nan"), y=float("nan"), z=float("nan"), w=float("nan")) if k == 2 else \
                Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
            m = PoseStamped(header=hdr(t), pose=Pose(position=Point(x=float(k), y=0.0, z=0.0), orientation=q))
            w.write(c, t, TS.serialize_ros1(m, PoseStamped.__msgtype__))
    ts, Ts, dropped = extract.gt_from_bag(p, "/gt_poses")
    assert dropped == 1 and len(ts) == 3 and np.isfinite(Ts).all()
