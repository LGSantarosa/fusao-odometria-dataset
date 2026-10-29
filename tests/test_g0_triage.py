import datetime as dt
import json
import os
import stat

import numpy as np
import pytest
from rosbags.highlevel import AnyReader
from rosbags.rosbag1 import Writer
from rosbags.typesys import Stores, get_typestore

from ofd import g0_triage as g

TS = get_typestore(Stores.ROS1_NOETIC)
Image = TS.types["sensor_msgs/msg/Image"]
PC2 = TS.types["sensor_msgs/msg/PointCloud2"]
PF = TS.types["sensor_msgs/msg/PointField"]
Imu = TS.types["sensor_msgs/msg/Imu"]
PoseStamped = TS.types["geometry_msgs/msg/PoseStamped"]
Pose = TS.types["geometry_msgs/msg/Pose"]
Point = TS.types["geometry_msgs/msg/Point"]
Quat = TS.types["geometry_msgs/msg/Quaternion"]
Vec3 = TS.types["geometry_msgs/msg/Vector3"]
Header = TS.types["std_msgs/msg/Header"]
Time = TS.types["builtin_interfaces/msg/Time"]
TOPICS = {"left": "/dalsa_gray/left/image_raw", "right": "/dalsa_gray/right/image_raw",
          "lidar": "/velodyne_points", "imu": "/imu/data"}
SEC = 10**9


def base_ns(mmdd):
    t = dt.datetime(2022, int(mmdd[:2]), int(mmdd[2:]), 10, tzinfo=dt.timezone(dt.timedelta(hours=8)))
    return int(t.timestamp()) * SEC


def hdr(ns, frame="x"):
    return Header(seq=0, stamp=Time(sec=ns // SEC, nanosec=ns % SEC), frame_id=frame)


def img(ns, enc="mono8"):
    return Image(header=hdr(ns), height=4, width=6, encoding=enc, is_bigendian=0, step=6,
                 data=np.arange(24, dtype=np.uint8))


def cloud(ns, time_type=7):
    fields = [PF(name=k, offset=o, datatype=t, count=1) for k, o, t in
              [("x", 0, 7), ("y", 4, 7), ("z", 8, 7), ("intensity", 12, 7), ("ring", 16, 4), ("time", 18, time_type)]]
    return PC2(header=hdr(ns, "velodyne"), height=1, width=3, fields=fields, is_bigendian=False, point_step=22,
               row_step=66, data=np.zeros(66, np.uint8), is_dense=True)


def imu(ns):
    v, q = Vec3(x=0.0, y=0.0, z=0.0), Quat(x=0.0, y=0.0, z=0.0, w=1.0)
    z9 = np.zeros(9)
    return Imu(header=hdr(ns, "imu_link"), orientation=q, orientation_covariance=z9, angular_velocity=v,
               angular_velocity_covariance=z9, linear_acceleration=v, linear_acceleration_covariance=z9)


def pose(ns, frame="/velodyne"):
    return PoseStamped(header=hdr(ns, frame),
                       pose=Pose(position=Point(x=1.5, y=2.5, z=3.5), orientation=Quat(x=0.0, y=0.0, z=0.0, w=1.0)))


def make_vlio(path, mmdd, dur_s=40, skip=(), empty=(), swap_types=(), enc="mono8", time_type=7, backwards=False):
    b = base_ns(mmdd)
    makers = {"left": (Image, lambda t: img(t, enc)), "right": (Image, lambda t: img(t, enc)),
              "lidar": (PC2, lambda t: cloud(t, time_type)), "imu": (Imu, imu)}
    with Writer(path) as w:
        conns = {}
        for k, topic in TOPICS.items():
            if k in skip:
                continue
            typ = Imu if k in swap_types else makers[k][0]
            conns[k] = (w.add_connection(topic, typ.__msgtype__, typestore=TS), typ)
        for i in range(dur_s + 1):
            t = b + i * SEC
            for k, (c, typ) in conns.items():
                if k in empty:
                    continue
                ts = b + (dur_s - i) * SEC if backwards and k == "imu" else t
                msg = imu(ts) if typ is Imu else makers[k][1](ts)
                w.write(c, t, TS.serialize_ros1(msg, typ.__msgtype__))


def make_gt(path, mmdd, dur_s=40, frame="/velodyne", start_s=0):
    b = base_ns(mmdd) + start_s * SEC
    with Writer(path) as w:
        c = w.add_connection("/gt_poses", PoseStamped.__msgtype__, typestore=TS)
        for i in range(dur_s + 1):
            t = b + i * SEC
            w.write(c, t, TS.serialize_ros1(pose(t, frame), PoseStamped.__msgtype__))


def make_calib(d, tweak=False):
    for f in g.CALIB_FILES:
        (d / f).parent.mkdir(parents=True, exist_ok=True)
        (d / f).write_text(f"{f}{'x' if tweak else ''}\n")
    return d


@pytest.fixture
def ref(tmp_path):
    dev = tmp_path / "dev"
    dev.mkdir()
    make_vlio(dev / "1018_00_VLIO.bag", "1018")
    make_gt(dev / "gt_1018_00_qnew.bag", "1018")
    make_vlio(dev / "1018_13_VLIO.bag", "1018")
    make_gt(dev / "gt_1018_13_qnew.bag", "1018")
    calib = make_calib(tmp_path / "calib")
    pairs = [(dev / "1018_00_VLIO.bag", dev / "gt_1018_00_qnew.bag"), (dev / "1018_13_VLIO.bag", dev / "gt_1018_13_qnew.bag")]
    return g.build_reference(pairs, calib, TOPICS, "/gt_poses", ["GT_pose_qnew"])


def candidate(tmp_path, seq="1005-00", mmdd="1005", vlio=None, gt=None, release="GT_pose_qnew", **extra):
    d = tmp_path / "cand"
    d.mkdir(exist_ok=True)
    day, num = seq.split("-")
    bag, gtb = d / f"{day}_{num}_VLIO.bag", d / f"gt_{day}_{num}_qnew.bag"
    make_vlio(bag, mmdd, **(vlio or {}))
    make_gt(gtb, mmdd, **(gt or {}))
    m = {"seq": seq, "bag": {"path": str(bag)}, "gt": {"path": str(gtb), "release": release},
         "calibration_dir": str(tmp_path / "calib")}
    m.update(extra)
    return m


def test_reference_from_dev(ref):
    assert ref["gt"]["frame_id"] == "/velodyne" and ref["gt"]["msgtype"] == g.GT_TYPE
    assert ref["left"]["schema"]["encoding"] == "mono8"
    assert [f[0] for f in ref["lidar"]["schema"]["fields"]][-1] == "time"
    assert set(ref["calibration"]) == set(g.CALIB_FILES) and ref["min_overlap_s"] == 30.0


def test_reference_requires_agreement(tmp_path):
    make_vlio(tmp_path / "a.bag", "1018")
    make_vlio(tmp_path / "b.bag", "1018", enc="8UC1")
    make_gt(tmp_path / "ga.bag", "1018")
    make_gt(tmp_path / "gb.bag", "1018")
    calib = make_calib(tmp_path / "calib")
    with pytest.raises(g.ManifestError):
        g.build_reference([(tmp_path / "a.bag", tmp_path / "ga.bag"), (tmp_path / "b.bag", tmp_path / "gb.bag")],
                          calib, TOPICS, "/gt_poses", ["GT_pose_qnew"])


def test_raw_parsers_match_rosbags(tmp_path):
    make_vlio(tmp_path / "v.bag", "1005")
    make_gt(tmp_path / "g.bag", "1005")
    with AnyReader([tmp_path / "v.bag", tmp_path / "g.bag"]) as r:
        for c, _, raw in r.messages():
            m = r.deserialize(raw, c.msgtype)
            ts, frame, off = g.parse_header(raw)
            assert ts == m.header.stamp.sec * SEC + m.header.stamp.nanosec and frame == m.header.frame_id
            if c.msgtype == "sensor_msgs/msg/Image":
                sig, n = g.parse_image(raw, off)
                assert (sig["height"], sig["width"], sig["encoding"], sig["step"], n) == \
                    (m.height, m.width, m.encoding, m.step, len(m.data))
            if c.msgtype == "sensor_msgs/msg/PointCloud2":
                sig, w, n = g.parse_cloud(raw, off)
                assert sig["fields"] == [[f.name, f.offset, f.datatype, f.count] for f in m.fields]
                assert (sig["point_step"], w, n) == (m.point_step, m.width, len(m.data))


def test_approved(tmp_path, ref):
    decision, codes, hashes = g.triage(candidate(tmp_path), ref)
    assert (decision, codes) == ("APPROVED", ["APPROVED"])
    assert set(hashes) == {"bag", "gt"} and set(hashes["gt"]) == {"md5", "sha256"}


def test_never_deserializes(tmp_path, ref, monkeypatch):
    m = candidate(tmp_path)

    def boom(*a, **k):
        raise AssertionError("payload desserializado")
    monkeypatch.setattr(AnyReader, "deserialize", boom)
    assert g.triage(m, ref)[0] == "APPROVED"


@pytest.mark.parametrize("kw, code", [
    ({"vlio": {"skip": ("right",)}}, "REQUIRED_TOPIC_MISSING"),
    ({"vlio": {"swap_types": ("lidar",)}}, "TOPIC_TYPE_MISMATCH"),
    ({"vlio": {"empty": ("imu",)}}, "EMPTY_TOPIC"),
    ({"vlio": {"backwards": True}}, "TIMESTAMP_INVALID"),
    ({"gt": {"dur_s": 20}}, "COMMON_OVERLAP_LT_30S"),
    ({"gt": {"start_s": 15}}, "COMMON_OVERLAP_LT_30S"),
    ({"vlio": {"enc": "8UC1"}}, "PAYLOAD_SCHEMA_INCOMPATIBLE"),
    ({"vlio": {"time_type": 8}}, "PAYLOAD_SCHEMA_INCOMPATIBLE"),
    ({"release": "outro_gt"}, "GT_PROVENANCE_MISMATCH"),
    ({"gt": {"frame": "/map"}}, "GT_FORMAT_MISMATCH"),
    ({"mmdd": "1006"}, "IDENTITY_MISMATCH"),
])
def test_rejection_codes(tmp_path, ref, kw, code):
    decision, codes, _ = g.triage(candidate(tmp_path, **kw), ref)
    assert decision == "REJECTED" and code in codes and "APPROVED" not in codes
    assert codes == [c for c in g.CODES if c in codes]


def test_filename_identity(tmp_path, ref):
    m = candidate(tmp_path)
    other = tmp_path / "cand" / "1005_01_VLIO.bag"
    os.rename(m["bag"]["path"], other)
    m["bag"]["path"] = str(other)
    assert "IDENTITY_MISMATCH" in g.triage(m, ref)[1]


def test_hash_mismatch_and_match(tmp_path, ref):
    m = candidate(tmp_path)
    good = g.file_hashes(m["bag"]["path"])["md5"]
    m["bag"]["md5"] = good.upper()
    assert g.triage(m, ref)[0] == "APPROVED"
    m["gt"]["sha256"] = "0" * 64
    assert "HASH_MISMATCH" in g.triage(m, ref)[1]
    m["gt"].pop("sha256")
    m["gt"]["sha1"] = "x"
    with pytest.raises(g.ManifestError):
        g.triage(m, ref)


def test_calibration_missing(tmp_path, ref):
    m = candidate(tmp_path)
    make_calib(tmp_path / "calib2", tweak=True)
    m["calibration_dir"] = str(tmp_path / "calib2")
    assert "CALIBRATION_MISSING" in g.triage(m, ref)[1]
    del m["calibration_dir"]
    assert "CALIBRATION_MISSING" in g.triage(m, ref)[1]


def test_unavailable(tmp_path, ref):
    m = candidate(tmp_path)
    os.remove(m["gt"]["path"])
    assert g.triage(m, ref) == ("DATA_UNAVAILABLE", ["DATA_UNAVAILABLE"], {})


def test_sealed_gt_requires_unseal(tmp_path, ref):
    m = candidate(tmp_path)
    os.chmod(m["gt"]["path"], 0)
    with pytest.raises(g.ManifestError):
        g.triage(m, ref)


@pytest.fixture
def files(tmp_path, ref, monkeypatch):
    m = candidate(tmp_path)
    (tmp_path / "m.json").write_text(json.dumps(m))
    (tmp_path / "ref.json").write_text(json.dumps(ref))
    state = {"dirty": ""}
    monkeypatch.setattr(g, "_git", lambda *a: state["dirty"] if a[0] == "status" else "abc123")
    return m, state


def test_run_output_whitelist_and_unseal(tmp_path, files):
    m, _ = files
    os.chmod(m["gt"]["path"], 0)
    res = g.run(tmp_path / "m.json", tmp_path / "ref.json", tmp_path / "out", unseal=True)
    assert set(res) == g.OUTPUT_KEYS and res["decision"] == "APPROVED" and res["commit"] == "abc123"
    assert json.loads((tmp_path / "out/1005-00.json").read_text()) == res
    assert stat.S_IMODE(os.stat(m["gt"]["path"]).st_mode) == 0
    log = [json.loads(x) for x in (tmp_path / "cand/CUSTODY.log").read_text().splitlines()]
    assert [e["action"] for e in log] == ["unseal_read", "reseal"]


def test_run_reseals_on_failure(tmp_path, files, monkeypatch):
    m, _ = files
    os.chmod(m["gt"]["path"], 0)
    monkeypatch.setattr(g, "triage", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        g.run(tmp_path / "m.json", tmp_path / "ref.json", tmp_path / "out", unseal=True)
    assert stat.S_IMODE(os.stat(m["gt"]["path"]).st_mode) == 0


def test_run_requires_clean_tree_for_candidates(tmp_path, files):
    _, state = files
    state["dirty"] = " M ofd/x.py"
    with pytest.raises(g.ManifestError):
        g.run(tmp_path / "m.json", tmp_path / "ref.json", tmp_path / "out")
