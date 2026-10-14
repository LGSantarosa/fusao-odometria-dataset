import numpy as np
from ofd.matching import match_monotonic

MS = 1_000_000


def test_basic_tolerance():
    a = np.array([100, 200, 300]) * MS
    b = np.array([99, 201, 500]) * MS
    assert match_monotonic(a, b, 5 * MS).tolist() == [0, 1, -1]


def test_one_to_one():
    a = np.array([100, 101]) * MS
    b = np.array([100]) * MS
    assert match_monotonic(a, b, 5 * MS).tolist() == [0, -1]


def test_monotonic_never_goes_back():
    a = np.array([100, 104]) * MS
    b = np.array([103, 99]) * MS  # b fora de ordem é ordenado pelo chamador; aqui já ordenado errado de propósito
    m = match_monotonic(a, np.sort(b), 5 * MS)
    assert m.tolist() == [0, 1]


def test_empty():
    assert match_monotonic(np.array([1, 2]), np.array([], dtype=np.int64), 5).tolist() == [-1, -1]


def test_maximizes_pairs_before_error():
    # guloso faria 100->100 e deixaria 101 sem par; o ótimo casa os dois
    a = np.array([100, 101]) * MS
    b = np.array([99, 100]) * MS
    assert match_monotonic(a, b, 5 * MS).tolist() == [0, 1]


def test_minimizes_error_among_max_matchings():
    a = np.array([100]) * MS
    b = np.array([97, 101, 104]) * MS
    assert match_monotonic(a, b, 5 * MS).tolist() == [1]


def test_brute_force_agreement():
    import itertools
    rng = np.random.default_rng(1)
    for _ in range(200):
        a = np.sort(rng.integers(0, 40, rng.integers(0, 6)))
        b = np.sort(rng.integers(0, 40, rng.integers(0, 6)))
        tol = 3
        best = (0, 0)
        for r in range(min(len(a), len(b)) + 1):
            for ia in itertools.combinations(range(len(a)), r):
                for ib in itertools.combinations(range(len(b)), r):
                    d = [abs(int(a[i]) - int(b[j])) for i, j in zip(ia, ib)]
                    if all(x <= tol for x in d):
                        best = max(best, (r, -sum(d)))
        m = match_monotonic(a, b, tol)
        pairs = [(i, j) for i, j in enumerate(m) if j >= 0]
        assert all(j1 < j2 for (_, j1), (_, j2) in zip(pairs, pairs[1:]))
        got = (len(pairs), -sum(abs(int(a[i]) - int(b[j])) for i, j in pairs))
        assert got == best, (a, b, m)
