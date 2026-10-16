import json

import pytest

from ofd import run_vo_repeat

ALL = [(s, m) for s in run_vo_repeat.SEQUENCES for m in run_vo_repeat.METHODS]


def _files(tmp_path):
    files = {}
    for name in ("bin", "vocab", "settings", "extract"):
        files[name] = tmp_path / name
        files[name].write_text(name)
    return files


def test_plan_is_interleaved_by_repetition_then_sequence_then_method():
    jobs = run_vo_repeat.plan([1, 2], ALL)
    assert jobs[:3] == [(1, "1018-00", "orbslam3"), (1, "1018-00", "stella"), (1, "1018-13", "orbslam3")]
    assert jobs[7] == (1, "00000", "stella") and jobs[8] == (2, "1018-00", "orbslam3")
    assert len(jobs) == 16


def test_plan_runs_only_the_exact_escalated_pairs_in_canonical_order():
    jobs = run_vo_repeat.plan([4, 5], [("1018-13", "stella"), ("1018-00", "orbslam3")])
    assert jobs == [(4, "1018-00", "orbslam3"), (4, "1018-13", "stella"),
                    (5, "1018-00", "orbslam3"), (5, "1018-13", "stella")]


@pytest.mark.parametrize("arg", ["1018-00/orbslam", "xx/stella", "1018-00"])
def test_parse_combos_rejects_unknown(arg):
    with pytest.raises(ValueError):
        run_vo_repeat.parse_combos(arg)


@pytest.mark.parametrize("arg", ["0", "11", "1,1", "a", ""])
def test_parse_reps_rejects_invalid(arg):
    with pytest.raises(ValueError):
        run_vo_repeat.parse_reps(arg)


def test_execute_records_protocol_items_and_exit_code(tmp_path):
    rec = run_vo_repeat.execute(["sh", "-c", "exit 3"], tmp_path / "runs" / "orbslam3_r1", _files(tmp_path),
                                seq_duration_s=10.0, record_path=tmp_path / "rec.json", method="orbslam3")
    saved = json.loads((tmp_path / "rec.json").read_text())
    assert rec == saved
    assert saved["exit_code"] == 3 and saved["attempt"] == 1
    for key in ("repo_commit", "method_commit", "method_patches", "cpu_model", "n_cpus", "loadavg_start",
                "loadavg_end", "wall_s", "wall_over_sequence", "sha256_bin", "sha256_vocab", "sha256_settings",
                "sha256_extract"):
        assert key in saved
    assert saved["method_commit"] == "4452a3c4ab75"
    assert saved["method_patches"] and all(len(h) == 64 for h in saved["method_patches"].values())
    assert saved["wall_over_sequence"] == pytest.approx(saved["wall_s"] / 10.0)


@pytest.mark.parametrize("existing", ["dir", "record"])
def test_execute_refuses_to_overwrite_without_external_cause(tmp_path, existing):
    out, rec = tmp_path / "orbslam3_r1", tmp_path / "r.json"
    (out.mkdir() if existing == "dir" else rec.write_text("{}"))
    with pytest.raises(FileExistsError):
        run_vo_repeat.execute(["true"], out, {}, seq_duration_s=1.0, record_path=rec, method="stella")


def test_retry_for_external_cause_archives_previous_attempt(tmp_path):
    out, rec, log = tmp_path / "runs" / "stella_r2", tmp_path / "logs" / "x_r2.json", tmp_path / "logs" / "x_r2.log"
    cmd = ["sh", "-c", f"mkdir -p {out} && echo run > {out}/frames.csv"]
    run_vo_repeat.execute(cmd, out, {}, 1.0, rec, log_path=log, method="stella")
    second = run_vo_repeat.execute(cmd, out, {}, 1.0, rec, log_path=log, method="stella",
                                   retry_cause="disco cheio")
    assert second["attempt"] == 2 and second["retry_cause"] == "disco cheio"
    assert (tmp_path / "runs" / "stella_r2.attempt1" / "frames.csv").exists()
    assert json.loads((tmp_path / "logs" / "x_r2.attempt1.json").read_text())["attempt"] == 1
    assert (tmp_path / "logs" / "x_r2.attempt1.log").exists()
    assert second["previous_attempts"][0]["record"].endswith("x_r2.attempt1.json")


# --- revisão 3: ciclo de tentativas seguro contra interrupção ----------------------------------

def test_orphan_log_counts_as_existing_attempt(tmp_path):
    log = tmp_path / "x.log"
    log.write_text("antigo")
    with pytest.raises(FileExistsError):
        run_vo_repeat.execute(["true"], tmp_path / "out", {}, 1.0, tmp_path / "x.json", log_path=log,
                              method="stella")
    assert log.read_text() == "antigo"


def test_retry_cause_without_previous_attempt_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        run_vo_repeat.execute(["true"], tmp_path / "out", {}, 1.0, tmp_path / "x.json",
                              log_path=tmp_path / "x.log", method="stella", retry_cause="disco cheio")


def test_initial_record_written_before_subprocess(tmp_path):
    rec = tmp_path / "x.json"
    # o comando lê o registro enquanto roda: ele já precisa existir, com a tentativa e sem código de saída
    cmd = ["sh", "-c", f"cp {rec} {tmp_path}/seen.json"]
    run_vo_repeat.execute(cmd, tmp_path / "out", {}, 1.0, rec, log_path=tmp_path / "x.log", method="stella")
    seen = json.loads((tmp_path / "seen.json").read_text())
    assert seen["status"] == "running" and seen["attempt"] == 1 and seen["exit_code"] is None
    final = json.loads(rec.read_text())
    assert final["status"] == "finished" and final["exit_code"] == 0


def test_interrupted_attempt_keeps_number_and_is_archived(tmp_path):
    out, rec, log = tmp_path / "runs" / "stella_r2", tmp_path / "x_r2.json", tmp_path / "x_r2.log"
    cmd = ["sh", "-c", f"mkdir -p {out}"]
    run_vo_repeat.execute(cmd, out, {}, 1.0, rec, log_path=log, method="stella")
    run_vo_repeat.execute(cmd, out, {}, 1.0, rec, log_path=log, method="stella", retry_cause="c1")
    # simula interrupção da tentativa 2: registro ficou "running"
    r = json.loads(rec.read_text()); r.update(status="running", exit_code=None); rec.write_text(json.dumps(r))
    third = run_vo_repeat.execute(cmd, out, {}, 1.0, rec, log_path=log, method="stella", retry_cause="c2")
    assert third["attempt"] == 3
    assert json.loads((tmp_path / "x_r2.attempt2.json").read_text())["status"] == "running"
    assert [p["attempt"] for p in third["previous_attempts"]] == [1, 2]


def test_corrupt_record_is_preserved_when_archiving(tmp_path):
    out, rec, log = tmp_path / "out", tmp_path / "x.json", tmp_path / "x.log"
    out.mkdir(); rec.write_text("{corrompido"); log.write_text("log")
    new = run_vo_repeat.execute(["true"], out, {}, 1.0, rec, log_path=log, method="stella", retry_cause="c")
    assert new["attempt"] == 2
    assert (tmp_path / "x.attempt1.json").read_text() == "{corrompido"
    assert new["previous_attempts"][0].get("record_unreadable") is True


def test_duplicate_combinations_are_rejected():
    with pytest.raises(ValueError):
        run_vo_repeat.parse_combos("1018-00/stella,1018-00/stella")
    with pytest.raises(ValueError):
        run_vo_repeat.plan([1], [("1018-00", "stella"), ("1018-00", "stella")])
