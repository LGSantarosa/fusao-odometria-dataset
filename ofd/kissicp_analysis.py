"""Metrics pre-registered in docs/protocol_kissicp.md.

The functions operate on explicit tracks/clouds and do not discover or run real
experiments on import.  This permits synthetic validation before unblinding the
prospective KISS-ICP conditions.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import se3, tracks
from ofd.evaluate import umeyama_se3


def trajectory_hash(run_dir):
    return hashlib.sha256((Path(run_dir) / "poses_causal.tum").read_bytes()).hexdigest()


def compare_repetitions(run_dirs):
    """Hash and maximum pose-wise SE(3) difference relative to repetition 1."""
    run_dirs = [Path(p) for p in run_dirs]
    if len(run_dirs) < 2:
        raise ValueError("ao menos duas repetições são necessárias")
    ref, _, _ = tracks.load_run(run_dirs[0])
    rows = []
    for k, path in enumerate(run_dirs):
        tr, _, _ = tracks.load_run(path)
        if not np.array_equal(ref.ts_ns, tr.ts_ns):
            raise ValueError(f"timestamps diferentes entre repetições: {path}")
        d = np.stack([se3.delta(a, b) for a, b in zip(ref.Ts, tr.Ts)])
        trans = np.linalg.norm(d[:, :3, 3], axis=1) if len(d) else np.zeros(0)
        rot = np.array([np.degrees(se3.rot_angle(T)) for T in d])
        rows.append({"repetition": k + 1, "path": str(path), "sha256": trajectory_hash(path),
                     "max_delta_t_m": float(trans.max()) if len(trans) else 0.0,
                     "max_delta_r_deg": float(rot.max()) if len(rot) else 0.0})
    return pd.DataFrame(rows)


def repeatability_decision(table, trans_limit_m=0.001, rot_limit_deg=0.01):
    if table["sha256"].nunique() == 1:
        return "deterministic"
    if table["max_delta_t_m"].max() < trans_limit_m and table["max_delta_r_deg"].max() < rot_limit_deg:
        return "numerically_equivalent"
    return "escalate_to_10"


def operational_metrics(run_dir):
    state = pd.read_csv(Path(run_dir) / "state.csv").sort_values("ts_ns")
    ok = state["ok"].to_numpy(dtype=np.int64)
    return {"coverage": float(ok.mean()) if len(ok) else 0.0,
            "n_failures": int(np.sum((ok[:-1] == 1) & (ok[1:] == 0))) if len(ok) > 1 else 0}


def _gt_on_timestamps(gt_ts, gt_Ts, timestamps):
    poses = [se3.interp(gt_ts, gt_Ts, int(t)) for t in timestamps]
    keep = np.array([T is not None for T in poses])
    return keep, np.stack([T for T in poses if T is not None]) if keep.any() else np.zeros((0, 4, 4))


def common_support(run_dirs, gt_ts, gt_Ts):
    """Tracks restricted to the exact timestamp intersection required by the protocol."""
    loaded = {name: tracks.load_run(path)[0] for name, path in run_dirs.items()}
    common = None
    for tr in loaded.values():
        s = set(map(int, tr.ts_ns))
        common = s if common is None else common & s
    ts = np.array(sorted(common or ()), dtype=np.int64)
    if not len(ts):
        raise ValueError("as condições não possuem timestamps em comum")
    keep, gt = _gt_on_timestamps(gt_ts, gt_Ts, ts)
    ts = ts[keep]
    out = {}
    for name, tr in loaded.items():
        pos = {int(t): i for i, t in enumerate(tr.ts_ns)}
        out[name] = tracks.Track(ts, np.stack([tr.Ts[pos[int(t)]] for t in ts]),
                                 np.zeros(len(ts), dtype=np.int64))
    return ts, gt, out


def distance_pairs(gt_Ts, distance_m):
    """Same start/end indices for every condition, following GT path length."""
    if len(gt_Ts) < 2:
        return np.zeros((0, 2), dtype=np.int64)
    step = np.linalg.norm(np.diff(gt_Ts[:, :3, 3], axis=0), axis=1)
    cum = np.r_[0.0, np.cumsum(step)]
    pairs = []
    for i in range(len(cum)):
        j = int(np.searchsorted(cum, cum[i] + distance_m))
        if j >= len(cum):
            break
        pairs.append((i, j))
    return np.asarray(pairs, dtype=np.int64).reshape(-1, 2)


def relative_error_series(ts_ns, gt_Ts, condition_tracks, distance_m):
    """Paired relative errors at a fixed GT distance for all conditions."""
    pairs = distance_pairs(gt_Ts, distance_m)
    rows = []
    for i, j in pairs:
        d_gt = se3.delta(gt_Ts[i], gt_Ts[j])
        gt_distance = float(np.sum(np.linalg.norm(np.diff(gt_Ts[i:j + 1, :3, 3], axis=0), axis=1)))
        base = {"start_ts_ns": int(ts_ns[i]), "end_ts_ns": int(ts_ns[j]),
                "start_index": int(i), "end_index": int(j), "distance_m": float(distance_m),
                "gt_path_distance_m": gt_distance}
        for name, tr in condition_tracks.items():
            err = se3.delta(d_gt, se3.delta(tr.Ts[i], tr.Ts[j]))
            rows.append({**base, "condition": name, "error_t_m": float(np.linalg.norm(err[:3, 3])),
                         "error_r_deg": float(np.degrees(se3.rot_angle(err)))})
    return pd.DataFrame(rows, columns=["start_ts_ns", "end_ts_ns", "start_index", "end_index",
                                       "distance_m", "gt_path_distance_m", "condition",
                                       "error_t_m", "error_r_deg"])


def frame_error_series(ts_ns, gt_Ts, condition_tracks):
    """Paired frame-to-frame RPE for the common support."""
    rows = []
    for k in range(1, len(ts_ns)):
        d_gt = se3.delta(gt_Ts[k - 1], gt_Ts[k])
        for name, tr in condition_tracks.items():
            err = se3.delta(d_gt, se3.delta(tr.Ts[k - 1], tr.Ts[k]))
            rows.append({"start_ts_ns": int(ts_ns[k - 1]), "end_ts_ns": int(ts_ns[k]),
                         "condition": name, "error_t_m": float(np.linalg.norm(err[:3, 3])),
                         "error_r_deg": float(np.degrees(se3.rot_angle(err)))})
    return pd.DataFrame(rows, columns=["start_ts_ns", "end_ts_ns", "condition",
                                       "error_t_m", "error_r_deg"])


def _rmse(values):
    values = np.asarray(values, dtype=np.float64)
    return float(np.sqrt(np.mean(values ** 2))) if len(values) else np.nan


def aligned_error_series(ts_ns, gt_Ts, condition_tracks):
    """Position and orientation error after one rigid alignment per condition."""
    rows = []
    G = gt_Ts[:, :3, 3]
    for name, tr in condition_tracks.items():
        A = umeyama_se3(tr.Ts[:, :3, 3], G)
        aligned = np.einsum("ij,njk->nik", A, tr.Ts)
        for t, est, gt in zip(ts_ns, aligned, gt_Ts):
            rows.append({"ts_ns": int(t), "condition": name,
                         "aligned_error_t_m": float(np.linalg.norm(est[:3, 3] - gt[:3, 3])),
                         "aligned_error_r_deg": float(np.degrees(se3.rot_angle(se3.delta(gt, est))))})
    return pd.DataFrame(rows)


def first_distance_indices(gt_Ts, distance_m=100.0):
    if not len(gt_Ts):
        return np.zeros(0, dtype=np.int64)
    cum = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(gt_Ts[:, :3, 3], axis=0), axis=1))]
    end = min(len(cum), int(np.searchsorted(cum, distance_m, side="left")) + 1)
    return np.arange(end, dtype=np.int64)


def metric_summary(ts_ns, gt_Ts, condition_tracks):
    """Primary/secondary metrics on identical GT support, including first 100 m."""
    rpe_frame = frame_error_series(ts_ns, gt_Ts, condition_tracks)
    rpe_10 = relative_error_series(ts_ns, gt_Ts, condition_tracks, 10.0)
    rpe_100 = relative_error_series(ts_ns, gt_Ts, condition_tracks, 100.0)
    aligned = aligned_error_series(ts_ns, gt_Ts, condition_tracks)
    prefix_idx = first_distance_indices(gt_Ts, 100.0)
    rows = []
    for name in condition_tracks:
        tr = condition_tracks[name]
        f = rpe_frame[rpe_frame.condition == name]
        r10 = rpe_10[rpe_10.condition == name]
        r100 = rpe_100[rpe_100.condition == name]
        a = aligned[aligned.condition == name]
        est100, gt100 = tr.Ts[prefix_idx], gt_Ts[prefix_idx]
        A100 = umeyama_se3(est100[:, :3, 3], gt100[:, :3, 3])
        aligned100 = np.einsum("ij,njk->nik", A100, est100)
        ate100 = _rmse(np.linalg.norm(aligned100[:, :3, 3] - gt100[:, :3, 3], axis=1))
        rows.append({"condition": name, "n_common_poses": len(ts_ns),
                     "rpe_t_frame": _rmse(f.error_t_m), "rpe_r_frame_deg": _rmse(f.error_r_deg),
                     "rpe_t_10m": _rmse(r10.error_t_m), "rpe_r_10m_deg": _rmse(r10.error_r_deg),
                     "error_t_100m_pct": _rmse(100.0 * r100.error_t_m / r100.gt_path_distance_m),
                     "error_r_100m_deg": _rmse(r100.error_r_deg),
                     "ate_rmse": _rmse(a.aligned_error_t_m),
                     "first_100m_ate_rmse": ate100,
                     "final_aligned_rotation_error_deg": (float(a.aligned_error_r_deg.iloc[-1])
                                                           if len(a) else np.nan)})
    return pd.DataFrame(rows), {"rpe_frame": rpe_frame, "rpe_10m": rpe_10,
                                "rpe_100m": rpe_100, "aligned": aligned}


def stratify_frame_errors(frame_errors, motion, quantiles=4):
    """Attach pre-registered movement quantiles without treating them as causal tests."""
    joined = frame_errors.merge(motion, left_on="end_ts_ns", right_on="ts_ns", validate="many_to_one")
    for col in ("v_dt_m", "omega_dt_rad", "abs_delta_omega_rad_s"):
        valid = joined[col].notna()
        joined.loc[valid, f"{col}_quantile"] = pd.qcut(joined.loc[valid, col], quantiles,
                                                       labels=False, duplicates="drop")
    return joined


def promotion_checks(metrics, sequences=("1018-00", "1018-13"), min_improvement=0.05,
                     max_ate_degradation=0.05):
    """Apply section 8 exactly; D4/D4prime are never candidates.

    ``metrics`` must contain sequence, condition, RPE/ATE, coverage and
    n_failures.  The output keeps every individual gate visible for reporting.
    """
    required = {"sequence", "condition", "rpe_t_10m", "rpe_r_10m_deg", "ate_rmse",
                "coverage", "n_failures"}
    missing = required - set(metrics.columns)
    if missing:
        raise ValueError(f"colunas ausentes: {sorted(missing)}")
    base = metrics[metrics.condition == "D0"].set_index("sequence")
    rows = []
    for condition in ("D1", "D2", "D3"):
        cand = metrics[metrics.condition == condition].set_index("sequence")
        for seq in sequences:
            if seq not in base.index or seq not in cand.index:
                rows.append({"condition": condition, "sequence": seq, "complete": False, "promote": False})
                continue
            b, c = base.loc[seq], cand.loc[seq]
            gates = {"rpe_t_improves_5pct": c.rpe_t_10m <= (1 - min_improvement) * b.rpe_t_10m,
                     "rpe_r_improves_5pct": c.rpe_r_10m_deg <= (1 - min_improvement) * b.rpe_r_10m_deg,
                     "ate_within_5pct": c.ate_rmse <= (1 + max_ate_degradation) * b.ate_rmse,
                     "coverage_not_lower": c.coverage >= b.coverage,
                     "failures_not_higher": c.n_failures <= b.n_failures}
            rows.append({"condition": condition, "sequence": seq, "complete": True, **gates,
                         "promote": bool(all(gates.values()))})
    out = pd.DataFrame(rows)
    if len(out):
        eligible = {name: bool(len(g) == len(sequences) and g["complete"].all() and g["promote"].all())
                    for name, g in out.groupby("condition")}
        out["promote_across_botanic"] = out.condition.map(eligible)
    return out


def motion_series(ts_ns, gt_Ts):
    """Per-scan v*dt, omega*dt and |delta omega| from GT."""
    rows, previous_omega = [], None
    for k in range(1, len(ts_ns)):
        dt = (int(ts_ns[k]) - int(ts_ns[k - 1])) / 1e9
        d = se3.delta(gt_Ts[k - 1], gt_Ts[k])
        omega = se3.rot_angle(d) / dt if dt > 0 else np.nan
        rows.append({"ts_ns": int(ts_ns[k]), "dt_s": dt,
                     "v_dt_m": float(np.linalg.norm(d[:3, 3])),
                     "omega_dt_rad": float(se3.rot_angle(d)),
                     "abs_delta_omega_rad_s": (float(abs(omega - previous_omega))
                                                if previous_omega is not None else np.nan)})
        previous_omega = omega
    return pd.DataFrame(rows)


def structure_metrics(points, voxel_m=1.0, max_range_m=100.0):
    """Sensor-only H3 fallback: occupancy and global PCA shape ratios."""
    points = np.asarray(points, dtype=np.float64)
    finite = np.isfinite(points).all(axis=1)
    points = points[finite & (np.linalg.norm(points, axis=1) <= max_range_m)]
    if not len(points):
        return {"n_points_structure": 0, "n_voxels_1m": 0, "pca_linearity": np.nan,
                "pca_planarity": np.nan, "pca_scattering": np.nan}
    voxels = np.unique(np.floor(points / voxel_m).astype(np.int64), axis=0)
    cov = np.cov(points, rowvar=False) if len(points) > 1 else np.zeros((3, 3))
    eig = np.sort(np.linalg.eigvalsh(cov))[::-1]
    if eig[0] <= 0:
        linearity = planarity = scattering = np.nan
    else:
        linearity = (eig[0] - eig[1]) / eig[0]
        planarity = (eig[1] - eig[2]) / eig[0]
        scattering = eig[2] / eig[0]
    return {"n_points_structure": int(len(points)), "n_voxels_1m": int(len(voxels)),
            "pca_linearity": float(linearity), "pca_planarity": float(planarity),
            "pca_scattering": float(scattering)}


def structure_series(seq_dir, d0_run_dir):
    """H3 fallback series merged with the already uniform registration indicators."""
    seq_dir = Path(seq_dir)
    stamps = pd.read_csv(seq_dir / "lidar_stamps.csv")
    rows = []
    for row in stamps.itertuples(index=False):
        points = np.load(seq_dir / "clouds" / f"{int(row.ts_ns)}.npz")["xyz"]
        rows.append({"ts_ns": int(row.end_ns), **structure_metrics(points)})
    base = pd.DataFrame(rows)
    indicators = pd.read_csv(Path(d0_run_dir) / "indicators.csv")
    return base.merge(indicators, on="ts_ns", how="left", validate="one_to_one")


def _named_paths(values):
    out = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"esperado CONDIÇÃO=CAMINHO, recebido: {value}")
        name, path = value.split("=", 1)
        if name in out:
            raise ValueError(f"condição repetida: {name}")
        out[name] = Path(path)
    return out


def main():
    ap = argparse.ArgumentParser(description="Análise pré-registrada do KISS-ICP, sem executar o estimador")
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--run", action="append", required=True, metavar="D0=DIR",
                    help="run oficial por condição; repetir a opção")
    ap.add_argument("--repetitions", action="append", default=[], metavar="D0=DIR1,DIR2,DIR3",
                    help="runs para auditoria H4; repetir por condição")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    seq_dir, out = Path(a.seq_dir), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    runs = _named_paths(a.run)
    decisions = {}
    for value in a.repetitions:
        condition, paths = value.split("=", 1)
        table = compare_repetitions(paths.split(","))
        table.to_csv(out / f"repeatability_{condition}.csv", index=False)
        decisions[condition] = repeatability_decision(table)
    if decisions:
        (out / "repeatability_decisions.json").write_text(json.dumps(decisions, indent=2))
    if "D0" in runs:
        structure_series(seq_dir, runs["D0"]).to_csv(out / "structure_d0.csv", index=False)
    gt_ts, gt_Ts = se3.load_tum(seq_dir / "gt.tum")
    if not len(gt_ts):
        return
    ts, gt, common = common_support(runs, gt_ts, gt_Ts)
    summary, series = metric_summary(ts, gt, common)
    summary.insert(0, "sequence", seq_dir.name)
    for condition, path in runs.items():
        op = operational_metrics(path)
        for key, value in op.items():
            summary.loc[summary.condition == condition, key] = value
    summary.to_csv(out / "summary.csv", index=False)
    for name, table in series.items():
        table.to_csv(out / f"{name}.csv", index=False)
    motion = motion_series(ts, gt)
    motion.to_csv(out / "motion.csv", index=False)
    stratify_frame_errors(series["rpe_frame"], motion).to_csv(out / "rpe_frame_stratified.csv", index=False)


if __name__ == "__main__":
    main()
