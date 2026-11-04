import numpy as np
import pandas as pd

from ofd import mc_external as ext


def _h1(values):
    seqs = ("1005-00", "1005-01", "1005-05", "1005-07", "1006-01", "1006-03", "1008-01", "1008-03")
    return pd.DataFrame({"seq": seqs, "day": [s[:4] for s in seqs], "b5_rmse_w": 1.0, "cnn_rmse_w": 0.9,
                         "delta_rmse_w": values, "favorable_angular": np.asarray(values) > 0})


def test_h1_requires_positive_overall_and_each_day():
    assert ext.decide_h1(_h1([0.1] * 8))["status"] == "positive"
    values = [0.1] * 6 + [-0.1, -0.1]
    got = ext.decide_h1(_h1(values))
    assert got["status"] == "negative" and got["day_median_delta_rmse_w"]["1008"] < 0


def test_h1_is_indeterminate_when_a_metric_is_missing():
    h = _h1([0.1] * 8)
    h.loc[0, "cnn_rmse_w"] = np.nan
    assert ext.decide_h1(h)["status"] == "indeterminate"


def test_seed_aggregation_is_mean_of_metrics_not_prediction_ensemble():
    rows = []
    for family in ext.FAMILIES:
        models = [family] if family not in ext.LEARNED else [f"{family}_s0", f"{family}_s1"]
        for i, model in enumerate(models, 1):
            rows.append({"seq": "1005-00", "model": model, **{m: float(i) for m in ext.METRICS}})
    got = ext.aggregate_seeds(pd.DataFrame(rows)).set_index("family")
    assert got.loc["CNN", "rmse_w"] == 1.5 and got.loc["CNN", "n_seeds"] == 2
    assert got.loc["B5", "rmse_w"] == 1.0 and np.isnan(got.loc["B5", "rmse_w_sd"])


def test_external_model_list_has_no_lstm_and_five_seeds():
    assert len(ext.MODELS) == 18 and not any(m.startswith("LSTM") for m in ext.MODELS)
    assert sum(m.startswith("CNN_s") for m in ext.MODELS) == 5
