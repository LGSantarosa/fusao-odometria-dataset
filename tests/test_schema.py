import pytest
from ofd import schema


def test_roles():
    s = schema.build_schema(schema.METHODS)
    assert s["gt_dx"] == "target"
    assert s["orbslam3_err_t"] == "evaluation"
    assert s["kissicp_fitness"] == "feature"
    assert s["stella_reproj_err_var_H"] == "feature"
    assert s["fastlio_src_ts"] == "metadata"
    assert s["fastlio_dt_ms"] == "feature"
    assert s["fastlio_age_ms"] == "feature"
    assert s["kissicp_vx"] == "feature" and s["gt_wz"] == "target"
    assert "orbslam3_fitness" not in s


def test_leak_detection():
    s = schema.build_schema(schema.METHODS)
    schema.assert_no_leak(s)
    s["orbslam3_err_t"] = "feature"
    with pytest.raises(ValueError):
        schema.assert_no_leak(s)
    s = schema.build_schema(schema.METHODS); s["gt_qw"] = "feature"
    with pytest.raises(ValueError):
        schema.assert_no_leak(s)
