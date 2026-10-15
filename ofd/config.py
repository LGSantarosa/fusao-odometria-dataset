from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml


@dataclass
class DatasetConfig:
    name: str
    gt_quality: str
    topics: dict
    point_time: dict
    T_L_S: dict
    max_age_ms: float = 100.0
    var_window: int = 10
    image_encoding: str = "mono8"
    stereo: dict | None = None
    kissicp_deskew: object = "auto"  # auto | false: desligar quando a evidência mostrar que piora (ver docs)   # K0, D0, K1, D1, T_c0_c1 (4x4 row-major), size [w, h] → retificação na extração
    lidar_rotation_direction: str | None = None


def load(path) -> DatasetConfig:
    d = yaml.safe_load(Path(path).read_text())
    T = {m: np.asarray(v, float).reshape(4, 4) for m, v in d["T_L_S"].items()}
    for m, M in T.items():
        Rm = M[:3, :3]
        if (not np.isfinite(M).all() or not np.allclose(M[3], [0, 0, 0, 1])
                or not np.allclose(Rm @ Rm.T, np.eye(3), atol=1e-4) or not abs(np.linalg.det(Rm) - 1.0) < 1e-4):
            raise ValueError(f"T_L_S[{m}] não é SE3 válida")
    rotation = d.get("lidar_rotation_direction")
    if rotation not in (None, "clockwise", "counterclockwise"):
        raise ValueError("lidar_rotation_direction deve ser clockwise ou counterclockwise")
    return DatasetConfig(d["name"], d["gt_quality"], d["topics"], d["point_time"], T,
                         d.get("max_age_ms", 100.0), d.get("var_window", 10), d.get("image_encoding", "mono8"),
                         d.get("stereo"), d.get("kissicp_deskew", "auto"), rotation)
