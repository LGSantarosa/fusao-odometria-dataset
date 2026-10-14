"""Generate configs/<dataset>/{dataset,orbslam3,stella,fastlio}.yaml from the dataset's own calibration.

Nothing is hand-copied: extrinsics are composed here, and the VO intrinsics come from the same stereo
rectification that `ofd.extract` applies (so VO settings and extracted images always agree).

    python -m tools.make_configs botanic --calib data/raw/botanic/calib_params
    python -m tools.make_configs rellis  --bag data/raw/rellis/example/example_filtered.bag
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
import yaml

from ofd import se3
from ofd.rectify import StereoRectifier

FASTLIO_DIR = Path("/home/rbe-luis/Workspace/Controle_robo_livox/ros2_packages/FAST_LIO/config")
EYE = np.eye(4).ravel().tolist()


def _flat(T):
    return [float(x) for x in np.asarray(T, float).ravel()]


def _rectifier(c):
    return StereoRectifier(c["K0"], c["D0"], c["K1"], c["D1"], c["T_c0_c1"], c["size"])


def orbslam3_yaml(rect, fps):
    p = rect.params()
    return f"""%YAML:1.0
# Gerado por tools/make_configs.py — imagens já retificadas pelo ofd.extract
File.version: "1.0"
Camera.type: "Rectified"
Camera1.fx: {p['fx']:.9f}
Camera1.fy: {p['fy']:.9f}
Camera1.cx: {p['cx']:.9f}
Camera1.cy: {p['cy']:.9f}
Stereo.b: {p['baseline']:.9f}
Camera.width: {p['width']}
Camera.height: {p['height']}
Camera.fps: {fps}
Camera.RGB: 0
Stereo.ThDepth: 40.0
loopClosing: 0
ORBextractor.nFeatures: 1500
ORBextractor.scaleFactor: 1.2
ORBextractor.nLevels: 8
ORBextractor.iniThFAST: 20
ORBextractor.minThFAST: 7
Viewer.KeyFrameSize: 0.05
Viewer.KeyFrameLineWidth: 1.0
Viewer.GraphLineWidth: 0.9
Viewer.PointSize: 2.0
Viewer.CameraSize: 0.08
Viewer.CameraLineWidth: 3.0
Viewer.ViewpointX: 0.0
Viewer.ViewpointY: -0.7
Viewer.ViewpointZ: -1.8
Viewer.ViewpointF: 500.0
"""


def stella_yaml(rect, fps, name):
    p = rect.params()
    d = {
        "Camera": {"name": name, "setup": "stereo", "model": "perspective",
                   "fx": p["fx"], "fy": p["fy"], "cx": p["cx"], "cy": p["cy"],
                   "k1": 0.0, "k2": 0.0, "p1": 0.0, "p2": 0.0, "k3": 0.0,
                   "focal_x_baseline": p["fx"] * p["baseline"], "fps": float(fps),
                   "cols": p["width"], "rows": p["height"], "color_order": "Gray"},
        "Preprocessing": {"min_size": 800},
        "Feature": {"name": "default ORB", "scale_factor": 1.2, "num_levels": 8,
                    "ini_fast_threshold": 20, "min_fast_threshold": 7},
        "Tracking": {"max_num_keypoints": 1500},
        "Mapping": {"baseline_dist_thr_ratio": 0.02, "redundant_obs_ratio_thr": 0.9},
        "LoopDetector": {"enabled": False},
    }
    return "# Gerado por tools/make_configs.py — imagens já retificadas pelo ofd.extract\n" + yaml.safe_dump(d, sort_keys=False)


def fastlio_yaml(template_text, c):
    d = yaml.safe_load(template_text)
    p = d["/**"]["ros__parameters"]
    p["common"]["lid_topic"] = c["topics"]["lidar"]
    p["common"]["imu_topic"] = c["topics"]["imu"]
    p["preprocess"].update({k: c["fastlio"][k] for k in ("lidar_type", "scan_line", "timestamp_unit", "blind")})
    if "scan_rate" in c["fastlio"]:
        p["preprocess"]["scan_rate"] = c["fastlio"]["scan_rate"]
    T = np.asarray(c["T_imu_L"], float)           # LiDAR no frame da IMU (convenção do FAST-LIO)
    p["mapping"]["extrinsic_est_en"] = False
    p["mapping"]["extrinsic_T"] = _flat(T[:3, 3])
    p["mapping"]["extrinsic_R"] = _flat(T[:3, :3])
    p.setdefault("pcd_save", {})["pcd_save_en"] = False
    p.setdefault("publish", {})["path_en"] = False
    return "# Gerado por tools/make_configs.py\n" + yaml.safe_dump(d, sort_keys=False)


def build(c, fastlio_template):
    rect = _rectifier(c)
    T_L_vo = np.asarray(c["T_L_cam0"], float) @ rect.T_cam0_rect   # VO = câmera esquerda retificada
    ds = {
        "name": c["name"], "gt_quality": c["gt_quality"], "max_age_ms": c.get("max_age_ms", 100), "var_window": 10,
        "image_encoding": "mono8", "topics": c["topics"], "point_time": c["point_time"],
        "kissicp_deskew": c.get("kissicp_deskew", "auto"),
        "T_L_S": {"orbslam3": _flat(T_L_vo), "stella": _flat(T_L_vo),
                  "fastlio": _flat(se3.inv(np.asarray(c["T_imu_L"], float))), "kissicp": EYE},
        "stereo": {"K0": np.asarray(c["K0"], float).tolist(), "D0": _flat(c["D0"]),
                   "K1": np.asarray(c["K1"], float).tolist(), "D1": _flat(c["D1"]),
                   "T_c0_c1": _flat(c["T_c0_c1"]), "size": list(c["size"])},
    }
    return {
        "dataset.yaml": "# Gerado por tools/make_configs.py\n" + yaml.safe_dump(ds, sort_keys=False),
        "orbslam3.yaml": orbslam3_yaml(rect, c["fps"]),
        "stella.yaml": stella_yaml(rect, c["fps"], c["name"]),
        "fastlio.yaml": fastlio_yaml(fastlio_template, c),
    }


# ---------------------------------------------------------------- dataset-specific calibration readers

def _cv_mat(fs, key):
    return np.asarray(fs.getNode(key).mat(), float)


def botanic_calib(calib_dir):
    calib_dir = Path(calib_dir)
    fs = cv2.FileStorage(str(calib_dir / "extrinsics/calib_chain.yaml"), cv2.FILE_STORAGE_READ)
    T_x_vlp, T_x_g0, T_g0_g1 = _cv_mat(fs, "T_xsens_vlp16"), _cv_mat(fs, "T_xsens_gray0"), _cv_mat(fs, "T_gray0_gray1")

    def intr(name):
        y = yaml.safe_load((calib_dir / f"camera_intrinsics/{name}.yaml").read_text().replace("%YAML:1.0", ""))
        pp, dd = y["projection_parameters"], y["distortion_parameters"]
        K = [[pp["fx"], 0, pp["cx"]], [0, pp["fy"], pp["cy"]], [0, 0, 1]]
        return K, [dd["k1"], dd["k2"], dd["p1"], dd["p2"], 0.0], [y["image_width"], y["image_height"]]

    K0, D0, size = intr("dalsa_gray0_down")   # bags trazem 960x600 (downsampled)
    K1, D1, _ = intr("dalsa_gray1_down")
    return dict(name="botanic", gt_quality="survey", size=size, fps=10, K0=K0, D0=D0, K1=K1, D1=D1,
                T_L_cam0=se3.inv(T_x_vlp) @ T_x_g0, T_c0_c1=T_g0_g1, T_imu_L=T_x_vlp,
                topics={"left": "/dalsa_gray/left/image_raw", "right": "/dalsa_gray/right/image_raw",
                        "lidar": "/velodyne_points", "imu": "/imu/data", "gt": "/gt_poses"},
                point_time={"field": "time", "unit": "s", "ref": "scan_start"},
                fastlio={"lidar_type": 2, "scan_line": 16, "timestamp_unit": 0, "blind": 2.0, "scan_rate": 10},
                fastlio_template="velodyne.yaml")


def _tf_static(bag):
    from rosbags.highlevel import AnyReader
    tf = {}
    with AnyReader([Path(bag)]) as r:
        conns = [c for c in r.connections if c.topic == "/tf_static"]
        for c, _, raw in r.messages(connections=conns):
            for t in r.deserialize(raw, c.msgtype).transforms:
                tr, q = t.transform.translation, t.transform.rotation
                tf[(t.header.frame_id, t.child_frame_id)] = se3.to_mat([tr.x, tr.y, tr.z], [q.x, q.y, q.z, q.w])
    return tf


def _camera_info(bag, topic):
    from rosbags.highlevel import AnyReader
    with AnyReader([Path(bag)]) as r:
        conns = [c for c in r.connections if c.topic == topic]
        for c, _, raw in r.messages(connections=conns):
            m = r.deserialize(raw, c.msgtype)
            return np.reshape(m.K, (3, 3)).tolist(), [*map(float, m.D[:4]), 0.0], [int(m.width), int(m.height)]
    raise ValueError(f"{topic} ausente em {bag}")


def rellis_calib(bag):
    tf = _tf_static(bag)

    def chain(*frames):
        T = np.eye(4)
        for a, b in zip(frames[:-1], frames[1:]):
            T = T @ tf[(a, b)]
        return T

    T_b_lidar = chain("base_link", "chassis_link", "top_chassis_link", "imu_link", "os1_frame",
                      "ouster1/os1_sensor", "ouster1/os1_lidar")
    T_b_left, T_b_right = tf[("base_link", "nerian_left")], tf[("base_link", "nerian_right")]
    T_s_imu, T_s_lidar = tf[("ouster1/os1_sensor", "ouster1/os1_imu")], tf[("ouster1/os1_sensor", "ouster1/os1_lidar")]
    K0, D0, size = _camera_info(bag, "/nerian/left/camera_info")
    K1, D1, _ = _camera_info(bag, "/nerian/right/camera_info")
    return dict(name="rellis", gt_quality="slam", size=size, fps=10, K0=K0, D0=D0, K1=K1, D1=D1,
                T_L_cam0=se3.inv(T_b_lidar) @ T_b_left, T_c0_c1=se3.inv(T_b_left) @ T_b_right,
                T_imu_L=se3.inv(T_s_imu) @ T_s_lidar,
                topics={"left": "/nerian/left/image_raw", "right": "/nerian/right/image_raw",
                        "lidar": "/os1_cloud_node/points", "imu": "/os1_cloud_node/imu", "gt": "/gt_poses"},
                point_time={"field": "t", "unit": "ns", "ref": "scan_start"},
                fastlio={"lidar_type": 3, "scan_line": 64, "timestamp_unit": 3, "blind": 2.0},
                # Evidência (docs/deskew_rellis.md): com deskew o KISS-ICP diverge do FAST-LIO e das rodas.
                kissicp_deskew=False,
                # Nerian a 15 Hz com descartes: intervalos de 66,7/133,3 ms -> idade máxima = 1 período máximo.
                max_age_ms=140,
                fastlio_template="ouster64.yaml")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=["botanic", "rellis"])
    ap.add_argument("--calib", help="botanic: pasta calib_params")
    ap.add_argument("--bag", help="rellis: bag com /tf_static e camera_info")
    ap.add_argument("--out", default="configs")
    a = ap.parse_args()
    c = botanic_calib(a.calib) if a.dataset == "botanic" else rellis_calib(a.bag)
    out = Path(a.out) / c["name"]
    out.mkdir(parents=True, exist_ok=True)
    for name, text in build(c, (FASTLIO_DIR / c["fastlio_template"]).read_text()).items():
        (out / name).write_text(text)
        print("escrito", out / name)


if __name__ == "__main__":
    main()
