import numpy as np
import yaml
from scipy.spatial.transform import Rotation as R
from ofd import config, se3
from tools import make_configs as mc

FASTLIO_TEMPLATE = """/**:
    ros__parameters:
        common:
            lid_topic:  "/x"
            imu_topic:  "/y"
        preprocess:
            lidar_type: 1
            scan_line: 6
            timestamp_unit: 2
            blind: 2.0
        mapping:
            extrinsic_est_en:  false
            extrinsic_T: [ 0.0, 0.0, 0.0 ]
            extrinsic_R: [1., 0., 0.,
                        0., 1., 0.,
                        0., 0., 1.]
        pcd_save:
            pcd_save_en: true
"""


def calib():
    T_L_cam0 = se3.to_mat([0.1, -0.2, 0.3], R.from_euler("xyz", [-90, 0, -90], degrees=True).as_quat())
    T_c0_c1 = se3.to_mat([0.25, 0.001, -0.001], R.from_euler("xyz", [0.2, -0.3, 0.1], degrees=True).as_quat())
    T_imu_L = se3.to_mat([0.05, 0.01, 0.17], R.from_euler("z", 1.5, degrees=True).as_quat())
    K = [[640.0, 0, 470.0], [0, 640.0, 300.0], [0, 0, 1]]
    return dict(name="toy", gt_quality="survey", size=[960, 600], fps=10,
                K0=K, D0=[-0.06, 0.1, 0, 0, 0], K1=K, D1=[-0.06, 0.1, 0, 0, 0],
                T_L_cam0=T_L_cam0, T_c0_c1=T_c0_c1, T_imu_L=T_imu_L,
                topics={"left": "/l", "right": "/r", "lidar": "/p", "imu": "/i", "gt": "/g"},
                point_time={"field": "time", "unit": "s", "ref": "scan_start"},
                fastlio={"lidar_type": 2, "scan_line": 16, "timestamp_unit": 0, "blind": 2.0})


def test_build_files_consistent(tmp_path):
    files = mc.build(calib(), FASTLIO_TEMPLATE)
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    cfg = config.load(tmp_path / "dataset.yaml")
    c = calib()
    from ofd.rectify import StereoRectifier
    rect = StereoRectifier(c["K0"], c["D0"], c["K1"], c["D1"], c["T_c0_c1"], c["size"])
    # VO no frame da câmera esquerda retificada
    np.testing.assert_allclose(cfg.T_L_S["orbslam3"], c["T_L_cam0"] @ rect.T_cam0_rect, atol=1e-9)
    np.testing.assert_allclose(cfg.T_L_S["stella"], cfg.T_L_S["orbslam3"], atol=1e-12)
    np.testing.assert_allclose(cfg.T_L_S["fastlio"], se3.inv(c["T_imu_L"]), atol=1e-9)   # IMU -> LiDAR
    np.testing.assert_allclose(cfg.T_L_S["kissicp"], np.eye(4))
    assert cfg.stereo is not None
    orb = files["orbslam3.yaml"]
    assert 'Camera.type: "Rectified"' in orb and "loopClosing: 0" in orb
    assert f"Stereo.b: {rect.baseline:.9f}" in orb
    st = yaml.safe_load(files["stella.yaml"])
    assert abs(st["Camera"]["focal_x_baseline"] - rect.fx * rect.baseline) < 1e-6
    assert st["LoopDetector"]["enabled"] is False and st["Camera"]["k1"] == 0.0


def test_fastlio_yaml_sets_topics_extrinsic_and_disables_pcd():
    c = calib()
    txt = mc.fastlio_yaml(FASTLIO_TEMPLATE, c)
    y = yaml.safe_load(txt)["/**"]["ros__parameters"]
    assert y["common"]["lid_topic"] == "/p" and y["common"]["imu_topic"] == "/i"
    assert y["preprocess"]["lidar_type"] == 2 and y["preprocess"]["scan_line"] == 16 and y["preprocess"]["timestamp_unit"] == 0
    np.testing.assert_allclose(y["mapping"]["extrinsic_T"], c["T_imu_L"][:3, 3])
    np.testing.assert_allclose(np.reshape(y["mapping"]["extrinsic_R"], (3, 3)), c["T_imu_L"][:3, :3], atol=1e-12)
    assert y["pcd_save"]["pcd_save_en"] is False
