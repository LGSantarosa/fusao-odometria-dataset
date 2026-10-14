"""Strictly causal sampling of method poses onto the LiDAR time grid."""
import numpy as np
import pandas as pd

from ofd import se3
from ofd.tracks import Track

VEC = ["dx", "dy", "dz", "qx", "qy", "qz", "qw"]
TW = ["vx", "vy", "vz", "wx", "wy", "wz"]


def _causal_index(ts_ns, grid_ns):
    # index of last pose with ts <= t, -1 if none
    return np.searchsorted(ts_ns, grid_ns, side="right") - 1


def method_deltas(track: Track, grid_ns, T_L_S, max_age_ms=100.0):
    grid_ns = np.asarray(grid_ns, dtype=np.int64)
    idx = _causal_index(track.ts_ns, grid_ns)
    n = len(grid_ns)
    out = {c: np.full(n, np.nan) for c in VEC + TW}
    src = np.where(idx >= 0, track.ts_ns[np.clip(idx, 0, None)] if len(track.ts_ns) else -1, -1)
    age = np.where(idx >= 0, (grid_ns - src) / 1e6, np.nan)
    seg = np.where(idx >= 0, track.segment[np.clip(idx, 0, None)] if len(track.ts_ns) else -1, -1)
    prev_src = np.full(n, -1, dtype=np.int64)
    dt = np.full(n, np.nan)
    valid = np.zeros(n, dtype=np.int64)
    fresh = (idx >= 0) & (age >= 0) & (age <= max_age_ms)
    for k in range(1, n):
        i, j = idx[k - 1], idx[k]
        if i < 0 or j < 0:
            continue
        prev_src[k] = track.ts_ns[i]
        dt[k] = (track.ts_ns[j] - track.ts_ns[i]) / 1e6
        if not (fresh[k] and fresh[k - 1]) or i == j or track.segment[i] != track.segment[j]:
            continue
        dT = se3.conjugate(se3.delta(track.Ts[i], track.Ts[j]), T_L_S)
        for c, v in zip(VEC, se3.to_vec(dT)):
            out[c][k] = v
        for c, v in zip(TW, se3.log_twist(dT) / (dt[k] / 1000.0)):
            out[c][k] = v
        valid[k] = 1
    df = pd.DataFrame(out)
    df["valid"] = valid
    df["src_ts"] = src.astype(np.int64)
    df["prev_src_ts"] = prev_src
    df["age_ms"] = age
    df["dt_ms"] = dt
    df["segment_id"] = seg.astype(np.int64)
    return df


def gt_deltas(gt_ts, gt_Ts, grid_ns):
    n = len(grid_ns)
    out = {f"gt_{c}": np.full(n, np.nan) for c in VEC + TW}
    prev = se3.interp(gt_ts, gt_Ts, int(grid_ns[0])) if n else None
    for k in range(1, n):
        cur = se3.interp(gt_ts, gt_Ts, int(grid_ns[k]))
        if prev is not None and cur is not None:
            dT = se3.delta(prev, cur)
            for c, v in zip(VEC, se3.to_vec(dT)):
                out[f"gt_{c}"][k] = v
            for c, v in zip(TW, se3.log_twist(dT) / ((grid_ns[k] - grid_ns[k - 1]) / 1e9)):
                out[f"gt_{c}"][k] = v
        prev = cur
    return pd.DataFrame(out)


def method_errors(md, track: Track, T_L_S, gt_ts, gt_Ts):
    n = len(md)
    err_t, err_r = np.full(n, np.nan), np.full(n, np.nan)
    for k in np.flatnonzero(md["valid"].to_numpy() == 1):
        a = se3.interp(gt_ts, gt_Ts, int(md["prev_src_ts"].iat[k]))
        b = se3.interp(gt_ts, gt_Ts, int(md["src_ts"].iat[k]))
        if a is None or b is None:
            continue
        dT_m = se3.to_mat(md.loc[k, ["dx", "dy", "dz"]].to_numpy(float),
                          md.loc[k, ["qx", "qy", "qz", "qw"]].to_numpy(float))
        E = se3.delta(se3.delta(a, b), dT_m)
        err_t[k] = float(np.linalg.norm(E[:3, 3]))
        err_r[k] = se3.rot_angle(E)
    return pd.DataFrame({"err_t": err_t, "err_r": err_r})
