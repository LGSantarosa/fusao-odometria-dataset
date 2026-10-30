"""Column roles: metadata | feature | target | evaluation."""
METHODS = {"orbslam3": "vo", "stella": "vo", "fastlio": "lo", "kissicp": "lo"}
VEC = ["dx", "dy", "dz", "qx", "qy", "qz", "qw"]
TW = ["vx", "vy", "vz", "wx", "wy", "wz"]
VO_IND = ["inliers", "n_features", "reproj_err", "tracked_ratio"]
LO_IND = ["fitness", "inlier_rmse", "unmatched_ratio", "n_points"]
VAR_OF = {"vo": "reproj_err", "lo": "fitness"}
# O Parquet é o formato canônico. O CSV deve ser lido com este dtype: sem ele, o pandas lê seq "00000" como 0.
CSV_DTYPE = {"seq": "string"}


def build_schema(methods):
    s = {c: "metadata" for c in ["t", "seq", "dataset", "gt_quality"]}
    # Representação decidida em 19/10/2026: o modelo consome a velocidade em se(3) (TW) com dt e age; o ΔT (VEC)
    # fica na tabela para auditoria (métodos) e avaliação (GT).
    s.update({f"gt_{c}": "evaluation" for c in VEC})
    s.update({f"gt_{c}": "target" for c in TW})
    for m, kind in methods.items():
        for c in ["src_ts", "segment_id", "uses_imu"] + VEC:
            s[f"{m}_{c}"] = "metadata"
        for c in TW + ["valid", "dt_ms", "age_ms"]:
            s[f"{m}_{c}"] = "feature"
        for c in (VO_IND if kind == "vo" else LO_IND):
            s[f"{m}_{c}"] = "feature"
        s[f"{m}_{VAR_OF[kind]}_var_H"] = "feature"
        for c in ["err_t", "err_r"]:
            s[f"{m}_{c}"] = "evaluation"
    return s


def blind_schema(methods):
    """Schema da tabela cega (G1): só metadados e features; alvo e colunas de avaliação não existem."""
    return {c: r for c, r in build_schema(methods).items() if r in ("metadata", "feature")}


def assert_no_leak(schema):
    bad = [c for c, r in schema.items() if r == "feature"
           and (c.startswith("gt_") or c.endswith("_err_t") or c.endswith("_err_r"))]
    if bad:
        raise ValueError(f"GT-derived columns marked as feature: {bad}")
