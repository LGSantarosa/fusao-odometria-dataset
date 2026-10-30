"""ROS1 bag -> stereo PNGs, per-scan NPZ (all fields), lidar_stamps.csv, gt.tum (LiDAR frame), meta.json.

Com `blind=True` (modo cego G1), o tópico de GT nunca é lido, mesmo quando está dentro do bag, e `gt.tum` não é
gravado.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from rosbags.highlevel import AnyReader

from ofd import config, pointtime, se3
from ofd.rectify import StereoRectifier

_DT = {1: "i1", 2: "u1", 3: "i2", 4: "u2", 5: "i4", 6: "u4", 7: "f4", 8: "f8"}


def stamp_ns(msg):
    return int(msg.header.stamp.sec) * 1_000_000_000 + int(msg.header.stamp.nanosec)


def cloud_to_struct(msg):
    dt = np.dtype({"names": [f.name for f in msg.fields],
                   "formats": [_DT[f.datatype] for f in msg.fields],
                   "offsets": [f.offset for f in msg.fields], "itemsize": msg.point_step})
    return np.frombuffer(bytes(msg.data), dtype=dt, count=msg.width * msg.height)


def image_to_array(msg):
    buf = np.frombuffer(bytes(msg.data), np.uint8)
    if msg.encoding in ("mono8", "8UC1"):
        return buf.reshape(msg.height, msg.step)[:, : msg.width]
    if msg.encoding in ("bgr8", "rgb8"):
        im = buf.reshape(msg.height, msg.step)[:, : msg.width * 3].reshape(msg.height, msg.width, 3)
        return cv2.cvtColor(im, cv2.COLOR_RGB2GRAY if msg.encoding == "rgb8" else cv2.COLOR_BGR2GRAY)
    if msg.encoding.startswith("bayer"):
        code = {"bayer_rggb8": cv2.COLOR_BayerRG2GRAY, "bayer_bggr8": cv2.COLOR_BayerBG2GRAY,
                "bayer_gbrg8": cv2.COLOR_BayerGB2GRAY, "bayer_grbg8": cv2.COLOR_BayerGR2GRAY}[msg.encoding]
        return cv2.cvtColor(buf.reshape(msg.height, msg.step)[:, : msg.width], code)
    raise ValueError(f"encoding não suportado: {msg.encoding}")


def gt_from_bag(bag, topic):
    """PoseStamped topic of a separate GT bag -> (ts_ns, Ts, n_dropped), sorted; non-finite poses are dropped."""
    rows, dropped = [], 0
    with AnyReader([Path(bag)]) as r:
        conns = [c for c in r.connections if c.topic == topic]
        if not conns:
            raise ValueError(f"tópico {topic} não existe em {bag}")
        for c, _, raw in r.messages(connections=conns):
            m = r.deserialize(raw, c.msgtype)
            p, q = m.pose.position, m.pose.orientation
            v = np.array([p.x, p.y, p.z, q.x, q.y, q.z, q.w])
            if not np.isfinite(v).all() or np.linalg.norm(v[3:]) < 1e-6:
                dropped += 1   # ex.: BotanicGarden 1018-00 tem 1 quaternion NaN no GT oficial
                continue
            rows.append((stamp_ns(m), se3.to_mat(v[:3], v[3:])))
    rows.sort(key=lambda x: x[0])
    return np.array([r[0] for r in rows], dtype=np.int64), np.stack([r[1] for r in rows]), dropped


def _rectifier(cfg):
    st = cfg.stereo
    if not st:
        return None
    return StereoRectifier(st["K0"], st["D0"], st["K1"], st["D1"],
                           np.asarray(st["T_c0_c1"], float).reshape(4, 4), st["size"])


def extract(bag, cfg, out, t0_s=None, dur_s=None, gt_tum=None, gt_bag=None, blind=False):
    if blind and (gt_tum or gt_bag):
        raise ValueError("modo cego não aceita GT")
    out = Path(out)
    for d in ["images/left", "images/right", "clouds"]:
        (out / d).mkdir(parents=True, exist_ok=True)
    tp = cfg.topics
    left, right, scans, deskew_ok = {}, {}, [], []
    gt_dropped = 0
    rect = _rectifier(cfg)
    pending = {}  # ts -> {side: img}; retificação exige o par
    gt_rows = []
    with AnyReader([Path(bag)]) as r:
        start = r.start_time + int((t0_s or 0) * 1e9)
        stop = start + int(dur_s * 1e9) if dur_s else r.end_time + 1
        want = {tp["left"], tp["right"], tp["lidar"]} | (set() if blind else {tp.get("gt")})
        conns = [c for c in r.connections if c.topic in want]
        for c, t, raw in r.messages(connections=conns, start=start, stop=stop):
            m = r.deserialize(raw, c.msgtype)
            ts = stamp_ns(m)
            if c.topic in (tp["left"], tp["right"]):
                side = "left" if c.topic == tp["left"] else "right"
                (left if side == "left" else right)[ts] = True
                img = image_to_array(m)
                if rect is None:
                    cv2.imwrite(str(out / "images" / side / f"{ts}.png"), img)
                else:
                    pair = pending.setdefault(ts, {})
                    pair[side] = img
                    if len(pair) == 2:
                        a, b = rect.apply(pair.pop("left"), pair.pop("right"))
                        cv2.imwrite(str(out / "images" / "left" / f"{ts}.png"), a)
                        cv2.imwrite(str(out / "images" / "right" / f"{ts}.png"), b)
                        del pending[ts]
            elif c.topic == tp["lidar"]:
                a = cloud_to_struct(m)
                xyz = np.c_[a["x"], a["y"], a["z"]].astype(np.float32)
                fin = np.isfinite(xyz).all(1) & (np.linalg.norm(xyz, axis=1) > 0.1)
                rec = {"xyz": xyz[fin]}
                names = a.dtype.names
                if "intensity" in names:
                    rec["intensity"] = a["intensity"][fin].astype(np.float32)
                if "ring" in names:
                    rec["ring"] = a["ring"][fin].astype(np.int16)
                f = cfg.point_time.get("field")
                tn, info = None, {"t_min_s": np.nan, "t_max_s": np.nan, "span_s": np.nan,
                                  "monotonic_frac": 0.0, "valid": False}
                if f and f in names:
                    ring = a["ring"][fin] if "ring" in names else None
                    tn, info = pointtime.normalize(a[f][fin], cfg.point_time["unit"], cfg.point_time["ref"], ts, ring)
                if tn is not None:
                    rec["t_norm"] = tn.astype(np.float32)
                deskew_ok.append(tn is not None)
                end = ts + int(round(info["t_max_s"] * 1e9)) if info["valid"] else ts
                np.savez_compressed(out / "clouds" / f"{ts}.npz", **rec)
                scans.append({"ts_ns": ts, "end_ns": end, **info})
            elif not blind and c.topic == tp.get("gt"):
                p, q = m.pose.position, m.pose.orientation
                gt_rows.append((ts, se3.to_mat([p.x, p.y, p.z], [q.x, q.y, q.z, q.w])))
    pairs = sorted(set(left) & set(right))
    pd.DataFrame({"ts_ns": pairs}).to_csv(out / "images" / "stamps.csv", index=False)
    sc = pd.DataFrame(scans).sort_values("ts_ns")
    sc.to_csv(out / "scans.csv", index=False)
    sc[["ts_ns", "end_ns"]].to_csv(out / "lidar_stamps.csv", index=False)
    if blind:
        ts_gt = None
    elif gt_tum:
        ts_gt, Ts_gt = se3.load_tum(gt_tum)
    elif gt_bag:
        ts_gt, Ts_gt, gt_dropped = gt_from_bag(gt_bag, tp.get("gt", "/gt_poses"))
    elif gt_rows:
        gt_rows.sort(key=lambda x: x[0])
        ts_gt = np.array([g[0] for g in gt_rows], dtype=np.int64)
        Ts_gt = np.stack([g[1] for g in gt_rows])
    else:
        ts_gt, Ts_gt = np.zeros(0, np.int64), np.zeros((0, 4, 4))
    if not blind:
        se3.save_tum(out / "gt.tum", ts_gt, Ts_gt)  # GT já no frame do LiDAR (ver docs do dataset)
    frac = float(np.mean(deskew_ok)) if deskew_ok else 0.0
    meta = {"bag": str(bag), "n_scans": len(scans), "n_stereo": len(pairs),
            "point_time": cfg.point_time, "deskew_valid_frac": frac, "deskew": bool(deskew_ok) and frac == 1.0,
            "unpaired_left": len(set(left) - set(right)), "unpaired_right": len(set(right) - set(left)),
            "rectified": rect.params() if rect is not None else None}
    meta.update({"blind": True} if blind else {"n_gt": int(len(ts_gt)), "gt_dropped_nonfinite": gt_dropped})
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=float)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--gt-tum")
    ap.add_argument("--gt-bag", help="bag separado com o GT (tópico topics.gt do config)")
    ap.add_argument("--blind", action="store_true", help="modo cego G1: ignora o tópico de GT e não grava gt.tum")
    a = ap.parse_args()
    print(json.dumps(extract(a.bag, config.load(a.config), a.out, a.start, a.duration, a.gt_tum, a.gt_bag, a.blind),
                     indent=2))


if __name__ == "__main__":
    main()
