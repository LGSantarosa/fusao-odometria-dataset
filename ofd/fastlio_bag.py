"""ROS1 bag -> ROS2 bag with only the LiDAR + IMU topics FAST-LIO needs, in FAST-LIO's time convention.

FAST-LIO treats the cloud header stamp as the scan *start* and per-point times as non-negative offsets from it
(lidar_end_time = header + max offset). Datasets whose header marks the scan *end* (point times <= 0, e.g.
BotanicGarden's VLP16) are rebased here: header += t_min and t -= t_min. The scan end is preserved, so FAST-LIO's
lidar_end_time equals the extraction's end_ns.
"""
from pathlib import Path

import numpy as np
from rosbags.highlevel import AnyReader
from rosbags.rosbag2 import Writer
from rosbags.typesys import Stores, get_typestore

from ofd import pointtime
from ofd.extract import cloud_to_struct, stamp_ns

TS2 = get_typestore(Stores.ROS2_JAZZY)


def _header(h, ns):
    Time, Header = TS2.types["builtin_interfaces/msg/Time"], TS2.types["std_msgs/msg/Header"]
    return Header(stamp=Time(sec=int(ns // 10**9), nanosec=int(ns % 10**9)), frame_id=h.frame_id)


def _cloud(m, point_time):
    ns = stamp_ns(m)
    data = np.frombuffer(bytes(m.data), np.uint8)
    f = point_time.get("field")
    if point_time.get("ref") == "scan_end" and f:
        a = cloud_to_struct(m).copy()
        unit = pointtime.UNIT_TO_S[point_time["unit"]]
        rel = a[f].astype(np.float64) * unit
        tmin = float(rel.min())
        a[f] = ((rel - tmin) / unit).astype(a[f].dtype)
        ns += int(round(tmin * 1e9))
        data = np.frombuffer(a.tobytes(), np.uint8)
    PF, PC2 = TS2.types["sensor_msgs/msg/PointField"], TS2.types["sensor_msgs/msg/PointCloud2"]
    fields = [PF(name=x.name, offset=x.offset, datatype=x.datatype, count=x.count) for x in m.fields]
    return PC2(header=_header(m.header, ns), height=m.height, width=m.width, fields=fields,
               is_bigendian=m.is_bigendian, point_step=m.point_step, row_step=m.row_step, data=data,
               is_dense=m.is_dense)


def _imu(m):
    V, Q, Imu = TS2.types["geometry_msgs/msg/Vector3"], TS2.types["geometry_msgs/msg/Quaternion"], TS2.types["sensor_msgs/msg/Imu"]
    o, w, a = m.orientation, m.angular_velocity, m.linear_acceleration
    return Imu(header=_header(m.header, stamp_ns(m)), orientation=Q(x=o.x, y=o.y, z=o.z, w=o.w),
               orientation_covariance=np.asarray(m.orientation_covariance, np.float64),
               angular_velocity=V(x=w.x, y=w.y, z=w.z),
               angular_velocity_covariance=np.asarray(m.angular_velocity_covariance, np.float64),
               linear_acceleration=V(x=a.x, y=a.y, z=a.z),
               linear_acceleration_covariance=np.asarray(m.linear_acceleration_covariance, np.float64))


def convert(bag1, dst, lidar_topic, imu_topic, point_time, start_s=None, dur_s=None):
    dst = Path(dst)
    msgtype = {lidar_topic: "sensor_msgs/msg/PointCloud2", imu_topic: "sensor_msgs/msg/Imu"}
    with AnyReader([Path(bag1)]) as r, Writer(dst, version=8) as w:
        start = r.start_time + int((start_s or 0) * 1e9)
        stop = start + int(dur_s * 1e9) if dur_s else r.end_time + 1
        out = {t: w.add_connection(t, msgtype[t], typestore=TS2) for t in (lidar_topic, imu_topic)}
        conns = [c for c in r.connections if c.topic in out]
        for c, t, raw in r.messages(connections=conns, start=start, stop=stop):
            m = r.deserialize(raw, c.msgtype)
            msg = _cloud(m, point_time) if c.topic == lidar_topic else _imu(m)
            w.write(out[c.topic], t, TS2.serialize_cdr(msg, msgtype[c.topic]))
