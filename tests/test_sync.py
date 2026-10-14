import numpy as np
from ofd import sync, se3
from ofd.tracks import Track

MS = 1_000_000


def line_track(ts_ms, seg=None):
    Ts = []
    for i, _ in enumerate(ts_ms):
        T = np.eye(4); T[0, 3] = float(i); Ts.append(T)
    return Track(np.array(ts_ms, dtype=np.int64) * MS, np.stack(Ts),
                 np.array(seg if seg is not None else [0] * len(ts_ms), dtype=np.int64))


def test_strictly_causal_never_uses_future():
    tr = line_track([0, 95, 205])
    grid = np.array([0, 100, 200], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    assert list(md["src_ts"]) == [0, 95 * MS, 95 * MS]
    assert (md["src_ts"].to_numpy() <= grid).all()


def test_age_and_dt_and_validity():
    tr = line_track([0, 95, 190])
    grid = np.array([0, 100, 200], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4), max_age_ms=100)
    assert md["valid"].tolist() == [0, 1, 1]
    np.testing.assert_allclose(md["age_ms"], [0, 5, 10])
    np.testing.assert_allclose(md["dt_ms"].iloc[1:], [95, 95])
    np.testing.assert_allclose(md["dx"].iloc[1:], [1, 1])


def test_too_old_is_invalid():
    tr = line_track([0, 50])
    grid = np.array([0, 100, 300], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4), max_age_ms=100)
    assert md["valid"].iloc[2] == 0


def test_same_source_twice_is_invalid():
    tr = line_track([0, 10])
    grid = np.array([50, 60], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    assert md["valid"].iloc[1] == 0  # dt_ms == 0


def test_cross_segment_invalid():
    tr = line_track([0, 100, 200], seg=[0, 0, 1])
    grid = np.array([0, 100, 200], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    assert md["valid"].tolist() == [0, 1, 0]
    assert md["segment_id"].tolist() == [0, 0, 1]


def test_causal_before_first_pose():
    tr = line_track([200, 300])
    grid = np.array([0, 100, 200, 300], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    assert md["src_ts"].tolist()[:2] == [-1, -1]
    assert md["valid"].tolist() == [0, 0, 0, 1]


def test_qw_nonnegative():
    tr = line_track([0, 100])
    tr.Ts[1][:3, :3] = se3.to_mat([0, 0, 0], [0, 0, np.sin(np.radians(100)), np.cos(np.radians(100))])[:3, :3]
    md = sync.method_deltas(tr, np.array([0, 100], dtype=np.int64) * MS, np.eye(4))
    assert md["qw"].iloc[1] >= 0


def test_gt_deltas_out_of_range_nan():
    gt = line_track([100, 200, 300])
    grid = np.array([0, 100, 200, 300, 400], dtype=np.int64) * MS
    g = sync.gt_deltas(gt.ts_ns, gt.Ts, grid)
    assert np.isnan(g["gt_dx"].iloc[0]) and np.isnan(g["gt_dx"].iloc[1]) and np.isnan(g["gt_dx"].iloc[4])
    np.testing.assert_allclose(g["gt_dx"].iloc[2:4], [1, 1])


def test_twist_is_delta_over_dt():
    tr = line_track([0, 95, 190])
    md = sync.method_deltas(tr, np.array([0, 100, 200], dtype=np.int64) * MS, np.eye(4))
    np.testing.assert_allclose(md["vx"].iloc[1:], 1 / 0.095)
    np.testing.assert_allclose(md["wz"].iloc[1:], 0, atol=1e-12)
    g = sync.gt_deltas(tr.ts_ns, tr.Ts, np.array([0, 95, 190], dtype=np.int64) * MS)
    np.testing.assert_allclose(g["gt_vx"].iloc[1:], 1 / 0.095)


def test_errors_use_method_source_instants():
    tr = line_track([0, 95])           # método: 1 m em 95 ms
    gt_ts = np.array([0, 95], dtype=np.int64) * MS
    gt_Ts = tr.Ts.copy()               # GT idêntico nos mesmos instantes
    grid = np.array([0, 100], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    e = sync.method_errors(md, tr, np.eye(4), gt_ts, gt_Ts)
    assert e["err_t"].iloc[1] < 1e-9 and np.isnan(e["err_t"].iloc[0])
