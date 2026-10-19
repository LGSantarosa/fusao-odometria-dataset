"""Validação sintética da fase 2 do protocolo docs/protocol_vo_repeat.md (seção 7)."""
import json

import numpy as np
import pandas as pd
import pytest

from ofd import se3, sync, tracks, vo_repeat_phase2 as p2

N = 450                                                # 45 s a 10 Hz, 0,1 m por quadro → 44,9 m
TS = (np.arange(N, dtype=np.int64) + 1) * 100_000_000
GRID = TS + 20_000_000                                 # grade LiDAR 20 ms depois de cada imagem


def _gt():
    Ts = np.stack([np.eye(4)] * N)
    Ts[:, 0, 3] = 0.1 * np.arange(N)
    return TS, Ts


def _table():
    gt_ts, gt_Ts = _gt()
    return pd.concat([pd.DataFrame({"t": GRID}), sync.gt_deltas(gt_ts, gt_Ts, GRID)], axis=1)


def _write(path, ok=None, map_id=None, scale=1.0, indicators=None):
    ok = np.ones(N, dtype=int) if ok is None else np.asarray(ok)
    map_id = np.zeros(N, dtype=int) if map_id is None else np.asarray(map_id)
    _, Ts = _gt()
    Ts = Ts.copy()
    Ts[:, 0, 3] *= scale
    ind = indicators if indicators is not None else pd.DataFrame(
        {"ts_ns": TS, "inliers": 100, "n_features": 1000, "reproj_err": 1.0, "tracked_ratio": 0.9})
    good = ok == 1
    tracks.write_run(path, TS[good], Ts[good], pd.DataFrame({"ts_ns": TS, "ok": ok, "map_id": map_id}),
                     ind, {"method": "orbslam3"})
    (path / "frames.csv").write_text("ts_ns\n")
    return path


def test_evaluate_run_with_gt_perfect_track(tmp_path):
    row = p2.evaluate_run(_write(tmp_path / "r1"), "orbslam3", _table(), np.eye(4), 100.0, gt=_gt())
    assert row["ate_rmse"] < 1e-9 and row["rpe_t_10m"] < 1e-9 and row["rpe_r_10m"] < 1e-9
    assert row["n_segments"] == 1 and row["n_eligible"] == 1
    assert row["coverage"] > 0.99 and row["n_failures"] == 0 and row["n_resets"] == 0
    assert row["longest_s"] > 44 and row["longest_m"] > 44
    assert row["inliers_median"] == 100 and row["inliers_missing_frac"] == 0


def test_evaluate_run_without_gt_has_no_error_metrics_nor_length(tmp_path):
    grid_only = _table()[["t"]]                         # sem gt_dx, gt_dy, gt_dz: lê-los seria erro
    row = p2.evaluate_run(_write(tmp_path / "r1"), "orbslam3", grid_only, np.eye(4), 100.0, gt=None)
    assert not set(row) & set(p2.ERROR_METRICS)
    assert "longest_m" not in row                       # emenda de 19/10 à seção 7: RELLIS só em segundos
    assert row["coverage"] > 0.99 and row["n_failures"] == 0 and row["longest_s"] > 44


def test_evaluate_run_undefined_error_metrics_without_support(tmp_path):
    ok = np.zeros(N, dtype=int)
    ok[:50] = 1                                         # 5 s e 4,9 m: nenhum segmento elegível, nenhuma janela de 10 m
    row = p2.evaluate_run(_write(tmp_path / "r1", ok=ok), "orbslam3", _table(), np.eye(4), 100.0, gt=_gt())
    assert np.isnan(row["ate_rmse"]) and np.isnan(row["rpe_t_10m"]) and np.isnan(row["rpe_r_10m"])
    assert row["n_segments"] == 1 and row["n_eligible"] == 0


def test_evaluate_run_counts_failure_and_reset(tmp_path):
    ok = np.ones(N, dtype=int)
    ok[200:210] = 0
    row = p2.evaluate_run(_write(tmp_path / "r1", ok=ok), "orbslam3", _table(), np.eye(4), 100.0, gt=_gt())
    assert row["n_failures"] == 1 and row["n_resets"] == 1 and row["n_segments"] == 2
    assert row["longest_s"] < 25


def _record(path, exit_code=0, status="finished"):
    path.write_text(json.dumps({"status": status, "exit_code": exit_code}))
    return path


def test_evaluate_combination_keeps_invalid_runs_without_metrics(tmp_path):
    dirs = [_write(tmp_path / f"r{k}") for k in (1, 2, 3)]
    recs = [_record(tmp_path / "r1.json"), _record(tmp_path / "r2.json", exit_code=139), tmp_path / "r3.json"]
    runs = p2.evaluate_combination(dirs, recs, TS, "orbslam3", _table(), np.eye(4), 100.0, gt=_gt())
    assert list(runs["repetition"]) == [1, 2, 3]
    assert list(runs["valid"]) == [True, False, False]
    assert list(runs["exit_code"].fillna(-1)) == [0, 139, -1]
    assert list(runs["record_status"]) == ["finished", "finished", "missing"]
    assert runs.loc[0, "ate_rmse"] < 1e-9
    assert runs.loc[1:, ["ate_rmse", "coverage", "inliers_median"]].isna().all().all()
    assert "código de saída 139" in runs.loc[1, "reasons"]


def _runs_table():
    nan = np.nan
    return pd.DataFrame({
        "repetition": [1, 2, 3, 4], "valid": [True, True, True, False], "exit_code": [0, 0, 0, 139],
        "ate_rmse": [1.0, 3.0, nan, nan],              # r3 sem segmento elegível; r4 inválida
        "rpe_t_10m": [0.1, nan, nan, nan],              # uma observação: sem desvio-padrão
        "rpe_r_10m": [nan, nan, nan, nan],              # nenhuma: indefinida
        "n_segments": [1, 2, 4, nan], "n_eligible": [1, 1, 0, nan],
        "coverage": [0.9, 0.8, 0.7, nan], "n_failures": [0, 1, 3, nan], "n_resets": [0, 1, 3, nan],
        "longest_s": [10.0, 20.0, 30.0, nan], "longest_m": [5.0, 6.0, 7.0, nan],
        **{f"{c}_median": [1.0, 2.0, nan, nan] for c in ("inliers", "n_features", "reproj_err", "tracked_ratio")},
    })


def test_summarize_uses_fixed_statistic_per_metric():
    s = p2.summarize(_runs_table(), with_gt=True).set_index("metric")
    assert s.loc["ate_rmse", "statistic"] == "mean_sd"
    assert s.loc["ate_rmse", "n_defined"] == 2 and s.loc["ate_rmse", "mean"] == 2.0
    assert np.isclose(s.loc["ate_rmse", "sd"], np.sqrt(2.0))                 # amostral, n − 1
    assert s.loc["rpe_t_10m", "n_defined"] == 1 and np.isnan(s.loc["rpe_t_10m", "sd"])
    assert s.loc["rpe_r_10m", "n_defined"] == 0 and np.isnan(s.loc["rpe_r_10m", "mean"])
    assert s.loc["n_failures", "statistic"] == "median_iqr"
    assert (s.loc["n_failures", ["median", "q1", "q3"]] == [1.0, 0.5, 2.0]).all()   # interpolação linear
    assert s.loc["inliers_median", "statistic"] == "mean_sd" and s.loc["inliers_median", "n_defined"] == 2
    assert (s.loc["coverage", ["min", "max"]] == [0.7, 0.9]).all()


def test_summarize_without_gt_reports_no_error_metric_nor_length():
    runs = _runs_table().drop(columns=list(p2.ERROR_METRICS) + ["longest_m"])
    s = p2.summarize(runs, with_gt=False)
    assert not set(s["metric"]) & set(p2.ERROR_METRICS)
    assert "longest_m" not in set(s["metric"])
    assert set(s["metric"]) == (set(p2.OPERATION_METRICS) - {"longest_m"}) | set(p2.INDICATOR_METRICS)


def test_success_rate_keeps_invalid_runs_in_denominator():
    assert p2.success_rate(_runs_table()) == {"n_runs": 4, "n_valid": 3, "success_rate": 0.75,
                                              "exit_codes": "0,0,0,139"}


def _sequence(root, seq, with_gt_file):
    ext = root / "extracted" / seq
    (ext / "images").mkdir(parents=True)
    pd.DataFrame({"ts_ns": TS}).to_csv(ext / "images" / "stamps.csv", index=False)
    if with_gt_file:
        se3.save_tum(ext / "gt.tum", *_gt())
    (root / "tables").mkdir(exist_ok=True)
    table = _table() if with_gt_file else _table()[["t"]]   # RELLIS: sem passos do GT na tabela
    table.to_parquet(root / "tables" / f"{seq}.parquet", index=False)
    runs, logs = root / "runs" / seq, root / "logs"
    logs.mkdir(exist_ok=True)
    _write(runs / "stella", scale=1.5)                                   # execução oficial, fora da amostra
    for k in (1, 2, 3):
        _write(runs / f"stella_r{k}", scale=1.0 + 0.001 * k)
        _record(logs / f"{seq}_stella_r{k}.json")


def test_phase2_writes_tables_and_keeps_official_run_apart(tmp_path):
    _sequence(tmp_path, "1018-00", with_gt_file=True)
    _sequence(tmp_path, "rellis_example", with_gt_file=False)            # GT ausente: carregá-lo seria erro
    cfg = {s: ({"stella": np.eye(4)}, 100.0) for s in ("1018-00", "rellis_example")}
    plan = {("1018-00", "stella"): [1, 2, 3], ("rellis_example", "stella"): [1, 2, 3]}
    out = tmp_path / "out"
    p2.phase2(plan, tmp_path / "runs", tmp_path / "extracted", tmp_path / "tables", tmp_path / "logs", cfg, out)

    runs = pd.read_csv(out / "1018-00_stella_runs.csv")
    assert list(runs["repetition"]) == [1, 2, 3] and runs["valid"].all()
    summary = pd.read_csv(out / "summary.csv")
    bg = summary[summary["sequence"] == "1018-00"].set_index("metric")
    assert bg.loc["ate_rmse", "n_defined"] == 3
    assert bg.loc["ate_rmse", "max"] < 0.1                               # oficial (escala 1,5) não entra
    rellis = summary[summary["sequence"] == "rellis_example"]
    assert not set(rellis["metric"]) & set(p2.ERROR_METRICS)
    official = pd.read_csv(out / "official.csv").set_index("sequence")
    assert official.loc["1018-00", "ate_rmse"] > bg.loc["ate_rmse", "max"]
    assert "ate_rmse" not in official.columns or np.isnan(official.loc["rellis_example", "ate_rmse"])
    assert "longest_m" in bg.index and "longest_m" not in set(rellis["metric"])
    assert "longest_m" not in pd.read_csv(out / "rellis_example_stella_runs.csv").columns
    assert np.isnan(official.loc["rellis_example", "longest_m"])
    success = pd.read_csv(out / "success.csv")
    assert (success["success_rate"] == 1.0).all() and len(success) == 2


def test_plan_uses_ten_runs_for_variable_and_run_1_otherwise():
    plan = p2.phase2_plan({"1018-00/stella": "variable", "00000/orbslam3": "deterministic",
                           "1018-13/stella": "numerically_equivalent"})
    assert plan == {("1018-00", "stella"): list(range(1, 11)), ("00000", "orbslam3"): [1],
                    ("1018-13", "stella"): [1]}


def test_configs_come_from_each_dataset_yaml():
    cfg = p2.load_configs(["1018-00", "rellis_example"])
    assert cfg["1018-00"][1] == 100.0 and cfg["rellis_example"][1] == 140.0
    assert set(cfg["1018-00"][0]) >= {"orbslam3", "stella"}


def test_all_invalid_combination_reports_undefined_metrics(tmp_path):
    dirs = [_write(tmp_path / f"r{k}") for k in (1, 2)]
    recs = [_record(tmp_path / f"r{k}.json", exit_code=139) for k in (1, 2)]
    runs = p2.evaluate_combination(dirs, recs, TS, "orbslam3", _table(), np.eye(4), 100.0, gt=_gt())
    s = p2.summarize(runs, with_gt=True)
    assert (s["n_defined"] == 0).all() and s["mean"].isna().all()
    assert p2.success_rate(runs)["success_rate"] == 0.0


def test_evaluate_combination_labels_runs_with_their_k(tmp_path):
    dirs = [_write(tmp_path / f"r{k}") for k in (4, 7)]
    recs = [_record(tmp_path / f"r{k}.json") for k in (4, 7)]
    runs = p2.evaluate_combination(dirs, recs, TS, "orbslam3", _table(), np.eye(4), 100.0, reps=[4, 7])
    assert list(runs["repetition"]) == [4, 7]


def test_plan_rejects_unknown_decision():
    with pytest.raises(ValueError, match="variabel"):
        p2.phase2_plan({"1018-00/stella": "variable", "00000/stella": "variabel"})
