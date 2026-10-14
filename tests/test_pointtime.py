import numpy as np
from ofd import pointtime

STAMP = 1_700_000_000_000_000_000


def test_scan_start_seconds():
    t = np.linspace(0, 0.1, 1000)
    n, info = pointtime.normalize(t, "s", "scan_start", STAMP)
    assert n.min() == 0 and abs(n.max() - 1) < 1e-9
    assert info["valid"] and abs(info["t_max_s"] - 0.1) < 1e-9 and abs(info["span_s"] - 0.1) < 1e-9


def test_scan_end_negative_offsets_microseconds():
    t = np.linspace(-100_000, 0, 1000)  # µs antes do stamp
    n, info = pointtime.normalize(t, "us", "scan_end", STAMP)
    assert abs(n[0]) < 1e-9 and abs(n[-1] - 1) < 1e-9
    assert abs(info["t_max_s"]) < 1e-9  # fim do scan = header


def test_absolute_nanoseconds():
    t = STAMP + np.linspace(0, 100_000_000, 1000)
    n, info = pointtime.normalize(t.astype(np.float64), "ns", "absolute", STAMP)
    assert abs(n.min()) < 1e-6 and abs(n.max() - 1) < 1e-6
    assert abs(info["t_max_s"] - 0.1) < 1e-6


def test_all_refs_same_normalization():
    base = np.linspace(0, 0.1, 500)
    a, _ = pointtime.normalize(base, "s", "scan_start", STAMP)
    b, _ = pointtime.normalize(base - 0.1, "s", "scan_end", STAMP)
    np.testing.assert_allclose(a, b, atol=1e-9)


def test_constant_times_rejected():
    n, info = pointtime.normalize(np.zeros(1000), "s", "scan_start", STAMP)
    assert n is None and not info["valid"]


def test_wrong_unit_rejected_by_span():
    t = np.linspace(0, 0.1, 1000)  # na verdade s, declarado ms -> span 0.1 ms
    assert pointtime.normalize(t, "ms", "scan_start", STAMP)[0] is None


def test_shuffled_times_rejected_by_monotonicity():
    t = np.random.default_rng(0).permutation(np.linspace(0, 0.1, 1000))
    n, info = pointtime.normalize(t, "s", "scan_start", STAMP)
    assert n is None and info["monotonic_frac"] < 0.99


def test_monotonic_within_ring_even_if_rings_interleave():
    # 16 rings armazenados ring a ring (cada ring varre 0..0.1 s): globalmente não monotônico
    t = np.tile(np.linspace(0, 0.1, 100), 16)
    ring = np.repeat(np.arange(16), 100)
    n, info = pointtime.normalize(t, "s", "scan_start", STAMP, ring=ring)
    assert n is not None and info["monotonic_frac"] == 1.0
