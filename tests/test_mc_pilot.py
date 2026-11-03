import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from ofd import mc_pilot


def test_pilot_grids_and_parameter_cap():
    assert mc_pilot.ALPHAS == (0.1, 0.2, 0.3, 0.5, 0.7, 1.0)
    assert mc_pilot.WINDOWS == (5, 10, 20)
    assert all(len(grid) == 18 for grid in mc_pilot.GRIDS.values())
    for family, grid in mc_pilot.GRIDS.items():
        W = 1 if family == "STEP" else max(mc_pilot.WINDOWS)
        for cfg in grid:
            model = mc_pilot.mc_models.build(family, "W", len(mc_pilot.fd.FEATURES), W,
                                               mc_pilot._model_cfg(cfg), 0)
            assert mc_pilot.mc_models.n_params(model) <= mc_pilot.MAX_PARAMS


def test_load_has_hard_development_allowlist():
    with pytest.raises(ValueError, match="allowlist"):
        mc_pilot._load("1005-00")


def test_choose_uses_one_percent_then_complexity():
    rows = [{"loss": 1.0, "n": 20}, {"loss": 1.005, "n": 10}, {"loss": 1.02, "n": 1}]
    assert mc_pilot._choose(rows, complexity_key="n") == rows[1]


def _fake_git(*a):
    return "abc" if a[0] in ("rev-parse", "log") else ""


def test_manifest_is_formal_and_immutable(tmp_path, monkeypatch):
    monkeypatch.setattr(mc_pilot, "_git", _fake_git)
    got = mc_pilot.initialize(tmp_path)
    assert got["status"] == "FORMAL_DEVELOPMENT_PILOT"
    assert not got["external_test_authorized"] and got["development_sequences"] == list(mc_pilot.DEV)
    sha = hashlib.sha256(mc_pilot.AMENDMENT.read_bytes()).hexdigest()
    assert got["amendment"] == {"path": str(mc_pilot.AMENDMENT), "commit": "abc", "sha256": sha}
    p = tmp_path / "manifest.json"
    old = json.loads(p.read_text())
    monkeypatch.setattr(mc_pilot, "ALPHAS", (0.5, 1.0))
    with pytest.raises(RuntimeError, match="configuração diferente"):
        mc_pilot.initialize(tmp_path)
    assert json.loads(p.read_text()) == old


def test_manifest_refuses_unregistered_amendment(tmp_path, monkeypatch):
    monkeypatch.setattr(mc_pilot, "_git", lambda *a: "abc" if a[0] == "rev-parse" else "")
    with pytest.raises(RuntimeError, match="emenda não registrada"):
        mc_pilot.initialize(tmp_path)
    monkeypatch.setattr(mc_pilot, "_git",
                        lambda *a: " M docs/x.md" if a[:2] == ("status", "--porcelain") and len(a) > 2
                        else _fake_git(*a))
    with pytest.raises(RuntimeError, match="emenda não registrada"):
        mc_pilot.initialize(tmp_path, require_clean=False)
    assert not (tmp_path / "manifest.json").exists()


def test_formal_pilot_never_reuses_provisional_root(monkeypatch):
    monkeypatch.setattr(mc_pilot, "_git", _fake_git)
    assert mc_pilot.ROOT != mc_pilot.PROVISIONAL_ROOT
    with pytest.raises(RuntimeError, match="provisório"):
        mc_pilot.initialize(mc_pilot.PROVISIONAL_ROOT)
