"""Pre-registered KISS-ICP deskew conditions (D0--D4') and pure helpers.

This module contains no dataset-specific execution or metric reporting.  Keeping
the transformations here makes it possible to validate their temporal and SE(3)
semantics on synthetic data before any real experimental run.
"""
from dataclasses import dataclass

import numpy as np
from scipy.spatial.transform import Rotation, Slerp


CONDITIONS = ("D0", "D1", "D2", "D3", "D4", "D4prime")
ROTATION_DIRECTIONS = ("clockwise", "counterclockwise")


@dataclass(frozen=True)
class PreparedScan:
    points: np.ndarray
    times: np.ndarray
    internal_deskew: bool
    externally_compensated: bool = False
    diagnostic: dict | None = None


def geometric_times(points, rotation_direction):
    """Reconstruct normalized acquisition time from azimuth and storage order.

    ``atan2(y, x)`` increases counterclockwise in a right-handed XY frame.  A
    clockwise sensor therefore advances as ``theta_start - theta``; a
    counterclockwise sensor advances as ``theta - theta_start``.
    """
    points = np.asarray(points, dtype=np.float64)
    if rotation_direction not in ROTATION_DIRECTIONS:
        raise ValueError(f"rotation_direction deve ser um de {ROTATION_DIRECTIONS}")
    if points.ndim != 2 or points.shape[1] != 3 or not len(points):
        raise ValueError("points deve ter forma (N, 3), N > 0")
    theta = np.arctan2(points[:, 1], points[:, 0])
    delta = theta[0] - theta if rotation_direction == "clockwise" else theta - theta[0]
    return np.mod(delta, 2.0 * np.pi) / (2.0 * np.pi)


def time_diagnostic(field_times, geometric, scan_span_s):
    """Agreement measures fixed by the protocol, expressed per scan."""
    a = np.asarray(field_times, dtype=np.float64).ravel()
    b = np.asarray(geometric, dtype=np.float64).ravel()
    if len(a) != len(b) or not len(a):
        raise ValueError("field_times e geometric devem ter o mesmo tamanho não nulo")
    corr = float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else np.nan
    return {
        "time_geo_corr": corr,
        "time_geo_abs_ms_median": float(np.median(np.abs(a - b)) * scan_span_s * 1e3),
    }


def point_times_ns(scan_row, normalized_times):
    """Absolute point times from header + t_min + normalized_time * span.

    This also covers sensors whose header is near scan end and whose original
    relative point times are negative (the BotanicGarden VLP-16 case).
    """
    t = np.asarray(normalized_times, dtype=np.float64).ravel()
    if np.any(~np.isfinite(t)) or np.any((t < -1e-7) | (t > 1.0 + 1e-7)):
        raise ValueError("tempo normalizado fora de [0, 1]")
    t_min_s = float(scan_row["t_min_s"])
    span_s = float(scan_row["span_s"])
    if not np.isfinite(t_min_s) or not np.isfinite(span_s) or span_s <= 0:
        raise ValueError("scan sem t_min_s/span_s válidos")
    return int(scan_row["ts_ns"]) + np.rint((t_min_s + t * span_s) * 1e9).astype(np.int64)


def _pose_at(ts_ns, poses, t_ns):
    ts_ns = np.asarray(ts_ns, dtype=np.int64)
    if len(ts_ns) == 0 or t_ns < ts_ns[0] or t_ns > ts_ns[-1]:
        return None
    j = int(np.searchsorted(ts_ns, t_ns, side="left"))
    if j < len(ts_ns) and ts_ns[j] == t_ns:
        return poses[j].copy()
    i = j - 1
    a = (t_ns - ts_ns[i]) / (ts_ns[j] - ts_ns[i])
    T = np.eye(4)
    T[:3, 3] = (1.0 - a) * poses[i, :3, 3] + a * poses[j, :3, 3]
    T[:3, :3] = Slerp([0.0, 1.0], Rotation.from_matrix(poses[[i, j], :3, :3]))([a]).as_matrix()[0]
    return T


def compensate_to_scan_end(points, point_ts_ns, end_ns, gt_ts_ns, gt_poses):
    """Transform raw points from their acquisition poses into the scan-end frame.

    GT poses follow the project convention ``T_W_L``.  A point acquired in
    ``L(t)`` is transformed as ``p_Lend = inv(T_W_Lend) @ T_W_L(t) @ p_Lt``.
    If GT does not bracket the complete scan, the protocol requires leaving the
    entire scan uncompensated.
    """
    points = np.asarray(points, dtype=np.float64)
    point_ts_ns = np.asarray(point_ts_ns, dtype=np.int64).ravel()
    gt_ts_ns = np.asarray(gt_ts_ns, dtype=np.int64)
    gt_poses = np.asarray(gt_poses, dtype=np.float64)
    if len(points) != len(point_ts_ns):
        raise ValueError("um timestamp é necessário para cada ponto")
    T_end = _pose_at(gt_ts_ns, gt_poses, int(end_ns))
    if T_end is None or not len(points) or point_ts_ns.min() < gt_ts_ns[0] or point_ts_ns.max() > gt_ts_ns[-1]:
        return points.copy(), False

    out = np.empty_like(points)
    # A scan normally crosses one or two GT intervals.  Grouping by interval
    # avoids constructing an (N, 4, 4) array and keeps D4 practical.
    right = np.searchsorted(gt_ts_ns, point_ts_ns, side="left")
    exact = (right < len(gt_ts_ns)) & (gt_ts_ns[np.minimum(right, len(gt_ts_ns) - 1)] == point_ts_ns)
    interval = np.where(exact, np.minimum(right, len(gt_ts_ns) - 1), right - 1)
    R_end_inv = T_end[:3, :3].T
    p_end = T_end[:3, 3]
    for idx in np.unique(interval):
        take = np.flatnonzero(interval == idx)
        exact_take = exact[take]
        if np.all(exact_take):
            R_t = np.repeat(gt_poses[idx, None, :3, :3], len(take), axis=0)
            p_t = np.repeat(gt_poses[idx, None, :3, 3], len(take), axis=0)
        else:
            j = idx + 1
            u = (point_ts_ns[take] - gt_ts_ns[idx]) / (gt_ts_ns[j] - gt_ts_ns[idx])
            R_t = Slerp([0.0, 1.0], Rotation.from_matrix(gt_poses[[idx, j], :3, :3]))(u).as_matrix()
            p_t = (1.0 - u[:, None]) * gt_poses[idx, :3, 3] + u[:, None] * gt_poses[j, :3, 3]
        world = np.einsum("nij,nj->ni", R_t, points[take]) + p_t
        out[take] = (world - p_end) @ R_end_inv.T
    return out, True


def prepare_scan(points, archive, scan_row, condition, rotation_direction=None, gt=None):
    """Prepare one scan according to pre-registered condition D0--D4'."""
    if condition not in CONDITIONS:
        raise ValueError(f"condition deve ser um de {CONDITIONS}")
    points = np.asarray(points, dtype=np.float64)
    zeros = np.zeros(len(points), dtype=np.float64)
    if condition == "D0":
        return PreparedScan(points, zeros, False)

    field = np.asarray(archive["t_norm"], dtype=np.float64) if "t_norm" in archive else None
    if condition in ("D1", "D2", "D4") and field is None:
        raise RuntimeError(f"{condition} exige t_norm validado")

    geo = None
    diag = None
    if condition in ("D3", "D4prime"):
        geo = geometric_times(points, rotation_direction)
        if field is not None:
            diag = time_diagnostic(field, geo, float(scan_row["span_s"]))

    if condition == "D1":
        return PreparedScan(points, field, True)
    if condition == "D2":
        return PreparedScan(points, 1.0 - field, True)
    if condition == "D3":
        return PreparedScan(points, geo, True, diagnostic=diag)

    use_times = field if condition == "D4" else geo
    if gt is None:
        raise RuntimeError(f"{condition} exige GT")
    p_ns = point_times_ns(scan_row, use_times)
    corrected, ok = compensate_to_scan_end(points, p_ns, int(scan_row["end_ns"]), gt[0], gt[1])
    return PreparedScan(corrected, zeros, False, externally_compensated=ok, diagnostic=diag)
