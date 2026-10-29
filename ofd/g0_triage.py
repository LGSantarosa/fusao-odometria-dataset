"""Triagem estrutural cega G0-B (docs/INVENTORY_G0.md §3).

Lê apenas nomes, tipos, contagens, cabeçalhos e campos estruturais dos bags. Os bytes de pose do GT nunca são
decodificados: de cada mensagem de GT só é lido o `std_msgs/Header` (stamp e frame_id) no início do payload ROS1.
A saída contém somente a decisão, os códigos congelados e hashes; nenhuma contagem, duração ou estatística.

    python -m ofd.g0_triage reference --bag <dev VLIO> --gt <dev GT> [--bag ... --gt ...] --calib <dir> --out <json>
    python -m ofd.g0_triage run --manifest <aquisição.json> --reference <json> --out-dir <dir> [--unseal]
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

from rosbags.highlevel import AnyReader

from ofd import bagcompat

bagcompat.install()

VERSION = 1
CODES = ("APPROVED", "DATA_UNAVAILABLE", "IDENTITY_MISMATCH", "HASH_MISMATCH", "REQUIRED_TOPIC_MISSING",
         "TOPIC_TYPE_MISMATCH", "EMPTY_TOPIC", "TIMESTAMP_INVALID", "COMMON_OVERLAP_LT_30S",
         "PAYLOAD_SCHEMA_INCOMPATIBLE", "CALIBRATION_MISSING", "GT_PROVENANCE_MISMATCH", "GT_FORMAT_MISMATCH")
DEV_SEQS = {"1018-00", "1018-13"}
SENSORS = ("left", "right", "lidar", "imu")
# tipos cujo payload começa por std_msgs/Header; outro tipo no tópico não é interpretado
TYPES = {"left": "sensor_msgs/msg/Image", "right": "sensor_msgs/msg/Image",
         "lidar": "sensor_msgs/msg/PointCloud2", "imu": "sensor_msgs/msg/Imu"}
GT_TYPE = "geometry_msgs/msg/PoseStamped"
CALIB_FILES = ("extrinsics/calib_chain.yaml", "camera_intrinsics/dalsa_gray0_down.yaml",
               "camera_intrinsics/dalsa_gray1_down.yaml")
# campos do manifesto que não são hashes; qualquer outro campo de bag/gt é um hash declarado
MANIFEST_META = {"path", "release", "onedrive"}
OUTPUT_KEYS = {"seq", "decision", "codes", "hashes", "commit", "reference_sha256", "triage_version", "run_at"}


class ManifestError(Exception):
    """Erro do operador (manifesto, referência ou ambiente); não é decisão sobre a sequência."""


# ---------------------------------------------------------------- parsing ROS1 cru (sem desserializar payloads)

def _string(raw, off):
    (n,) = struct.unpack_from("<I", raw, off)
    return bytes(raw[off + 4:off + 4 + n]).decode("utf-8", "replace"), off + 4 + n


def parse_header(raw):
    """std_msgs/Header no início do payload -> (stamp_ns, frame_id, offset do campo seguinte)."""
    _seq, sec, nsec = struct.unpack_from("<III", raw, 0)
    frame, off = _string(raw, 12)
    return sec * 1_000_000_000 + nsec, frame, off


def parse_image(raw, off):
    h, w = struct.unpack_from("<II", raw, off)
    enc, off = _string(raw, off + 8)
    be, step, n = struct.unpack_from("<BII", raw, off)
    return {"height": h, "width": w, "encoding": enc, "is_bigendian": be, "step": step}, n


def parse_cloud(raw, off):
    h, w, nf = struct.unpack_from("<III", raw, off)
    off += 12
    fields = []
    for _ in range(nf):
        name, off = _string(raw, off)
        o, t, c = struct.unpack_from("<IBI", raw, off)
        off += 9
        fields.append([name, o, t, c])
    be, ps, rs, n = struct.unpack_from("<?III", raw, off)
    return {"height": h, "fields": fields, "is_bigendian": be, "point_step": ps}, w, n


# ---------------------------------------------------------------- varredura

def scan_sensors(bag, topics):
    """Por tópico: msgtype, digest, n, primeiro/último stamp, monotonicidade e assinaturas estruturais vistas.
    Os valores ficam em memória; só os códigos derivados deles saem do módulo."""
    out = {}
    with AnyReader([Path(bag)]) as r:
        conns = {c.topic: c for c in r.connections if c.topic in topics.values()}
        for k, t in topics.items():
            if t in conns:
                out[k] = {"msgtype": conns[t].msgtype, "digest": conns[t].digest, "n": 0, "first": None,
                          "last": None, "monotonic": True, "schemas": set(), "length_ok": True}
        key = {t: k for k, t in topics.items()}
        readable = [c for t, c in conns.items() if c.msgtype == TYPES[key[t]]]
        for c, _, raw in r.messages(connections=readable):
            s = out[key[c.topic]]
            ts, _frame, off = parse_header(raw)
            if s["last"] is not None and ts <= s["last"]:
                s["monotonic"] = False
            s["first"] = ts if s["first"] is None else s["first"]
            s["last"] = ts
            s["n"] += 1
            if key[c.topic] in ("left", "right"):
                sig, n = parse_image(raw, off)
                s["length_ok"] &= n == sig["step"] * sig["height"]
                s["schemas"].add(json.dumps(sig, sort_keys=True))
            elif key[c.topic] == "lidar":
                sig, w, n = parse_cloud(raw, off)
                s["length_ok"] &= n == sig["point_step"] * w * sig["height"]
                s["schemas"].add(json.dumps(sig, sort_keys=True))
    return out


def scan_gt(bag, topic):
    """Somente header das mensagens de GT; a pose não é lida."""
    with AnyReader([Path(bag)]) as r:
        conns = [c for c in r.connections if c.topic == topic]
        if not conns:
            return None
        s = {"msgtype": conns[0].msgtype, "digest": conns[0].digest, "n": 0, "first": None, "last": None,
             "monotonic": True, "frames": set()}
        if s["msgtype"] != GT_TYPE:
            return s
        for _c, _, raw in r.messages(connections=conns):
            ts, frame, _ = parse_header(raw)
            if s["last"] is not None and ts <= s["last"]:
                s["monotonic"] = False
            s["first"] = ts if s["first"] is None else s["first"]
            s["last"] = ts
            s["n"] += 1
            s["frames"].add(frame)
        return s


def file_hashes(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            md5.update(chunk)
            sha.update(chunk)
    return {"md5": md5.hexdigest(), "sha256": sha.hexdigest()}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _local_mmdd(ns, utc_offset_h):
    return dt.datetime.fromtimestamp(ns / 1e9, dt.timezone(dt.timedelta(hours=utc_offset_h))).strftime("%m%d")


# ---------------------------------------------------------------- referência

def build_reference(pairs, calib_dir, topics, gt_topic, accepted_releases, utc_offset_h=8, min_overlap_s=30.0):
    """Assinatura estrutural extraída dos bags de desenvolvimento; todos os pares precisam concordar."""
    sigs = []
    for bag, gt in pairs:
        sc, g = scan_sensors(bag, topics), scan_gt(gt, gt_topic)
        sig = {}
        for k in SENSORS:
            s = sc[k]
            if len(s["schemas"]) > 1:
                raise ManifestError(f"{bag}: {k} tem mais de uma assinatura estrutural")
            sig[k] = {"topic": topics[k], "msgtype": s["msgtype"], "digest": s["digest"]}
            if s["schemas"]:
                sig[k]["schema"] = json.loads(next(iter(s["schemas"])))
        if len(g["frames"]) != 1:
            raise ManifestError(f"{gt}: GT com mais de um frame_id")
        sig["gt"] = {"topic": gt_topic, "msgtype": g["msgtype"], "digest": g["digest"], "frame_id": next(iter(g["frames"]))}
        sigs.append(sig)
    if any(s != sigs[0] for s in sigs[1:]):
        raise ManifestError("bags de desenvolvimento discordam na assinatura estrutural")
    ref = sigs[0]
    ref["gt"].update(container="rosbag1", accepted_releases=sorted(accepted_releases))
    ref["calibration"] = {f: _sha256(Path(calib_dir) / f) for f in CALIB_FILES}
    ref["identity"] = {"bag_name": "{day}_{num}_VLIO.bag", "gt_name": "gt_{day}_{num}_qnew.bag",
                       "utc_offset_h": utc_offset_h}
    ref["min_overlap_s"] = min_overlap_s
    return ref


# ---------------------------------------------------------------- decisão

def _check_hashes(declared, got):
    if not declared:
        return True
    known = {k: v for k, v in declared.items() if k in got}
    if set(declared) - set(got):
        raise ManifestError(f"hash não suportado: {sorted(set(declared) - set(got))}")
    return all(got[k] == v.lower() for k, v in known.items())


def triage(manifest, ref):
    """-> (decision, codes, hashes). Única função que transforma a varredura em saída."""
    seq = manifest["seq"]
    m = re.fullmatch(r"(\d{4})-(\d{2})", seq)
    if not m:
        raise ManifestError(f"seq inválida: {seq!r}")
    day, num = m.groups()
    bag, gt = Path(manifest["bag"]["path"]), Path(manifest["gt"]["path"])
    if not bag.is_file() or not gt.is_file():
        return "DATA_UNAVAILABLE", ["DATA_UNAVAILABLE"], {}
    if not os.access(gt, os.R_OK):
        raise ManifestError(f"{gt} sem permissão de leitura (lacrado?) — use --unseal")
    codes = set()
    idn = ref["identity"]
    if bag.name != idn["bag_name"].format(day=day, num=num) or gt.name != idn["gt_name"].format(day=day, num=num):
        codes.add("IDENTITY_MISMATCH")

    hashes = {"bag": file_hashes(bag), "gt": file_hashes(gt)}
    for k in ("bag", "gt"):
        if not _check_hashes({h: v for h, v in manifest[k].items() if h not in MANIFEST_META}, hashes[k]):
            codes.add("HASH_MISMATCH")

    cal = Path(manifest.get("calibration_dir", ""))
    for f, h in ref["calibration"].items():
        if not manifest.get("calibration_dir") or not (cal / f).is_file() or _sha256(cal / f) != h:
            codes.add("CALIBRATION_MISSING")

    g_ref = ref["gt"]
    if manifest["gt"].get("release") not in g_ref["accepted_releases"]:
        codes.add("GT_PROVENANCE_MISMATCH")

    sc = scan_sensors(bag, {k: ref[k]["topic"] for k in SENSORS})
    spans = []
    for k in SENSORS:
        s = sc.get(k)
        if s is None:
            codes.add("REQUIRED_TOPIC_MISSING")
            continue
        if (s["msgtype"], s["digest"]) != (ref[k]["msgtype"], ref[k]["digest"]):
            codes.add("TOPIC_TYPE_MISMATCH")
            continue
        if s["n"] == 0:
            codes.add("EMPTY_TOPIC")
            continue
        if not s["monotonic"]:
            codes.add("TIMESTAMP_INVALID")
        if "schema" in ref[k] and (not s["length_ok"] or s["schemas"] != {json.dumps(ref[k]["schema"], sort_keys=True)}):
            codes.add("PAYLOAD_SCHEMA_INCOMPATIBLE")
        spans.append((s["first"], s["last"]))
    if spans and _local_mmdd(min(a for a, _ in spans), idn["utc_offset_h"]) != day:
        codes.add("IDENTITY_MISMATCH")

    g = scan_gt(gt, g_ref["topic"])
    if g is None or (g["msgtype"], g["digest"]) != (g_ref["msgtype"], g_ref["digest"]) or g["frames"] - {g_ref["frame_id"]}:
        codes.add("GT_FORMAT_MISMATCH")
    elif g["n"] == 0:
        codes.add("EMPTY_TOPIC")
    else:
        if not g["monotonic"]:
            codes.add("TIMESTAMP_INVALID")
        if _local_mmdd(g["first"], idn["utc_offset_h"]) != day:
            codes.add("IDENTITY_MISMATCH")
        spans.append((g["first"], g["last"]))

    if len(spans) == len(SENSORS) + 1:
        overlap = min(b for _, b in spans) - max(a for a, _ in spans)
        if overlap < ref["min_overlap_s"] * 1e9:
            codes.add("COMMON_OVERLAP_LT_30S")
    codes = [c for c in CODES if c in codes]
    return ("REJECTED", codes, hashes) if codes else ("APPROVED", ["APPROVED"], hashes)


# ---------------------------------------------------------------- execução auditável

def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def _custody(path, action, seq, commit):
    log = Path(path).parent / "CUSTODY.log"
    entry = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "file": Path(path).name, "action": action,
             "seq": seq, "commit": commit, "by": "ofd.g0_triage"}
    with open(log, "a") as f:
        f.write(json.dumps(entry) + "\n")


def run(manifest_path, ref_path, out_dir, unseal=False):
    manifest = json.loads(Path(manifest_path).read_text())
    ref_bytes = Path(ref_path).read_bytes()
    seq = manifest["seq"]
    commit = _git("rev-parse", "HEAD")
    if _git("status", "--porcelain") and seq not in DEV_SEQS:
        raise ManifestError("árvore git suja: a triagem de candidatas exige commit limpo")
    gt = Path(manifest["gt"]["path"])
    sealed = unseal and gt.is_file() and not os.access(gt, os.R_OK)
    if sealed:
        _custody(gt, "unseal_read", seq, commit)
        os.chmod(gt, 0o400)
    try:
        decision, codes, hashes = triage(manifest, json.loads(ref_bytes))
    finally:
        if sealed:
            os.chmod(gt, 0o000)
            _custody(gt, "reseal", seq, commit)
    res = {"seq": seq, "decision": decision, "codes": codes, "hashes": hashes, "commit": commit,
           "reference_sha256": hashlib.sha256(ref_bytes).hexdigest(), "triage_version": VERSION,
           "run_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    assert set(res) == OUTPUT_KEYS
    out = Path(out_dir) / f"{seq}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2) + "\n")
    return res


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reference")
    r.add_argument("--bag", action="append", required=True)
    r.add_argument("--gt", action="append", required=True)
    r.add_argument("--calib", required=True)
    r.add_argument("--release", action="append", required=True)
    r.add_argument("--out", required=True)
    x = sub.add_parser("run")
    x.add_argument("--manifest", required=True)
    x.add_argument("--reference", required=True)
    x.add_argument("--out-dir", required=True)
    x.add_argument("--unseal", action="store_true", help="libera leitura do GT lacrado só durante a triagem")
    a = ap.parse_args()
    if a.cmd == "reference":
        topics = {"left": "/dalsa_gray/left/image_raw", "right": "/dalsa_gray/right/image_raw",
                  "lidar": "/velodyne_points", "imu": "/imu/data"}
        ref = build_reference(list(zip(a.bag, a.gt, strict=True)), a.calib, topics, "/gt_poses", a.release)
        Path(a.out).write_text(json.dumps(ref, indent=2) + "\n")
    else:
        print(json.dumps(run(a.manifest, a.reference, a.out_dir, a.unseal), indent=2))


if __name__ == "__main__":
    main()
