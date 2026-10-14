"""LiDAR quality indicators computed uniformly from each method's ΔT, plus causal rolling stats."""
import numpy as np
import open3d as o3d
import pandas as pd


def _pcd(xyz, voxel):
    p = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.asarray(xyz, dtype=np.float64)))
    return p.voxel_down_sample(voxel) if voxel > 0 else p


def registration_quality(src_xyz, tgt_xyz, dT, voxel=0.25, max_corr=0.5, unmatched_dist=1.0):
    src, tgt = _pcd(src_xyz, voxel), _pcd(tgt_xyz, voxel)
    ev = o3d.pipelines.registration.evaluate_registration(src, tgt, max_corr, dT)
    src_t = o3d.geometry.PointCloud(src).transform(dT)
    d = np.asarray(src_t.compute_point_cloud_distance(tgt))
    return {
        "fitness": float(ev.fitness),
        "inlier_rmse": float(ev.inlier_rmse),
        "unmatched_ratio": float(np.mean(d > unmatched_dist)) if d.size else np.nan,
        "n_points": int(len(src.points)),
    }


def causal_rolling_var(s: pd.Series, H: int = 10) -> pd.Series:
    return s.rolling(window=H, min_periods=2).var()
