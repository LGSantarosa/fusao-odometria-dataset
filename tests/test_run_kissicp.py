import numpy as np
import pandas as pd
import pytest
from ofd import run_kissicp, se3, tracks
from ofd.kissicp_conditions import (compensate_to_scan_end, geometric_times, point_times_ns,
                                    prepare_scan)


def scene(seed=0):
    rng = np.random.default_rng(seed)
    ground = np.c_[rng.uniform(-30, 30, (6000, 2)), np.zeros(6000)]
    walls = np.vstack([np.c_[rng.uniform(-30, 30, 3000), np.full(3000, y), rng.uniform(0, 3, 3000)] for y in (-8, 9)])
    poles = np.vstack([np.c_[np.full(300, x), np.full(300, 2.0), rng.uniform(0, 4, 300)] for x in range(-25, 30, 5)])
    return np.vstack([ground, walls, poles]).astype(np.float32)


def make_seq(tmp_path, n=40, with_t=False):
    seq = tmp_path / "seq"; (seq / "clouds").mkdir(parents=True)
    W = scene()
    ts = (1_700_000_000 * 10**9 + np.arange(n) * 100_000_000).astype(np.int64)
    for k, t in enumerate(ts):
        rec = {"xyz": W - np.array([0.5 * k, 0, 0], np.float32)}
        if with_t:
            rec["t_norm"] = np.zeros(len(W), np.float32)
        np.savez_compressed(seq / "clouds" / f"{t}.npz", **rec)
    pd.DataFrame({"ts_ns": ts, "end_ns": ts + 99_000_000}).to_csv(seq / "lidar_stamps.csv", index=False)
    return seq, ts


def test_kissicp_tracks_translation_and_uses_end_ns(tmp_path):
    seq, ts = make_seq(tmp_path)
    run_kissicp.run(seq, tmp_path / "run", deskew=False)
    tr, _, meta = tracks.load_run(tmp_path / "run")
    assert len(tr.ts_ns) == 40 and abs(tr.Ts[-1][0, 3] - 19.5) < 0.5
    assert tr.ts_ns[0] == ts[0] + 99_000_000
    assert meta["uses_imu"] is False and meta["deskew"] is False
    st = pd.read_csv(tmp_path / "run" / "state.csv")
    assert len(st) == 40 and st["ok"].all()


def test_deskew_without_times_raises(tmp_path):
    seq, _ = make_seq(tmp_path, n=3, with_t=False)
    with pytest.raises(RuntimeError):
        run_kissicp.run(seq, tmp_path / "run", deskew=True)


def test_resolve_deskew_respects_config_override():
    # meta da extração diz que o tempo por ponto é válido, mas o dataset desliga o deskew do KISS-ICP
    assert run_kissicp.resolve_deskew({"deskew": True}, "auto") is True
    assert run_kissicp.resolve_deskew({"deskew": False}, "auto") is False
    assert run_kissicp.resolve_deskew({"deskew": True}, False) is False
    assert run_kissicp.resolve_deskew({"deskew": False}, True) is False   # nunca liga sem tempos válidos


def test_geometric_time_follows_manufacturer_rotation_direction():
    clockwise_angles = np.deg2rad([90, 0, -90, 180, 91])
    pts = np.c_[np.cos(clockwise_angles), np.sin(clockwise_angles), np.zeros(5)]
    np.testing.assert_allclose(geometric_times(pts, "clockwise"), [0, .25, .5, .75, 359 / 360])
    np.testing.assert_allclose(geometric_times(pts[[0, 3, 2, 1]], "counterclockwise"), [0, .25, .5, .75])


def test_point_times_respect_negative_time_relative_to_header():
    row = {"ts_ns": 1_000_000_000, "t_min_s": -.099, "span_s": .100, "end_ns": 1_001_000_000}
    np.testing.assert_array_equal(point_times_ns(row, [0, .5, 1]), [901_000_000, 951_000_000, 1_001_000_000])


def test_gt_assisted_compensation_recovers_scan_end_frame():
    gt_ts = np.array([0, 100_000_000], np.int64)
    gt = np.stack([np.eye(4), se3.exp_twist(np.array([1., 0, 0, 0, 0, np.pi / 2]))])
    point_ts = np.array([0, 25_000_000, 50_000_000, 75_000_000, 100_000_000], np.int64)
    world = np.tile([4., 2., .5], (len(point_ts), 1))
    raw = []
    for t, p in zip(point_ts, world):
        T = se3.interp(gt_ts, gt, int(t))
        raw.append((p - T[:3, 3]) @ T[:3, :3])
    corrected, ok = compensate_to_scan_end(np.asarray(raw), point_ts, gt_ts[-1], gt_ts, gt)
    T_end = gt[-1]
    expected = (world - T_end[:3, 3]) @ T_end[:3, :3]
    assert ok
    np.testing.assert_allclose(corrected, expected, atol=1e-12)


def test_conditions_select_times_and_external_compensation():
    ang = np.linspace(np.pi / 2, np.pi / 2 - 2 * np.pi, 9, endpoint=False)
    pts = np.c_[4 * np.cos(ang), 4 * np.sin(ang), np.zeros(9)]
    field = np.arange(9) / 9
    archive = {"t_norm": field}
    row = {"ts_ns": 0, "end_ns": 100_000_000, "t_min_s": 0., "span_s": .1}
    d1 = prepare_scan(pts, archive, row, "D1")
    d2 = prepare_scan(pts, archive, row, "D2")
    d3 = prepare_scan(pts, archive, row, "D3", "clockwise")
    assert d1.internal_deskew and d2.internal_deskew and d3.internal_deskew
    np.testing.assert_allclose(d1.times, field)
    np.testing.assert_allclose(d2.times, 1 - field)
    np.testing.assert_allclose(d3.times, field)
    gt_ts = np.array([0, 100_000_000], np.int64)
    gt = np.repeat(np.eye(4)[None], 2, axis=0)
    d4 = prepare_scan(pts, archive, row, "D4", gt=(gt_ts, gt))
    d4p = prepare_scan(pts, archive, row, "D4prime", "clockwise", (gt_ts, gt))
    assert d4.externally_compensated and d4p.externally_compensated
    assert not d4.internal_deskew and not d4p.internal_deskew
