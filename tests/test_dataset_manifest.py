"""Manifesto reproduzível dos artefatos locais do dataset (tools/dataset_manifest.py)."""
import hashlib
import json

import pandas as pd

from ofd import schema
from tools import dataset_manifest as dm


def _output(root, seq="s1"):
    out = root / "output"
    out.mkdir()
    sch = schema.build_schema(schema.METHODS)
    (out / "schema.json").write_text(json.dumps(sch, indent=2))
    df = pd.DataFrame({c: [0.0, 1.0] for c in sch})
    df["t"] = [10, 20]
    df["seq"] = seq
    df["dataset"] = "botanic"
    df["gt_quality"] = "survey"
    df.to_parquet(out / f"{seq}.parquet", index=False)
    df.to_csv(out / f"{seq}.csv", index=False)
    pd.DataFrame({"seq": ["s1"], "ate_rmse": [1.0]}).to_csv(out / "metrics.csv", index=False)
    return out


def test_manifest_lists_files_with_hash_size_and_shape(tmp_path):
    out = _output(tmp_path)
    m = dm.build_manifest(out, commit="abc1234")
    files = {f["path"]: f for f in m["files"]}
    assert set(files) == {"metrics.csv", "s1.csv", "s1.parquet", "schema.json"}
    pq = files["s1.parquet"]
    assert pq["sha256"] == hashlib.sha256((out / "s1.parquet").read_bytes()).hexdigest()
    assert pq["bytes"] == (out / "s1.parquet").stat().st_size
    assert pq["rows"] == 2 and pq["columns"] == len(schema.build_schema(schema.METHODS))
    assert m["sequences"] == [{"seq": "s1", "dataset": "botanic", "rows": 2, "t_first_ns": 10, "t_last_ns": 20,
                               "csv_matches_parquet": True}]


def test_manifest_records_schema_version(tmp_path):
    m = dm.build_manifest(_output(tmp_path), commit="abc1234")
    assert m["commit"] == "abc1234"
    assert m["schema"]["roles"] == {"evaluation": 15, "feature": 56, "metadata": 44, "target": 6}
    assert m["schema"]["matches_code"] is True
    assert len(m["schema"]["sha256"]) == 64


def test_manifest_is_deterministic(tmp_path):
    out = _output(tmp_path)
    assert dm.dumps(dm.build_manifest(out, "abc1234")) == dm.dumps(dm.build_manifest(out, "abc1234"))


def test_check_detects_changed_and_missing_files(tmp_path):
    out = _output(tmp_path)
    m = dm.build_manifest(out, "abc1234")
    assert dm.check(m, out) == []
    (out / "metrics.csv").write_text("seq,ate_rmse\ns1,2.0\n")
    (out / "s1.csv").unlink()
    problems = dm.check(m, out)
    assert any("metrics.csv" in p for p in problems) and any("s1.csv" in p for p in problems)


def test_numeric_looking_sequence_csv_matches_parquet_with_typed_read(tmp_path):
    out = _output(tmp_path, seq="00000")
    assert pd.read_csv(out / "00000.csv")["seq"].iat[0] == 0                   # leitura padrão perde os zeros
    assert pd.read_csv(out / "00000.csv", dtype=schema.CSV_DTYPE)["seq"].iat[0] == "00000"
    (entry,) = dm.build_manifest(out, "abc1234")["sequences"]
    assert entry["seq"] == "00000" and entry["csv_matches_parquet"] is True


def test_csv_differing_from_parquet_is_flagged(tmp_path):
    out = _output(tmp_path)
    df = pd.read_csv(out / "s1.csv", dtype=schema.CSV_DTYPE)
    df.loc[1, "orbslam3_vx"] = 9.0
    df.to_csv(out / "s1.csv", index=False)
    (entry,) = dm.build_manifest(out, "abc1234")["sequences"]
    assert entry["csv_matches_parquet"] is False


def test_integer_columns_are_compared_exactly(tmp_path):
    out = _output(tmp_path)
    df = pd.read_parquet(out / "s1.parquet")
    df["t"] = [1_581_624_652_670_700_800, 1_581_624_652_770_700_800]   # escala real: rtol=1e-12 aceitaria ~1,6 ms
    df["orbslam3_src_ts"] = df["t"] - 5
    df["orbslam3_uses_imu"] = [False, True]
    df.to_parquet(out / "s1.parquet", index=False)
    df.to_csv(out / "s1.csv", index=False)
    assert dm.csv_matches_parquet(out / "s1.parquet", out / "s1.csv")
    for col, value in (("t", df["t"].iat[1] + 1), ("orbslam3_src_ts", df["orbslam3_src_ts"].iat[1] + 1),
                       ("orbslam3_uses_imu", False)):
        changed = df.copy()
        changed.loc[1, col] = value
        changed.to_csv(out / "s1.csv", index=False)
        assert not dm.csv_matches_parquet(out / "s1.parquet", out / "s1.csv"), col
