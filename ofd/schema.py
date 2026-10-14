"""Column roles: metadata | feature | target | evaluation."""
METHODS = {"orbslam3": "vo", "stella": "vo", "fastlio": "lo", "kissicp": "lo"}
VEC = ["dx", "dy", "dz", "qx", "qy", "qz", "qw"]
TW = ["vx", "vy", "vz", "wx", "wy", "wz"]
VO_IND = ["inliers", "n_features", "reproj_err", "tracked_ratio"]
LO_IND = ["fitness", "inlier_rmse", "unmatched_ratio", "n_points"]
VAR_OF = {"vo": "reproj_err", "lo": "fitness"}


def build_schema(methods):
    s = {c: "metadata" for c in ["t", "seq", "dataset", "gt_quality"]}
    s.update({f"gt_{c}": "target" for c in VEC + TW})
    for m, kind in methods.items():
        for c in ["src_ts", "segment_id", "uses_imu"]:
            s[f"{m}_{c}"] = "metadata"
        for c in VEC + TW + ["valid", "dt_ms", "age_ms"]:
            s[f"{m}_{c}"] = "feature"
        for c in (VO_IND if kind == "vo" else LO_IND):
            s[f"{m}_{c}"] = "feature"
        s[f"{m}_{VAR_OF[kind]}_var_H"] = "feature"
        for c in ["err_t", "err_r"]:
            s[f"{m}_{c}"] = "evaluation"
    return s


def assert_no_leak(schema):
    bad = [c for c, r in schema.items() if r == "feature"
           and (c.startswith("gt_") or c.endswith("_err_t") or c.endswith("_err_r"))]
    if bad:
        raise ValueError(f"GT-derived columns marked as feature: {bad}")
