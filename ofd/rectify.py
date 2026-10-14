"""Stereo rectification done once at extraction, so both VOs run on the same ideal pinhole pair.

The VO pose frame becomes the *rectified* left camera; its pose in the raw left camera is a pure rotation
(`T_cam0_rect`), which must be composed into the VO extrinsic (T_L_S = T_L_cam0 @ T_cam0_rect).
"""
import cv2
import numpy as np


class StereoRectifier:
    def __init__(self, K0, D0, K1, D1, T_c0_c1, size):
        """T_c0_c1: pose of camera 1 in camera 0 (maps cam1 coords -> cam0). size: (width, height)."""
        K0, K1 = np.asarray(K0, float), np.asarray(K1, float)
        D0, D1 = np.asarray(D0, float).ravel(), np.asarray(D1, float).ravel()
        T = np.asarray(T_c0_c1, float)
        R_10 = T[:3, :3].T                 # cam0 -> cam1, como o OpenCV espera (x1 = R x0 + t)
        t_10 = (-R_10 @ T[:3, 3]).reshape(3, 1)  # OpenCV 5 exige vetor coluna
        R1, R2, P1, P2, _, _, _ = cv2.stereoRectify(K0, D0, K1, D1, tuple(size), R_10, t_10,
                                                    flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
        self.K = (K0, K1)
        self.D = (D0, D1)
        self.Rr = (R1, R2)
        self.P = (P1, P2)
        self.size = tuple(size)
        self.fx, self.fy = float(P1[0, 0]), float(P1[1, 1])
        self.cx, self.cy = float(P1[0, 2]), float(P1[1, 2])
        self.baseline = float(-P2[0, 3] / P2[0, 0])
        self.T_cam0_rect = np.eye(4)
        self.T_cam0_rect[:3, :3] = R1.T    # x_rect = R1 x_cam0  =>  pose do frame retificado em cam0
        self._maps = [cv2.initUndistortRectifyMap(self.K[i], self.D[i], self.Rr[i], self.P[i], self.size,
                                                  cv2.CV_16SC2) for i in (0, 1)]

    def rectify_points(self, uv, side):
        pts = np.asarray(uv, np.float64).reshape(-1, 1, 2)
        return cv2.undistortPoints(pts, self.K[side], self.D[side], R=self.Rr[side], P=self.P[side]).reshape(-1, 2)

    def apply(self, left, right):
        return tuple(cv2.remap(img, *self._maps[i], cv2.INTER_LINEAR) for i, img in enumerate((left, right)))

    def params(self):
        return {"fx": self.fx, "fy": self.fy, "cx": self.cx, "cy": self.cy, "baseline": self.baseline,
                "width": self.size[0], "height": self.size[1], "T_cam0_rect": self.T_cam0_rect.ravel().tolist()}
