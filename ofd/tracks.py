"""Common run format: poses_causal.tum, state.csv, indicators.csv, run.json."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import se3


@dataclass
class Track:
    ts_ns: np.ndarray
    Ts: np.ndarray
    segment: np.ndarray


def segments_from_state(state: pd.DataFrame) -> pd.DataFrame:
    st = state.sort_values("ts_ns").reset_index(drop=True)
    seg, cur, prev_ok, prev_map = [], -1, False, None
    for ok, mid in zip(st["ok"].astype(bool), st["map_id"]):
        if ok and (not prev_ok or mid != prev_map):
            cur += 1
        seg.append(cur if ok else -1)
        prev_ok, prev_map = ok, mid
    return pd.DataFrame({"ts_ns": st["ts_ns"].astype(np.int64), "ok": st["ok"], "segment": seg})


def load_run(run_dir):
    run_dir = Path(run_dir)
    ts, Ts = se3.load_tum(run_dir / "poses_causal.tum")
    order = np.argsort(ts, kind="stable")
    ts, Ts = ts[order], Ts[order]
    keep = np.ones(len(ts), bool)
    keep[:-1] = ts[:-1] != ts[1:]  # keep last of duplicates
    ts, Ts = ts[keep], Ts[keep]
    seg = segments_from_state(pd.read_csv(run_dir / "state.csv")).set_index("ts_ns")["segment"]
    seg = seg[~seg.index.duplicated(keep="last")]
    s = seg.reindex(ts).fillna(-1).astype(np.int64).to_numpy()
    good = s >= 0
    track = Track(ts[good], Ts[good], s[good])
    ind = pd.read_csv(run_dir / "indicators.csv")
    ind = ind.drop_duplicates("ts_ns", keep="last").set_index("ts_ns").sort_index()
    meta = json.loads((run_dir / "run.json").read_text())
    return track, ind, meta


def write_run(run_dir, ts_ns, Ts, state_df, indicators_df, meta):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    se3.save_tum(run_dir / "poses_causal.tum", ts_ns, Ts)
    state_df.to_csv(run_dir / "state.csv", index=False)
    indicators_df.to_csv(run_dir / "indicators.csv", index=False)
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2))
