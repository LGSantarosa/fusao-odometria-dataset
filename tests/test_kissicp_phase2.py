import numpy as np
import pandas as pd

from tools import kissicp_phase2


def _windows(n=10):
    idx = np.arange(n, dtype=np.float64)
    win = pd.DataFrame({"error_r_deg_D0": idx, "error_t_m_D0": idx[::-1],
                        "mean_omega_dt_deg": idx})
    for col in ("max_abs_delta_omega_rad_s", "mean_v_dt_m", *kissicp_phase2.STRUCTURE):
        win[col] = 1.0
    return win


def test_q1_rest_groups_are_complements_of_each_top_group():
    # top 10% rotacional = janela 9; top 10% translacional = janela 0
    q1 = kissicp_phase2.q1_localization(_windows())
    row = q1.loc["mean_omega_dt_deg"]
    assert row.top10_rot == 9 and row.top10_trans == 0
    assert row.rest_rot == 4.0      # janelas 0..8 (~top_r), não a exclusão da união (4,5)
    assert row.rest_trans == 5.0    # janelas 1..9 (~top_t)
    assert "rest" not in q1.columns
