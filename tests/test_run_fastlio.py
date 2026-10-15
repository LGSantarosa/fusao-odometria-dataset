import numpy as np
import pytest
from ofd import run_fastlio

MS = 1_000_000


def poses(n):
    Ts = np.stack([np.eye(4)] * n)
    for i in range(n):
        Ts[i][0, 3] = i
    return Ts


def test_every_scan_has_state_and_missing_scan_is_not_ok():
    end = np.arange(10) * 100 * MS
    raw_ts = np.delete(end, 4) + 2 * MS          # scan 4 não gerou pose; demais com 2 ms de diferença
    ts, Ts, st, info = run_fastlio.assemble(raw_ts, poses(9), end)
    assert len(st) == 10 and st["ok"].tolist() == [1, 1, 1, 1, 0, 1, 1, 1, 1, 1]
    assert ts.tolist() == np.delete(end, 4).tolist()   # pose carimbada com end_ns do scan
    assert info["matched_frac"] == 0.9


def test_offset_mismatch_raises_with_diagnostic():
    end = np.arange(10) * 100 * MS
    with pytest.raises(RuntimeError, match="mediana"):
        run_fastlio.assemble(end + 50 * MS, poses(10), end)


def test_lidar_runners_declare_continuous_frame():
    import inspect
    from ofd import run_kissicp
    assert '"continuous_frame": True' in inspect.getsource(run_fastlio.run)
    assert '"continuous_frame": True' in inspect.getsource(run_kissicp.run)


def _attempt(tmp_path, end, raw_ts):
    from ofd import se3
    att = tmp_path / "fastlio.attempts" / "a1"; att.mkdir(parents=True)
    se3.save_tum(att / "raw_odom.tum", raw_ts, poses(len(raw_ts)))
    (att / "log.txt").write_text("IMU Initial Done\n")
    return att


def test_finalize_promotes_atomically_and_replaces_stale_files(tmp_path):
    out = tmp_path / "fastlio"; out.mkdir()
    (out / "stale.txt").write_text("velho")
    end = np.arange(10) * 100 * MS
    att = _attempt(tmp_path, end, end + 1 * MS)
    run_fastlio.finalize(att, out, end, {"config": "x"})
    assert not (out / "stale.txt").exists()
    import json
    meta = json.loads((out / "run.json").read_text())
    assert meta["attempt_dir"] == str(att) and meta["matched_frac"] == 1.0
    assert (att / "log.txt").exists()                       # tentativa preservada


def test_finalize_failure_keeps_previous_output(tmp_path):
    out = tmp_path / "fastlio"; out.mkdir()
    (out / "run.json").write_text('{"bom": true}')
    end = np.arange(10) * 100 * MS
    att = _attempt(tmp_path, end, end + 50 * MS)            # nada casa
    with pytest.raises(RuntimeError):
        run_fastlio.finalize(att, out, end, {})
    assert (out / "run.json").read_text() == '{"bom": true}'   # saída anterior intacta
    assert (att / "raw_odom.tum").exists()
    assert not any(p.name.startswith("fastlio.staging") for p in tmp_path.iterdir())


def test_match_fraction_only_over_scans_with_imu_coverage():
    end = np.arange(100) * 100 * MS
    covered = (end >= 20 * 100 * MS) & (end <= 79 * 100 * MS)      # IMU só cobre os scans 20..79
    raw = end[covered][:-3] + 1 * MS                                 # 57 de 60 cobertos têm pose
    ts, Ts, st, info = run_fastlio.assemble(raw, poses(len(raw)), end, imu_window=(int(end[20]), int(end[79])))
    assert len(st) == 100                                            # estado para todos os scans
    assert abs(info["matched_frac"] - 57 / 60) < 1e-12
    assert abs(info["matched_frac_all"] - 57 / 100) < 1e-12
    assert info["n_scans_without_imu"] == 40


def test_pose_outside_imu_coverage_is_not_ok():
    end = np.arange(10) * 100 * MS
    raw = end + 1 * MS                                               # pose para todos, inclusive antes da IMU
    ts, Ts, st, info = run_fastlio.assemble(raw, poses(10), end, imu_window=(int(end[3]), int(end[9])))
    assert st["ok"].tolist() == [0, 0, 0] + [1] * 7
    assert ts.tolist() == end[3:].tolist() and np.allclose(Ts[:, 0, 3], np.arange(3, 10))
