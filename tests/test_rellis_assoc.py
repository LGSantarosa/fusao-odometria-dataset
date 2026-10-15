import numpy as np
import pytest
from scipy.spatial.transform import Rotation as R

from tools import rellis_assoc as ra

MS = 1_000_000


def synthetic(N=400, drops=(37, 250), seed=1, noise=0.02):
    """Trajetória com guinada e velocidade variáveis; poses = scans do bag sem `drops`; IMU sintético a 200 Hz."""
    rng = np.random.default_rng(seed)
    t_scan = 10**12 + np.arange(N) * 100 * MS + rng.integers(-2, 3, N) * MS
    tt = np.arange(t_scan[0] - 500 * MS, t_scan[-1] + 500 * MS, 5 * MS)
    s = (tt - tt[0]) / 1e9
    wz = 0.4 * np.sin(0.7 * s) + 0.25 * np.sin(2.3 * s + 1)          # rad/s
    v = 1.0 + 0.3 * np.sin(0.4 * s)
    yaw = np.concatenate([[0], np.cumsum(0.5 * (wz[1:] + wz[:-1]) * np.diff(s))])
    x = np.concatenate([[0], np.cumsum(v[1:] * np.cos(yaw[1:]) * np.diff(s))])
    y = np.concatenate([[0], np.cumsum(v[1:] * np.sin(yaw[1:]) * np.diff(s))])
    T = np.tile(np.eye(4), (N, 1, 1))
    ys = np.interp(t_scan, tt, yaw)
    T[:, :3, :3] = R.from_euler("z", ys[:, None]).as_matrix(); T[:, 0, 3] = np.interp(t_scan, tt, x); T[:, 1, 3] = np.interp(t_scan, tt, y)
    keep = np.ones(N, bool); keep[list(drops)] = False
    imu = np.c_[tt, 0 * s, 0 * s, wz + noise * rng.standard_normal(len(s))]
    wheel = np.c_[tt, v + noise * rng.standard_normal(len(s)), wz + noise * rng.standard_normal(len(s))]
    return t_scan, T[keep], imu, wheel


def test_prefix_sum_enumeration_matches_brute_force():
    t, Ts, imu, wheel = synthetic()
    N, M = len(t), len(Ts)
    phi, d = ra.pose_increments(Ts)
    sig = ra.ImuSig("imu", phi, d, t, imu)
    p0 = np.arange(M - 1); sig.calibrate(p0, p0 + 1, p0 + 2)
    T, P = ra.cost_tables(sig, M, N)
    C = ra.enumerate_pairs(T, N)
    rng = np.random.default_rng(0)
    pairs = [(0, 1), (0, N - 1), (N - 2, N - 1), (5, 6), (5, 9), (0, 7), (7, N - 1), (N - 3, N - 2)]
    pairs += [tuple(sorted(rng.choice(N, 2, replace=False))) for _ in range(20)]
    for i, j in pairs:
        B = ra.mapping(i, j, N)
        r = sig.residual(np.arange(M - 1), B[:-1], B[1:])
        c = np.nansum(np.sum(r ** 2, 1))
        assert C[i, j] == pytest.approx(c, rel=1e-9, abs=1e-9), (i, j)


@pytest.mark.parametrize("drops", [(37, 250), (0, 1), (398, 399), (0, 399), (120, 121), (0, 200), (200, 399)])
def test_recovers_known_drops(drops):
    t, Ts, imu, wheel = synthetic(drops=drops)
    N, M = len(t), len(Ts)
    phi, d = ra.pose_increments(Ts)
    for sig in (ra.ImuSig("imu", phi, d, t, imu), ra.WheelSig("rodas", phi, d, t, wheel)):
        p0 = np.arange(M - 1); sig.calibrate(p0, p0 + 1, p0 + 2)
        B = ra.mapping(*drops, N); sig.calibrate(p0, B[:-1], B[1:])
        T, _ = ra.cost_tables(sig, M, N)
        i, j, _ = ra.ranking(ra.enumerate_pairs(T, N), 1)[0]
        assert abs(i - drops[0]) <= 1 and abs(j - drops[1]) <= 1, (sig.name, (i, j), drops)


@pytest.mark.parametrize("drops", [(0, 1), (0, 200), (398, 399), (2, 3)])
def test_recovers_drops_when_sensor_starts_late(drops):
    t, Ts, imu, wheel = synthetic(drops=drops)
    late = wheel[:, 0] >= t[0] + 250 * MS                              # como as rodas do 00000 (+0,25 s)
    N, M = len(t), len(Ts)
    phi, d = ra.pose_increments(Ts)
    sig = ra.WheelSig("rodas", phi, d, t, wheel[late])
    p0 = np.arange(M - 1); sig.calibrate(p0, p0 + 1, p0 + 2)
    T, _ = ra.cost_tables(sig, M, N)
    C = ra.enumerate_pairs(T, N)
    i, j, _ = ra.ranking(C, 1)[0]
    ev = ra.valid_poses(sig, M, N)                                    # só o que algum sensor consegue distinguir
    Bb, Bt = ra.mapping(i, j, N), ra.mapping(*drops, N)
    assert np.array_equal(Bb[:-1][ev], Bt[:-1][ev]) and np.array_equal(Bb[1:][ev], Bt[1:][ev]), ((i, j), drops)
    assert C[drops] == pytest.approx(C[i, j], abs=1e-9)                # o verdadeiro empata com o vencedor
