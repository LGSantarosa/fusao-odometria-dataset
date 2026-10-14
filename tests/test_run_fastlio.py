import numpy as np
import pytest
from ofd import run_fastlio

MS = 1_000_000


def poses(n):
    Ts = np.stack([np.eye(4)] * n)
    for i in range(n):
        Ts[i][0, 3] = i
    return Ts


def test_every_scan_has_state_and_missing_scan_is_not_ok():
    end = np.arange(10) * 100 * MS
    raw_ts = np.delete(end, 4) + 2 * MS          # scan 4 não gerou pose; demais com 2 ms de diferença
    ts, Ts, st, info = run_fastlio.assemble(raw_ts, poses(9), end)
    assert len(st) == 10 and st["ok"].tolist() == [1, 1, 1, 1, 0, 1, 1, 1, 1, 1]
    assert ts.tolist() == np.delete(end, 4).tolist()   # pose carimbada com end_ns do scan
    assert info["matched_frac"] == 0.9


def test_offset_mismatch_raises_with_diagnostic():
    end = np.arange(10) * 100 * MS
    with pytest.raises(RuntimeError, match="mediana"):
        run_fastlio.assemble(end + 50 * MS, poses(10), end)
