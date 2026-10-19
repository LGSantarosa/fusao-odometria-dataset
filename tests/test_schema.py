import pytest
from ofd import schema


def test_roles():
    s = schema.build_schema(schema.METHODS)
    assert s["gt_vx"] == "target"
    assert s["orbslam3_err_t"] == "evaluation"
    assert s["kissicp_fitness"] == "feature"
    assert s["stella_reproj_err_var_H"] == "feature"
    assert s["fastlio_src_ts"] == "metadata"
    assert s["fastlio_dt_ms"] == "feature"
    assert s["fastlio_age_ms"] == "feature"
    assert s["kissicp_vx"] == "feature" and s["gt_wz"] == "target"
    assert "orbslam3_fitness" not in s


def test_roles_twist_representation():
    """Decisão de 19/10/2026: o modelo consome a velocidade em se(3); o ΔT fica para auditoria e avaliação."""
    s = schema.build_schema(schema.METHODS)
    for m in schema.METHODS:
        for c in schema.TW + ["dt_ms", "age_ms", "valid"]:
            assert s[f"{m}_{c}"] == "feature", f"{m}_{c}"
        for c in schema.VEC:
            assert s[f"{m}_{c}"] == "metadata", f"{m}_{c}"
    assert [c for c, r in s.items() if r == "target"] == [f"gt_{c}" for c in schema.TW]
    for c in schema.VEC:
        assert s[f"gt_{c}"] == "evaluation"
    schema.assert_no_leak(s)


def test_role_counts():
    roles = list(schema.build_schema(schema.METHODS).values())
    assert {r: roles.count(r) for r in set(roles)} == {"feature": 56, "metadata": 44, "target": 6, "evaluation": 15}


def test_leak_detection():
    s = schema.build_schema(schema.METHODS)
    schema.assert_no_leak(s)
    s["orbslam3_err_t"] = "feature"
    with pytest.raises(ValueError):
        schema.assert_no_leak(s)
    s = schema.build_schema(schema.METHODS); s["gt_qw"] = "feature"
    with pytest.raises(ValueError):
        schema.assert_no_leak(s)


def test_csv_dtype_keeps_identifier_columns_as_text():
    assert schema.CSV_DTYPE == {"seq": "string"}
