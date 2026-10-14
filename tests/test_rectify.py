import cv2
import numpy as np
from scipy.spatial.transform import Rotation as R
from ofd.rectify import StereoRectifier


def calib(rot_deg=(0.3, -0.5, 0.8), dist=(-0.06, 0.1)):
    K0 = np.array([[643.6, 0, 475.2], [0, 642.7, 307.4], [0, 0, 1]])
    K1 = np.array([[645.6, 0, 471.3], [0, 644.7, 304.3], [0, 0, 1]])
    D0 = np.array([dist[0], dist[1], 0, 0, 0.0]); D1 = D0.copy()
    T01 = np.eye(4)  # câmera 1 no frame da câmera 0
    T01[:3, :3] = R.from_euler("xyz", rot_deg, degrees=True).as_matrix()
    T01[:3, 3] = [0.254, 0.0008, -0.0011]
    return K0, D0, K1, D1, T01


def project(K, D, T_c_w, P):
    Pc = (T_c_w[:3, :3] @ P.T).T + T_c_w[:3, 3]
    uv, _ = cv2.projectPoints(Pc, np.zeros(3), np.zeros(3), K, D)
    return uv.reshape(-1, 2)


def test_rectified_points_share_rows_and_baseline():
    K0, D0, K1, D1, T01 = calib()
    rect = StereoRectifier(K0, D0, K1, D1, T01, (960, 600))
    rng = np.random.default_rng(0)
    P = np.c_[rng.uniform(-3, 3, 200), rng.uniform(-1.5, 1.5, 200), rng.uniform(4, 30, 200)]
    uv0 = project(K0, D0, np.eye(4), P)
    uv1 = project(K1, D1, np.linalg.inv(T01), P)
    r0 = rect.rectify_points(uv0, side=0)
    r1 = rect.rectify_points(uv1, side=1)
    assert np.abs(r0[:, 1] - r1[:, 1]).max() < 0.05          # mesma linha após retificar
    # disparidade = fx * b / Z no frame retificado
    Z_rect = (rect.T_cam0_rect[:3, :3].T @ P.T).T[:, 2]
    np.testing.assert_allclose(r0[:, 0] - r1[:, 0], rect.fx * rect.baseline / Z_rect, rtol=1e-3)
    assert abs(rect.baseline - np.linalg.norm(T01[:3, 3])) < 1e-6


def test_T_cam0_rect_is_pure_rotation():
    rect = StereoRectifier(*calib(), (960, 600))
    T = rect.T_cam0_rect
    np.testing.assert_allclose(T[:3, 3], 0)
    np.testing.assert_allclose(T[:3, :3] @ T[:3, :3].T, np.eye(3), atol=1e-12)
    assert abs(np.linalg.det(T[:3, :3]) - 1) < 1e-12


def test_apply_returns_same_size_gray():
    rect = StereoRectifier(*calib(), (960, 600))
    L = np.zeros((600, 960), np.uint8); Rimg = L.copy()
    a, b = rect.apply(L, Rimg)
    assert a.shape == (600, 960) and b.shape == (600, 960)
