import numpy as np
from rosbags.highlevel import AnyReader
from rosbags.rosbag1 import Writer
from rosbags.typesys import Stores, get_typestore
from ofd import fastlio_bag
from ofd.extract import cloud_to_struct

TS = get_typestore(Stores.ROS1_NOETIC)
PC2, PF, Imu = TS.types["sensor_msgs/msg/PointCloud2"], TS.types["sensor_msgs/msg/PointField"], TS.types["sensor_msgs/msg/Imu"]
Header, Time = TS.types["std_msgs/msg/Header"], TS.types["builtin_interfaces/msg/Time"]
Vec3, Quat = TS.types["geometry_msgs/msg/Vector3"], TS.types["geometry_msgs/msg/Quaternion"]
BASE = 1_666_059_817_000_000_000


def hdr(ns):
    return Header(seq=0, stamp=Time(sec=ns // 10**9, nanosec=ns % 10**9), frame_id="velodyne")


def cloud(ns, t):   # campo time float32 relativo ao FIM do scan (como no BotanicGarden)
    n = len(t)
    pts = np.zeros(n, dtype=[("x", "f4"), ("y", "f4"), ("z", "f4"), ("intensity", "f4"), ("ring", "u2"), ("time", "f4")])
    pts["x"] = 5.0; pts["time"] = t
    fields = [PF(name=k, offset=o, datatype=d, count=1) for k, o, d in
              [("x", 0, 7), ("y", 4, 7), ("z", 8, 7), ("intensity", 12, 7), ("ring", 16, 4), ("time", 18, 7)]]
    return PC2(header=hdr(ns), height=1, width=n, fields=fields, is_bigendian=False, point_step=22,
               row_step=22 * n, data=np.frombuffer(pts.tobytes(), np.uint8), is_dense=True)


def imu(ns):
    return Imu(header=hdr(ns), orientation=Quat(x=0., y=0., z=0., w=1.), orientation_covariance=np.zeros(9),
               angular_velocity=Vec3(x=0., y=0., z=0.1), angular_velocity_covariance=np.zeros(9),
               linear_acceleration=Vec3(x=0., y=0., z=9.8), linear_acceleration_covariance=np.zeros(9))


def make_bag(p):
    with Writer(p) as w:
        cl = w.add_connection("/velodyne_points", PC2.__msgtype__, typestore=TS)
        ci = w.add_connection("/imu/data", Imu.__msgtype__, typestore=TS)
        for k in range(3):
            t = BASE + k * 100_000_000
            w.write(cl, t, TS.serialize_ros1(cloud(t, np.linspace(-0.0995, 0.0013, 100).astype(np.float32)), PC2.__msgtype__))
            w.write(ci, t, TS.serialize_ros1(imu(t), Imu.__msgtype__))


def read(p):
    out = {}
    with AnyReader([p]) as r:
        for c, _, raw in r.messages():
            out.setdefault(c.topic, []).append(r.deserialize(raw, c.msgtype))
    return out


def test_scan_end_clouds_rebased_to_scan_start(tmp_path):
    src = tmp_path / "in.bag"; make_bag(src)
    dst = tmp_path / "out_ros2"
    fastlio_bag.convert(src, dst, "/velodyne_points", "/imu/data", {"field": "time", "unit": "s", "ref": "scan_end"})
    m = read(dst)
    assert len(m["/velodyne_points"]) == 3 and len(m["/imu/data"]) == 3
    c = m["/velodyne_points"][0]
    a = cloud_to_struct(c)
    stamp = c.header.stamp.sec * 10**9 + c.header.stamp.nanosec
    assert abs(stamp - (BASE - 99_500_000)) < 1_000          # header = início do scan
    assert a["time"].min() >= 0 and abs(a["time"].max() - 0.1008) < 1e-5
    end = stamp + int(round(float(a["time"].max()) * 1e9))
    assert abs(end - (BASE + 1_300_000)) < 2_000             # fim do scan preservado (= end_ns da extração)
    i = m["/imu/data"][0]
    assert i.header.stamp.sec * 10**9 + i.header.stamp.nanosec == BASE   # IMU intacta


def test_scan_start_passthrough(tmp_path):
    src = tmp_path / "in.bag"; make_bag(src)
    dst = tmp_path / "out_ros2"
    fastlio_bag.convert(src, dst, "/velodyne_points", "/imu/data", {"field": "time", "unit": "s", "ref": "scan_start"})
    c = read(dst)["/velodyne_points"][0]
    assert c.header.stamp.sec * 10**9 + c.header.stamp.nanosec == BASE
