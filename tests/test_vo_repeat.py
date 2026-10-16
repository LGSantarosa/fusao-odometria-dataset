"""Validação sintética do protocolo docs/protocol_vo_repeat.md (seções 5–7)."""
import numpy as np
import pandas as pd
import pytest

from ofd import se3, tracks, vo_repeat

N = 60
TS = (np.arange(N, dtype=np.int64) + 1) * 100_000_000
STEP = np.array([0.10, 0.0, 0.0, 0.0, 0.0, 0.02])  # 10 cm e ~1,15° por quadro


def _poses(n=N, perturb=None, every=None, world=None):
    """Trajetória por incrementos; `perturb` = {k: E} multiplica o incremento k; `every` = E em todos."""
    T, out = np.eye(4) if world is None else world.copy(), []
    for k in range(n):
        if k:
            d = se3.exp_twist(STEP)
            if every is not None:
                d = d @ every
            if perturb and k in perturb:
                d = d @ perturb[k]
            T = T @ d
        out.append(T.copy())
    return np.stack(out)


def _write(path, Ts, ok=None, map_id=None, ts=TS, indicators=None, frames=True, meta=None):
    ok = np.ones(len(ts), dtype=int) if ok is None else np.asarray(ok)
    map_id = np.zeros(len(ts), dtype=int) if map_id is None else np.asarray(map_id)
    state = pd.DataFrame({"ts_ns": ts, "ok": ok, "map_id": map_id})
    ind = indicators if indicators is not None else pd.DataFrame(
        {"ts_ns": ts, "inliers": 100, "n_features": 1000, "reproj_err": 1.0, "tracked_ratio": 0.9})
    good = ok == 1
    tracks.write_run(path, ts[good], Ts[: len(ts)][good], state, ind,
                     meta or {"method": "orbslam3"})
    if frames:
        (path / "frames.csv").write_text("ts_ns\n")
    return path


def _E(t=0.0, r_deg=0.0):
    return se3.exp_twist([t, 0, 0, 0, 0, np.radians(r_deg)])


# --- 5.1 integridade -------------------------------------------------------------------------

def test_valid_run_passes_integrity(tmp_path):
    ok, reasons = vo_repeat.validate_run(_write(tmp_path / "a", _poses()), TS, exit_code=0)
    assert ok and reasons == []


@pytest.mark.parametrize("case", ["exit", "missing_artifact", "truncated", "duplicate", "extra",
                                  "pose_not_ok", "indicators_mismatch"])
def test_invalid_runs_are_detected(tmp_path, case):
    run = _write(tmp_path / "a", _poses())
    exit_code = 0
    if case == "exit":
        exit_code = 139
    elif case == "missing_artifact":
        (run / "frames.csv").unlink()
    elif case == "truncated":
        st = pd.read_csv(run / "state.csv"); st.iloc[:-5].to_csv(run / "state.csv", index=False)
    elif case == "duplicate":
        st = pd.read_csv(run / "state.csv"); pd.concat([st, st.iloc[[3]]]).to_csv(run / "state.csv", index=False)
    elif case == "extra":
        st = pd.read_csv(run / "state.csv")
        pd.concat([st, pd.DataFrame({"ts_ns": [TS[-1] + 1], "ok": [0], "map_id": [0]})]).to_csv(
            run / "state.csv", index=False)
    elif case == "pose_not_ok":
        st = pd.read_csv(run / "state.csv"); st.loc[10, "ok"] = 0; st.to_csv(run / "state.csv", index=False)
    elif case == "indicators_mismatch":
        ind = pd.read_csv(run / "indicators.csv"); ind.iloc[:-1].to_csv(run / "indicators.csv", index=False)
    ok, reasons = vo_repeat.validate_run(run, TS, exit_code=exit_code)
    assert not ok and reasons


# --- 5.3–5.5 componentes A, B, C ---------------------------------------------------------------

def test_identical_runs_have_zero_differences(tmp_path):
    a, b = _write(tmp_path / "a", _poses()), _write(tmp_path / "b", _poses())
    p = vo_repeat.compare_pair(a, b)
    assert p["A_identical"] and p["B_n"] == N - 1 and p["C_n"] == N
    assert p["B_max_t_m"] < 1e-12 and p["C_max_t_m"] < 1e-12  # só arredondamento de inv(A)·P


def test_different_map_frame_gives_zero_B_and_C(tmp_path):
    G = se3.exp_twist([5.0, -3.0, 1.0, 0.3, -0.2, 1.0])
    p = vo_repeat.compare_pair(_write(tmp_path / "a", _poses()), _write(tmp_path / "b", _poses(world=G)))
    assert p["A_identical"]
    assert p["B_max_t_m"] < 1e-6 and p["B_max_r_deg"] < 1e-5
    assert p["C_max_t_m"] < 1e-6 and p["C_max_r_deg"] < 1e-5


def test_single_increment_perturbation_detected_by_B_and_C(tmp_path):
    E = _E(t=0.005, r_deg=0.05)
    p = vo_repeat.compare_pair(_write(tmp_path / "a", _poses()),
                               _write(tmp_path / "b", _poses(perturb={30: E})))
    assert p["B_max_t_m"] == pytest.approx(0.005, abs=1e-6)
    assert p["B_max_r_deg"] == pytest.approx(0.05, abs=1e-5)
    assert p["C_max_t_m"] >= 0.005 and p["C_max_r_deg"] >= 0.05 - 1e-5


def test_small_accumulated_drift_detected_only_by_C(tmp_path):
    E = _E(t=0.0001)  # 0,1 mm por quadro, abaixo do limiar por incremento
    p = vo_repeat.compare_pair(_write(tmp_path / "a", _poses()), _write(tmp_path / "b", _poses(every=E)))
    assert p["B_max_t_m"] < 0.001
    assert p["C_max_t_m"] > 0.001


def test_reset_in_one_run_breaks_A_and_compares_overlaps_separately(tmp_path):
    ok_b = np.ones(N, dtype=int); ok_b[30] = 0
    map_b = np.r_[np.zeros(31, int), np.ones(N - 31, int)]
    G = se3.exp_twist([2.0, 1.0, 0.0, 0.0, 0.0, 0.5])
    Tb = _poses()
    Tb[31:] = G @ Tb[31:]  # novo mapa com referencial próprio
    p = vo_repeat.compare_pair(_write(tmp_path / "a", _poses()), _write(tmp_path / "b", Tb, ok=ok_b, map_id=map_b))
    assert not p["A_identical"]
    assert p["A_n_ok_diverge"] == 1 and p["A_boundaries_differ"]
    assert p["C_n_overlaps"] == 2
    assert p["C_max_t_m"] < 1e-6 and p["B_max_t_m"] < 1e-6
    assert p["B_n"] == N - 3  # pares (29,30), (30,31) fora do suporte comum


# --- 6 regra de decisão -------------------------------------------------------------------------

def _decide(tmp_path, runs, exit_codes=None):
    dirs = [_write(tmp_path / f"r{k}", **kw) for k, kw in enumerate(runs, 1)]
    return vo_repeat.analyze_combination(dirs, TS, exit_codes or [0] * len(dirs))


def test_decision_deterministic(tmp_path):
    out = _decide(tmp_path, [dict(Ts=_poses())] * 3)
    assert out["decision"] == "deterministic"
    assert len(out["pairs"]) == 3


def test_decision_numerically_equivalent(tmp_path):
    tiny = _E(t=1e-6)
    out = _decide(tmp_path, [dict(Ts=_poses()), dict(Ts=_poses(perturb={10: tiny})), dict(Ts=_poses())])
    assert out["decision"] == "numerically_equivalent"


def test_decision_variable_above_threshold(tmp_path):
    out = _decide(tmp_path, [dict(Ts=_poses()), dict(Ts=_poses(perturb={10: _E(t=0.002)})), dict(Ts=_poses())])
    assert out["decision"] == "variable"


def test_truncated_runs_identical_are_not_deterministic(tmp_path):
    short = TS[:-5]
    out = _decide(tmp_path, [dict(Ts=_poses(), ts=short)] * 3)
    assert out["decision"] == "variable"
    assert not out["runs"]["valid"].any()
    assert out["pairs"]["B_max_t_m"].isna().all()


def test_failed_exit_makes_combination_variable(tmp_path):
    out = _decide(tmp_path, [dict(Ts=_poses())] * 3, exit_codes=[0, 0, 134])
    assert out["decision"] == "variable"
    assert list(out["runs"]["exit_code"]) == [0, 0, 134]


def test_indicator_difference_with_identical_trajectory_is_variable(tmp_path):
    ind = pd.DataFrame({"ts_ns": TS, "inliers": 100, "n_features": 1000, "reproj_err": 1.0, "tracked_ratio": 0.9})
    ind2 = ind.copy(); ind2.loc[5, "inliers"] = 99
    out = _decide(tmp_path, [dict(Ts=_poses(), indicators=ind), dict(Ts=_poses(), indicators=ind2),
                             dict(Ts=_poses(), indicators=ind)])
    assert out["decision"] == "variable"


def test_no_comparable_support_with_different_hashes_is_variable(tmp_path):
    alt = np.arange(N) % 2  # ok alternado: nenhum par consecutivo, segmentos de um quadro
    out = _decide(tmp_path, [dict(Ts=_poses(), ok=alt), dict(Ts=_poses(world=_E(t=1e-7)), ok=alt),
                             dict(Ts=_poses(), ok=alt)])
    assert (out["pairs"]["B_n"] == 0).all() and (out["pairs"]["C_n"] == 0).all()
    assert out["decision"] == "variable"


# --- 7 estatísticas -----------------------------------------------------------------------------

def test_describe_mean_sd_ignores_undefined_and_needs_two_for_sd():
    d = vo_repeat.describe([1.0, np.nan, 3.0], "mean_sd")
    assert d["n_defined"] == 2 and d["mean"] == 2.0 and d["sd"] == pytest.approx(np.sqrt(2))
    one = vo_repeat.describe([np.nan, 4.0], "mean_sd")
    assert one["n_defined"] == 1 and one["mean"] == 4.0 and np.isnan(one["sd"])
    none = vo_repeat.describe([np.nan], "mean_sd")
    assert none["n_defined"] == 0 and np.isnan(none["mean"])


def test_describe_median_iqr_uses_linear_percentiles():
    d = vo_repeat.describe([1, 2, 3, 4, 10], "median_iqr")
    assert d["median"] == 3 and d["q1"] == 2 and d["q3"] == 4 and d["min"] == 1 and d["max"] == 10


def test_indicator_medians_over_ok_frames_with_missing(tmp_path):
    ok = np.ones(N, dtype=int); ok[:10] = 0
    ind = pd.DataFrame({"ts_ns": TS, "inliers": np.arange(N), "n_features": 1000,
                        "reproj_err": np.r_[np.full(N - 5, 2.0), np.full(5, np.nan)],
                        "tracked_ratio": np.nan})
    m = vo_repeat.indicator_medians(_write(tmp_path / "a", _poses(), ok=ok, indicators=ind))
    assert m["inliers_median"] == np.median(np.arange(10, N))
    assert m["reproj_err_missing_frac"] == pytest.approx(5 / 50)
    assert np.isnan(m["tracked_ratio_median"]) and m["tracked_ratio_missing_frac"] == 1.0


# --- ponto de entrada da fase 1 ----------------------------------------------------------------

def test_phase1_reads_records_and_writes_decisions(tmp_path):
    import json
    runs, ext, logs, out = tmp_path / "runs", tmp_path / "extracted", tmp_path / "logs", tmp_path / "out"
    (ext / "s1" / "images").mkdir(parents=True)
    pd.DataFrame({"ts_ns": TS}).to_csv(ext / "s1" / "images" / "stamps.csv", index=False)
    logs.mkdir()
    for k in (1, 2, 3):
        _write(runs / "s1" / f"stella_r{k}", _poses())
        (logs / f"s1_stella_r{k}.json").write_text(
            json.dumps({"status": "finished", "exit_code": 0 if k < 3 else 1}))
    # orbslam3 sem registro na repetição 2: execução ausente, conta como inválida
    for k in (1, 3):
        _write(runs / "s1" / f"orbslam3_r{k}", _poses())
        (logs / f"s1_orbslam3_r{k}.json").write_text(json.dumps({"status": "finished", "exit_code": 0}))
    plan = {("s1", m): [1, 2, 3] for m in ("orbslam3", "stella")}
    decisions = vo_repeat.phase1(plan, runs, ext, logs, out)
    assert decisions == {"s1/orbslam3": "variable", "s1/stella": "variable"}
    assert json.loads((out / "decisions.json").read_text()) == decisions
    assert (out / "s1_stella_pairs.csv").exists() and (out / "s1_stella_runs.csv").exists()
    r = pd.read_csv(out / "s1_orbslam3_runs.csv")
    assert list(r["valid"]) == [True, False, True]


# --- revisão 2: robustez, componente A completo, escalonamento por combinação ------------------

@pytest.mark.parametrize("case", ["state_no_ts", "state_no_ok", "indicators_no_col", "state_garbage",
                                  "poses_garbage", "ok_not_binary"])
def test_malformed_artifacts_are_invalid_not_exceptions(tmp_path, case):
    run = _write(tmp_path / "a", _poses())
    st = pd.read_csv(run / "state.csv")
    if case == "state_no_ts":
        st.drop(columns="ts_ns").to_csv(run / "state.csv", index=False)
    elif case == "state_no_ok":
        st.drop(columns="ok").to_csv(run / "state.csv", index=False)
    elif case == "indicators_no_col":
        pd.read_csv(run / "indicators.csv").drop(columns="reproj_err").to_csv(run / "indicators.csv", index=False)
    elif case == "state_garbage":
        (run / "state.csv").write_bytes(b"\x00\xff garbage\n\"unterminated")
    elif case == "poses_garbage":
        (run / "poses_causal.tum").write_text("1.0 x y\n")
    elif case == "ok_not_binary":
        st.loc[3, "ok"] = 2; st.to_csv(run / "state.csv", index=False)
    ok, reasons = vo_repeat.validate_run(run, TS, exit_code=0)
    assert not ok and reasons


def test_component_A_reports_failures_resets_and_divergent_boundaries(tmp_path):
    ok_b = np.ones(N, dtype=int); ok_b[30] = 0
    map_b = np.r_[np.zeros(31, int), np.ones(N - 31, int)]
    p = vo_repeat.compare_pair(_write(tmp_path / "a", _poses()),
                               _write(tmp_path / "b", _poses(), ok=ok_b, map_id=map_b))
    assert p["A_failures_a"] == 0 and p["A_failures_b"] == 1
    assert p["A_resets_a"] == 0 and p["A_resets_b"] == 1
    assert p["A_boundaries_only_a"] == "" and p["A_boundaries_only_b"] == str(TS[31])
    assert p["A_ok_diverge_ts"] == str(TS[30])


def test_single_run_cannot_be_classified(tmp_path):
    with pytest.raises(ValueError):
        vo_repeat.analyze_combination([_write(tmp_path / "a", _poses())], TS, [0])


def test_phase1_uses_ten_runs_only_for_escalated_combinations(tmp_path):
    import json
    runs, ext, logs, out = tmp_path / "runs", tmp_path / "extracted", tmp_path / "logs", tmp_path / "out"
    (ext / "s1" / "images").mkdir(parents=True)
    pd.DataFrame({"ts_ns": TS}).to_csv(ext / "s1" / "images" / "stamps.csv", index=False)
    logs.mkdir()
    for method, ks in (("orbslam3", range(1, 11)), ("stella", range(1, 4))):
        for k in ks:
            _write(runs / "s1" / f"{method}_r{k}", _poses())
            (logs / f"s1_{method}_r{k}.json").write_text(json.dumps({"status": "finished", "exit_code": 0}))
    plan = {("s1", "orbslam3"): list(range(1, 11)), ("s1", "stella"): [1, 2, 3]}
    vo_repeat.phase1(plan, runs, ext, logs, out)
    assert len(pd.read_csv(out / "s1_orbslam3_pairs.csv")) == 45
    assert len(pd.read_csv(out / "s1_stella_pairs.csv")) == 3


def test_reps_plan_from_decisions_escalates_only_variable():
    decisions = {"1018-00/orbslam3": "variable", "1018-00/stella": "deterministic"}
    plan = vo_repeat.reps_plan(decisions)
    assert plan == {("1018-00", "orbslam3"): list(range(1, 11)), ("1018-00", "stella"): [1, 2, 3]}


# --- revisão 3: valores inválidos e registros corrompidos --------------------------------------

@pytest.mark.parametrize("case", ["ts_fractional", "map_id_nan", "map_id_fractional", "pose_nan", "ok_nan"])
def test_values_that_would_change_ABC_make_run_invalid(tmp_path, case):
    run = _write(tmp_path / "a", _poses())
    if case == "ts_fractional":
        for name in ("state.csv", "indicators.csv"):
            df = pd.read_csv(run / name)
            df["ts_ns"] = df["ts_ns"].astype(float) + 0.9
            df.to_csv(run / name, index=False)
    elif case in ("map_id_nan", "map_id_fractional", "ok_nan"):
        st = pd.read_csv(run / "state.csv")
        col = "ok" if case == "ok_nan" else "map_id"
        st[col] = st[col].astype(float)
        st.loc[7, col] = 0.5 if case == "map_id_fractional" else np.nan
        st.to_csv(run / "state.csv", index=False)
    elif case == "pose_nan":
        lines = (run / "poses_causal.tum").read_text().splitlines()
        tok = lines[4].split(); tok[1] = "nan"; lines[4] = " ".join(tok)
        (run / "poses_causal.tum").write_text("\n".join(lines) + "\n")
    ok, reasons = vo_repeat.validate_run(run, TS, exit_code=0)
    assert not ok and reasons


def test_fractional_grid_is_not_truncated_to_canonical(tmp_path):
    """1,9 e 2,1 não podem passar contra a grade 1, 2."""
    ts = np.array([1, 2], dtype=np.int64)
    run = _write(tmp_path / "a", _poses(2), ts=ts)
    for name in ("state.csv", "indicators.csv"):
        df = pd.read_csv(run / name); df["ts_ns"] = [1.9, 2.1]; df.to_csv(run / name, index=False)
    assert not vo_repeat.validate_run(run, ts, exit_code=0)[0]


@pytest.mark.parametrize("content", ["{not json", '{"exit_code": null, "status": "running"}', "[]"])
def test_phase1_marks_unreadable_or_incomplete_record_invalid(tmp_path, content):
    import json
    runs, ext, logs, out = tmp_path / "runs", tmp_path / "extracted", tmp_path / "logs", tmp_path / "out"
    (ext / "s1" / "images").mkdir(parents=True)
    pd.DataFrame({"ts_ns": TS}).to_csv(ext / "s1" / "images" / "stamps.csv", index=False)
    logs.mkdir()
    for k in (1, 2, 3):
        _write(runs / "s1" / f"stella_r{k}", _poses())
        (logs / f"s1_stella_r{k}.json").write_text(
            content if k == 2 else json.dumps({"exit_code": 0, "status": "finished"}))
    d = vo_repeat.phase1({("s1", "stella"): [1, 2, 3]}, runs, ext, logs, out)
    r = pd.read_csv(out / "s1_stella_runs.csv")
    assert d["s1/stella"] == "variable"
    assert list(r["valid"]) == [True, False, True]
    assert r.loc[1, "record_status"] in ("unreadable", "incomplete")


@pytest.mark.parametrize("rec, expected", [
    ({"status": "finished", "exit_code": 0}, (0, "finished")),
    ({"status": "finished", "exit_code": 139}, (139, "finished")),
    ({"exit_code": 0}, (None, "incomplete")),                          # status ausente
    ({"status": "inválido", "exit_code": 0}, (None, "incomplete")),    # status desconhecido
    ({"status": "running", "exit_code": None}, (None, "incomplete")),
    ({"status": "finished", "exit_code": None}, (None, "incomplete")),
    ({"status": "finished", "exit_code": True}, (None, "incomplete")),
])
def test_read_record_requires_explicit_finished_status(tmp_path, rec, expected):
    import json
    path = tmp_path / "r.json"
    path.write_text(json.dumps(rec))
    assert vo_repeat.read_record(path) == expected
