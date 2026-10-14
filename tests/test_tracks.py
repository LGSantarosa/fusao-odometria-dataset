import json
import numpy as np
import pandas as pd
from ofd import tracks, se3


def test_segments_increment_on_loss_and_map_change():
    st = pd.DataFrame({"ts_ns": [1, 2, 3, 4, 5, 6], "ok": [1, 1, 0, 1, 1, 1],
                       "map_id": [0, 0, 0, 0, 1, 1]})
    seg = tracks.segments_from_state(st)
    assert list(seg["segment"]) == [0, 0, -1, 1, 2, 2]


def _write(run, ts, ok, map_id=None):
    run.mkdir(parents=True, exist_ok=True)
    Ts = np.stack([np.eye(4)] * len(ts))
    for i, T in enumerate(Ts):
        T[0, 3] = i
    st = pd.DataFrame({"ts_ns": ts, "ok": ok, "map_id": map_id or [0] * len(ts)})
    good = [t for t, o in zip(ts, ok) if o]
    tracks.write_run(run, np.array(good, dtype=np.int64), Ts[: len(good)], st,
                     pd.DataFrame({"ts_ns": ts, "inliers": range(len(ts))}),
                     {"method": "x", "uses_imu": False})


def test_load_run_roundtrip(tmp_path):
    _write(tmp_path / "r", [10, 20, 30], [1, 1, 1])
    tr, ind, meta = tracks.load_run(tmp_path / "r")
    assert list(tr.ts_ns) == [10, 20, 30]
    assert list(tr.segment) == [0, 0, 0]
    assert meta["method"] == "x"
    assert ind.loc[20, "inliers"] == 1


def test_load_run_sorts_and_dedups(tmp_path):
    run = tmp_path / "r"; run.mkdir()
    Ts = np.stack([np.eye(4)] * 4)
    se3.save_tum(run / "poses_causal.tum", np.array([30, 10, 20, 20], dtype=np.int64), Ts)
    pd.DataFrame({"ts_ns": [10, 20, 30], "ok": [1, 1, 1], "map_id": [0, 0, 0]}).to_csv(run / "state.csv", index=False)
    pd.DataFrame({"ts_ns": [10, 20, 30]}).to_csv(run / "indicators.csv", index=False)
    (run / "run.json").write_text(json.dumps({"method": "x"}))
    tr, _, _ = tracks.load_run(run)
    assert list(tr.ts_ns) == [10, 20, 30]


def test_pose_on_lost_frame_is_dropped(tmp_path):
    run = tmp_path / "r"; run.mkdir()
    se3.save_tum(run / "poses_causal.tum", np.array([10, 20], dtype=np.int64), np.stack([np.eye(4)] * 2))
    pd.DataFrame({"ts_ns": [10, 20], "ok": [1, 0], "map_id": [0, 0]}).to_csv(run / "state.csv", index=False)
    pd.DataFrame({"ts_ns": [10, 20]}).to_csv(run / "indicators.csv", index=False)
    (run / "run.json").write_text("{}")
    tr, _, _ = tracks.load_run(run)
    assert list(tr.ts_ns) == [10]
