import numpy as np
import pandas as pd
from ofd import lidar_indicators, tracks
from tests.test_run_kissicp import make_seq


def test_indicators_keyed_by_end_ns(tmp_path):
    seq, ts = make_seq(tmp_path, n=5)
    end = ts + 99_000_000
    Ts = np.stack([np.eye(4)] * 5)
    for k in range(5):
        Ts[k][0, 3] = 0.5 * k  # pose correta do sensor
    tracks.write_run(tmp_path / "run", end, Ts, pd.DataFrame({"ts_ns": end, "ok": 1, "map_id": 0}),
                     pd.DataFrame({"ts_ns": end}), {"method": "kissicp"})
    out = lidar_indicators.compute(seq, tmp_path / "run", np.eye(4))
    assert out["fitness"].notna().sum() == 4 and out["fitness"].dropna().min() > 0.9
    assert set(out["ts_ns"]) == set(end)
