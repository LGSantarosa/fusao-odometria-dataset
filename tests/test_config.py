import numpy as np
import yaml
from ofd import config


def test_load(tmp_path):
    d = {"name": "x", "gt_quality": "survey", "max_age_ms": 100, "var_window": 10,
         "image_encoding": "mono8",
         "topics": {"left": "/l", "right": "/r", "lidar": "/p", "imu": "/i", "gt": "/g"},
         "point_time": {"field": "time", "unit": "s", "ref": "scan_start"},
         "T_L_S": {m: np.eye(4).ravel().tolist() for m in ["orbslam3", "stella", "fastlio", "kissicp"]}}
    p = tmp_path / "c.yaml"; p.write_text(yaml.safe_dump(d))
    c = config.load(p)
    assert c.T_L_S["fastlio"].shape == (4, 4) and c.point_time["unit"] == "s"
    assert c.lidar_rotation_direction is None


def test_rejects_non_se3(tmp_path):
    import pytest
    bad = np.eye(4).ravel().tolist(); bad[0] = 2.0
    d = {"name": "x", "gt_quality": "survey", "topics": {}, "point_time": {},
         "T_L_S": {"kissicp": bad}}
    p = tmp_path / "c.yaml"; p.write_text(yaml.safe_dump(d))
    with pytest.raises(ValueError):
        config.load(p)


def _write(tmp_path, M):
    d = {"name": "x", "gt_quality": "survey", "topics": {}, "point_time": {},
         "T_L_S": {"kissicp": np.asarray(M, float).ravel().tolist()}}
    p = tmp_path / "c.yaml"; p.write_text(yaml.safe_dump(d))
    return p


def test_rejects_reflection(tmp_path):
    import pytest
    M = np.eye(4); M[2, 2] = -1.0  # ortogonal, mas det(R) = -1
    with pytest.raises(ValueError):
        config.load(_write(tmp_path, M))


def test_rejects_nan(tmp_path):
    import pytest
    M = np.eye(4); M[0, 3] = np.nan
    with pytest.raises(ValueError):
        config.load(_write(tmp_path, M))
