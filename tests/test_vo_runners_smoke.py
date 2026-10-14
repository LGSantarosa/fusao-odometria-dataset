"""Smoke dos binários VO com estéreo sintético retificado de geometria conhecida (pulado se não compilados).

Cena plana a profundidade Z = fx*b/d; a câmera anda +6 px/frame para a direita => +6*b/d m por frame em +x.
O runner deve gravar T_W_C (câmera no mundo): x final positivo e ≈ 99*6*b/d.
"""
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest

TP = Path(__file__).resolve().parents[1] / "third_party"
FX, B, D, STEP, N = 458.0, 0.10917, 30, 6, 100
EXPECTED_X = (N - 1) * STEP * B / D


def make_seq(root):
    rng = np.random.default_rng(0)
    W = np.full((600, 3000), 128, np.uint8)
    for _ in range(2500):
        x, y = int(rng.integers(0, 3000)), int(rng.integers(0, 600))
        c, s = int(rng.integers(0, 255)), int(rng.integers(4, 25))
        if rng.random() < 0.5:
            cv2.rectangle(W, (x, y), (x + s, y + int(rng.integers(4, 25))), c, -1)
        else:
            cv2.circle(W, (x, y), s // 2, c, -1)
    (root / "images/left").mkdir(parents=True)
    (root / "images/right").mkdir(parents=True)
    ts = []
    for k in range(N):
        x = 100 + STEP * k
        t = 1_700_000_000_000_000_000 + k * 50_000_000
        cv2.imwrite(str(root / f"images/left/{t}.png"), W[60:540, x:x + 752])
        cv2.imwrite(str(root / f"images/right/{t}.png"), W[60:540, x + D:x + D + 752])  # u_R = u_L - d
        ts.append(t)
    pd.DataFrame({"ts_ns": ts}).to_csv(root / "images/stamps.csv", index=False)


ORB_YAML = f"""%YAML:1.0
File.version: "1.0"
Camera.type: "Rectified"
Camera1.fx: {FX}
Camera1.fy: {FX}
Camera1.cx: 376.0
Camera1.cy: 240.0
Stereo.b: {B}
Camera.width: 752
Camera.height: 480
Camera.fps: 20
Camera.RGB: 1
Stereo.ThDepth: 60.0
loopClosing: 0
ORBextractor.nFeatures: 1200
ORBextractor.scaleFactor: 1.2
ORBextractor.nLevels: 8
ORBextractor.iniThFAST: 20
ORBextractor.minThFAST: 7
Viewer.KeyFrameSize: 0.05
Viewer.KeyFrameLineWidth: 1.0
Viewer.GraphLineWidth: 0.9
Viewer.PointSize: 2.0
Viewer.CameraSize: 0.08
Viewer.CameraLineWidth: 3.0
Viewer.ViewpointX: 0.0
Viewer.ViewpointY: -0.7
Viewer.ViewpointZ: -1.8
Viewer.ViewpointF: 500.0
"""

STELLA_YAML = f"""Camera:
  name: "synthetic"
  setup: "stereo"
  model: "perspective"
  fx: {FX}
  fy: {FX}
  cx: 376.0
  cy: 240.0
  k1: 0.0
  k2: 0.0
  p1: 0.0
  p2: 0.0
  k3: 0.0
  focal_x_baseline: {FX * B}
  fps: 20
  cols: 752
  rows: 480
  color_order: "Gray"
Preprocessing:
  min_size: 800
Feature:
  name: "default ORB"
  scale_factor: 1.2
  num_levels: 8
  ini_fast_threshold: 20
  min_fast_threshold: 7
Tracking:
  max_num_keypoints: 1500
Mapping:
  baseline_dist_thr_ratio: 0.02
  redundant_obs_ratio_thr: 0.9
LoopDetector:
  enabled: false
"""

CASES = {
    "orbslam3": (TP / "bin/orbslam3_stereo_log", TP / "ORB_SLAM3/Vocabulary/ORBvoc.txt", ORB_YAML),
    "stella": (TP / "bin/stella_stereo_log", TP / "orb_vocab.fbow", STELLA_YAML),
}


@pytest.mark.parametrize("method", list(CASES))
def test_runner_on_synthetic_stereo(tmp_path, method):
    binary, vocab, settings = CASES[method]
    if not binary.exists() or not vocab.exists():
        pytest.skip(f"{method} não compilado")
    make_seq(tmp_path / "seq")
    (tmp_path / "settings.yaml").write_text(settings)
    (tmp_path / "out").mkdir()
    env = {**os.environ, "VO_RATE": "0"}
    r = subprocess.run([str(binary), str(vocab), str(tmp_path / "settings.yaml"), str(tmp_path / "seq"),
                        str(tmp_path / "out")], capture_output=True, text=True, env=env, timeout=900)
    assert r.returncode == 0, r.stderr[-2000:]
    f = pd.read_csv(tmp_path / "out/frames.csv")
    assert len(f) == N
    assert f["ok"].mean() > 0.9, f"tracking OK em só {f['ok'].mean():.0%} dos frames"
    last = f[f["ok"] == 1].iloc[-1]
    assert last["x"] > 0, f"x final {last['x']:.3f} < 0: pose gravada não é T_W_C"
    assert abs(last["x"] - EXPECTED_X) < 0.1 * EXPECTED_X, (last["x"], EXPECTED_X)
    ok = f[f["ok"] == 1]
    assert ok["reproj_err"].median() < 3.0
    assert (ok["inliers"].iloc[1:] > 0).all()  # frame 0 = inicialização estéreo, sem etapa de casamento
