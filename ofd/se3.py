"""Pose math. Convention: T_W_B maps B->W; delta(T_prev, T_cur) = inv(T_prev) @ T_cur."""
from decimal import Decimal
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp


def to_mat(t, q_xyzw):
    T = np.eye(4)
    T[:3, :3] = R.from_quat(np.asarray(q_xyzw, float)).as_matrix()
    T[:3, 3] = np.asarray(t, float)
    return T


def to_vec(T):
    q = R.from_matrix(T[:3, :3]).as_quat()
    if q[3] < 0:
        q = -q
    return np.concatenate([T[:3, 3], q])


def inv(T):
    Ti = np.eye(4)
    Ti[:3, :3] = T[:3, :3].T
    Ti[:3, 3] = -T[:3, :3].T @ T[:3, 3]
    return Ti


def delta(T_prev, T_cur):
    return inv(T_prev) @ T_cur


def conjugate(dT_S, T_L_S):
    return T_L_S @ dT_S @ inv(T_L_S)


def rot_angle(T):
    return float(np.linalg.norm(R.from_matrix(T[:3, :3]).as_rotvec()))


def _hat(w):
    return np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])


def log_twist(T):
    w = R.from_matrix(T[:3, :3]).as_rotvec()
    th = np.linalg.norm(w)
    W = _hat(w)
    if th < 1e-8:
        V_inv = np.eye(3) - 0.5 * W + W @ W / 12.0
    else:
        V_inv = np.eye(3) - 0.5 * W + (1 - th * np.sin(th) / (2 * (1 - np.cos(th)))) / th**2 * (W @ W)
    return np.concatenate([V_inv @ T[:3, 3], w])


def exp_twist(xi):
    v, w = np.asarray(xi[:3], float), np.asarray(xi[3:], float)
    th = np.linalg.norm(w)
    W = _hat(w)
    if th < 1e-8:
        V = np.eye(3) + 0.5 * W
    else:
        V = np.eye(3) + (1 - np.cos(th)) / th**2 * W + (th - np.sin(th)) / th**3 * (W @ W)
    T = np.eye(4)
    T[:3, :3] = R.from_rotvec(w).as_matrix()
    T[:3, 3] = V @ v
    return T


def interp(ts_ns, Ts, t_ns):
    ts_ns = np.asarray(ts_ns, dtype=np.int64)
    if len(ts_ns) == 0 or t_ns < ts_ns[0] or t_ns > ts_ns[-1]:
        return None
    j = int(np.searchsorted(ts_ns, t_ns, side="left"))
    if ts_ns[j] == t_ns:
        return Ts[j].copy()
    i = j - 1
    a = (t_ns - ts_ns[i]) / (ts_ns[j] - ts_ns[i])
    out = np.eye(4)
    out[:3, 3] = (1 - a) * Ts[i][:3, 3] + a * Ts[j][:3, 3]
    slerp = Slerp([0.0, 1.0], R.from_matrix(np.stack([Ts[i][:3, :3], Ts[j][:3, :3]])))
    out[:3, :3] = slerp([a]).as_matrix()[0]
    return out


def _s_to_ns(tok: str) -> int:
    return int((Decimal(tok) * 1_000_000_000).to_integral_value())


def load_tum(path):
    ts, Ts = [], []
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        tok = line.split()
        ts.append(_s_to_ns(tok[0]))
        v = np.array([float(x) for x in tok[1:8]])
        Ts.append(to_mat(v[:3], v[3:]))
    return np.array(ts, dtype=np.int64), (np.stack(Ts) if Ts else np.zeros((0, 4, 4)))


def save_tum(path, ts_ns, Ts):
    with open(path, "w") as f:
        for t, T in zip(ts_ns, Ts):
            v = to_vec(T)
            f.write(f"{int(t) // 1_000_000_000}.{int(t) % 1_000_000_000:09d} "
                    + " ".join(f"{x:.9f}" for x in v) + "\n")
