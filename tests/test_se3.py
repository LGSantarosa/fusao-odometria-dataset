import numpy as np
from scipy.spatial.transform import Rotation as R
from ofd import se3


def rand_T(seed):
    rng = np.random.default_rng(seed)
    T = np.eye(4)
    T[:3, :3] = R.random(random_state=seed).as_matrix()
    T[:3, 3] = rng.normal(size=3)
    return T


def test_vec_roundtrip_and_qw_positive():
    T = rand_T(1)
    v = se3.to_vec(T)
    assert v[6] >= 0
    np.testing.assert_allclose(se3.to_mat(v[:3], v[3:]), T, atol=1e-9)


def test_qw_sign_normalized():
    q = R.from_euler("z", 200, degrees=True).as_quat()  # qw < 0 para 200°
    T = se3.to_mat(np.zeros(3), q)
    assert se3.to_vec(T)[6] >= 0


def test_delta_composes_back():
    A, B = rand_T(2), rand_T(3)
    np.testing.assert_allclose(A @ se3.delta(A, B), B, atol=1e-9)


def test_delta_translation_in_previous_body_frame():
    A = se3.to_mat(np.zeros(3), R.from_euler("z", 90, degrees=True).as_quat())
    B = A.copy(); B[:3, 3] = [0, 1, 0]  # andou +y no mundo = +x no corpo de A
    np.testing.assert_allclose(se3.delta(A, B)[:3, 3], [1, 0, 0], atol=1e-9)


def test_conjugate_matches_frame_change():
    T_L_S = rand_T(4)
    A_S, B_S = rand_T(5), rand_T(6)
    A_L = A_S @ se3.inv(T_L_S)
    B_L = B_S @ se3.inv(T_L_S)
    np.testing.assert_allclose(se3.conjugate(se3.delta(A_S, B_S), T_L_S),
                               se3.delta(A_L, B_L), atol=1e-9)


def test_interp_midpoint_and_out_of_range():
    A = np.eye(4)
    B = se3.to_mat(np.array([2.0, 0, 0]), R.from_euler("z", 90, degrees=True).as_quat())
    ts = np.array([0, 100], dtype=np.int64)
    M = se3.interp(ts, np.stack([A, B]), 50)
    np.testing.assert_allclose(M[:3, 3], [1, 0, 0], atol=1e-9)
    assert abs(se3.rot_angle(M) - np.pi / 4) < 1e-9
    assert se3.interp(ts, np.stack([A, B]), 101) is None
    assert se3.interp(ts, np.stack([A, B]), -1) is None


def test_twist_roundtrip_and_pure_translation():
    T = rand_T(9)
    np.testing.assert_allclose(se3.exp_twist(se3.log_twist(T)), T, atol=1e-9)
    P = np.eye(4); P[:3, 3] = [1.0, 2.0, 3.0]
    np.testing.assert_allclose(se3.log_twist(P), [1, 2, 3, 0, 0, 0], atol=1e-12)


def test_twist_small_rotation_stable():
    T = se3.to_mat([0.1, 0, 0], R.from_rotvec([0, 0, 1e-12]).as_quat())
    assert np.all(np.isfinite(se3.log_twist(T)))


def test_tum_roundtrip(tmp_path):
    ts = np.array([1_700_000_000_123_456_789, 1_700_000_000_223_456_789], dtype=np.int64)
    Ts = np.stack([rand_T(7), rand_T(8)])
    p = tmp_path / "x.tum"
    se3.save_tum(p, ts, Ts)
    ts2, Ts2 = se3.load_tum(p)
    assert np.all(np.abs(ts2 - ts) < 1000)  # < 1 µs
    np.testing.assert_allclose(Ts2, Ts, atol=1e-6)


import pytest
import warnings


@pytest.mark.parametrize("theta", [1e-8, 2e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1.1e-4, 1e-3])
def test_twist_small_rotations_stable_and_accurate(theta):
    axis = np.array([0.3, -0.5, 0.8]); axis /= np.linalg.norm(axis)
    w = theta * axis
    t = np.array([1.0, -2.0, 0.5])
    T = se3.to_mat(t, R.from_rotvec(w).as_quat())
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        xi = se3.log_twist(T)
        T2 = se3.exp_twist(xi)
    assert np.all(np.isfinite(xi))
    np.testing.assert_allclose(T2, T, atol=1e-12)
    # referência independente de 1ª ordem: v = t - 0.5 w×t + O(θ²|t|)
    np.testing.assert_allclose(xi[:3], t - 0.5 * np.cross(w, t), atol=10 * theta**2 * np.linalg.norm(t) + 1e-15)
    np.testing.assert_allclose(xi[3:], w, atol=1e-15)


def test_exp_small_branch_includes_second_order():
    w = np.array([0, 0, 1e-5]); v = np.array([1.0, 0, 0])
    T = se3.exp_twist(np.r_[v, w])
    expected = v + 0.5 * np.cross(w, v) + np.cross(w, np.cross(w, v)) / 6.0
    np.testing.assert_allclose(T[:3, 3], expected, atol=1e-16)
