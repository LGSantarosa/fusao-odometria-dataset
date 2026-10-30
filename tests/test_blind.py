"""Modo cego G1: extração e tabela sem GT, manifestos, predição e abertura única (docs/PLAN_model_comparison.md)."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from rosbags.highlevel import AnyReader
from rosbags.rosbag1 import Writer

from ofd import blind, build_dataset, contract, extract, schema, se3, tracks
from tests.test_extract import TS, Image, PC2, PoseStamped, Pose, Point, Quaternion, _cfg, cloud, hdr, img

MS = 1_000_000
T0 = 1_700_000_000 * 10**9


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _tree(d):
    return {str(p.relative_to(d)): _sha(p) for p in sorted(Path(d).rglob("*")) if p.is_file()}


def _pose_msg(t, x):
    return PoseStamped(header=hdr(t), pose=Pose(position=Point(x=x, y=0.0, z=0.0),
                                                orientation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)))


def bag_with_embedded_gt(p):
    with Writer(p) as w:
        cl = w.add_connection("/l", Image.__msgtype__, typestore=TS)
        cr = w.add_connection("/r", Image.__msgtype__, typestore=TS)
        cp = w.add_connection("/p", PC2.__msgtype__, typestore=TS)
        cg = w.add_connection("/gt_poses", PoseStamped.__msgtype__, typestore=TS)
        for k in range(3):
            t = T0 + k * 100 * MS
            w.write(cp, t, TS.serialize_ros1(cloud(t), PC2.__msgtype__))
            w.write(cl, t, TS.serialize_ros1(img(t), Image.__msgtype__))
            w.write(cr, t, TS.serialize_ros1(img(t), Image.__msgtype__))
            w.write(cg, t, TS.serialize_ros1(_pose_msg(t, float(k)), PoseStamped.__msgtype__))


# ---------------------------------------------------------------- passo 3: extração sem GT

def test_blind_extract_never_deserializes_gt_and_keeps_sensor_outputs(tmp_path, monkeypatch):
    bag = tmp_path / "x.bag"
    bag_with_embedded_gt(bag)
    extract.extract(bag, _cfg(), tmp_path / "open")
    assert (tmp_path / "open/gt.tum").exists()

    real = AnyReader.deserialize

    def guarded(self, raw, msgtype):
        assert msgtype != PoseStamped.__msgtype__, "modo cego desserializou o GT"
        return real(self, raw, msgtype)
    monkeypatch.setattr(AnyReader, "deserialize", guarded)
    meta = extract.extract(bag, _cfg(), tmp_path / "blind", blind=True)
    assert meta["blind"] is True and "n_gt" not in meta and "gt_dropped_nonfinite" not in meta
    assert not (tmp_path / "blind/gt.tum").exists()
    a, b = _tree(tmp_path / "open"), _tree(tmp_path / "blind")
    del a["gt.tum"], a["meta.json"], b["meta.json"]
    assert a == b


def test_blind_extract_rejects_gt_inputs(tmp_path):
    bag = tmp_path / "x.bag"
    bag_with_embedded_gt(bag)
    for kw in ({"gt_bag": bag}, {"gt_tum": tmp_path / "gt.tum"}):
        with pytest.raises(ValueError, match="cego"):
            extract.extract(bag, _cfg(), tmp_path / "o", blind=True, **kw)


# ---------------------------------------------------------------- sequência sintética completa

def gt_pose(ts_ns):
    t = (np.asarray(ts_ns, np.int64) - T0) / 1e9
    Ts = np.stack([np.eye(4)] * len(t))
    Ts[:, 0, 3] = t + 0.05 * t ** 2
    return Ts


def make_sequence(root, n=400):
    """Extração cega (sem gt.tum), runs dos quatro métodos e GT em bag separado, lacrado como no G0."""
    seq, runs = root / "ext" / "SYN-01", root / "runs" / "SYN-01"
    seq.mkdir(parents=True)
    end = (T0 + np.arange(n) * 100 * MS).astype(np.int64)
    pd.DataFrame({"ts_ns": end - 100 * MS, "end_ns": end}).to_csv(seq / "lidar_stamps.csv", index=False)
    rng = np.random.default_rng(0)
    for m, kind in schema.METHODS.items():
        ts = end - 30 * MS if kind == "vo" else end
        Ts = gt_pose(ts)
        ok = np.ones(n, int)
        if m == "stella":
            ok[200:220] = 0
        if m == "kissicp":
            Ts[:, 1, 3] += rng.normal(0, 0.01, n)
        cols = schema.VO_IND if kind == "vo" else schema.LO_IND
        tracks.write_run(runs / m, ts[ok == 1], Ts[ok == 1], pd.DataFrame({"ts_ns": ts, "ok": ok, "map_id": 0}),
                         pd.DataFrame({"ts_ns": ts, **{c: rng.random(n) for c in cols}}),
                         {"method": m, "uses_imu": m == "fastlio"})
    gt_ts = np.sort(np.r_[end, end - 30 * MS])
    sealed = root / "sealed"
    sealed.mkdir()
    gt = sealed / "gt_syn_01_qnew.bag"
    with Writer(gt) as w:
        c = w.add_connection("/gt_poses", PoseStamped.__msgtype__, typestore=TS)
        for t, T in zip(gt_ts, gt_pose(gt_ts)):
            w.write(c, int(t), TS.serialize_ros1(_pose_msg(int(t), float(T[0, 3])), PoseStamped.__msgtype__))
    acq = root / "acq"
    acq.mkdir()
    (acq / "SYN-01.json").write_text(json.dumps({"seq": "SYN-01", "gt": {"path": str(gt), "sha256": _sha(gt)}}))
    gt.chmod(0)
    cfg = root / "dataset.yaml"
    cfg.write_text(yaml.safe_dump({"name": "synthetic", "gt_quality": "survey", "topics": {"gt": "/gt_poses"},
                                   "point_time": {}, "T_L_S": {m: np.eye(4).ravel().tolist() for m in schema.METHODS}}))
    (root / "protocol.md").write_text("protocolo congelado\n")
    return seq, runs, gt, acq, cfg, gt_ts


def blind_table(root, seq, runs):
    eye = {m: np.eye(4) for m in schema.METHODS}
    df = build_dataset.build_sequence(seq, runs, eye, "synthetic", "survey", blind=True)
    build_dataset.write_outputs(df, schema.blind_schema(schema.METHODS), root / "tables", seq.name)
    return root / "tables" / f"{seq.name}.parquet"


@pytest.fixture
def flow(tmp_path):
    seq, runs, gt, acq, cfg, gt_ts = make_sequence(tmp_path)
    table = blind_table(tmp_path, seq, runs)
    fm = tmp_path / "blind" / "feature_manifest.json"
    blind.freeze_features({"SYN-01": (table, runs)}, cfg, tmp_path / "protocol.md", fm, require_clean=False)
    blind.predict(fm, ["B5"], tmp_path / "blind", require_clean=False)
    yield {"root": tmp_path, "seq": seq, "runs": runs, "gt": gt, "acq": acq, "table": table, "fm": fm,
           "pm": tmp_path / "blind" / "prediction_manifest.json", "gt_ts": gt_ts}
    gt.chmod(0o600)  # limpeza do tmp_path


OPEN = schema.build_schema(schema.METHODS)
GT_DERIVED = {c for c, r in OPEN.items() if r in ("target", "evaluation")}


def _custody(f):
    log = f["gt"].parent / "CUSTODY.log"
    return [json.loads(x)["action"] for x in log.read_text().splitlines()] if log.exists() else []


# ---------------------------------------------------------------- passo 4: tabela e predição cegas

def test_blind_table_has_no_gt_columns_and_matches_open_features(tmp_path):
    seq, runs, *_ , gt_ts = make_sequence(tmp_path)
    eye = {m: np.eye(4) for m in schema.METHODS}
    df = build_dataset.build_sequence(seq, runs, eye, "synthetic", "survey", blind=True)
    sch = schema.blind_schema(schema.METHODS)
    assert set(sch.values()) == {"metadata", "feature"}
    contract.check(df, sch, seq="SYN-01")
    assert not GT_DERIVED & set(df.columns)

    se3.save_tum(seq / "gt.tum", gt_ts, gt_pose(gt_ts))
    with pytest.raises(ValueError, match="cego"):
        build_dataset.build_sequence(seq, runs, eye, "synthetic", "survey", blind=True)
    full = build_dataset.build_sequence(seq, runs, eye, "synthetic", "survey")
    assert blind.logical_sha256(full[list(sch)]) == blind.logical_sha256(df)


def test_blind_outputs_carry_no_target_error_or_metric(flow):
    blind_dir = flow["root"] / "blind"
    for p in [flow["table"], *(blind_dir / "predictions").glob("*.parquet")]:
        cols = set(pd.read_parquet(p).columns)
        assert not cols & GT_DERIVED and cols <= set(OPEN) | {f"B5_{c}" for c in blind.PRED}
    names = {p.name for p in flow["root"].rglob("*")}
    assert not names & {"metrics.csv", "source_metrics.csv", "prediction_metrics.csv", "unlock_manifest.json"}
    assert _custody(flow) == []
    pred = pd.read_parquet(blind_dir / "predictions" / "SYN-01.parquet")
    assert list(pred.columns) == ["t", "seq"] + [f"B5_{c}" for c in blind.PRED]


def test_b5_is_mean_of_valid_sources():
    df = pd.DataFrame({f"{m}_{c}": [float(i), 9.0] for i, m in enumerate(schema.METHODS) for c in schema.TW})
    for m in schema.METHODS:
        df[f"{m}_valid"] = [1, 0]
    df.loc[0, "kissicp_valid"] = 0
    p = blind.b5_mean(df)
    np.testing.assert_allclose(p[0], np.mean([i for i, m in enumerate(schema.METHODS) if m != "kissicp"]))
    assert np.isnan(p[1]).all()


def test_blind_script_never_evaluates_or_takes_gt():
    s = Path("scripts/run_sequence_blind.sh").read_text()
    code = [x for x in s.splitlines() if not x.lstrip().startswith("#")]
    assert not [x for x in code if "ofd.evaluate" in x or "--gt" in x or "gt.tum" in x]
    assert any("ofd.extract --blind" in x for x in code) and any("ofd.build_dataset --blind" in x for x in code)


# ---------------------------------------------------------------- passo 5: manifestos

def test_logical_hash_is_stable_and_sensitive(tmp_path):
    df = pd.DataFrame({"t": np.arange(3, dtype=np.int64), "seq": ["a"] * 3, "x": [1.0, np.nan, 3.0], "b": [True] * 3})
    df.to_parquet(tmp_path / "a.parquet", index=False)
    h = blind.logical_sha256(df)
    assert blind.logical_sha256(pd.read_parquet(tmp_path / "a.parquet")) == h
    df2 = df.copy()
    df2.loc[2, "x"] = 3.0000001
    assert blind.logical_sha256(df2) != h
    assert blind.logical_sha256(df.rename(columns={"x": "y"})) != h


def test_tampered_table_blocks_predict_and_unlock_before_reading_gt(flow):
    df = pd.read_parquet(flow["table"])
    df.loc[5, "fastlio_vx"] += 1e-6
    df.to_parquet(flow["table"], index=False)
    with pytest.raises(blind.BlindError, match="alterados"):
        blind.predict(flow["fm"], ["B5"], flow["root"] / "other", require_clean=False)
    out = flow["root"] / "unlock"
    with pytest.raises(blind.BlindError, match="alterados"):
        blind.unlock(flow["fm"], flow["pm"], flow["acq"], out, require_clean=False)
    assert _custody(flow) == [] and not (out / "UNLOCK_STARTED").exists()
    assert os.stat(flow["gt"]).st_mode & 0o777 == 0


def test_manifests_are_never_overwritten(flow):
    with pytest.raises(blind.BlindError, match="já existe"):
        blind.freeze_features({"SYN-01": (flow["table"], flow["runs"])}, flow["root"] / "dataset.yaml",
                              flow["root"] / "protocol.md", flow["fm"], require_clean=False)


def test_freeze_rejects_non_blind_table(flow):
    df = pd.read_parquet(flow["table"])
    df["gt_vx"] = 0.0
    df.to_parquet(flow["root"] / "open.parquet", index=False)
    with pytest.raises(blind.BlindError, match="schema cego"):
        blind.freeze_features({"SYN-01": (flow["root"] / "open.parquet", flow["runs"])}, flow["root"] / "dataset.yaml",
                              flow["root"] / "protocol.md", flow["root"] / "fm2.json", require_clean=False)


# ---------------------------------------------------------------- passo 6: abertura única

def test_unlock_attaches_gt_without_touching_features_and_reseals(flow):
    before = _sha(flow["table"])
    out = flow["root"] / "unlock"
    um = blind.unlock(flow["fm"], flow["pm"], flow["acq"], out, require_clean=False)
    assert _sha(flow["table"]) == before
    assert os.stat(flow["gt"]).st_mode & 0o777 == 0
    assert _custody(flow) == ["unlock_read", "reseal"]
    assert um["gt"]["SYN-01"]["sha256"] == json.loads((flow["acq"] / "SYN-01.json").read_text())["gt"]["sha256"]

    # GT anexado = o que a montagem aberta produziria com o mesmo GT
    se3.save_tum(flow["seq"] / "gt.tum", flow["gt_ts"], gt_pose(flow["gt_ts"]))
    full = build_dataset.build_sequence(flow["seq"], flow["runs"], {m: np.eye(4) for m in schema.METHODS},
                                        "synthetic", "survey")
    ev = pd.read_parquet(out / "evaluation" / "SYN-01.parquet")
    cols = [c for c in ev.columns if c != "t"]
    pd.testing.assert_frame_equal(ev[cols], full[cols], check_exact=False, atol=1e-12)

    src = pd.read_csv(out / "source_metrics.csv").set_index("method")
    assert src.loc["fastlio", "ate_rmse"] < 1e-6 and src.loc["stella", "n_failures"] == 1
    pm = pd.read_csv(out / "prediction_metrics.csv").iloc[0]
    y = full[[f"gt_{c}" for c in schema.TW]].to_numpy()[1:]
    e = blind.b5_mean(full)[1:] - y
    assert pm["model"] == "B5" and pm["n_target"] == len(ev) - 1 and pm["n_pred_missing"] == 0
    np.testing.assert_allclose([pm["rmse_v"], pm["rmse_w"]],
                               [np.sqrt(np.mean(np.sum(e[:, :3] ** 2, 1))), np.sqrt(np.mean(np.sum(e[:, 3:] ** 2, 1)))])
    assert blind.verify_manifest(flow["fm"], "features")


def test_unlock_happens_once(flow):
    out = flow["root"] / "unlock"
    blind.unlock(flow["fm"], flow["pm"], flow["acq"], out, require_clean=False)
    with pytest.raises(blind.BlindError, match="já iniciada"):
        blind.unlock(flow["fm"], flow["pm"], flow["acq"], out, require_clean=False)
    assert _custody(flow) == ["unlock_read", "reseal"]


def test_failure_after_start_consumes_the_opening_and_reseals(flow):
    acq = flow["acq"] / "SYN-01.json"
    a = json.loads(acq.read_text())
    a["gt"]["sha256"] = "0" * 64
    acq.write_text(json.dumps(a))
    out = flow["root"] / "unlock"
    with pytest.raises(blind.BlindError, match="difere"):
        blind.unlock(flow["fm"], flow["pm"], flow["acq"], out, require_clean=False)
    assert (out / "UNLOCK_STARTED").exists() and not (out / "unlock_manifest.json").exists()
    assert os.stat(flow["gt"]).st_mode & 0o777 == 0 and _custody(flow) == ["unlock_read", "reseal"]
    with pytest.raises(blind.BlindError, match="já iniciada"):
        blind.unlock(flow["fm"], flow["pm"], flow["acq"], out, require_clean=False)


def test_unlock_rejects_predictions_from_other_features(flow):
    other = flow["root"] / "fm_other.json"
    blind.freeze_features({"SYN-01": (flow["table"], flow["runs"])}, flow["root"] / "dataset.yaml",
                          flow["root"] / "protocol.md", other, require_clean=False)
    out = flow["root"] / "unlock"
    with pytest.raises(blind.BlindError, match="não corresponde"):
        blind.unlock(other, flow["pm"], flow["acq"], out, require_clean=False)
    assert _custody(flow) == [] and not (out / "UNLOCK_STARTED").exists()
