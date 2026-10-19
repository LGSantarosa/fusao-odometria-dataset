"""Fase 0 do protocolo do modelo de fusão (docs/protocol_fusion_model.md), seções 3–5: só dados sintéticos."""
import numpy as np
import pytest

from ofd import fusion_data as fd, schema
from tests.fusion_synth import synth_sequence


def test_features_and_target_follow_schema():
    assert len(fd.FEATURES) == 56 and fd.TARGET == [f"gt_{c}" for c in schema.TW]
    sch = schema.build_schema(schema.METHODS)
    assert all(sch[c] == "feature" for c in fd.FEATURES)


def test_target_rows_require_all_six_components():
    df = synth_sequence(50)
    df.loc[3, "gt_wz"] = np.nan
    mask = fd.target_rows(df)
    assert mask.sum() == 49 and not mask[3]


def test_blocks_are_contiguous_with_purge_and_remainder_in_last():
    folds = fd.blocks(103, k=5, purge=10)
    assert len(folds) == 5
    val = [v for _, v in folds]
    assert [len(v) for v in val] == [20, 20, 20, 20, 23]
    assert np.array_equal(np.concatenate(val), np.arange(103))
    tr, v = folds[2]                                            # validação 40..59
    assert not set(tr) & set(range(30, 70))                     # 10 linhas purgadas de cada lado
    assert set(tr) == set(range(0, 30)) | set(range(70, 103))
    tr0, _ = folds[0]
    assert tr0.min() == 30                                      # primeiro bloco: purga só depois


def test_standardizer_uses_valid_rows_and_keeps_valid_binary():
    df = synth_sequence(60, invalid_every={"orbslam3": 3})
    st = fd.Standardizer().fit(df)
    ok = df["orbslam3_valid"] == 1
    assert np.isclose(st.mean["orbslam3_vx"], df.loc[ok, "orbslam3_vx"].mean())
    assert np.isclose(st.scale["orbslam3_vx"], df.loc[ok, "orbslam3_vx"].std(ddof=0))   # populacional
    X = st.transform(df)
    j = fd.FEATURES.index("orbslam3_valid")
    assert set(np.unique(X[:, j])) == {0.0, 1.0} and "orbslam3_valid" not in st.mean
    assert np.isfinite(X).all()
    assert (X[~ok.to_numpy(), fd.FEATURES.index("orbslam3_vx")] == 0).all()          # imputação neutra


def test_standardizer_zero_sd_uses_scale_one():
    df = synth_sequence(30)
    st = fd.Standardizer().fit(df)
    assert st.scale["orbslam3_dt_ms"] == 1.0                      # constante 100 ms
    assert (st.transform(df)[:, fd.FEATURES.index("orbslam3_dt_ms")] == 0).all()


def test_standardizer_column_without_values_is_an_error():
    df = synth_sequence(30)
    df["stella_reproj_err"] = np.nan
    with pytest.raises(fd.EmptyColumnError, match="stella_reproj_err"):
        fd.Standardizer().fit(df)


def test_standardizer_statistics_ignore_rows_outside_fit():
    df = synth_sequence(100)
    a = fd.Standardizer().fit(df.iloc[:50])
    changed = df.copy()
    changed.loc[50:, fd.FEATURES] = changed.loc[50:, fd.FEATURES] * 100     # validação/teste alterados
    b = fd.Standardizer().fit(changed.iloc[:50])
    assert a.mean == b.mean and a.scale == b.scale


def test_target_sigma_population_without_centering_and_zero_to_one():
    df = synth_sequence(80)
    df["gt_vz"] = 0.0
    sigma = fd.target_sigma(df)
    assert np.isclose(sigma[0], df["gt_vx"].std(ddof=0)) and sigma[2] == 1.0


def test_method_twists_and_valid_mask():
    df = synth_sequence(20, invalid_every={"stella": 2})
    tw, valid = fd.method_twists(df)
    assert tw.shape == (20, 4, 6) and valid.shape == (20, 4)
    assert not valid[0, 1] and valid[1, 1] and np.isnan(tw[0, 1]).all()
    assert np.allclose(tw[:, 0, 0], df["orbslam3_vx"])


def test_n_valid_counts_sources_per_row():
    df = synth_sequence(6, invalid_every={"orbslam3": 2, "stella": 3})
    assert list(fd.n_valid(df)) == [2, 4, 3, 3, 3, 4]
