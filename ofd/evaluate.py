"""Per-method trajectory metrics: segment ATE (eligible only), RPE, coverage on the grid."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, schema, se3, tracks
from ofd.tracks import Track


def umeyama_se3(src, dst):
    mu_s, mu_d = src.mean(0), dst.mean(0)
    C = (dst - mu_d).T @ (src - mu_s) / len(src)
    U, _, Vt = np.linalg.svd(C)
    D = np.eye(3)
    D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    T = np.eye(4)
    T[:3, :3] = U @ D @ Vt
    T[:3, 3] = mu_d - T[:3, :3] @ mu_s
    return T


def _to_lidar(Ts, T_L_S):
    Ti = se3.inv(T_L_S)
    return np.stack([T @ Ti for T in Ts]) if len(Ts) else Ts


def segment_metrics(track: Track, T_L_S, gt_ts, gt_Ts, min_dur_s=30.0, min_len_m=20.0):
    rows = []
    est = _to_lidar(track.Ts, T_L_S)
    for s in np.unique(track.segment):
        idx = np.flatnonzero(track.segment == s)
        pairs = [(i, se3.interp(gt_ts, gt_Ts, int(track.ts_ns[i]))) for i in idx]
        pairs = [(i, g) for i, g in pairs if g is not None]
        if len(pairs) < 3:
            rows.append(dict(segment=int(s), n=len(pairs), dur_s=0.0, len_m=0.0, eligible=False, ate_rmse=np.nan))
            continue
        P = np.stack([est[i][:3, 3] for i, _ in pairs])
        G = np.stack([g[:3, 3] for _, g in pairs])
        dur = (track.ts_ns[pairs[-1][0]] - track.ts_ns[pairs[0][0]]) / 1e9
        length = float(np.sum(np.linalg.norm(np.diff(G, axis=0), axis=1)))
        A = umeyama_se3(P, G)
        res = (A[:3, :3] @ P.T).T + A[:3, 3] - G
        rows.append(dict(segment=int(s), n=len(pairs), dur_s=dur, len_m=length,
                         eligible=bool(dur >= min_dur_s and length >= min_len_m),
                         ate_rmse=float(np.sqrt(np.mean(np.sum(res ** 2, axis=1))))))
    return pd.DataFrame(rows, columns=["segment", "n", "dur_s", "len_m", "eligible", "ate_rmse"])


def aggregate_ate(seg_df):
    e = seg_df[seg_df["eligible"]]
    if e.empty:
        return float("nan")
    return float(np.sqrt(np.sum(e["n"] * e["ate_rmse"] ** 2) / np.sum(e["n"])))


def rpe(track: Track, T_L_S, gt_ts, gt_Ts, delta_m=10.0):
    est = _to_lidar(track.Ts, T_L_S)
    gts = [se3.interp(gt_ts, gt_Ts, int(t)) for t in track.ts_ns]
    et, er, e10, r10 = [], [], [], []
    for k in range(1, len(track.ts_ns)):
        if track.segment[k] != track.segment[k - 1] or gts[k] is None or gts[k - 1] is None:
            continue
        E = se3.delta(se3.delta(gts[k - 1], gts[k]), se3.delta(est[k - 1], est[k]))
        et.append(np.linalg.norm(E[:3, 3])); er.append(se3.rot_angle(E))
    for s in np.unique(track.segment):
        idx = [i for i in np.flatnonzero(track.segment == s) if gts[i] is not None]
        if len(idx) < 2:
            continue
        G = np.stack([gts[i][:3, 3] for i in idx])
        cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(G, axis=0), axis=1))]
        for a in range(len(idx)):
            b = int(np.searchsorted(cum, cum[a] + delta_m))
            if b >= len(idx):
                break
            i, j = idx[a], idx[b]
            E = se3.delta(se3.delta(gts[i], gts[j]), se3.delta(est[i], est[j]))
            e10.append(np.linalg.norm(E[:3, 3]))
            r10.append(se3.rot_angle(E))

    def rm(x):
        return float(np.sqrt(np.mean(np.square(x)))) if x else float("nan")
    return {"rpe_t_frame": rm(et), "rpe_r_frame": rm(er), "rpe_t_10m": rm(e10), "rpe_r_10m": rm(r10)}


def _step_len(df_seq):
    return np.nan_to_num(np.linalg.norm(df_seq[["gt_dx", "gt_dy", "gt_dz"]].to_numpy(float), axis=1))


def gt_path_length(df_seq):
    return float(_step_len(df_seq).sum())


def coverage(df_seq, method, state):
    v = df_seq[f"{method}_valid"].to_numpy().astype(int)
    seg = df_seq[f"{method}_segment_id"].to_numpy()
    t = df_seq["t"].to_numpy(np.int64)
    step = _step_len(df_seq)
    st = state.sort_values("ts_ns")
    ok = st["ok"].to_numpy().astype(int)
    n_fail = int(np.sum((ok[:-1] == 1) & (ok[1:] == 0)))
    segs = tracks.segments_from_state(st)["segment"]
    n_resets = max(0, int(segs[segs >= 0].nunique()) - 1)
    best_s = best_m = 0.0
    start = None
    for k in range(len(v)):
        cont = v[k] == 1 and (start is not None and seg[k] == seg[k - 1])
        if v[k] == 1 and not cont:
            start = k
        if v[k] != 1:
            start = None
            continue
        best_s = max(best_s, (t[k] - t[start - 1]) / 1e9 if start > 0 else 0.0)
        best_m = max(best_m, float(step[start:k + 1].sum()))
    return {"coverage": float(v.mean()) if len(v) else 0.0, "n_failures": n_fail, "n_resets": n_resets,
            "longest_s": best_s, "longest_m": best_m}


def evaluate_sequence(seq_dir, runs_dir, table, T_L_S, min_dur_s=30.0, min_len_m=20.0):
    gt_ts, gt_Ts = se3.load_tum(Path(seq_dir) / "gt.tum")
    total = gt_path_length(table)
    rows = []
    for m in schema.METHODS:
        run = Path(runs_dir) / m
        tr, _, meta = tracks.load_run(run)
        sm = segment_metrics(tr, T_L_S[m], gt_ts, gt_Ts, min_dur_s, min_len_m)
        el = sm[sm["eligible"]]
        rows.append({"seq": Path(seq_dir).name, "method": m, "uses_imu": meta.get("uses_imu", False),
                     "ate_rmse": aggregate_ate(sm),
                     "eligible_frac": min(1.0, float(el["len_m"].sum() / total)) if total > 0 else 0.0,
                     "n_segments": len(sm), "n_eligible": len(el),
                     **rpe(tr, T_L_S[m], gt_ts, gt_Ts),
                     **coverage(table, m, pd.read_csv(run / "state.csv"))})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="data/output/metrics.csv")
    a = ap.parse_args()
    cfg = config.load(a.config)
    res = evaluate_sequence(a.seq_dir, a.runs_dir, pd.read_parquet(a.table), cfg.T_L_S)
    out = Path(a.out)
    if out.exists():
        old = pd.read_csv(out)
        res = pd.concat([old[old["seq"] != res["seq"].iat[0]], res])
    res.to_csv(out, index=False)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
