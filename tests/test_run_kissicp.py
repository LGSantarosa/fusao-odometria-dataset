import numpy as np
import pandas as pd
import pytest
from ofd import run_kissicp, tracks


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
