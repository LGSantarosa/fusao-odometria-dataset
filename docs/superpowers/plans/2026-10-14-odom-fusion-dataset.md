# Dataset de Odometrias para Fusão VO/LO — Implementation Plan

> **Para quem executa:** execução nativa e sequencial, com revisão nos marcos das Tasks 4, 8, 10, 12 e 14. Se o ambiente tiver as skills `superpowers:executing-plans` / `superpowers:subagent-driven-development`, podem ser usadas (opcional). Passos em checkbox (`- [ ]`).

**Goal:** Gerar, a partir de BotanicGarden e RELLIS-3D, uma tabela por sequência (10 Hz) com ΔT causal + indicadores de qualidade de ORB-SLAM3, Stella VSLAM, FAST-LIO2 e KISS-ICP, o ΔT do GT como rótulo, e métricas ATE/RPE/cobertura por método.

**Architecture:** Núcleo Python puro e testado (`ofd/`: SE3, trilhas, sincronização causal, indicadores, schema, avaliação) que só lê/escreve arquivos em `data/`. Em volta, adaptadores que produzem um formato de execução comum (`poses_causal.tum`, `state.csv`, `indicators.csv`, `run.json`): KISS-ICP via API Python, FAST-LIO via ROS 2 (`ros2 bag play` + gravador), ORB-SLAM3 e Stella VSLAM via binários C++ próprios com patch de log. Cada etapa pode ser reexecutada isoladamente.

**Tech Stack:** Python 3.12 (numpy, scipy, pandas, pyarrow, open3d, rosbags, kiss-icp, opencv-python-headless, pyyaml, pytest), ROS 2 Jazzy (FAST-LIO, ros2 bag), C++17 (ORB-SLAM3 v1.0, stella_vslam), Ubuntu 24.04.

**Spec:** `docs/superpowers/specs/2026-10-14-odom-fusion-dataset-design.md` (rev. 4)

## Global Constraints

- Convenção: `T_W_B` (B→W); **ΔT_k = T_{k-1}⁻¹ · T_k**; translação de ΔT no frame do corpo em k-1.
- Frame comum = frame do LiDAR (VLP16 no BotanicGarden, OS1-64 no RELLIS). Troca de frame por conjugação: `ΔT_L = T_L_S · ΔT_S · T_L_S⁻¹`.
- Quaternion (qx, qy, qz, qw) com **qw ≥ 0**.
- Timestamps internos em **int64 nanossegundos**; arquivos TUM em segundos com 9 casas decimais.
- Instante de disponibilidade do LiDAR = **`end_ns`** (header + deslocamento até o último ponto; = header se a semântica do tempo for desconhecida). **Grade = `end_ns`**. Poses de KISS-ICP e FAST-LIO têm timestamp = `end_ns` do scan casado. VO: timestamp da imagem.
- Sincronização de métodos **estritamente causal**: última pose com `src_ts ≤ t_k`, sem interpolação, válida se `0 ≤ age_ms ≤ max_age_ms` (padrão **100**). `m_dt_ms = src_ts(k) − src_ts(k−1)`; `m_dt_ms = 0` → inválido.
- `m_dt_ms` e `m_age_ms` são **features**; velocidade se(3) `m_vx..m_wz = log(ΔT)/dt` (m/s, rad/s) é feature; `gt_vx..gt_wz` é target.
- Casamentos de timestamps (FAST-LIO pose↔scan, RELLIS scan↔pose) são **monotônicos e um-para-um** (`ofd/matching.py`), tolerância padrão 5 ms.
- `state.csv` tem **uma linha por frame/scan de entrada**, inclusive os que não produziram pose (ok=0).
- Falhas = transições ok 1→0 no `state.csv`; resets = nº de segmentos − 1. Amostra repetida/pose velha não é falha.
- GT pode ser interpolado (linear + SLERP); `m_err_*` usa GT interpolado em `src_ts(k−1)` e `src_ts(k)`.
- Toda transição entre `segment_id` diferentes → `m_valid = 0`.
- Variância móvel **causal** (janela H só de passado), padrão H = 10.
- Papéis de coluna: `metadata | feature | target | evaluation`; `gt_*` = target, `*_err_t|*_err_r` = evaluation.
- VOs: estéreo, **sem IMU**, **loop closure desligado**. FAST-LIO: `uses_imu=true`. KISS-ICP: `uses_imu=false`.
- Tempo por ponto normalizado em [0, 1]; validação por scan = span 80–120 ms **e** ≥ 99% de passos não decrescentes por ring; **deskew=true só se 100% dos scans passarem**; limites observados em `scans.csv`.
- ATE: segmentos elegíveis ≥ 30 s **e** ≥ 20 m (GT); agregação `√(Σ nᵢ·RMSEᵢ² / Σ nᵢ)`.
- Nada de Docker; tudo nativo. Um algoritmo por vez (RAM 15 GB).
- Reprodutibilidade: Python 3.12 com `requirements.lock` (pip freeze, commitado); commits fixos: Pangolin `7364b59a` (v0.9.1), ORB_SLAM3 `4452a3c4ab75`, g2o `e8df2004` (20230223_git), FBoW `c6e3c29e3332`, stella_vslam `e445b5452535`, FBoW_orb_vocab `708407ae4cd5`; FAST_LIO = commit do port local (`git -C … rev-parse HEAD`) registrado em `run.json`. Mudanças em código de terceiros só via `patches/*.patch`.
- VOs alimentadas **respeitando os timestamps** (taxa `--rate`, padrão 1.0) — nada de rodar à velocidade máxima.
- Downloads grandes do RELLIS (00000) **condicionados ao resultado do preflight (Task 9)**, que tem três saídas (A/B/C). BotanicGarden 1018-13 só depois dos smoke tests.
- Métodos: nomes canônicos `orbslam3`, `stella`, `fastlio`, `kissicp`.

## Review Focus

1. **Método que nunca inicializa / roda vazio** (ex.: ORB-SLAM3 perde tracking a sequência inteira) — o pipeline deve produzir colunas do método com `valid=0`, cobertura 0 e ATE vazio, não quebrar. Teste em Task 7 (`test_build_with_empty_method`) e Task 8 (`test_metrics_no_eligible_segment`).
2. **Timestamps duplicados ou fora de ordem** num `poses_causal.tum` (comum em logs de SLAM após reset) — devem ser ordenados e deduplicados (mantém a última) antes da amostragem. Teste em Task 3 (`test_load_run_sorts_and_dedups`).
3. **Grade começando antes da primeira pose do método** — primeiros passos com `valid=0`, `src_ts` vazio (−1), sem exceção. Teste em Task 4 (`test_causal_before_first_pose`).
4. **GT não cobre toda a grade** (GT começa depois/termina antes do LiDAR) — `gt_*` = NaN nessas linhas e `m_err_*` = NaN; linhas mantidas. Teste em Task 4 (`test_gt_deltas_out_of_range_nan`).
5. **Nuvem com campo de tempo ausente ou inconsistente** (ex.: todos zeros) — `deskew=false` e registro em `meta.json`, sem abortar. Teste em Task 5 (`test_constant_times_rejected`).

---

## Estrutura de arquivos

```
odom-fusion-dataset/
  pyproject.toml
  ofd/__init__.py
  ofd/se3.py            # matemática de pose (TUM <-> 4x4, ΔT, conjugação, SLERP)
  ofd/tracks.py         # formato de execução comum: load_run / write_run / segmentos
  ofd/sync.py           # amostragem causal, ΔT por método, GT na grade, erros
  ofd/pointtime.py      # semântica e normalização do tempo por ponto
  ofd/indicators.py     # fitness / inlier_rmse / unmatched_ratio / variância causal
  ofd/schema.py         # papéis de coluna + checagem de vazamento
  ofd/build_dataset.py  # tabela final por sequência
  ofd/evaluate.py       # ATE por segmento, RPE, cobertura
  ofd/config.py         # leitura de configs/<dataset>/dataset.yaml
  ofd/extract.py        # bag ROS1 -> imagens / nuvens npz / gt.tum / meta.json
  ofd/preflight_rellis.py
  ofd/run_kissicp.py
  ofd/run_fastlio.py    # orquestra conversão + bag play + gravador
  ofd/run_vo.py         # executa binários VO e converte logs
  ofd/lidar_indicators.py  # aplica indicators.py sobre uma execução LiDAR
  tools/fastlio_recorder.py   # rclpy (python do sistema), grava /Odometry
  tools/vo_runners/orbslam3_stereo_log.cc
  tools/vo_runners/stella_stereo_log.cc
  tools/vo_runners/CMakeLists.txt
  patches/orbslam3/*.patch
  configs/botanic/dataset.yaml, orbslam3.yaml, stella.yaml, fastlio.yaml
  configs/rellis/dataset.yaml, orbslam3.yaml, stella.yaml, fastlio.yaml
  scripts/setup_env.sh, scripts/build_orbslam3.sh, scripts/build_stella.sh, scripts/build_fastlio.sh
  scripts/run_sequence.sh
  tests/...
  data/ (fora do git)
```

## Formato de execução comum (contrato entre adaptadores e núcleo)

`data/runs/<seq>/<method>/`:
- `poses_causal.tum` — `ts_s x y z qx qy qz qw`, pose do **sensor do método** (câmera esquerda p/ VO, IMU/body p/ FAST-LIO, LiDAR p/ KISS-ICP) no mundo do método, **emitida no instante** do frame. Só frames com tracking OK. Timestamp = instante de disponibilidade: `end_ns` do scan (LiDAR) ou timestamp da imagem (VO).
- `state.csv` — `ts_ns,ok,map_id` com **uma linha por frame/scan de entrada**, inclusive os que não geraram pose (ok=0). Mesmo `ts_ns` usado em `poses_causal.tum`.
- `indicators.csv` — `ts_ns,<colunas>`; VO: `inliers,n_features,reproj_err,tracked_ratio`; LiDAR: `fitness,inlier_rmse,unmatched_ratio,n_points`.
- `run.json` — `{"method","uses_imu","sensor_frame","deskew","config","version","max_age_ms"}`.

---

### Task 1: Ambiente Python e esqueleto do projeto

**Files:**
- Create: `pyproject.toml`, `ofd/__init__.py`, `tests/__init__.py`, `scripts/setup_env.sh`, `scripts/test.sh`, `tests/test_smoke_import.py`

**Interfaces:**
- Produces: venv em `.venv/` com todas as dependências; pacote importável `ofd`.

- [ ] **Step 1: Criar `pyproject.toml`**

```toml
[project]
name = "ofd"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "numpy>=1.26", "scipy>=1.11", "pandas>=2.1", "pyarrow>=15",
  "open3d>=0.19", "rosbags>=0.10", "kiss-icp>=1.2", "opencv-python-headless>=4.9",
  "pyyaml>=6", "matplotlib>=3.8", "gdown>=5.2",
]
[project.optional-dependencies]
dev = ["pytest>=8"]
[tool.setuptools]
packages = ["ofd"]
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Criar `scripts/setup_env.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install -U pip
if [ -f requirements.lock ]; then
  .venv/bin/pip install -r requirements.lock
  .venv/bin/pip install --no-deps -e .
else
  .venv/bin/pip install -e '.[dev]'
  .venv/bin/pip freeze --exclude-editable > requirements.lock   # trava versões na 1ª instalação
fi
.venv/bin/python -c "import sys, open3d, kiss_icp, rosbags, pandas; assert sys.version_info[:2] == (3, 12); print('env ok')"
```

- [ ] **Step 2b: `scripts/test.sh`** — o `.bashrc` faz `source /opt/ros/jazzy/setup.bash`, e os plugins pytest do ROS (via `PYTHONPATH`) quebram o pytest do venv (`ModuleNotFoundError: lark`). Todos os testes rodam por este wrapper:

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")/.."
exec env -u PYTHONPATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest "$@"
```

- [ ] **Step 3: Teste de import** — `tests/test_smoke_import.py`

```python
def test_import():
    import ofd  # noqa: F401
```

`ofd/__init__.py` e `tests/__init__.py`: vazios (o segundo permite `from tests.test_x import helper` entre testes).

- [ ] **Step 4: Rodar**

Run: `bash scripts/setup_env.sh && scripts/test.sh -q`
Expected: `env ok` e `1 passed`; `requirements.lock` criado.

- [ ] **Step 5: Checkpoint de reprodutibilidade** — recriar do zero **a partir do lock** e comparar:

```bash
mv .venv .venv.first
bash scripts/setup_env.sh
diff <(.venv.first/bin/pip freeze --exclude-editable) <(.venv/bin/pip freeze --exclude-editable) && echo "lock reproduz"
scripts/test.sh -q
rm -rf .venv.first
{ echo "# Ambiente"; echo; echo "- Python: $(.venv/bin/python -V)"; echo "- SO: $(lsb_release -ds)";
  echo "- Gerado em: $(date -I)"; echo; echo "Versões resolvidas: ver \`requirements.lock\`."; } > docs/ENV.md
```
Expected: `lock reproduz` e `1 passed`. **Não avançar para a Task 2 se a recriação pelo lock falhar.**

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml requirements.lock docs/ENV.md ofd/__init__.py tests/__init__.py scripts/setup_env.sh scripts/test.sh tests/test_smoke_import.py
git commit -m "chore: ambiente python travado e esqueleto do pacote ofd"
```

---

### Task 2: `ofd/se3.py` — matemática de pose

**Files:**
- Create: `ofd/se3.py`
- Test: `tests/test_se3.py`

**Interfaces:**
- Produces:
  - `to_mat(t: ndarray(3), q_xyzw: ndarray(4)) -> ndarray(4,4)`
  - `to_vec(T) -> ndarray(7)` `[x,y,z,qx,qy,qz,qw]`, qw ≥ 0
  - `delta(T_prev, T_cur) -> ndarray(4,4)` = `inv(T_prev) @ T_cur`
  - `conjugate(dT_S, T_L_S) -> ndarray(4,4)` = `T_L_S @ dT_S @ inv(T_L_S)`
  - `inv(T) -> ndarray(4,4)`
  - `rot_angle(T) -> float` (rad)
  - `log_twist(T) -> ndarray(6)` `[vx,vy,vz,wx,wy,wz]` (logaritmo em se(3)); `exp_twist(xi) -> ndarray(4,4)`
  - `interp(ts_ns: ndarray[int64], Ts: ndarray(N,4,4), t_ns: int) -> ndarray(4,4) | None` (None fora do intervalo)
  - `load_tum(path) -> (ts_ns: ndarray[int64], Ts: ndarray(N,4,4))`
  - `save_tum(path, ts_ns, Ts) -> None`

- [ ] **Step 1: Testes que falham** — `tests/test_se3.py`

```python
import numpy as np
from scipy.spatial.transform import Rotation as R
from ofd import se3


def rand_T(seed):
    rng = np.random.default_rng(seed)
    T = np.eye(4)
    T[:3, :3] = R.random(random_state=seed).as_matrix()
    T[:3, 3] = rng.normal(size=3)
    return T


def test_vec_roundtrip_and_qw_positive():
    T = rand_T(1)
    v = se3.to_vec(T)
    assert v[6] >= 0
    np.testing.assert_allclose(se3.to_mat(v[:3], v[3:]), T, atol=1e-9)


def test_qw_sign_normalized():
    q = R.from_euler("z", 200, degrees=True).as_quat()  # qw < 0 para 200°
    T = se3.to_mat(np.zeros(3), q)
    assert se3.to_vec(T)[6] >= 0


def test_delta_composes_back():
    A, B = rand_T(2), rand_T(3)
    np.testing.assert_allclose(A @ se3.delta(A, B), B, atol=1e-9)


def test_delta_translation_in_previous_body_frame():
    A = se3.to_mat(np.zeros(3), R.from_euler("z", 90, degrees=True).as_quat())
    B = A.copy(); B[:3, 3] = [0, 1, 0]  # andou +y no mundo = +x no corpo de A
    np.testing.assert_allclose(se3.delta(A, B)[:3, 3], [1, 0, 0], atol=1e-9)


def test_conjugate_matches_frame_change():
    T_L_S = rand_T(4)
    A_S, B_S = rand_T(5), rand_T(6)
    A_L = A_S @ se3.inv(T_L_S)
    B_L = B_S @ se3.inv(T_L_S)
    np.testing.assert_allclose(se3.conjugate(se3.delta(A_S, B_S), T_L_S),
                               se3.delta(A_L, B_L), atol=1e-9)


def test_interp_midpoint_and_out_of_range():
    A = np.eye(4)
    B = se3.to_mat(np.array([2.0, 0, 0]), R.from_euler("z", 90, degrees=True).as_quat())
    ts = np.array([0, 100], dtype=np.int64)
    M = se3.interp(ts, np.stack([A, B]), 50)
    np.testing.assert_allclose(M[:3, 3], [1, 0, 0], atol=1e-9)
    assert abs(se3.rot_angle(M) - np.pi / 4) < 1e-9
    assert se3.interp(ts, np.stack([A, B]), 101) is None
    assert se3.interp(ts, np.stack([A, B]), -1) is None


def test_twist_roundtrip_and_pure_translation():
    T = rand_T(9)
    np.testing.assert_allclose(se3.exp_twist(se3.log_twist(T)), T, atol=1e-9)
    P = np.eye(4); P[:3, 3] = [1.0, 2.0, 3.0]
    np.testing.assert_allclose(se3.log_twist(P), [1, 2, 3, 0, 0, 0], atol=1e-12)


def test_twist_small_rotation_stable():
    T = se3.to_mat([0.1, 0, 0], R.from_rotvec([0, 0, 1e-12]).as_quat())
    assert np.all(np.isfinite(se3.log_twist(T)))


def test_tum_roundtrip(tmp_path):
    ts = np.array([1_700_000_000_123_456_789, 1_700_000_000_223_456_789], dtype=np.int64)
    Ts = np.stack([rand_T(7), rand_T(8)])
    p = tmp_path / "x.tum"
    se3.save_tum(p, ts, Ts)
    ts2, Ts2 = se3.load_tum(p)
    assert np.all(np.abs(ts2 - ts) < 1000)  # < 1 µs
    np.testing.assert_allclose(Ts2, Ts, atol=1e-6)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `scripts/test.sh tests/test_se3.py -q`
Expected: FAIL (`cannot import name 'se3'`).

- [ ] **Step 3: Implementar `ofd/se3.py`**

```python
"""Pose math. Convention: T_W_B maps B->W; delta(T_prev, T_cur) = inv(T_prev) @ T_cur."""
from decimal import Decimal
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp


def to_mat(t, q_xyzw):
    T = np.eye(4)
    T[:3, :3] = R.from_quat(np.asarray(q_xyzw, float)).as_matrix()
    T[:3, 3] = np.asarray(t, float)
    return T


def to_vec(T):
    q = R.from_matrix(T[:3, :3]).as_quat()
    if q[3] < 0:
        q = -q
    return np.concatenate([T[:3, 3], q])


def inv(T):
    Ti = np.eye(4)
    Ti[:3, :3] = T[:3, :3].T
    Ti[:3, 3] = -T[:3, :3].T @ T[:3, 3]
    return Ti


def delta(T_prev, T_cur):
    return inv(T_prev) @ T_cur


def conjugate(dT_S, T_L_S):
    return T_L_S @ dT_S @ inv(T_L_S)


def rot_angle(T):
    return float(np.linalg.norm(R.from_matrix(T[:3, :3]).as_rotvec()))


def _hat(w):
    return np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])


def log_twist(T):
    w = R.from_matrix(T[:3, :3]).as_rotvec()
    th = np.linalg.norm(w)
    W = _hat(w)
    if th < 1e-8:
        V_inv = np.eye(3) - 0.5 * W + W @ W / 12.0
    else:
        V_inv = np.eye(3) - 0.5 * W + (1 - th * np.sin(th) / (2 * (1 - np.cos(th)))) / th**2 * (W @ W)
    return np.concatenate([V_inv @ T[:3, 3], w])


def exp_twist(xi):
    v, w = np.asarray(xi[:3], float), np.asarray(xi[3:], float)
    th = np.linalg.norm(w)
    W = _hat(w)
    if th < 1e-8:
        V = np.eye(3) + 0.5 * W
    else:
        V = np.eye(3) + (1 - np.cos(th)) / th**2 * W + (th - np.sin(th)) / th**3 * (W @ W)
    T = np.eye(4)
    T[:3, :3] = R.from_rotvec(w).as_matrix()
    T[:3, 3] = V @ v
    return T


def interp(ts_ns, Ts, t_ns):
    ts_ns = np.asarray(ts_ns, dtype=np.int64)
    if len(ts_ns) == 0 or t_ns < ts_ns[0] or t_ns > ts_ns[-1]:
        return None
    j = int(np.searchsorted(ts_ns, t_ns, side="left"))
    if ts_ns[j] == t_ns:
        return Ts[j].copy()
    i = j - 1
    a = (t_ns - ts_ns[i]) / (ts_ns[j] - ts_ns[i])
    out = np.eye(4)
    out[:3, 3] = (1 - a) * Ts[i][:3, 3] + a * Ts[j][:3, 3]
    slerp = Slerp([0.0, 1.0], R.from_matrix(np.stack([Ts[i][:3, :3], Ts[j][:3, :3]])))
    out[:3, :3] = slerp([a]).as_matrix()[0]
    return out


def _s_to_ns(tok: str) -> int:
    return int((Decimal(tok) * 1_000_000_000).to_integral_value())


def load_tum(path):
    ts, Ts = [], []
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        tok = line.split()
        ts.append(_s_to_ns(tok[0]))
        v = np.array([float(x) for x in tok[1:8]])
        Ts.append(to_mat(v[:3], v[3:]))
    return np.array(ts, dtype=np.int64), (np.stack(Ts) if Ts else np.zeros((0, 4, 4)))


def save_tum(path, ts_ns, Ts):
    with open(path, "w") as f:
        for t, T in zip(ts_ns, Ts):
            v = to_vec(T)
            f.write(f"{int(t) // 1_000_000_000}.{int(t) % 1_000_000_000:09d} "
                    + " ".join(f"{x:.9f}" for x in v) + "\n")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `scripts/test.sh tests/test_se3.py -q`
Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add ofd/se3.py tests/test_se3.py
git commit -m "feat(se3): convenção de pose, ΔT, conjugação, SLERP, log/exp se(3) e I/O TUM"
```

---

### Task 3: `ofd/tracks.py` — formato de execução comum e segmentos

**Files:**
- Create: `ofd/tracks.py`
- Test: `tests/test_tracks.py`

**Interfaces:**
- Consumes: `se3.load_tum`, `se3.save_tum`
- Produces:
  - `@dataclass Track: ts_ns: ndarray[int64]; Ts: ndarray(N,4,4); segment: ndarray[int64]`
  - `segments_from_state(state: DataFrame[ts_ns, ok, map_id]) -> DataFrame[ts_ns, ok, segment]` — segmento novo a cada transição ok 0→1 ou mudança de `map_id`.
  - `load_run(run_dir) -> (Track, indicators: DataFrame indexado por ts_ns, run_meta: dict)`
  - `write_run(run_dir, ts_ns, Ts, state_df, indicators_df, meta) -> None`

- [ ] **Step 1: Testes** — `tests/test_tracks.py`

```python
import json
import numpy as np
import pandas as pd
from ofd import tracks, se3


def test_segments_increment_on_loss_and_map_change():
    st = pd.DataFrame({"ts_ns": [1, 2, 3, 4, 5, 6], "ok": [1, 1, 0, 1, 1, 1],
                       "map_id": [0, 0, 0, 0, 1, 1]})
    seg = tracks.segments_from_state(st)
    assert list(seg["segment"]) == [0, 0, -1, 1, 2, 2]


def _write(run, ts, ok, map_id=None):
    run.mkdir(parents=True, exist_ok=True)
    Ts = np.stack([np.eye(4)] * len(ts))
    for i, T in enumerate(Ts):
        T[0, 3] = i
    st = pd.DataFrame({"ts_ns": ts, "ok": ok, "map_id": map_id or [0] * len(ts)})
    good = [t for t, o in zip(ts, ok) if o]
    tracks.write_run(run, np.array(good, dtype=np.int64), Ts[: len(good)], st,
                     pd.DataFrame({"ts_ns": ts, "inliers": range(len(ts))}),
                     {"method": "x", "uses_imu": False})


def test_load_run_roundtrip(tmp_path):
    _write(tmp_path / "r", [10, 20, 30], [1, 1, 1])
    tr, ind, meta = tracks.load_run(tmp_path / "r")
    assert list(tr.ts_ns) == [10, 20, 30]
    assert list(tr.segment) == [0, 0, 0]
    assert meta["method"] == "x"
    assert ind.loc[20, "inliers"] == 1


def test_load_run_sorts_and_dedups(tmp_path):
    run = tmp_path / "r"; run.mkdir()
    Ts = np.stack([np.eye(4)] * 4)
    se3.save_tum(run / "poses_causal.tum", np.array([30, 10, 20, 20], dtype=np.int64), Ts)
    pd.DataFrame({"ts_ns": [10, 20, 30], "ok": [1, 1, 1], "map_id": [0, 0, 0]}).to_csv(run / "state.csv", index=False)
    pd.DataFrame({"ts_ns": [10, 20, 30]}).to_csv(run / "indicators.csv", index=False)
    (run / "run.json").write_text(json.dumps({"method": "x"}))
    tr, _, _ = tracks.load_run(run)
    assert list(tr.ts_ns) == [10, 20, 30]


def test_pose_on_lost_frame_is_dropped(tmp_path):
    run = tmp_path / "r"; run.mkdir()
    se3.save_tum(run / "poses_causal.tum", np.array([10, 20], dtype=np.int64), np.stack([np.eye(4)] * 2))
    pd.DataFrame({"ts_ns": [10, 20], "ok": [1, 0], "map_id": [0, 0]}).to_csv(run / "state.csv", index=False)
    pd.DataFrame({"ts_ns": [10, 20]}).to_csv(run / "indicators.csv", index=False)
    (run / "run.json").write_text("{}")
    tr, _, _ = tracks.load_run(run)
    assert list(tr.ts_ns) == [10]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `scripts/test.sh tests/test_tracks.py -q` → FAIL (import).

- [ ] **Step 3: Implementar `ofd/tracks.py`**

```python
"""Common run format: poses_causal.tum, state.csv, indicators.csv, run.json."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import se3


@dataclass
class Track:
    ts_ns: np.ndarray
    Ts: np.ndarray
    segment: np.ndarray


def segments_from_state(state: pd.DataFrame) -> pd.DataFrame:
    st = state.sort_values("ts_ns").reset_index(drop=True)
    seg, cur, prev_ok, prev_map = [], -1, False, None
    for ok, mid in zip(st["ok"].astype(bool), st["map_id"]):
        if ok and (not prev_ok or mid != prev_map):
            cur += 1
        seg.append(cur if ok else -1)
        prev_ok, prev_map = ok, mid
    return pd.DataFrame({"ts_ns": st["ts_ns"].astype(np.int64), "ok": st["ok"], "segment": seg})


def load_run(run_dir):
    run_dir = Path(run_dir)
    ts, Ts = se3.load_tum(run_dir / "poses_causal.tum")
    order = np.argsort(ts, kind="stable")
    ts, Ts = ts[order], Ts[order]
    keep = np.ones(len(ts), bool)
    keep[:-1] = ts[:-1] != ts[1:]  # keep last of duplicates
    ts, Ts = ts[keep], Ts[keep]
    seg = segments_from_state(pd.read_csv(run_dir / "state.csv")).set_index("ts_ns")["segment"]
    seg = seg[~seg.index.duplicated(keep="last")]
    s = seg.reindex(ts).fillna(-1).astype(np.int64).to_numpy()
    good = s >= 0
    track = Track(ts[good], Ts[good], s[good])
    ind = pd.read_csv(run_dir / "indicators.csv")
    ind = ind.drop_duplicates("ts_ns", keep="last").set_index("ts_ns").sort_index()
    meta = json.loads((run_dir / "run.json").read_text())
    return track, ind, meta


def write_run(run_dir, ts_ns, Ts, state_df, indicators_df, meta):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    se3.save_tum(run_dir / "poses_causal.tum", ts_ns, Ts)
    state_df.to_csv(run_dir / "state.csv", index=False)
    indicators_df.to_csv(run_dir / "indicators.csv", index=False)
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2))
```

- [ ] **Step 4: Rodar** — `scripts/test.sh tests/test_tracks.py -q` → `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add ofd/tracks.py tests/test_tracks.py
git commit -m "feat(tracks): formato comum de execução e segmentação por estado"
```

---

### Task 4: `ofd/sync.py` — amostragem causal, ΔT, GT e erros

**Files:**
- Create: `ofd/sync.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: `Track`, `se3.*`
- Produces:
  - `method_deltas(track: Track, grid_ns: ndarray[int64], T_L_S: ndarray(4,4), max_age_ms: float = 100.0) -> DataFrame` com colunas `dx,dy,dz,qx,qy,qz,qw,vx,vy,vz,wx,wy,wz,valid,src_ts,age_ms,dt_ms,segment_id,prev_src_ts` (uma linha por passo da grade; `src_ts=-1` se não há pose; `v*/w*` = `log_twist(ΔT)/(dt_ms/1000)`).
  - `gt_deltas(gt_ts: ndarray[int64], gt_Ts, grid_ns) -> DataFrame` colunas `gt_dx..gt_qw, gt_vx..gt_wz` (NaN quando fora do GT ou k=0).
  - `method_errors(md: DataFrame, track: Track, T_L_S, gt_ts, gt_Ts) -> DataFrame` colunas `err_t, err_r` (NaN se inválido ou GT ausente). GT assumido já no frame do LiDAR.

- [ ] **Step 1: Testes** — `tests/test_sync.py`

```python
import numpy as np
from ofd import sync, se3
from ofd.tracks import Track

MS = 1_000_000


def line_track(ts_ms, seg=None):
    Ts = []
    for i, _ in enumerate(ts_ms):
        T = np.eye(4); T[0, 3] = float(i); Ts.append(T)
    return Track(np.array(ts_ms, dtype=np.int64) * MS, np.stack(Ts),
                 np.array(seg if seg is not None else [0] * len(ts_ms), dtype=np.int64))


def test_strictly_causal_never_uses_future():
    tr = line_track([0, 95, 205])
    grid = np.array([0, 100, 200], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    assert list(md["src_ts"]) == [0, 95 * MS, 95 * MS]
    assert (md["src_ts"].to_numpy() <= grid).all()


def test_age_and_dt_and_validity():
    tr = line_track([0, 95, 190])
    grid = np.array([0, 100, 200], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4), max_age_ms=100)
    assert md["valid"].tolist() == [0, 1, 1]
    np.testing.assert_allclose(md["age_ms"], [0, 5, 10])
    np.testing.assert_allclose(md["dt_ms"].iloc[1:], [95, 95])
    np.testing.assert_allclose(md["dx"].iloc[1:], [1, 1])


def test_too_old_is_invalid():
    tr = line_track([0, 50])
    grid = np.array([0, 100, 300], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4), max_age_ms=100)
    assert md["valid"].iloc[2] == 0


def test_same_source_twice_is_invalid():
    tr = line_track([0, 10])
    grid = np.array([50, 60], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    assert md["valid"].iloc[1] == 0  # dt_ms == 0


def test_cross_segment_invalid():
    tr = line_track([0, 100, 200], seg=[0, 0, 1])
    grid = np.array([0, 100, 200], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    assert md["valid"].tolist() == [0, 1, 0]
    assert md["segment_id"].tolist() == [0, 0, 1]


def test_causal_before_first_pose():
    tr = line_track([200, 300])
    grid = np.array([0, 100, 200, 300], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    assert md["src_ts"].tolist()[:2] == [-1, -1]
    assert md["valid"].tolist() == [0, 0, 0, 1]


def test_qw_nonnegative():
    tr = line_track([0, 100])
    tr.Ts[1][:3, :3] = se3.to_mat([0, 0, 0], [0, 0, np.sin(np.radians(100)), np.cos(np.radians(100))])[:3, :3]
    md = sync.method_deltas(tr, np.array([0, 100], dtype=np.int64) * MS, np.eye(4))
    assert md["qw"].iloc[1] >= 0


def test_gt_deltas_out_of_range_nan():
    gt = line_track([100, 200, 300])
    grid = np.array([0, 100, 200, 300, 400], dtype=np.int64) * MS
    g = sync.gt_deltas(gt.ts_ns, gt.Ts, grid)
    assert np.isnan(g["gt_dx"].iloc[0]) and np.isnan(g["gt_dx"].iloc[1]) and np.isnan(g["gt_dx"].iloc[4])
    np.testing.assert_allclose(g["gt_dx"].iloc[2:4], [1, 1])


def test_twist_is_delta_over_dt():
    tr = line_track([0, 95, 190])
    md = sync.method_deltas(tr, np.array([0, 100, 200], dtype=np.int64) * MS, np.eye(4))
    np.testing.assert_allclose(md["vx"].iloc[1:], 1 / 0.095)
    np.testing.assert_allclose(md["wz"].iloc[1:], 0, atol=1e-12)
    g = sync.gt_deltas(tr.ts_ns, tr.Ts, np.array([0, 95, 190], dtype=np.int64) * MS)
    np.testing.assert_allclose(g["gt_vx"].iloc[1:], 1 / 0.095)


def test_errors_use_method_source_instants():
    tr = line_track([0, 95])           # método: 1 m em 95 ms
    gt_ts = np.array([0, 95], dtype=np.int64) * MS
    gt_Ts = tr.Ts.copy()               # GT idêntico nos mesmos instantes
    grid = np.array([0, 100], dtype=np.int64) * MS
    md = sync.method_deltas(tr, grid, np.eye(4))
    e = sync.method_errors(md, tr, np.eye(4), gt_ts, gt_Ts)
    assert e["err_t"].iloc[1] < 1e-9 and np.isnan(e["err_t"].iloc[0])
```

- [ ] **Step 2: Rodar e ver falhar** — `scripts/test.sh tests/test_sync.py -q` → FAIL.

- [ ] **Step 3: Implementar `ofd/sync.py`**

```python
"""Strictly causal sampling of method poses onto the LiDAR time grid."""
import numpy as np
import pandas as pd

from ofd import se3
from ofd.tracks import Track

VEC = ["dx", "dy", "dz", "qx", "qy", "qz", "qw"]
TW = ["vx", "vy", "vz", "wx", "wy", "wz"]


def _causal_index(ts_ns, grid_ns):
    # index of last pose with ts <= t, -1 if none
    return np.searchsorted(ts_ns, grid_ns, side="right") - 1


def method_deltas(track: Track, grid_ns, T_L_S, max_age_ms=100.0):
    grid_ns = np.asarray(grid_ns, dtype=np.int64)
    idx = _causal_index(track.ts_ns, grid_ns)
    n = len(grid_ns)
    out = {c: np.full(n, np.nan) for c in VEC + TW}
    src = np.where(idx >= 0, track.ts_ns[np.clip(idx, 0, None)] if len(track.ts_ns) else -1, -1)
    age = np.where(idx >= 0, (grid_ns - src) / 1e6, np.nan)
    seg = np.where(idx >= 0, track.segment[np.clip(idx, 0, None)] if len(track.ts_ns) else -1, -1)
    prev_src = np.full(n, -1, dtype=np.int64)
    dt = np.full(n, np.nan)
    valid = np.zeros(n, dtype=np.int64)
    fresh = (idx >= 0) & (age >= 0) & (age <= max_age_ms)
    for k in range(1, n):
        i, j = idx[k - 1], idx[k]
        if i < 0 or j < 0:
            continue
        prev_src[k] = track.ts_ns[i]
        dt[k] = (track.ts_ns[j] - track.ts_ns[i]) / 1e6
        if not (fresh[k] and fresh[k - 1]) or i == j or track.segment[i] != track.segment[j]:
            continue
        dT = se3.conjugate(se3.delta(track.Ts[i], track.Ts[j]), T_L_S)
        for c, v in zip(VEC, se3.to_vec(dT)):
            out[c][k] = v
        for c, v in zip(TW, se3.log_twist(dT) / (dt[k] / 1000.0)):
            out[c][k] = v
        valid[k] = 1
    df = pd.DataFrame(out)
    df["valid"] = valid
    df["src_ts"] = src.astype(np.int64)
    df["prev_src_ts"] = prev_src
    df["age_ms"] = age
    df["dt_ms"] = dt
    df["segment_id"] = seg.astype(np.int64)
    return df


def gt_deltas(gt_ts, gt_Ts, grid_ns):
    n = len(grid_ns)
    out = {f"gt_{c}": np.full(n, np.nan) for c in VEC + TW}
    prev = se3.interp(gt_ts, gt_Ts, int(grid_ns[0])) if n else None
    for k in range(1, n):
        cur = se3.interp(gt_ts, gt_Ts, int(grid_ns[k]))
        if prev is not None and cur is not None:
            dT = se3.delta(prev, cur)
            for c, v in zip(VEC, se3.to_vec(dT)):
                out[f"gt_{c}"][k] = v
            for c, v in zip(TW, se3.log_twist(dT) / ((grid_ns[k] - grid_ns[k - 1]) / 1e9)):
                out[f"gt_{c}"][k] = v
        prev = cur
    return pd.DataFrame(out)


def method_errors(md, track: Track, T_L_S, gt_ts, gt_Ts):
    n = len(md)
    err_t, err_r = np.full(n, np.nan), np.full(n, np.nan)
    for k in np.flatnonzero(md["valid"].to_numpy() == 1):
        a = se3.interp(gt_ts, gt_Ts, int(md["prev_src_ts"].iat[k]))
        b = se3.interp(gt_ts, gt_Ts, int(md["src_ts"].iat[k]))
        if a is None or b is None:
            continue
        dT_m = se3.to_mat(md.loc[k, ["dx", "dy", "dz"]].to_numpy(float),
                          md.loc[k, ["qx", "qy", "qz", "qw"]].to_numpy(float))
        E = se3.delta(se3.delta(a, b), dT_m)
        err_t[k] = float(np.linalg.norm(E[:3, 3]))
        err_r[k] = se3.rot_angle(E)
    return pd.DataFrame({"err_t": err_t, "err_r": err_r})
```

Nota: `method_errors` recebe `track`/`T_L_S` para manter a assinatura estável caso se queira recomputar a partir das poses; o ΔT já convertido vem de `md`.

- [ ] **Step 4: Rodar** — `scripts/test.sh tests/test_sync.py -q` → `10 passed`.

- [ ] **Step 5: Commit**

```bash
git add ofd/sync.py tests/test_sync.py
git commit -m "feat(sync): amostragem estritamente causal, ΔT por método, GT e erros"
```

---

### Task 5: `ofd/pointtime.py` — semântica do tempo por ponto

**Files:**
- Create: `ofd/pointtime.py`
- Test: `tests/test_pointtime.py`

**Interfaces:**
- Produces:
  - `UNIT_TO_S = {"s":1.0,"ms":1e-3,"us":1e-6,"ns":1e-9}`
  - `normalize(t_raw: ndarray, unit: str, ref: str, scan_stamp_ns: int, ring: ndarray|None = None) -> (t_norm: ndarray|None, info: dict)` — `t_norm` em [0, 1] ao longo do scan ou `None` se inválido; `info = {t_min_s, t_max_s, span_s, monotonic_frac, valid}` com tempos **relativos ao header** (s). `ref ∈ {"scan_start","scan_end","absolute"}`.
  - Validação: `0.08 ≤ span_s ≤ 0.12` **e** `monotonic_frac ≥ 0.99`, onde `monotonic_frac` = fração de passos não decrescentes do tempo na ordem original dos pontos (ordem de disparo), calculada **dentro de cada ring** quando `ring` é dado.

- [ ] **Step 1: Testes** — `tests/test_pointtime.py`

```python
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
```

- [ ] **Step 2: Rodar e ver falhar** — `scripts/test.sh tests/test_pointtime.py -q` → FAIL.

- [ ] **Step 3: Implementar `ofd/pointtime.py`**

```python
"""Per-point time semantics -> times normalized to [0, 1] across the scan (KISS-ICP convention)."""
import numpy as np

UNIT_TO_S = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9}
SPAN_LO, SPAN_HI, MONO_MIN = 0.08, 0.12, 0.99


def _monotonic_frac(rel, ring):
    if rel.size < 2:
        return 0.0
    if ring is None:
        return float(np.mean(np.diff(rel) >= 0))
    ok = tot = 0
    for r in np.unique(ring):
        d = np.diff(rel[ring == r])
        ok += int(np.sum(d >= 0)); tot += d.size
    return ok / tot if tot else 0.0


def normalize(t_raw, unit, ref, scan_stamp_ns, ring=None):
    info = {"t_min_s": np.nan, "t_max_s": np.nan, "span_s": np.nan, "monotonic_frac": 0.0, "valid": False}
    t = np.asarray(t_raw, dtype=np.float64)
    if t.size == 0 or unit not in UNIT_TO_S or ref not in ("scan_start", "scan_end", "absolute"):
        return None, info
    if ref == "absolute":
        rel = t * UNIT_TO_S[unit] - scan_stamp_ns * 1e-9  # ns absoluto em float64: erro ~256 ns, irrelevante
    else:
        rel = t * UNIT_TO_S[unit]  # relativo ao header (scan_end => valores <= 0)
    if not np.all(np.isfinite(rel)):
        return None, info
    info.update(t_min_s=float(rel.min()), t_max_s=float(rel.max()), span_s=float(rel.max() - rel.min()),
                monotonic_frac=_monotonic_frac(rel, None if ring is None else np.asarray(ring)))
    info["valid"] = bool(SPAN_LO <= info["span_s"] <= SPAN_HI and info["monotonic_frac"] >= MONO_MIN)
    if not info["valid"]:
        return None, info
    return (rel - rel.min()) / (rel.max() - rel.min()), info
```

- [ ] **Step 4: Rodar** — `scripts/test.sh tests/test_pointtime.py -q` → `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add ofd/pointtime.py tests/test_pointtime.py
git commit -m "feat(pointtime): normalização do tempo por ponto com validação de span e monotonicidade por ring"
```

---

### Task 6: `ofd/indicators.py` — indicadores LiDAR uniformes e variância causal

**Files:**
- Create: `ofd/indicators.py`
- Test: `tests/test_indicators.py`

**Interfaces:**
- Produces:
  - `registration_quality(src_xyz: ndarray(N,3), tgt_xyz: ndarray(M,3), dT: ndarray(4,4), voxel=0.25, max_corr=0.5, unmatched_dist=1.0) -> dict{fitness, inlier_rmse, unmatched_ratio, n_points}` — `dT` leva pontos do scan k (src) ao frame do scan k-1 (tgt), i.e. o ΔT_k.
  - `causal_rolling_var(s: pd.Series, H: int = 10) -> pd.Series`

- [ ] **Step 1: Testes** — `tests/test_indicators.py`

```python
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
from ofd import indicators


def scene(seed=0):
    rng = np.random.default_rng(seed)
    ground = np.c_[rng.uniform(-20, 20, (4000, 2)), np.zeros(4000)]
    wall = np.c_[rng.uniform(-20, 20, 2000), np.full(2000, 10.0), rng.uniform(0, 3, 2000)]
    pole = np.c_[np.full(500, 3.0), np.full(500, -4.0), rng.uniform(0, 4, 500)]
    return np.vstack([ground, wall, pole])


def make_dT():
    T = np.eye(4)
    T[:3, :3] = R.from_euler("z", 5, degrees=True).as_matrix()
    T[:3, 3] = [0.8, 0.1, 0.0]
    return T


def test_correct_delta_scores_high():
    tgt = scene()
    dT = make_dT()
    src = (np.linalg.inv(dT) @ np.c_[tgt, np.ones(len(tgt))].T).T[:, :3]  # scan k visto do frame k
    q = indicators.registration_quality(src, tgt, dT)
    assert q["fitness"] > 0.95 and q["inlier_rmse"] < 0.15 and q["unmatched_ratio"] < 0.02


def test_wrong_delta_scores_low():
    tgt = scene()
    dT = make_dT()
    src = (np.linalg.inv(dT) @ np.c_[tgt, np.ones(len(tgt))].T).T[:, :3]
    bad = dT.copy(); bad[2, 3] += 1.5  # erro vertical: o chão inteiro deixa de casar
    q = indicators.registration_quality(src, tgt, bad)
    assert q["fitness"] < 0.6 and q["unmatched_ratio"] > 0.2


def test_causal_variance_ignores_future():
    s = pd.Series(np.arange(30, dtype=float))
    a = indicators.causal_rolling_var(s, H=5)
    s2 = s.copy(); s2.iloc[20:] = 1e6
    b = indicators.causal_rolling_var(s2, H=5)
    pd.testing.assert_series_equal(a.iloc[:20], b.iloc[:20])
    assert np.isnan(a.iloc[0])
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar `ofd/indicators.py`**

```python
"""LiDAR quality indicators computed uniformly from each method's ΔT, plus causal rolling stats."""
import numpy as np
import open3d as o3d
import pandas as pd


def _pcd(xyz, voxel):
    p = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.asarray(xyz, dtype=np.float64)))
    return p.voxel_down_sample(voxel) if voxel > 0 else p


def registration_quality(src_xyz, tgt_xyz, dT, voxel=0.25, max_corr=0.5, unmatched_dist=1.0):
    src, tgt = _pcd(src_xyz, voxel), _pcd(tgt_xyz, voxel)
    ev = o3d.pipelines.registration.evaluate_registration(src, tgt, max_corr, dT)
    src_t = o3d.geometry.PointCloud(src).transform(dT)
    d = np.asarray(src_t.compute_point_cloud_distance(tgt))
    return {
        "fitness": float(ev.fitness),
        "inlier_rmse": float(ev.inlier_rmse),
        "unmatched_ratio": float(np.mean(d > unmatched_dist)) if d.size else np.nan,
        "n_points": int(len(src.points)),
    }


def causal_rolling_var(s: pd.Series, H: int = 10) -> pd.Series:
    return s.rolling(window=H, min_periods=2).var()
```

- [ ] **Step 4: Rodar** — `scripts/test.sh tests/test_indicators.py -q` → `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add ofd/indicators.py tests/test_indicators.py
git commit -m "feat(indicators): fitness/inlier_rmse/unmatched_ratio via Open3D e variância causal"
```

---

### Task 7: `ofd/schema.py` + `ofd/build_dataset.py`

**Files:**
- Create: `ofd/schema.py`, `ofd/build_dataset.py`, `ofd/config.py`
- Test: `tests/test_schema.py`, `tests/test_build_dataset.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `tracks.load_run`, `sync.method_deltas|gt_deltas|method_errors`, `indicators.causal_rolling_var`, `se3.load_tum`
- Produces:
  - `schema.METHODS = {"orbslam3":"vo","stella":"vo","fastlio":"lo","kissicp":"lo"}`
  - `schema.VO_IND = ["inliers","n_features","reproj_err","tracked_ratio"]`; `schema.LO_IND = ["fitness","inlier_rmse","unmatched_ratio","n_points"]`
  - `schema.build_schema(methods: dict[str,str]) -> dict[str,str]` (coluna → papel)
  - `schema.assert_no_leak(schema: dict) -> None` (levanta `ValueError`)
  - `build_dataset.build_sequence(seq_dir: Path, runs_dir: Path, T_L_S: dict[str, ndarray], dataset: str, gt_quality: str, max_age_ms=100.0, H=10) -> DataFrame`
  - `build_dataset.write_outputs(df, schema, out_dir: Path, seq: str) -> None` (parquet + csv + schema.json)
  - CLI: `python -m ofd.build_dataset --seq-dir data/extracted/<seq> --runs-dir data/runs/<seq> --config configs/<ds>/dataset.yaml --out data/output`

- [ ] **Step 1: Testes do schema** — `tests/test_schema.py`

```python
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
```

- [ ] **Step 2: Implementar `ofd/schema.py`**

```python
"""Column roles: metadata | feature | target | evaluation."""
METHODS = {"orbslam3": "vo", "stella": "vo", "fastlio": "lo", "kissicp": "lo"}
VEC = ["dx", "dy", "dz", "qx", "qy", "qz", "qw"]
TW = ["vx", "vy", "vz", "wx", "wy", "wz"]
VO_IND = ["inliers", "n_features", "reproj_err", "tracked_ratio"]
LO_IND = ["fitness", "inlier_rmse", "unmatched_ratio", "n_points"]
VAR_OF = {"vo": "reproj_err", "lo": "fitness"}


def build_schema(methods):
    s = {c: "metadata" for c in ["t", "seq", "dataset", "gt_quality"]}
    s.update({f"gt_{c}": "target" for c in VEC + TW})
    for m, kind in methods.items():
        for c in ["src_ts", "segment_id", "uses_imu"]:
            s[f"{m}_{c}"] = "metadata"
        for c in VEC + TW + ["valid", "dt_ms", "age_ms"]:
            s[f"{m}_{c}"] = "feature"
        for c in (VO_IND if kind == "vo" else LO_IND):
            s[f"{m}_{c}"] = "feature"
        s[f"{m}_{VAR_OF[kind]}_var_H"] = "feature"
        for c in ["err_t", "err_r"]:
            s[f"{m}_{c}"] = "evaluation"
    return s


def assert_no_leak(schema):
    bad = [c for c, r in schema.items() if r == "feature"
           and (c.startswith("gt_") or c.endswith("_err_t") or c.endswith("_err_r"))]
    if bad:
        raise ValueError(f"GT-derived columns marked as feature: {bad}")
```

- [ ] **Step 3: Rodar** — `scripts/test.sh tests/test_schema.py -q` → `2 passed`.

- [ ] **Step 4: Testes do build** — `tests/test_build_dataset.py`

```python
import json
import numpy as np
import pandas as pd
from ofd import build_dataset, schema, se3, tracks

MS = 1_000_000


def fake_seq(tmp_path, n=50, empty=None):
    seq, runs = tmp_path / "ext", tmp_path / "runs"
    seq.mkdir()
    grid = (np.arange(n) * 100 * MS + 1_000 * MS).astype(np.int64)
    pd.DataFrame({"ts_ns": grid, "end_ns": grid}).to_csv(seq / "lidar_stamps.csv", index=False)
    Ts = np.stack([np.eye(4)] * n)
    for i in range(n):
        Ts[i][0, 3] = 0.5 * i
    se3.save_tum(seq / "gt.tum", grid, Ts)
    for m, kind in schema.METHODS.items():
        st = pd.DataFrame({"ts_ns": grid, "ok": 0 if m == empty else 1, "map_id": 0})
        cols = schema.VO_IND if kind == "vo" else schema.LO_IND
        ind = pd.DataFrame({"ts_ns": grid, **{c: 1.0 for c in cols}})
        good = grid if m != empty else grid[:0]
        tracks.write_run(runs / m, good, Ts[: len(good)], st, ind, {"method": m, "uses_imu": m == "fastlio"})
    return seq, runs


def test_build_shape_and_values(tmp_path):
    seq, runs = fake_seq(tmp_path)
    df = build_dataset.build_sequence(seq, runs, {m: np.eye(4) for m in schema.METHODS}, "botanic", "survey")
    assert len(df) == 50
    s = schema.build_schema(schema.METHODS)
    assert set(s) == set(df.columns)
    v = df[df["kissicp_valid"] == 1]
    np.testing.assert_allclose(v["kissicp_dx"], 0.5)
    assert v["kissicp_err_t"].max() < 1e-6
    feat_cols = [c for c in df.columns if c.startswith("kissicp_") and s[c] == "feature" and not c.endswith("_var_H")]
    assert not v[feat_cols].isna().any().any()  # variância móvel começa com NaN por definição
    assert df["fastlio_uses_imu"].all() and not df["kissicp_uses_imu"].any()


def test_build_with_empty_method(tmp_path):
    seq, runs = fake_seq(tmp_path, empty="orbslam3")
    df = build_dataset.build_sequence(seq, runs, {m: np.eye(4) for m in schema.METHODS}, "botanic", "survey")
    assert (df["orbslam3_valid"] == 0).all()
    assert df["orbslam3_err_t"].isna().all()


def test_write_outputs(tmp_path):
    seq, runs = fake_seq(tmp_path)
    df = build_dataset.build_sequence(seq, runs, {m: np.eye(4) for m in schema.METHODS}, "botanic", "survey")
    s = schema.build_schema(schema.METHODS)
    build_dataset.write_outputs(df, s, tmp_path / "out", "seqA")
    assert (tmp_path / "out" / "seqA.parquet").exists()
    assert json.loads((tmp_path / "out" / "schema.json").read_text())["gt_dx"] == "target"
```

- [ ] **Step 5: Implementar `ofd/build_dataset.py`**

```python
"""Assemble the per-sequence table on the LiDAR time grid."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, indicators, schema, se3, sync, tracks


def build_sequence(seq_dir, runs_dir, T_L_S, dataset, gt_quality, max_age_ms=100.0, H=10):
    seq_dir, runs_dir = Path(seq_dir), Path(runs_dir)
    grid = pd.read_csv(seq_dir / "lidar_stamps.csv")["end_ns"].to_numpy(np.int64)  # instante de disponibilidade
    gt_ts, gt_Ts = se3.load_tum(seq_dir / "gt.tum")
    df = pd.DataFrame({"t": grid, "seq": seq_dir.name, "dataset": dataset, "gt_quality": gt_quality})
    df = pd.concat([df, sync.gt_deltas(gt_ts, gt_Ts, grid)], axis=1)
    for m, kind in schema.METHODS.items():
        track, ind, meta = tracks.load_run(runs_dir / m)
        md = sync.method_deltas(track, grid, T_L_S[m], max_age_ms)
        err = sync.method_errors(md, track, T_L_S[m], gt_ts, gt_Ts)
        cols = schema.VO_IND if kind == "vo" else schema.LO_IND
        src = md["src_ts"].to_numpy()
        ind_rows = ind.reindex(src)[cols].reset_index(drop=True)  # indicadores do frame de origem (causal)
        ind_rows.loc[md["valid"].to_numpy() == 0, :] = np.nan
        block = pd.concat([md.drop(columns=["prev_src_ts"]), ind_rows, err], axis=1)
        var_col = schema.VAR_OF[kind]
        block[f"{var_col}_var_H"] = indicators.causal_rolling_var(block[var_col], H)
        block["uses_imu"] = bool(meta.get("uses_imu", False))
        df = pd.concat([df, block.add_prefix(f"{m}_")], axis=1)
    return df[list(schema.build_schema(schema.METHODS))]


def write_outputs(df, sch, out_dir, seq):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    schema.assert_no_leak(sch)
    df.to_parquet(out_dir / f"{seq}.parquet", index=False)
    df.to_csv(out_dir / f"{seq}.csv", index=False)
    (out_dir / "schema.json").write_text(json.dumps(sch, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="data/output")
    a = ap.parse_args()
    cfg = config.load(a.config)
    df = build_sequence(a.seq_dir, a.runs_dir, cfg.T_L_S, cfg.name, cfg.gt_quality, cfg.max_age_ms, cfg.var_window)
    write_outputs(df, schema.build_schema(schema.METHODS), a.out, Path(a.seq_dir).name)


if __name__ == "__main__":
    main()
```

Nota: o indicador usado em k é o do **frame de origem** `src_ts(k)` — nunca de um frame posterior a t_k.

`build_dataset` e `evaluate` dependem de `ofd/config.py`; ele é criado **nesta task** (código e teste abaixo).

`tests/test_config.py`:

```python
import numpy as np
import yaml
from ofd import config


def test_load(tmp_path):
    d = {"name": "x", "gt_quality": "survey", "max_age_ms": 100, "var_window": 10,
         "image_encoding": "mono8",
         "topics": {"left": "/l", "right": "/r", "lidar": "/p", "imu": "/i", "gt": "/g"},
         "point_time": {"field": "time", "unit": "s", "ref": "scan_start"},
         "T_L_S": {m: list(np.eye(4).ravel()) for m in ["orbslam3", "stella", "fastlio", "kissicp"]}}
    p = tmp_path / "c.yaml"; p.write_text(yaml.safe_dump(d))
    c = config.load(p)
    assert c.T_L_S["fastlio"].shape == (4, 4) and c.point_time["unit"] == "s"


def test_rejects_non_se3(tmp_path):
    import pytest
    bad = list(np.eye(4).ravel()); bad[0] = 2.0
    d = {"name": "x", "gt_quality": "survey", "topics": {}, "point_time": {},
         "T_L_S": {"kissicp": bad}}
    p = tmp_path / "c.yaml"; p.write_text(yaml.safe_dump(d))
    with pytest.raises(ValueError):
        config.load(p)
```

`ofd/config.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml


@dataclass
class DatasetConfig:
    name: str
    gt_quality: str
    topics: dict
    point_time: dict
    T_L_S: dict
    max_age_ms: float = 100.0
    var_window: int = 10
    image_encoding: str = "mono8"


def load(path) -> DatasetConfig:
    d = yaml.safe_load(Path(path).read_text())
    T = {m: np.asarray(v, float).reshape(4, 4) for m, v in d["T_L_S"].items()}
    for m, M in T.items():
        if not np.allclose(M[3], [0, 0, 0, 1]) or not np.allclose(M[:3, :3] @ M[:3, :3].T, np.eye(3), atol=1e-4):
            raise ValueError(f"T_L_S[{m}] não é SE3 válida")
    return DatasetConfig(d["name"], d["gt_quality"], d["topics"], d["point_time"], T,
                         d.get("max_age_ms", 100.0), d.get("var_window", 10), d.get("image_encoding", "mono8"))
```

- [ ] **Step 6: Rodar** — `scripts/test.sh tests/test_schema.py tests/test_build_dataset.py tests/test_config.py -q` → `7 passed`.

- [ ] **Step 7: Commit**

```bash
git add ofd/schema.py ofd/build_dataset.py ofd/config.py tests/test_schema.py tests/test_build_dataset.py tests/test_config.py
git commit -m "feat(dataset): schema com papéis, checagem de vazamento e montagem da tabela"
```

---

### Task 8: `ofd/evaluate.py` — ATE por segmento, RPE, cobertura

**Files:**
- Create: `ofd/evaluate.py`
- Test: `tests/test_evaluate.py`

**Interfaces:**
- Consumes: `Track`, `tracks.load_run`, `tracks.segments_from_state`, `se3.*`, `config.load`
- Produces:
  - `umeyama_se3(src: ndarray(N,3), dst: ndarray(N,3)) -> ndarray(4,4)` (alinha src→dst, sem escala)
  - `segment_metrics(track: Track, T_L_S, gt_ts, gt_Ts, min_dur_s=30.0, min_len_m=20.0) -> DataFrame[segment, n, dur_s, len_m, eligible, ate_rmse]`
  - `aggregate_ate(seg_df) -> float` (NaN se nenhum elegível)
  - `rpe(track, T_L_S, gt_ts, gt_Ts, delta_m=10.0) -> dict{rpe_t_frame, rpe_r_frame, rpe_t_10m}`
  - `coverage(df_seq: DataFrame, method: str, state: DataFrame[ts_ns, ok, map_id]) -> dict{coverage, n_failures, n_resets, longest_s, longest_m}` — tudo na **grade**; falhas/resets vêm do **estado**; `longest_*` = maior sequência de passos válidos consecutivos do mesmo `segment_id`, em s (de `t[k−1]` a `t[j]`) e em m (soma de ‖gt_d(x,y,z)‖ nesses passos).
  - `gt_path_length(df_seq) -> float` (soma de ‖gt_d(x,y,z)‖ na grade, NaN → 0)
  - `evaluate_sequence(seq_dir, runs_dir, table, T_L_S, min_dur_s=30.0, min_len_m=20.0) -> DataFrame` uma linha por método, com `eligible_frac = min(1, Σ len_m elegíveis / gt_path_length)`.
  - CLI: `python -m ofd.evaluate --seq-dir … --runs-dir … --table data/output/<seq>.parquet --config … --out data/output/metrics.csv`

- [ ] **Step 1: Testes** — `tests/test_evaluate.py`

```python
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
from ofd import evaluate
from ofd.tracks import Track

S = 1_000_000_000


def straight(n, step=1.0, seg=None):
    Ts = np.stack([np.eye(4)] * n)
    for i in range(n):
        Ts[i][0, 3] = step * i
    ts = (np.arange(n) * S // 10).astype(np.int64)  # 10 Hz
    return Track(ts, Ts, np.array(seg if seg is not None else [0] * n, dtype=np.int64))


def test_umeyama_recovers_rigid():
    rng = np.random.default_rng(0)
    P = rng.normal(size=(100, 3))
    T = np.eye(4); T[:3, :3] = R.from_euler("xyz", [10, 20, 30], degrees=True).as_matrix(); T[:3, 3] = [1, 2, 3]
    Q = (T[:3, :3] @ P.T).T + T[:3, 3]
    np.testing.assert_allclose(evaluate.umeyama_se3(P, Q), T, atol=1e-9)


def test_perfect_track_zero_ate():
    gt = straight(400, 0.1)  # 39.9 s, 39.9 m
    sm = evaluate.segment_metrics(gt, np.eye(4), gt.ts_ns, gt.Ts)
    assert sm["eligible"].all() and sm["ate_rmse"].max() < 1e-9


def test_short_segments_not_eligible():
    seg = [0] * 100 + [1] * 310
    tr = straight(410, 0.1, seg)
    sm = evaluate.segment_metrics(tr, np.eye(4), tr.ts_ns, tr.Ts).set_index("segment")
    assert not sm.loc[0, "eligible"]   # 9.9 s
    assert sm.loc[1, "eligible"]       # 30.9 s, 30.9 m


def test_metrics_no_eligible_segment():
    tr = straight(50, 0.1)
    sm = evaluate.segment_metrics(tr, np.eye(4), tr.ts_ns, tr.Ts)
    assert np.isnan(evaluate.aggregate_ate(sm))


def test_aggregate_weighted_by_poses():
    sm = pd.DataFrame({"n": [100, 300], "eligible": [True, True], "ate_rmse": [1.0, 2.0]})
    assert abs(evaluate.aggregate_ate(sm) - np.sqrt((100 * 1 + 300 * 4) / 400)) < 1e-12


def table(valid, seg=None):
    n = len(valid)
    return pd.DataFrame({"t": np.arange(n) * S // 10, "m_valid": valid,
                         "m_segment_id": seg if seg is not None else [0] * n,
                         "gt_dx": 0.5, "gt_dy": 0.0, "gt_dz": 0.0})


def test_coverage_longest_and_failures_from_state():
    df = table([0, 1, 1, 1, 0, 0, 1, 1, 0, 1])
    state = pd.DataFrame({"ts_ns": range(6), "ok": [1, 1, 0, 1, 0, 1], "map_id": 0})
    c = evaluate.coverage(df, "m", state)
    assert abs(c["coverage"] - 0.6) < 1e-12
    assert c["n_failures"] == 2 and c["n_resets"] == 2
    assert abs(c["longest_s"] - 0.3) < 1e-9 and abs(c["longest_m"] - 1.5) < 1e-9


def test_repeated_sample_is_not_failure():
    # valid cai para 0 (amostra repetida) mas o estado nunca perdeu tracking
    df = table([0, 1, 0, 1, 1])
    state = pd.DataFrame({"ts_ns": range(5), "ok": 1, "map_id": 0})
    assert evaluate.coverage(df, "m", state)["n_failures"] == 0


def test_longest_breaks_on_segment_change():
    df = table([0, 1, 1, 1, 1], seg=[0, 0, 0, 1, 1])
    state = pd.DataFrame({"ts_ns": range(5), "ok": 1, "map_id": [0, 0, 0, 1, 1]})
    c = evaluate.coverage(df, "m", state)
    assert abs(c["longest_s"] - 0.2) < 1e-9


def test_gt_path_length_ignores_nan():
    df = table([0, 1, 1]); df.loc[0, "gt_dx"] = np.nan
    assert abs(evaluate.gt_path_length(df) - 1.0) < 1e-12
```

- [ ] **Step 2: Rodar e ver falhar** — `scripts/test.sh tests/test_evaluate.py -q` → FAIL.

- [ ] **Step 3: Implementar `ofd/evaluate.py`**

```python
"""Per-method trajectory metrics: segment ATE (eligible only), RPE, coverage on the grid."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, schema, se3, tracks
from ofd.tracks import Track


def umeyama_se3(src, dst):
    mu_s, mu_d = src.mean(0), dst.mean(0)
    C = (dst - mu_d).T @ (src - mu_s) / len(src)
    U, _, Vt = np.linalg.svd(C)
    D = np.eye(3)
    D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    T = np.eye(4)
    T[:3, :3] = U @ D @ Vt
    T[:3, 3] = mu_d - T[:3, :3] @ mu_s
    return T


def _to_lidar(Ts, T_L_S):
    Ti = se3.inv(T_L_S)
    return np.stack([T @ Ti for T in Ts]) if len(Ts) else Ts


def segment_metrics(track: Track, T_L_S, gt_ts, gt_Ts, min_dur_s=30.0, min_len_m=20.0):
    rows = []
    est = _to_lidar(track.Ts, T_L_S)
    for s in np.unique(track.segment):
        idx = np.flatnonzero(track.segment == s)
        pairs = [(i, se3.interp(gt_ts, gt_Ts, int(track.ts_ns[i]))) for i in idx]
        pairs = [(i, g) for i, g in pairs if g is not None]
        if len(pairs) < 3:
            rows.append(dict(segment=int(s), n=len(pairs), dur_s=0.0, len_m=0.0, eligible=False, ate_rmse=np.nan))
            continue
        P = np.stack([est[i][:3, 3] for i, _ in pairs])
        G = np.stack([g[:3, 3] for _, g in pairs])
        dur = (track.ts_ns[pairs[-1][0]] - track.ts_ns[pairs[0][0]]) / 1e9
        length = float(np.sum(np.linalg.norm(np.diff(G, axis=0), axis=1)))
        A = umeyama_se3(P, G)
        res = (A[:3, :3] @ P.T).T + A[:3, 3] - G
        rows.append(dict(segment=int(s), n=len(pairs), dur_s=dur, len_m=length,
                         eligible=bool(dur >= min_dur_s and length >= min_len_m),
                         ate_rmse=float(np.sqrt(np.mean(np.sum(res ** 2, axis=1))))))
    return pd.DataFrame(rows, columns=["segment", "n", "dur_s", "len_m", "eligible", "ate_rmse"])


def aggregate_ate(seg_df):
    e = seg_df[seg_df["eligible"]]
    if e.empty:
        return float("nan")
    return float(np.sqrt(np.sum(e["n"] * e["ate_rmse"] ** 2) / np.sum(e["n"])))


def rpe(track: Track, T_L_S, gt_ts, gt_Ts, delta_m=10.0):
    est = _to_lidar(track.Ts, T_L_S)
    gts = [se3.interp(gt_ts, gt_Ts, int(t)) for t in track.ts_ns]
    et, er, e10 = [], [], []
    for k in range(1, len(track.ts_ns)):
        if track.segment[k] != track.segment[k - 1] or gts[k] is None or gts[k - 1] is None:
            continue
        E = se3.delta(se3.delta(gts[k - 1], gts[k]), se3.delta(est[k - 1], est[k]))
        et.append(np.linalg.norm(E[:3, 3])); er.append(se3.rot_angle(E))
    for s in np.unique(track.segment):
        idx = [i for i in np.flatnonzero(track.segment == s) if gts[i] is not None]
        if len(idx) < 2:
            continue
        G = np.stack([gts[i][:3, 3] for i in idx])
        cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(G, axis=0), axis=1))]
        for a in range(len(idx)):
            b = int(np.searchsorted(cum, cum[a] + delta_m))
            if b >= len(idx):
                break
            i, j = idx[a], idx[b]
            E = se3.delta(se3.delta(gts[i], gts[j]), se3.delta(est[i], est[j]))
            e10.append(np.linalg.norm(E[:3, 3]))

    def rm(x):
        return float(np.sqrt(np.mean(np.square(x)))) if x else float("nan")
    return {"rpe_t_frame": rm(et), "rpe_r_frame": rm(er), "rpe_t_10m": rm(e10)}


def _step_len(df_seq):
    return np.nan_to_num(np.linalg.norm(df_seq[["gt_dx", "gt_dy", "gt_dz"]].to_numpy(float), axis=1))


def gt_path_length(df_seq):
    return float(_step_len(df_seq).sum())


def coverage(df_seq, method, state):
    v = df_seq[f"{method}_valid"].to_numpy().astype(int)
    seg = df_seq[f"{method}_segment_id"].to_numpy()
    t = df_seq["t"].to_numpy(np.int64)
    step = _step_len(df_seq)
    st = state.sort_values("ts_ns")
    ok = st["ok"].to_numpy().astype(int)
    n_fail = int(np.sum((ok[:-1] == 1) & (ok[1:] == 0)))
    segs = tracks.segments_from_state(st)["segment"]
    n_resets = max(0, int(segs[segs >= 0].nunique()) - 1)
    best_s = best_m = 0.0
    start = None
    for k in range(len(v)):
        cont = v[k] == 1 and (start is not None and seg[k] == seg[k - 1])
        if v[k] == 1 and not cont:
            start = k
        if v[k] != 1:
            start = None
            continue
        best_s = max(best_s, (t[k] - t[start - 1]) / 1e9 if start > 0 else 0.0)
        best_m = max(best_m, float(step[start:k + 1].sum()))
    return {"coverage": float(v.mean()) if len(v) else 0.0, "n_failures": n_fail, "n_resets": n_resets,
            "longest_s": best_s, "longest_m": best_m}


def evaluate_sequence(seq_dir, runs_dir, table, T_L_S, min_dur_s=30.0, min_len_m=20.0):
    gt_ts, gt_Ts = se3.load_tum(Path(seq_dir) / "gt.tum")
    total = gt_path_length(table)
    rows = []
    for m in schema.METHODS:
        run = Path(runs_dir) / m
        tr, _, meta = tracks.load_run(run)
        sm = segment_metrics(tr, T_L_S[m], gt_ts, gt_Ts, min_dur_s, min_len_m)
        el = sm[sm["eligible"]]
        rows.append({"seq": Path(seq_dir).name, "method": m, "uses_imu": meta.get("uses_imu", False),
                     "ate_rmse": aggregate_ate(sm),
                     "eligible_frac": min(1.0, float(el["len_m"].sum() / total)) if total > 0 else 0.0,
                     "n_segments": len(sm), "n_eligible": len(el),
                     **rpe(tr, T_L_S[m], gt_ts, gt_Ts),
                     **coverage(table, m, pd.read_csv(run / "state.csv"))})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="data/output/metrics.csv")
    a = ap.parse_args()
    cfg = config.load(a.config)
    res = evaluate_sequence(a.seq_dir, a.runs_dir, pd.read_parquet(a.table), cfg.T_L_S)
    out = Path(a.out)
    if out.exists():
        old = pd.read_csv(out)
        res = pd.concat([old[old["seq"] != res["seq"].iat[0]], res])
    res.to_csv(out, index=False)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
```

Nota sobre `longest_s`: um passo válido k representa o movimento de `t[k−1]` a `t[k]`; por isso a duração de uma sequência de passos válidos k..j é `t[j] − t[k−1]` (no teste, passos 1..3 → `t[3] − t[0]` = 0,3 s).

- [ ] **Step 4: Rodar** — `scripts/test.sh tests/test_evaluate.py -q` → `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add ofd/evaluate.py tests/test_evaluate.py
git commit -m "feat(evaluate): ATE por segmento elegível, RPE e cobertura na grade com falhas do estado"
```

---

### Task 9: `ofd/matching.py` + preflight do GT do RELLIS-3D (gate dos downloads do RELLIS)

**Files:**
- Create: `ofd/matching.py`, `ofd/preflight_rellis.py`, `docs/preflight_rellis.md` (resultado)
- Test: `tests/test_matching.py`

**Interfaces:**
- Produces:
  - `matching.match_monotonic(a_ns: ndarray[int64], b_ns: ndarray[int64], tol_ns: int) -> ndarray[int]` — para cada elemento de `a` (ordenado), índice em `b` (ordenado) ou −1; casamento **monotônico** (índices casados estritamente crescentes) e **um-para-um**, **ótimo**: maximiza primeiro o nº de pares e, entre os máximos, minimiza a soma de |a−b|. Só pares dentro da tolerância são candidatos (poucos por elemento), resolvido por programação dinâmica com árvore de Fenwick de máximo sobre o índice de `b` — O(P log m), P = nº de pares candidatos.
  - `preflight_rellis.bag_scan_stamps(bag, topic) -> ndarray[int64]`
  - Veredito A/B/C em `docs/preflight_rellis.md`.

- [ ] **Step 1: Testes** — `tests/test_matching.py`

```python
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
```

- [ ] **Step 2: Implementar `ofd/matching.py`**

```python
"""Optimal monotonic one-to-one matching of timestamp sequences.

Maximizes the number of pairs, then minimizes the total |a-b|. Only pairs within tol are candidates.
DP over a (in order) with a Fenwick tree of prefix-max over b's index; score = (count, -error).
"""
import numpy as np

_NEG = (-1, 0)


class _FenwickMax:
    def __init__(self, n):
        self.n = n
        self.val = [_NEG] * (n + 1)
        self.arg = [None] * (n + 1)

    def update(self, i, v, arg):  # position i (0-based)
        i += 1
        while i <= self.n:
            if v > self.val[i]:
                self.val[i], self.arg[i] = v, arg
            i += i & -i

    def query(self, i):  # max over positions [0, i) ; returns (score, arg)
        best, arg = (0, 0), None
        while i > 0:
            if self.val[i] > best:
                best, arg = self.val[i], self.arg[i]
            i -= i & -i
        return best, arg


def match_monotonic(a_ns, b_ns, tol_ns):
    a = np.asarray(a_ns, dtype=np.int64)
    b = np.asarray(b_ns, dtype=np.int64)
    out = np.full(len(a), -1, dtype=int)
    if len(a) == 0 or len(b) == 0:
        return out
    fw = _FenwickMax(len(b))
    node = {}  # (i, j) -> (score, prev_node)
    best_total, best_node = (0, 0), None
    for i, t in enumerate(a):
        lo = int(np.searchsorted(b, t - tol_ns, side="left"))
        hi = int(np.searchsorted(b, t + tol_ns, side="right"))
        row = []
        for j in range(lo, hi):
            prev_score, prev = fw.query(j)  # pares anteriores com índice de b < j (e de a < i)
            score = (prev_score[0] + 1, prev_score[1] - abs(int(b[j]) - int(t)))
            node[(i, j)] = (score, prev)
            row.append((j, score))
            if score > best_total:
                best_total, best_node = score, (i, j)
        for j, score in row:  # só depois da linha inteira: um elemento de a casa no máximo uma vez
            fw.update(j, score, (i, j))
    cur = best_node
    while cur is not None:
        out[cur[0]] = cur[1]
        cur = node[cur][1]
    return out
```

Run: `scripts/test.sh tests/test_matching.py -q` → `7 passed`.

- [ ] **Step 3: Baixar só o pequeno** (para `data/raw/rellis/`):
  - exemplo full-stack merged 60 s (4,2 GB): Google Drive id `1qSeOoY6xbQGjcrZycgPM8Ty37eKDjpJL`
  - "Ouster LiDAR Scan Poses files" (174 MB) — link na seção *Download* do README do RELLIS-3D
  - (se existir) arquivo de timestamps por scan da sequência — conferir no README (`Rellis_3D_os1_cloud_node_kitti_bin`, `poses`).

```bash
mkdir -p data/raw/rellis   # gdown já está no requirements.lock (Task 1)
.venv/bin/gdown 1qSeOoY6xbQGjcrZycgPM8Ty37eKDjpJL -O data/raw/rellis/example_fullstack.bag
```

- [ ] **Step 4: Inspecionar** — tópicos e janela de tempo do bag; formato do `poses.txt` (KITTI 3×4 por linha?); de qual sequência é o exemplo; se existe arquivo de tempos por scan; o que o README/paper diz sobre a **origem** do `poses.txt`.

```bash
.venv/bin/python -c "
from rosbags.highlevel import AnyReader; from pathlib import Path
with AnyReader([Path('data/raw/rellis/example_fullstack.bag')]) as r:
    print(r.start_time, r.end_time)
    for c in r.connections: print(c.topic, c.msgtype, c.msgcount)
"
ls -R data/raw/rellis | head -50
```

- [ ] **Step 5: Implementar `ofd/preflight_rellis.py`**

```python
"""Prove (or refute) the mapping RELLIS-3D bag scans -> poses.txt entries (monotonic, one-to-one)."""
import argparse
from pathlib import Path

import numpy as np
from rosbags.highlevel import AnyReader

from ofd.matching import match_monotonic


def bag_scan_stamps(bag, topic="/os1_cloud_node/points"):
    with AnyReader([Path(bag)]) as r:
        conns = [c for c in r.connections if c.topic == topic]
        out = []
        for c, _, raw in r.messages(connections=conns):
            h = r.deserialize(raw, c.msgtype).header.stamp
            out.append(h.sec * 1_000_000_000 + h.nanosec)
    return np.sort(np.array(out, dtype=np.int64))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--pose-times", required=True, help="1 timestamp (s) por linha, alinhado linha a linha ao poses.txt")
    ap.add_argument("--tol-ms", type=float, default=5.0)
    a = ap.parse_args()
    b = bag_scan_stamps(a.bag)
    p = np.sort((np.loadtxt(a.pose_times) * 1e9).astype(np.int64))
    m = match_monotonic(b, p, int(a.tol_ms * 1e6))
    frac = float((m >= 0).mean()) if len(m) else 0.0
    print(f"scans no bag: {len(b)}  casados: {(m >= 0).sum()} ({frac:.1%})  idx poses: {m[m >= 0][:1]}..{m[m >= 0][-1:]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Rodar e decidir** — escrever `docs/preflight_rellis.md` com: origem do `poses.txt`, formato, a que sequência pertence o exemplo, existência de tempos por scan, % casado. Veredito:
  - **A — amostra mapeável** (≥ 95% dos scans do exemplo casados um-para-um): smoke do RELLIS com GT; **liberar** download da 00000.
  - **B — amostra não mapeável, mas a sequência completa resolve** (ex.: tempos por scan só existem para a 00000 inteira, ou o exemplo é um recorte cujo deslocamento de índice é recuperável na sequência completa): smoke de 60 s **sem métricas de GT** (`gt.tum` vazio → `gt_*` NaN); **liberar só** a 00000 e repetir o preflight nela antes de usar o GT.
  - **C — GT incompatível / não verificável** (não há timestamps nem forma de casar): RELLIS **sai da etapa supervisionada**; pode ser processado sem GT para análise qualitativa; o artigo segue com BotanicGarden. Avisar o usuário.

- [ ] **Step 7: Commit**

```bash
git add ofd/matching.py ofd/preflight_rellis.py tests/test_matching.py docs/preflight_rellis.md
git commit -m "feat: casamento monotônico 1:1 de timestamps e preflight do GT do RELLIS"
```

---

### Task 10: `ofd/extract.py` + configs dos datasets

**Files:**
- Create: `ofd/extract.py`, `configs/botanic/dataset.yaml`, `configs/rellis/dataset.yaml`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: `config.load` / `DatasetConfig` (Task 7), `pointtime.normalize`, `se3`
- Produces:
  - `extract.extract(bag: Path, cfg: DatasetConfig, out: Path, t0_s: float|None, dur_s: float|None, gt_tum: Path|None) -> dict meta`
  - Saída: `out/images/{left,right}/<ts_ns>.png`, `out/images/stamps.csv` (pares esquerdo/direito), `out/clouds/<ts_ns>.npz` (xyz, intensity?, ring?, t_norm? — chave = header), `out/lidar_stamps.csv` (`ts_ns` = header, `end_ns` = header + `t_max_s` do scan, ou header se a semântica for desconhecida), `out/scans.csv` (`ts_ns,end_ns,t_min_s,t_max_s,span_s,monotonic_frac,valid`), `out/gt.tum` (no frame do LiDAR), `out/meta.json` (`deskew` = **todos** os scans válidos).
  - CLI: `python -m ofd.extract --bag <bag> --config configs/<ds>/dataset.yaml --out data/extracted/<seq> [--start S --duration S] [--gt-tum file]`

- [ ] **Step 1: Escrever `configs/botanic/dataset.yaml`**

Valores de extrínsecas copiados do arquivo de calibração do BotanicGarden (`calib/` no repositório GitHub, chaves `T_*`). Matrizes 4×4 **S→L** (sensor para LiDAR VLP16):

```yaml
name: botanic
gt_quality: survey
max_age_ms: 100
var_window: 10
image_encoding: mono8
topics:
  left: /dalsa_gray/left/image_raw
  right: /dalsa_gray/right/image_raw
  lidar: /velodyne_points
  imu: /imu/data
  gt: /gt_poses
point_time:
  field: time        # confirmar no Step 2 (nome do campo no PointCloud2 do VLP16)
  unit: s            # confirmar no Step 2
  ref: scan_start    # confirmar no Step 2
T_L_S:   # 4x4 row-major, sensor -> VLP16
  orbslam3: <copiar T_vlp16_cam0 = inv(T_cam0_vlp16) da calibração>
  stella:   <mesmo valor de orbslam3>
  fastlio:  <T_vlp16_xsens = inv(T_xsens_vlp16)>
  kissicp:  [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
```

`configs/rellis/dataset.yaml` análogo: `left: /nerian/left/image_raw`, `right: /nerian/right/image_raw`, `lidar: /os1_cloud_node/points`, `imu: /os1_cloud_node/imu`, `gt_quality: slam`, extrínsecas dos arquivos de calibração do RELLIS (`Nerian -> Ouster`, `Ouster IMU -> Ouster`).

> Os campos com `<copiar …>` são **dados a ler dos arquivos de calibração**, não decisões em aberto. O Step 2 imprime os campos reais do PointCloud2 para confirmar `point_time`.

- [ ] **Step 2: Inspecionar campos reais da nuvem** (depois do download do 1018-00 / exemplo RELLIS):

```bash
.venv/bin/python - <<'EOF'
from rosbags.highlevel import AnyReader; from pathlib import Path
import sys
bag, topic = "data/raw/botanic/1018-00.bag", "/velodyne_points"
with AnyReader([Path(bag)]) as r:
    c = [c for c in r.connections if c.topic == topic][0]
    for _, _, raw in r.messages(connections=[c]):
        m = r.deserialize(raw, c.msgtype)
        print([(f.name, f.datatype, f.offset) for f in m.fields], m.point_step, m.header.stamp)
        break
EOF
```
Atualizar `point_time` no yaml conforme o que aparecer; se não houver campo de tempo → `field: null`.

- [ ] **Step 3: Teste do extract com bag sintético** — `tests/test_extract.py`

Gera um bag ROS1 mínimo com `rosbags.rosbag1.Writer` (2 imagens mono8 por lado, 3 nuvens com campo `time`) e verifica saída.

```python
import numpy as np
from pathlib import Path
from rosbags.rosbag1 import Writer
from rosbags.typesys import Stores, get_typestore
from ofd import extract, config

TS = get_typestore(Stores.ROS1_NOETIC)
Image = TS.types["sensor_msgs/msg/Image"]
PC2 = TS.types["sensor_msgs/msg/PointCloud2"]
PF = TS.types["sensor_msgs/msg/PointField"]
Header = TS.types["std_msgs/msg/Header"]
Time = TS.types["builtin_interfaces/msg/Time"]


def hdr(ns):
    return Header(seq=0, stamp=Time(sec=ns // 10**9, nanosec=ns % 10**9), frame_id="x")


def cloud(ns, n=200):
    pts = np.zeros(n, dtype=[("x", "f4"), ("y", "f4"), ("z", "f4"), ("intensity", "f4"), ("time", "f4")])
    pts["x"] = np.linspace(1, 10, n); pts["time"] = np.linspace(0, 0.1, n)
    fields = [PF(name=k, offset=o, datatype=7, count=1) for k, o in
              [("x", 0), ("y", 4), ("z", 8), ("intensity", 12), ("time", 16)]]
    return PC2(header=hdr(ns), height=1, width=n, fields=fields, is_bigendian=False,
               point_step=20, row_step=20 * n, data=np.frombuffer(pts.tobytes(), np.uint8), is_dense=True)


def img(ns):
    return Image(header=hdr(ns), height=4, width=6, encoding="mono8", is_bigendian=0, step=6,
                 data=np.arange(24, dtype=np.uint8))


def make_bag(p):
    base = 1_700_000_000 * 10**9
    with Writer(p) as w:
        cl = w.add_connection("/l", Image.__msgtype__, typestore=TS)
        cr = w.add_connection("/r", Image.__msgtype__, typestore=TS)
        cp = w.add_connection("/p", PC2.__msgtype__, typestore=TS)
        for k in range(3):
            t = base + k * 100_000_000
            w.write(cp, t, TS.serialize_ros1(cloud(t), PC2.__msgtype__))
            w.write(cl, t, TS.serialize_ros1(img(t), Image.__msgtype__))
            w.write(cr, t, TS.serialize_ros1(img(t), Image.__msgtype__))
    return base


def test_extract(tmp_path):
    bag = tmp_path / "x.bag"; make_bag(bag)
    cfg = config.DatasetConfig("x", "survey", {"left": "/l", "right": "/r", "lidar": "/p", "imu": "/i", "gt": "/g"},
                               {"field": "time", "unit": "s", "ref": "scan_start"},
                               {m: np.eye(4) for m in ["orbslam3", "stella", "fastlio", "kissicp"]})
    meta = extract.extract(bag, cfg, tmp_path / "out", None, None, None)
    assert len(list((tmp_path / "out/images/left").glob("*.png"))) == 3
    z = np.load(sorted((tmp_path / "out/clouds").glob("*.npz"))[0])
    assert {"xyz", "intensity", "t_norm"} <= set(z.files)
    assert meta["deskew"] is True and meta["n_scans"] == 3
    st = __import__("pandas").read_csv(tmp_path / "out/lidar_stamps.csv")
    assert ((st["end_ns"] - st["ts_ns"]) > 90_000_000).all()  # end = header + ~0.1 s (ref scan_start)
    assert (tmp_path / "out/scans.csv").exists()


def test_extract_one_bad_scan_disables_deskew(tmp_path, monkeypatch):
    bag = tmp_path / "x.bag"; make_bag(bag)
    calls = {"n": 0}
    real = extract.pointtime.normalize

    def flaky(*a, **k):
        calls["n"] += 1
        return (None, {"t_min_s": 0, "t_max_s": 0, "span_s": 0, "monotonic_frac": 0, "valid": False}) \
            if calls["n"] == 2 else real(*a, **k)
    monkeypatch.setattr(extract.pointtime, "normalize", flaky)
    cfg = config.DatasetConfig("x", "survey", {"left": "/l", "right": "/r", "lidar": "/p", "imu": "/i", "gt": "/g"},
                               {"field": "time", "unit": "s", "ref": "scan_start"},
                               {m: np.eye(4) for m in ["orbslam3", "stella", "fastlio", "kissicp"]})
    meta = extract.extract(bag, cfg, tmp_path / "out", None, None, None)
    assert meta["deskew"] is False and meta["deskew_valid_frac"] < 1.0
```

- [ ] **Step 4: Implementar `ofd/extract.py`**

```python
"""ROS1 bag -> stereo PNGs, per-scan NPZ (all fields), lidar_stamps.csv, gt.tum (LiDAR frame), meta.json."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from rosbags.highlevel import AnyReader

from ofd import config, pointtime, se3

_DT = {1: "i1", 2: "u1", 3: "i2", 4: "u2", 5: "i4", 6: "u4", 7: "f4", 8: "f8"}


def stamp_ns(msg):
    return int(msg.header.stamp.sec) * 1_000_000_000 + int(msg.header.stamp.nanosec)


def cloud_to_struct(msg):
    dt = np.dtype({"names": [f.name for f in msg.fields],
                   "formats": [_DT[f.datatype] for f in msg.fields],
                   "offsets": [f.offset for f in msg.fields], "itemsize": msg.point_step})
    return np.frombuffer(bytes(msg.data), dtype=dt, count=msg.width * msg.height)


def image_to_array(msg):
    buf = np.frombuffer(bytes(msg.data), np.uint8)
    if msg.encoding in ("mono8", "8UC1"):
        return buf.reshape(msg.height, msg.step)[:, : msg.width]
    if msg.encoding in ("bgr8", "rgb8"):
        im = buf.reshape(msg.height, msg.step)[:, : msg.width * 3].reshape(msg.height, msg.width, 3)
        return cv2.cvtColor(im, cv2.COLOR_RGB2GRAY if msg.encoding == "rgb8" else cv2.COLOR_BGR2GRAY)
    if msg.encoding.startswith("bayer"):
        code = {"bayer_rggb8": cv2.COLOR_BayerRG2GRAY, "bayer_bggr8": cv2.COLOR_BayerBG2GRAY,
                "bayer_gbrg8": cv2.COLOR_BayerGB2GRAY, "bayer_grbg8": cv2.COLOR_BayerGR2GRAY}[msg.encoding]
        return cv2.cvtColor(buf.reshape(msg.height, msg.step)[:, : msg.width], code)
    raise ValueError(f"encoding não suportado: {msg.encoding}")


def extract(bag, cfg, out, t0_s=None, dur_s=None, gt_tum=None):
    out = Path(out)
    for d in ["images/left", "images/right", "clouds"]:
        (out / d).mkdir(parents=True, exist_ok=True)
    tp = cfg.topics
    left, right, scans, deskew_ok = {}, {}, [], []
    gt_rows = []
    with AnyReader([Path(bag)]) as r:
        start = r.start_time + int((t0_s or 0) * 1e9)
        stop = start + int(dur_s * 1e9) if dur_s else r.end_time + 1
        want = {tp["left"], tp["right"], tp["lidar"], tp.get("gt")}
        conns = [c for c in r.connections if c.topic in want]
        for c, t, raw in r.messages(connections=conns, start=start, stop=stop):
            m = r.deserialize(raw, c.msgtype)
            ts = stamp_ns(m)
            if c.topic in (tp["left"], tp["right"]):
                side = "left" if c.topic == tp["left"] else "right"
                cv2.imwrite(str(out / "images" / side / f"{ts}.png"), image_to_array(m))
                (left if side == "left" else right)[ts] = True
            elif c.topic == tp["lidar"]:
                a = cloud_to_struct(m)
                xyz = np.c_[a["x"], a["y"], a["z"]].astype(np.float32)
                fin = np.isfinite(xyz).all(1) & (np.linalg.norm(xyz, axis=1) > 0.1)
                rec = {"xyz": xyz[fin]}
                names = a.dtype.names
                if "intensity" in names:
                    rec["intensity"] = a["intensity"][fin].astype(np.float32)
                if "ring" in names:
                    rec["ring"] = a["ring"][fin].astype(np.int16)
                f = cfg.point_time.get("field")
                tn, info = None, {"t_min_s": np.nan, "t_max_s": np.nan, "span_s": np.nan,
                                  "monotonic_frac": 0.0, "valid": False}
                if f and f in names:
                    ring = a["ring"][fin] if "ring" in names else None
                    tn, info = pointtime.normalize(a[f][fin], cfg.point_time["unit"], cfg.point_time["ref"], ts, ring)
                if tn is not None:
                    rec["t_norm"] = tn.astype(np.float32)
                deskew_ok.append(tn is not None)
                end = ts + int(round(info["t_max_s"] * 1e9)) if info["valid"] else ts
                np.savez_compressed(out / "clouds" / f"{ts}.npz", **rec)
                scans.append({"ts_ns": ts, "end_ns": end, **info})
            elif c.topic == tp.get("gt"):
                p, q = m.pose.position, m.pose.orientation
                gt_rows.append((ts, se3.to_mat([p.x, p.y, p.z], [q.x, q.y, q.z, q.w])))
    pairs = sorted(set(left) & set(right))
    pd.DataFrame({"ts_ns": pairs}).to_csv(out / "images" / "stamps.csv", index=False)
    sc = pd.DataFrame(scans).sort_values("ts_ns")
    sc.to_csv(out / "scans.csv", index=False)
    sc[["ts_ns", "end_ns"]].to_csv(out / "lidar_stamps.csv", index=False)
    if gt_tum:
        ts_gt, Ts_gt = se3.load_tum(gt_tum)
    elif gt_rows:
        gt_rows.sort(key=lambda x: x[0])
        ts_gt = np.array([g[0] for g in gt_rows], dtype=np.int64)
        Ts_gt = np.stack([g[1] for g in gt_rows])
    else:
        ts_gt, Ts_gt = np.zeros(0, np.int64), np.zeros((0, 4, 4))
    se3.save_tum(out / "gt.tum", ts_gt, Ts_gt)  # GT já no frame do LiDAR (ver docs do dataset)
    frac = float(np.mean(deskew_ok)) if deskew_ok else 0.0
    meta = {"bag": str(bag), "n_scans": len(scans), "n_stereo": len(pairs), "n_gt": int(len(ts_gt)),
            "point_time": cfg.point_time, "deskew_valid_frac": frac, "deskew": bool(deskew_ok) and frac == 1.0,
            "unpaired_left": len(set(left) - set(right)), "unpaired_right": len(set(right) - set(left))}
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=float)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--gt-tum")
    a = ap.parse_args()
    print(json.dumps(extract(a.bag, config.load(a.config), a.out, a.start, a.duration, a.gt_tum), indent=2))


if __name__ == "__main__":
    main()
```

Nota sobre o GT do BotanicGarden: o arquivo GT-pose (TUM) rastreia o frame do VLP16 — passar via `--gt-tum`. Se a documentação exigir a relação hand-eye, aplicá-la num passo explícito e registrar em `meta.json` (`gt_frame_fix`). Pares estéreo: `stamps.csv` só contém timestamps presentes nos dois lados (BotanicGarden é sincronizado em hardware; se o RELLIS tiver offsets, casar por vizinho mais próximo ≤ 5 ms — ajustar `extract` se `unpaired_*` > 1%).

- [ ] **Step 5: Rodar testes** — `scripts/test.sh tests/test_extract.py -q` → `2 passed`.

- [ ] **Step 6: Extrair trecho real** (depois do download do 1018-00, Google/OneDrive):

```bash
.venv/bin/python -m ofd.extract --bag data/raw/botanic/1018-00.bag --config configs/botanic/dataset.yaml \
  --out data/extracted/1018-00_smoke --start 0 --duration 120 --gt-tum data/raw/botanic/1018-00_gt.tum
```
Expected: `n_scans ≈ 1200`, `n_stereo ≈ 1200`, `deskew` true/false coerente com o Step 2, `unpaired_*` ≈ 0. Se `deskew` sair false, inspecionar `scans.csv` (quais scans falharam e por quê: span ou monotonicidade) antes de seguir.

- [ ] **Step 7: Commit**

```bash
git add ofd/extract.py configs/ tests/test_extract.py
git commit -m "feat(extract): extração de bag ROS1 preservando campos da nuvem e semântica de tempo"
```

---

### Task 11: KISS-ICP runner + indicadores LiDAR

**Files:**
- Create: `ofd/run_kissicp.py`, `ofd/lidar_indicators.py`
- Test: `tests/test_run_kissicp.py`, `tests/test_lidar_indicators.py`

**Interfaces:**
- Consumes: `tracks.write_run|load_run`, `indicators.registration_quality`, saída do `extract` (Task 10: `lidar_stamps.csv` com `ts_ns,end_ns`; `clouds/<ts_ns>.npz`; `meta.json["deskew"]`)
- Produces:
  - `run_kissicp.run(seq_dir: Path, out_dir: Path, deskew: bool) -> None` — formato comum; **timestamp da pose = `end_ns`** do scan; `state.csv` com uma linha por scan; se `deskew=True` e algum scan não tiver `t_norm` → `RuntimeError` (o `extract` garante 100% antes de ligar o deskew).
  - `lidar_indicators.compute(seq_dir: Path, run_dir: Path, T_L_S: ndarray) -> DataFrame` — para cada par de poses consecutivas do método no mesmo segmento cujos timestamps são `end_ns` de scans extraídos, registra scan k → k−1 com o ΔT do método (frame do LiDAR) e mescla `fitness,inlier_rmse,unmatched_ratio,n_points` em `indicators.csv` (chave `ts_ns` = `end_ns`).
  - CLIs: `python -m ofd.run_kissicp --seq-dir … --out …`; `python -m ofd.lidar_indicators --seq-dir … --run-dir … --config … --method fastlio|kissicp`

- [ ] **Step 1: Teste do runner** — `tests/test_run_kissicp.py`

```python
import numpy as np
import pandas as pd
import pytest
from ofd import run_kissicp, tracks


def scene(seed=0):
    rng = np.random.default_rng(seed)
    ground = np.c_[rng.uniform(-30, 30, (6000, 2)), np.zeros(6000)]
    walls = np.vstack([np.c_[rng.uniform(-30, 30, 3000), np.full(3000, y), rng.uniform(0, 3, 3000)] for y in (-8, 9)])
    poles = np.vstack([np.c_[np.full(300, x), np.full(300, 2.0), rng.uniform(0, 4, 300)] for x in range(-25, 30, 5)])
    return np.vstack([ground, walls, poles]).astype(np.float32)


def make_seq(tmp_path, n=40, with_t=False):
    seq = tmp_path / "seq"; (seq / "clouds").mkdir(parents=True)
    W = scene()
    ts = (1_700_000_000 * 10**9 + np.arange(n) * 100_000_000).astype(np.int64)
    for k, t in enumerate(ts):
        rec = {"xyz": W - np.array([0.5 * k, 0, 0], np.float32)}
        if with_t:
            rec["t_norm"] = np.zeros(len(W), np.float32)
        np.savez_compressed(seq / "clouds" / f"{t}.npz", **rec)
    pd.DataFrame({"ts_ns": ts, "end_ns": ts + 99_000_000}).to_csv(seq / "lidar_stamps.csv", index=False)
    return seq, ts


def test_kissicp_tracks_translation_and_uses_end_ns(tmp_path):
    seq, ts = make_seq(tmp_path)
    run_kissicp.run(seq, tmp_path / "run", deskew=False)
    tr, _, meta = tracks.load_run(tmp_path / "run")
    assert len(tr.ts_ns) == 40 and abs(tr.Ts[-1][0, 3] - 19.5) < 0.5
    assert tr.ts_ns[0] == ts[0] + 99_000_000
    assert meta["uses_imu"] is False and meta["deskew"] is False
    st = pd.read_csv(tmp_path / "run" / "state.csv")
    assert len(st) == 40 and st["ok"].all()


def test_deskew_without_times_raises(tmp_path):
    seq, _ = make_seq(tmp_path, n=3, with_t=False)
    with pytest.raises(RuntimeError):
        run_kissicp.run(seq, tmp_path / "run", deskew=True)
```

- [ ] **Step 2: Implementar `ofd/run_kissicp.py`**

```python
"""KISS-ICP (pure LiDAR odometry) over extracted clouds -> common run format."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from kiss_icp.config import load_config
from kiss_icp.kiss_icp import KissICP

from ofd import tracks


def run(seq_dir, out_dir, deskew):
    seq_dir = Path(seq_dir)
    cfg = load_config(None, deskew=bool(deskew), max_range=100.0)
    odom = KissICP(config=cfg)
    stamps = pd.read_csv(seq_dir / "lidar_stamps.csv")
    Ts, ok = [], []
    for t in stamps["ts_ns"].to_numpy(np.int64):
        z = np.load(seq_dir / "clouds" / f"{t}.npz")
        pts = z["xyz"].astype(np.float64)
        if deskew:
            if "t_norm" not in z.files:
                raise RuntimeError(f"deskew=True mas scan {t} sem t_norm")
            times = z["t_norm"].astype(np.float64)
        else:
            times = np.zeros(len(pts))
        odom.register_frame(pts, times)
        Ts.append(odom.last_pose.copy())
        ok.append(1)
    end = stamps["end_ns"].to_numpy(np.int64)
    state = pd.DataFrame({"ts_ns": end, "ok": ok, "map_id": 0})
    meta = {"method": "kissicp", "uses_imu": False, "sensor_frame": "lidar", "deskew": bool(deskew),
            "kiss_icp_version": __import__("kiss_icp").__version__,
            "config": json.loads(cfg.model_dump_json()) if hasattr(cfg, "model_dump_json") else str(cfg)}
    tracks.write_run(out_dir, end, np.stack(Ts), state, pd.DataFrame({"ts_ns": end}), meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    deskew = json.loads((Path(a.seq_dir) / "meta.json").read_text()).get("deskew", False)
    run(a.seq_dir, a.out, deskew)


if __name__ == "__main__":
    main()
```

> Conferir a API da versão travada antes de rodar: `.venv/bin/python -c "import kiss_icp, inspect; from kiss_icp.config import load_config; from kiss_icp.kiss_icp import KissICP; print(kiss_icp.__version__, inspect.signature(load_config), inspect.signature(KissICP.register_frame))"`. Se `load_config` não aceitar `deskew`, usar `cfg.data.deskew = bool(deskew)` após `load_config(None, max_range=100.0)`.

- [ ] **Step 3: Teste dos indicadores** — `tests/test_lidar_indicators.py`

```python
import numpy as np
import pandas as pd
from ofd import lidar_indicators, tracks
from tests.test_run_kissicp import make_seq


def test_indicators_keyed_by_end_ns(tmp_path):
    seq, ts = make_seq(tmp_path, n=5)
    end = ts + 99_000_000
    Ts = np.stack([np.eye(4)] * 5)
    for k in range(5):
        Ts[k][0, 3] = 0.5 * k  # pose correta do sensor
    tracks.write_run(tmp_path / "run", end, Ts, pd.DataFrame({"ts_ns": end, "ok": 1, "map_id": 0}),
                     pd.DataFrame({"ts_ns": end}), {"method": "kissicp"})
    out = lidar_indicators.compute(seq, tmp_path / "run", np.eye(4))
    assert out["fitness"].notna().sum() == 4 and out["fitness"].dropna().min() > 0.9
    assert set(out["ts_ns"]) == set(end)
```

- [ ] **Step 4: Implementar `ofd/lidar_indicators.py`**

```python
"""Uniform LiDAR indicators from a method's own consecutive ΔT (causal: uses scans k-1, k only)."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, indicators, se3, tracks


def compute(seq_dir, run_dir, T_L_S):
    seq_dir, run_dir = Path(seq_dir), Path(run_dir)
    tr, ind, _ = tracks.load_run(run_dir)
    st = pd.read_csv(seq_dir / "lidar_stamps.csv")
    cloud_of = dict(zip(st["end_ns"].astype(np.int64), st["ts_ns"].astype(np.int64)))  # end_ns -> arquivo
    rows = []
    for k in range(1, len(tr.ts_ns)):
        a, b = int(tr.ts_ns[k - 1]), int(tr.ts_ns[k])
        if tr.segment[k] != tr.segment[k - 1] or a not in cloud_of or b not in cloud_of:
            continue
        dT = se3.conjugate(se3.delta(tr.Ts[k - 1], tr.Ts[k]), T_L_S)
        src = np.load(seq_dir / "clouds" / f"{cloud_of[b]}.npz")["xyz"]
        tgt = np.load(seq_dir / "clouds" / f"{cloud_of[a]}.npz")["xyz"]
        rows.append({"ts_ns": b, **indicators.registration_quality(src, tgt, dT)})
    new = pd.DataFrame(rows, columns=["ts_ns", "fitness", "inlier_rmse", "unmatched_ratio", "n_points"])
    base = ind.drop(columns=[c for c in new.columns if c in ind.columns], errors="ignore").reset_index()
    merged = base.merge(new, on="ts_ns", how="outer").sort_values("ts_ns")
    merged.to_csv(run_dir / "indicators.csv", index=False)
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--method", required=True, choices=["fastlio", "kissicp"])
    a = ap.parse_args()
    compute(a.seq_dir, a.run_dir, config.load(a.config).T_L_S[a.method])


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Rodar** — `scripts/test.sh tests/test_run_kissicp.py tests/test_lidar_indicators.py -q` → `3 passed`.

- [ ] **Step 6: Rodar no smoke real**

```bash
.venv/bin/python -m ofd.run_kissicp --seq-dir data/extracted/1018-00_smoke --out data/runs/1018-00_smoke/kissicp
.venv/bin/python -m ofd.lidar_indicators --seq-dir data/extracted/1018-00_smoke --run-dir data/runs/1018-00_smoke/kissicp --config configs/botanic/dataset.yaml --method kissicp
```
Expected: ~1200 poses; `fitness` mediano > 0.5.

- [ ] **Step 7: Commit**

```bash
git add ofd/run_kissicp.py ofd/lidar_indicators.py tests/test_run_kissicp.py tests/test_lidar_indicators.py
git commit -m "feat(kissicp): runner offline com tempo de disponibilidade e indicadores LiDAR uniformes"
```

---

### Task 12: FAST-LIO2 runner (ROS 2 Jazzy)

**Files:**
- Create: `scripts/build_fastlio.sh`, `tools/fastlio_recorder.py`, `ofd/run_fastlio.py`, `configs/botanic/fastlio.yaml`, `configs/rellis/fastlio.yaml`
- Test: `tests/test_fastlio_recorder_parse.py`, `tests/test_run_fastlio.py`

**Interfaces:**
- Consumes: bag ROS1 original, `lidar_stamps.csv` da extração (Task 10), `matching.match_monotonic` (Task 9), `tracks.write_run`
- Produces:
  - `run_fastlio.assemble(raw_ts: ndarray[int64], raw_Ts, end_ns: ndarray[int64], tol_ms=5.0, min_match=0.9) -> (pose_ts, pose_Ts, state_df, info)` — casa cada scan (`end_ns`) com no máximo uma pose publicada (monotônico, 1:1, ≤ tol); **uma linha de estado por scan** (`ok=0` se o scan não gerou pose); timestamp da pose = `end_ns` do scan casado. Se a fração casada < `min_match`, levanta `RuntimeError` informando a mediana de (pose − scan mais próximo) para diagnosticar offset.
  - `run_fastlio.run(...)` → `data/runs/<seq>/fastlio/` (sensor_frame = `imu`: o `body` do FAST-LIO é o frame da IMU, publicado com `lidar_end_time`; `T_L_S["fastlio"]` = IMU→LiDAR).

- [ ] **Step 1: `scripts/build_fastlio.sh`** — workspace próprio com symlinks para o FAST_LIO e livox_ros_driver2 já existentes (sem alterar o projeto original):

```bash
#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
mkdir -p ros2_ws/src
SRC=/home/rbe-luis/Workspace/Controle_robo_livox/ros2_packages
ln -sfn "$SRC/FAST_LIO" ros2_ws/src/FAST_LIO
ln -sfn "$SRC/livox_ros_driver2" ros2_ws/src/livox_ros_driver2
source /opt/ros/jazzy/setup.bash
cd ros2_ws && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release --packages-up-to fast_lio
git -C "$SRC/FAST_LIO" rev-parse HEAD > ../third_party_fastlio_commit.txt
```
Adicionar `ros2_ws/build ros2_ws/install ros2_ws/log ros2_ws/src` ao `.gitignore` e commitar `third_party_fastlio_commit.txt`.
Run: `bash scripts/build_fastlio.sh` → Expected: `Summary: N packages finished`. (Se `livox_ros_driver2` exigir `ROS_EDITION`, usar os mesmos argumentos de `Controle_robo_livox/setup_livox.sh`.)

- [ ] **Step 2: Configs FAST-LIO** — `configs/botanic/fastlio.yaml`: copiar `velodyne.yaml` do FAST_LIO e alterar: `lid_topic: /velodyne_points`, `imu_topic: /imu/data`, `scan_line: 16`, `timestamp_unit` conforme Task 10 Step 2 (0=s,1=ms,2=us,3=ns), `extrinsic_T/extrinsic_R` = LiDAR no frame da IMU (Xsens) da calibração do BotanicGarden, `pcd_save_en: false`, `path_en: false`. `configs/rellis/fastlio.yaml`: copiar `ouster64.yaml`, `lid_topic: /os1_cloud_node/points`, `imu_topic: /os1_cloud_node/imu`, extrínseca IMU interna do Ouster.

- [ ] **Step 3: Gravador** — `tools/fastlio_recorder.py` (roda com `/usr/bin/python3` + ROS 2, **não** com o venv):

```python
#!/usr/bin/env python3
"""Record /Odometry from FAST-LIO into TUM (ts from header = lidar_end_time) until idle timeout."""
import sys
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy


def odom_to_line(msg):
    s = msg.header.stamp
    p, q = msg.pose.pose.position, msg.pose.pose.orientation
    return f"{s.sec}.{s.nanosec:09d} {p.x:.9f} {p.y:.9f} {p.z:.9f} {q.x:.9f} {q.y:.9f} {q.z:.9f} {q.w:.9f}\n"


class Rec(Node):
    def __init__(self, path):
        super().__init__("fastlio_recorder")
        self.f = open(path, "w")
        self.last = time.time()
        qos = QoSProfile(depth=1000, reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST)
        self.create_subscription(Odometry, "/Odometry", self.cb, qos)

    def cb(self, msg):
        self.f.write(odom_to_line(msg)); self.f.flush(); self.last = time.time()


def main():
    path, idle = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    rclpy.init(); n = Rec(path)
    try:
        while rclpy.ok() and time.time() - n.last < idle:
            rclpy.spin_once(n, timeout_sec=0.5)
    finally:
        n.f.close(); rclpy.shutdown()


if __name__ == "__main__":
    main()
```

Teste `tests/test_fastlio_recorder_parse.py` (roda no venv sem ROS, com stubs):

```python
import importlib.util, sys, types
from types import SimpleNamespace as NS


def test_odom_to_line():
    for mod in ["rclpy", "rclpy.node", "rclpy.qos", "nav_msgs", "nav_msgs.msg"]:
        sys.modules.setdefault(mod, types.ModuleType(mod))
    sys.modules["rclpy.node"].Node = object
    sys.modules["nav_msgs.msg"].Odometry = object
    q = sys.modules["rclpy.qos"]; q.QoSProfile = q.ReliabilityPolicy = q.HistoryPolicy = object
    spec = importlib.util.spec_from_file_location("rec", "tools/fastlio_recorder.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    msg = NS(header=NS(stamp=NS(sec=5, nanosec=7)),
             pose=NS(pose=NS(position=NS(x=1, y=2, z=3), orientation=NS(x=0, y=0, z=0, w=1))))
    assert m.odom_to_line(msg).startswith("5.000000007 1.000000000 2.000000000 3.000000000")
```

- [ ] **Step 4: Teste do `assemble`** — `tests/test_run_fastlio.py`

```python
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
```

- [ ] **Step 5: Orquestrador** — `ofd/run_fastlio.py`

```python
"""Convert ROS1 bag -> ROS2, run FAST-LIO, play bag, record /Odometry -> common run format."""
import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import se3, tracks
from ofd.matching import match_monotonic

ROS = "source /opt/ros/jazzy/setup.bash && source ros2_ws/install/setup.bash && "


def assemble(raw_ts, raw_Ts, end_ns, tol_ms=5.0, min_match=0.9):
    order = np.argsort(raw_ts, kind="stable")
    raw_ts, raw_Ts = np.asarray(raw_ts, np.int64)[order], raw_Ts[order]
    end_ns = np.sort(np.asarray(end_ns, np.int64))
    m = match_monotonic(end_ns, raw_ts, int(tol_ms * 1e6))
    frac = float((m >= 0).mean()) if len(m) else 0.0
    if frac < min_match:
        near = [int(raw_ts[np.argmin(np.abs(raw_ts - e))] - e) for e in end_ns] if len(raw_ts) else [0]
        raise RuntimeError(f"só {frac:.1%} dos scans casaram com poses; mediana(pose - scan) = "
                           f"{np.median(near) / 1e6:.1f} ms — conferir timestamp_unit/end_ns")
    ok = (m >= 0).astype(int)
    state = pd.DataFrame({"ts_ns": end_ns, "ok": ok, "map_id": 0})
    return end_ns[ok == 1], raw_Ts[m[ok == 1]], state, {"matched_frac": frac, "tol_ms": tol_ms}


def run(bag1, ros2_bag_dir, cfg_yaml, seq_dir, out_dir, topics, rate=0.5, start=None, duration=None):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    if not Path(ros2_bag_dir).exists():
        inc = " ".join(f"--include-topic {t}" for t in topics)
        subprocess.run(["bash", "-c", f".venv/bin/rosbags-convert --src {bag1} --dst {ros2_bag_dir} {inc}"], check=True)
    cfg_yaml = Path(cfg_yaml).resolve()
    extra = (f" --start-offset {start}" if start else "") + (f" --playback-duration {duration}" if duration else "")
    with open(out_dir / "log.txt", "w") as log:
        node = subprocess.Popen(["bash", "-c", ROS + f"exec ros2 launch fast_lio mapping.launch.py rviz:=false "
                                 f"config_path:={cfg_yaml.parent} config_file:={cfg_yaml.name}"], stdout=log, stderr=log)
        rec = subprocess.Popen(["bash", "-c", ROS + f"exec /usr/bin/python3 tools/fastlio_recorder.py "
                                f"{out_dir / 'raw_odom.tum'} 30"], stdout=log, stderr=log)
        try:
            time.sleep(5)
            subprocess.run(["bash", "-c", ROS + f"ros2 bag play {ros2_bag_dir} --rate {rate}{extra}"],
                           check=True, stdout=log, stderr=log)
            rec.wait(timeout=600)
        finally:
            for p in (rec, node):
                if p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        p.kill()
    raw_ts, raw_Ts = se3.load_tum(out_dir / "raw_odom.tum")
    end_ns = pd.read_csv(Path(seq_dir) / "lidar_stamps.csv")["end_ns"].to_numpy(np.int64)
    ts, Ts, state, info = assemble(raw_ts, raw_Ts, end_ns)
    commit = Path("third_party_fastlio_commit.txt").read_text().strip() if Path("third_party_fastlio_commit.txt").exists() else "unknown"
    meta = {"method": "fastlio", "uses_imu": True, "sensor_frame": "imu", "deskew": True,
            "fastlio_commit": commit, "config": cfg_yaml.read_text(), "rate": rate,
            "start": start, "duration": duration, **info}
    tracks.write_run(out_dir, ts, Ts, state, pd.DataFrame({"ts_ns": ts}), meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--ros2-bag", required=True)
    ap.add_argument("--fastlio-config", required=True)
    ap.add_argument("--seq-dir", required=True, help="extração correspondente (para lidar_stamps.csv)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--topics", nargs="+", required=True)
    ap.add_argument("--rate", type=float, default=0.5)
    ap.add_argument("--start", type=float)
    ap.add_argument("--duration", type=float)
    a = ap.parse_args()
    run(a.bag, a.ros2_bag, a.fastlio_config, a.seq_dir, a.out, a.topics, a.rate, a.start, a.duration)


if __name__ == "__main__":
    main()
```

> Conferir `rosbags-convert --help` (versão travada) e `ros2 bag play --help` (Jazzy: `--start-offset`, `--playback-duration`) antes do smoke. O `start`/`duration` do play deve ser o mesmo da extração; scans da extração fora da janela tocada aparecem como `ok=0` e o `assemble` falha se forem > 10% — usar exatamente a mesma janela.

- [ ] **Step 6: Rodar testes** — `scripts/test.sh tests/test_fastlio_recorder_parse.py tests/test_run_fastlio.py -q` → `3 passed`.

- [ ] **Step 7: Rodar no smoke** (mesmo trecho de 120 s do Task 10):

```bash
.venv/bin/python -m ofd.run_fastlio --bag data/raw/botanic/1018-00.bag --ros2-bag data/raw/botanic/1018-00_ros2 \
  --fastlio-config configs/botanic/fastlio.yaml --seq-dir data/extracted/1018-00_smoke \
  --out data/runs/1018-00_smoke/fastlio --topics /velodyne_points /imu/data --start 0 --duration 120
.venv/bin/python -m ofd.lidar_indicators --seq-dir data/extracted/1018-00_smoke --run-dir data/runs/1018-00_smoke/fastlio --config configs/botanic/dataset.yaml --method fastlio
```
Expected: `matched_frac` ≥ 0.9 em `run.json`; `indicators.csv` com fitness.

- [ ] **Step 8: Commit**

```bash
git add scripts/build_fastlio.sh third_party_fastlio_commit.txt tools/fastlio_recorder.py ofd/run_fastlio.py configs/*/fastlio.yaml tests/test_fastlio_recorder_parse.py tests/test_run_fastlio.py .gitignore
git commit -m "feat(fastlio): build ROS 2, gravador, casamento pose↔scan 1:1 e estado por scan"
```

---

### Task 13: ORB-SLAM3 — build, patch de log causal, runner

**Files:**
- Create: `scripts/build_orbslam3.sh`, `patches/orbslam3/0001-causal-log-and-no-loop.patch`, `tools/vo_runners/orbslam3_stereo_log.cc`, `tools/vo_runners/CMakeLists.txt`, `configs/botanic/orbslam3.yaml`, `configs/rellis/orbslam3.yaml`, `ofd/run_vo.py`
- Test: `tests/test_run_vo.py` (conversão de log), execução real no smoke

**Interfaces:**
- Produces:
  - binário `third_party/bin/orbslam3_stereo_log <vocab> <settings.yaml> <seq_dir> <out_dir>` que escreve `frames.csv`: `ts_ns,ok,map_id,inliers,n_features,reproj_err,tracked_ratio,x,y,z,qx,qy,qz,qw` (pose **T_W_C** emitida no frame; vazia se ok=0).
  - `run_vo.convert(frames_csv: Path, out_dir: Path, method: str, meta: dict) -> None` (→ formato comum)
  - CLI: `python -m ofd.run_vo --method orbslam3|stella --seq-dir … --out … --settings …`

- [ ] **Step 1: Dependências do sistema** (pedir ao usuário rodar com sudo):

```bash
sudo apt install -y build-essential cmake git libeigen3-dev libopencv-dev libglew-dev libboost-all-dev libssl-dev \
  libyaml-cpp-dev libsqlite3-dev libgoogle-glog-dev libsuitesparse-dev
```

- [ ] **Step 2: `scripts/build_orbslam3.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p third_party && cd third_party
[ -d Pangolin ] || (git clone https://github.com/stevenlovegrove/Pangolin.git && git -C Pangolin checkout 7364b59a58045d1c429b146e44f6f088fd1cc518)
cmake -S Pangolin -B Pangolin/build -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=OFF -DBUILD_TESTS=OFF \
  -DCMAKE_INSTALL_PREFIX=$PWD/local && cmake --build Pangolin/build -j8 --target install
[ -d ORB_SLAM3 ] || git clone https://github.com/UZ-SLAMLab/ORB_SLAM3.git
cd ORB_SLAM3
git checkout 4452a3c4ab75   # HEAD de master (pós v1.0-release) — fixo
for p in ../../patches/orbslam3/*.patch; do
  git apply --check "$p" 2>/dev/null && git apply "$p" || git apply --check -R "$p"   # idempotente
done
(cd Thirdparty/DBoW2 && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j8)
(cd Thirdparty/g2o && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j8)
(cd Thirdparty/Sophus && cmake -B build -DBUILD_TESTS=OFF && cmake --build build -j8)
[ -f Vocabulary/ORBvoc.txt ] || (cd Vocabulary && tar xf ORBvoc.txt.tar.gz)
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=$PWD/../local && cmake --build build -j8 --target ORB_SLAM3
cd ../.. && cmake -S tools/vo_runners -B tools/vo_runners/build -DCMAKE_BUILD_TYPE=Release \
  -DORB_SLAM3_DIR=$PWD/third_party/ORB_SLAM3 -DCMAKE_PREFIX_PATH=$PWD/third_party/local \
  && cmake --build tools/vo_runners/build -j8 --target orbslam3_stereo_log
mkdir -p third_party/bin && cp tools/vo_runners/build/orbslam3_stereo_log third_party/bin/
```
**Nenhum `sed` no script**: toda alteração no código do ORB-SLAM3 vive em `patches/orbslam3/` e é aplicada pelo loop acima. O patch de build é criado assim (uma vez, dentro de `third_party/ORB_SLAM3` limpo no commit fixo):

```bash
cd third_party/ORB_SLAM3
sed -i 's/-std=c++11/-std=c++17/; s/CXX_STANDARD 11/CXX_STANDARD 17/; s/COMPILER_SUPPORTS_CXX11/TRUE/' CMakeLists.txt
sed -i 's/find_package(OpenCV 4.4)/find_package(OpenCV 4)/' CMakeLists.txt
# compilar; para cada erro de 24.04 corrigir à mão (típicos: monotonic_clock -> steady_clock,
# #include <unistd.h> faltando em LoopClosing.h/System.h, std::numeric_limits sem <limits>)
git diff -- CMakeLists.txt src include Thirdparty > ../../patches/orbslam3/0000-build-ubuntu2404.patch
git checkout -- .   # volta ao commit limpo; o script reaplica os patches
```
(`0000-` aplica antes de `0001-`, que é o patch de log da etapa seguinte; os dois são gerados como diffs separados.)

- [ ] **Step 3: Patch** — criar `patches/orbslam3/0001-causal-log-and-no-loop.patch` com as mudanças abaixo (gerar via `git diff > ...` após editar à mão dentro de `third_party/ORB_SLAM3`):

1. **Loop closure desligado:** em `src/System.cc`, localizar `new LoopClosing(` (`grep -n "new LoopClosing" src/System.cc`) e passar `false` como último argumento (`bActiveLC`); conferir com `grep -n "bActiveLC\|mbActiveLC" include/LoopClosing.h src/LoopClosing.cc` que o flag desativa a detecção.
2. **Métricas causais acessíveis:** em `include/Tracking.h`, adicionar campos públicos:
```cpp
public:
    int mLogInliers = 0;
    int mLogNFeatures = 0;
    float mLogReprojErr = -1.f;
    float mLogTrackedRatio = 0.f;
```
3. Em `src/Tracking.cc`, ao final de `Tracking::Track()` (logo antes do bloco que salva `mlRelativeFramePoses`, procurar `if(mCurrentFrame.isSet())` / `mlRelativeFramePoses.push_back`), inserir:
```cpp
    {
        mLogInliers = mnMatchesInliers;
        mLogNFeatures = mCurrentFrame.N;
        double se = 0; int cnt = 0;
        if (mState == OK && mCurrentFrame.isSet()) {
            const Sophus::SE3f Tcw = mCurrentFrame.GetPose();
            for (int i = 0; i < mCurrentFrame.N; ++i) {
                MapPoint* pMP = mCurrentFrame.mvpMapPoints[i];
                if (!pMP || mCurrentFrame.mvbOutlier[i]) continue;
                const Eigen::Vector3f pc = Tcw * pMP->GetWorldPos();
                if (pc(2) <= 0) continue;
                const float u = mCurrentFrame.fx * pc(0) / pc(2) + mCurrentFrame.cx;
                const float v = mCurrentFrame.fy * pc(1) / pc(2) + mCurrentFrame.cy;
                const cv::KeyPoint& kp = mCurrentFrame.mvKeysUn[i];
                se += std::hypot(u - kp.pt.x, v - kp.pt.y); ++cnt;
            }
        }
        mLogReprojErr = cnt ? float(se / cnt) : -1.f;
        mLogTrackedRatio = mCurrentFrame.N ? float(cnt) / mCurrentFrame.N : 0.f;
    }
```
4. Em `include/System.h` adicionar getter público: `Tracking* GetTracker() { return mpTracker; }` e `int GetActiveMapId();` com implementação em `src/System.cc`: `int System::GetActiveMapId(){ return mpAtlas->GetCurrentMap()->GetId(); }`.

- [ ] **Step 4: Runner** — `tools/vo_runners/orbslam3_stereo_log.cc`

```cpp
// Stereo ORB-SLAM3 over extracted PNGs; logs the pose emitted at each frame (causal) + indicators.
#include <System.h>
#include <Tracking.h>
#include <opencv2/opencv.hpp>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <thread>

int main(int argc, char** argv) {
    if (argc != 5) { std::cerr << "usage: vocab settings seq_dir out_dir\n"; return 1; }
    std::string seq = argv[3], out = argv[4];
    std::ifstream st(seq + "/images/stamps.csv");
    std::string line; std::getline(st, line);  // header
    std::vector<long long> ts;
    while (std::getline(st, line)) if (!line.empty()) ts.push_back(std::stoll(line));
    ORB_SLAM3::System slam(argv[1], argv[2], ORB_SLAM3::System::STEREO, false);
    const double rate = std::getenv("VO_RATE") ? std::atof(std::getenv("VO_RATE")) : 1.0;  // tempo real
    const auto wall0 = std::chrono::steady_clock::now();
    const long long t0 = ts.empty() ? 0 : ts.front();
    std::ofstream f(out + "/frames.csv");
    f << "ts_ns,ok,map_id,inliers,n_features,reproj_err,tracked_ratio,x,y,z,qx,qy,qz,qw\n" << std::setprecision(9) << std::fixed;
    for (long long t : ts) {
        cv::Mat L = cv::imread(seq + "/images/left/" + std::to_string(t) + ".png", cv::IMREAD_GRAYSCALE);
        cv::Mat R = cv::imread(seq + "/images/right/" + std::to_string(t) + ".png", cv::IMREAD_GRAYSCALE);
        if (rate > 0)  // espera o instante do frame: as threads de mapeamento acompanham como online
            std::this_thread::sleep_until(wall0 + std::chrono::nanoseconds((long long)((t - t0) / rate)));
        Sophus::SE3f Tcw = slam.TrackStereo(L, R, t * 1e-9);
        auto* tr = slam.GetTracker();
        bool ok = slam.GetTrackingState() == ORB_SLAM3::Tracking::OK;
        f << t << "," << ok << "," << slam.GetActiveMapId() << "," << tr->mLogInliers << "," << tr->mLogNFeatures
          << "," << tr->mLogReprojErr << "," << tr->mLogTrackedRatio;
        if (ok) {
            Sophus::SE3f Twc = Tcw.inverse();
            Eigen::Vector3f p = Twc.translation(); Eigen::Quaternionf q = Twc.unit_quaternion();
            f << "," << p.x() << "," << p.y() << "," << p.z() << "," << q.x() << "," << q.y() << "," << q.z() << "," << q.w();
        } else f << ",,,,,,,";
        f << "\n";
    }
    slam.Shutdown();
}
```

`tools/vo_runners/CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.16)
project(vo_runners CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(OpenCV 4 REQUIRED)
find_package(Eigen3 REQUIRED)
if(ORB_SLAM3_DIR)
  find_package(Pangolin REQUIRED)
  add_executable(orbslam3_stereo_log orbslam3_stereo_log.cc)
  target_include_directories(orbslam3_stereo_log PRIVATE ${ORB_SLAM3_DIR} ${ORB_SLAM3_DIR}/include
    ${ORB_SLAM3_DIR}/include/CameraModels ${ORB_SLAM3_DIR}/Thirdparty/Sophus ${EIGEN3_INCLUDE_DIR})
  target_link_libraries(orbslam3_stereo_log ${ORB_SLAM3_DIR}/lib/libORB_SLAM3.so
    ${ORB_SLAM3_DIR}/Thirdparty/DBoW2/lib/libDBoW2.so ${ORB_SLAM3_DIR}/Thirdparty/g2o/lib/libg2o.so
    ${OpenCV_LIBS} ${Pangolin_LIBRARIES} pthread)
endif()
if(STELLA_PREFIX)
  find_package(stella_vslam REQUIRED PATHS ${STELLA_PREFIX})
  add_executable(stella_stereo_log stella_stereo_log.cc)
  target_link_libraries(stella_stereo_log stella_vslam::stella_vslam ${OpenCV_LIBS} yaml-cpp)
endif()
```

- [ ] **Step 5: Settings** — `configs/botanic/orbslam3.yaml` no formato `File.version: "1.0"`, `Camera.type: "PinHole"`, `Camera1.fx/fy/cx/cy/k1/k2/p1/p2`, `Camera2.*`, `Stereo.T_c1_c2` (matriz 4×4), `Camera.width/height` (960×600 nos bags do BotanicGarden — **dividir intrínsecas da calibração 1920×1200 por 2**), `Camera.fps: 10`, `Stereo.ThDepth: 40.0`, `ORBextractor.nFeatures: 1500`, demais `ORBextractor.*` padrão do `Examples/Stereo/EuRoC.yaml`, `Viewer.*` copiados do EuRoC. Valores da calibração do dataset (gray left/right). RELLIS: idem com a calibração Nerian.

- [ ] **Step 6: `ofd/run_vo.py` + teste**

`tests/test_run_vo.py`:

```python
import pandas as pd
from ofd import run_vo, tracks


def test_convert_frames(tmp_path):
    f = tmp_path / "frames.csv"
    f.write_text("ts_ns,ok,map_id,inliers,n_features,reproj_err,tracked_ratio,x,y,z,qx,qy,qz,qw\n"
                 "100,1,0,200,1000,0.8,0.2,0,0,0,0,0,0,1\n"
                 "200,0,0,5,900,-1,0.0,,,,,,,\n"
                 "300,1,1,150,950,1.1,0.16,1,0,0,0,0,0,1\n")
    run_vo.convert(f, tmp_path / "run", "orbslam3", {"uses_imu": False})
    tr, ind, meta = tracks.load_run(tmp_path / "run")
    assert list(tr.ts_ns) == [100, 300] and list(tr.segment) == [0, 1]
    assert ind.loc[200, "reproj_err"] != ind.loc[200, "reproj_err"]  # -1 -> NaN
    assert meta["method"] == "orbslam3" and meta["sensor_frame"] == "cam_left"
```

`ofd/run_vo.py`:

```python
"""Run VO binaries over extracted stereo and convert frames.csv -> common run format."""
import argparse
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import se3, tracks

BIN = {"orbslam3": "third_party/bin/orbslam3_stereo_log", "stella": "third_party/bin/stella_stereo_log"}
VOCAB = {"orbslam3": "third_party/ORB_SLAM3/Vocabulary/ORBvoc.txt", "stella": "third_party/orb_vocab.fbow"}


def convert(frames_csv, out_dir, method, meta):
    f = pd.read_csv(frames_csv)
    ok = f[f["ok"] == 1]
    Ts = np.stack([se3.to_mat(r[["x", "y", "z"]].to_numpy(float), r[["qx", "qy", "qz", "qw"]].to_numpy(float))
                   for _, r in ok.iterrows()]) if len(ok) else np.zeros((0, 4, 4))
    ind = f[["ts_ns", "inliers", "n_features", "reproj_err", "tracked_ratio"]].copy()
    ind.loc[ind["reproj_err"] < 0, "reproj_err"] = np.nan
    tracks.write_run(out_dir, ok["ts_ns"].to_numpy(np.int64), Ts, f[["ts_ns", "ok", "map_id"]], ind,
                     {"method": method, "uses_imu": False, "sensor_frame": "cam_left", "loop_closure": False, **meta})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True, choices=list(BIN))
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--settings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rate", type=float, default=1.0, help="1.0 = tempo real; 0 = sem espera (só debug)")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "VO_RATE": str(a.rate)}
    with open(out / "log.txt", "w") as log:
        subprocess.run([BIN[a.method], VOCAB[a.method], a.settings, a.seq_dir, str(out)],
                       check=True, stdout=log, stderr=log, env=env)
    commit = {"orbslam3": "4452a3c4ab75", "stella": "e445b5452535"}[a.method]
    convert(out / "frames.csv", out, a.method,
            {"settings": Path(a.settings).read_text(), "rate": a.rate, "commit": commit})


if __name__ == "__main__":
    main()
```

Run: `scripts/test.sh tests/test_run_vo.py -q` → `1 passed`.

- [ ] **Step 7: Build e smoke**

```bash
bash scripts/build_orbslam3.sh
.venv/bin/python -m ofd.run_vo --method orbslam3 --seq-dir data/extracted/1018-00_smoke \
  --settings configs/botanic/orbslam3.yaml --out data/runs/1018-00_smoke/orbslam3
```
Expected: `frames.csv` com ~1200 linhas, maioria `ok=1`, `reproj_err` ~0.5–2 px; nenhum "Loop detected" no `log.txt` (`grep -c -i loop data/runs/1018-00_smoke/orbslam3/log.txt` só mensagens de inicialização).

- [ ] **Step 8: Commit**

```bash
git add scripts/build_orbslam3.sh patches/orbslam3 tools/vo_runners configs/*/orbslam3.yaml ofd/run_vo.py tests/test_run_vo.py
git commit -m "feat(orbslam3): build 24.04 via patches, log causal sem loop closure, runner estéreo em tempo real"
```

---

### Task 14: Stella VSLAM — build e runner

**Files:**
- Create: `scripts/build_stella.sh`, `tools/vo_runners/stella_stereo_log.cc`, `configs/botanic/stella.yaml`, `configs/rellis/stella.yaml`, `patches/stella/0001-log-indicators.patch` (se necessário)
- Test: reaproveita `tests/test_run_vo.py` (mesmo `frames.csv`); smoke real

**Interfaces:**
- Produces: binário `third_party/bin/stella_stereo_log <vocab.fbow> <config.yaml> <seq_dir> <out_dir>` com o **mesmo** `frames.csv` do Task 13.

- [ ] **Step 1: `scripts/build_stella.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p third_party && cd third_party
P=$PWD/local
[ -d g2o ] || (git clone https://github.com/RainerKuemmerle/g2o.git && git -C g2o checkout e8df2004e07ea8f5b8e6a8b9f2dc067b45b45036)
cmake -S g2o -B g2o/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$P -DBUILD_SHARED_LIBS=ON \
  -DG2O_BUILD_APPS=OFF -DG2O_BUILD_EXAMPLES=OFF -DG2O_USE_OPENGL=OFF && cmake --build g2o/build -j8 --target install
[ -d FBoW ] || (git clone https://github.com/stella-cv/FBoW.git && git -C FBoW checkout c6e3c29e3332)
cmake -S FBoW -B FBoW/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$P && cmake --build FBoW/build -j8 --target install
[ -d stella_vslam ] || (git clone https://github.com/stella-cv/stella_vslam.git && git -C stella_vslam checkout e445b5452535 \
  && git -C stella_vslam submodule update --init --recursive)
for p in ../patches/stella/*.patch; do [ -e "$p" ] || continue
  git -C stella_vslam apply --check "$p" 2>/dev/null && git -C stella_vslam apply "$p" || git -C stella_vslam apply --check -R "$p"
done
cmake -S stella_vslam -B stella_vslam/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$P -DCMAKE_PREFIX_PATH=$P
cmake --build stella_vslam/build -j8 --target install
[ -f orb_vocab.fbow ] || curl -sfL https://github.com/stella-cv/FBoW_orb_vocab/raw/708407ae4cd5/orb_vocab.fbow -o orb_vocab.fbow
cd .. && cmake -S tools/vo_runners -B tools/vo_runners/build -DSTELLA_PREFIX=$P/lib/cmake/stella_vslam \
  -DCMAKE_PREFIX_PATH=$P && cmake --build tools/vo_runners/build -j8 --target stella_stereo_log
mkdir -p third_party/bin && cp tools/vo_runners/build/stella_stereo_log third_party/bin/
```
Commits fixos (Global Constraints); `run_vo` já grava o commit no `run.json`. Antes de investir tempo: `git -C third_party/stella_vslam log -1 --format=%cd` — se o repositório estiver parado há >2 anos ou o build falhar sem correção simples em ~2 h, **parar e reportar** (fallback a decidir com o usuário: OpenVINS sem IMU não serve; alternativa provável seria DSO estéreo/ORB-SLAM2).

- [ ] **Step 2: Inspecionar a API para indicadores**

```bash
grep -n "feed_stereo_frame\|disable_loop_detector\|get_frame_publisher\|tracker_state" third_party/stella_vslam/src/stella_vslam/system.h
grep -n "get_tracking_state\|get_num_tracked\|get_landmarks\|curr_frm_" third_party/stella_vslam/src/stella_vslam/publish/frame_publisher.h third_party/stella_vslam/src/stella_vslam/tracking_module.h
grep -n "num_tracked_lms_\|optimize(\|outlier_flags\|reproject_to_image" third_party/stella_vslam/src/stella_vslam/tracking_module.cc | head -30
```
O runner usa: `system::feed_stereo_frame(img_l, img_r, ts_s)` → `std::shared_ptr<Mat44_t>` (T_cw ou nullptr), `system::disable_loop_detector()`, estado do tracker via `tracker_->tracking_state_` (público em `tracking_module`), `tracker_->num_tracked_lms_`. Para **reproj_err** e **inliers**, aplicar patch em `tracking_module.cc`: logo após a otimização de pose do frame atual (`pose_optimizer_->optimize(curr_frm_` …), calcular — com `curr_frm_.get_landmarks()`, `curr_frm_.frm_obs_.undist_keypts_`, `curr_frm_.get_pose_cw()` e `camera_->reproject_to_image(R_cw, t_cw, lm->get_pos_in_world(), reproj, x_right)` — a média de `|reproj - kp.pt|` sobre landmarks não outlier, e guardar em membros públicos novos `last_reproj_err_`, `last_inliers_`, `last_n_features_`. Salvar como `patches/stella/0001-log-indicators.patch`. Para o `map_id`: incrementar um contador no runner sempre que `tracking_state_` voltar de `Lost`/`Initializing` para `Tracking` (stella reinicializa o mapa ao reset).

- [ ] **Step 3: Runner** — `tools/vo_runners/stella_stereo_log.cc`

```cpp
#include <stella_vslam/system.h>
#include <stella_vslam/config.h>
#include <stella_vslam/tracking_module.h>
#include <opencv2/opencv.hpp>
#include <Eigen/Geometry>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <thread>

int main(int argc, char** argv) {
    if (argc != 5) { std::cerr << "usage: vocab config seq_dir out_dir\n"; return 1; }
    std::string seq = argv[3], out = argv[4];
    const double rate = std::getenv("VO_RATE") ? std::atof(std::getenv("VO_RATE")) : 1.0;  // tempo real
    const auto wall0 = std::chrono::steady_clock::now();
    long long t0 = -1;
    auto cfg = std::make_shared<stella_vslam::config>(argv[2]);
    stella_vslam::system slam(cfg, argv[1]);
    slam.startup();
    slam.disable_loop_detector();
    std::ifstream st(seq + "/images/stamps.csv"); std::string line; std::getline(st, line);
    std::ofstream f(out + "/frames.csv");
    f << "ts_ns,ok,map_id,inliers,n_features,reproj_err,tracked_ratio,x,y,z,qx,qy,qz,qw\n" << std::setprecision(9) << std::fixed;
    int map_id = 0; bool prev_ok = false, started = false;
    while (std::getline(st, line)) {
        if (line.empty()) continue;
        long long t = std::stoll(line);
        cv::Mat L = cv::imread(seq + "/images/left/" + std::to_string(t) + ".png", cv::IMREAD_GRAYSCALE);
        cv::Mat R = cv::imread(seq + "/images/right/" + std::to_string(t) + ".png", cv::IMREAD_GRAYSCALE);
        if (t0 < 0) t0 = t;
        if (rate > 0)
            std::this_thread::sleep_until(wall0 + std::chrono::nanoseconds((long long)((t - t0) / rate)));
        auto Tcw = slam.feed_stereo_frame(L, R, t * 1e-9);
        auto* tr = slam.tracker_;
        bool ok = Tcw && tr->tracking_state_ == stella_vslam::tracker_state_t::Tracking;
        if (ok && !prev_ok) { if (started) ++map_id; started = true; }  // novo mapa após perda/reinício
        prev_ok = ok;
        int nf = tr->last_n_features_;
        f << t << "," << ok << "," << map_id << "," << tr->last_inliers_ << "," << nf << ","
          << tr->last_reproj_err_ << "," << (nf ? double(tr->num_tracked_lms_) / nf : 0.0);
        if (ok) {
            Eigen::Matrix4d Twc = Tcw->inverse();
            Eigen::Quaterniond q(Twc.block<3, 3>(0, 0));
            f << "," << Twc(0, 3) << "," << Twc(1, 3) << "," << Twc(2, 3) << "," << q.x() << "," << q.y() << "," << q.z() << "," << q.w();
        } else f << ",,,,,,,";
        f << "\n";
    }
    slam.shutdown();
}
```

Se `tracker_` não for membro público de `system` na versão clonada, adicionar ao mesmo patch um getter `tracking_module* get_tracker() { return tracker_; }` em `system.h` e usar `slam.get_tracker()`.

- [ ] **Step 4: Config** — `configs/botanic/stella.yaml` (formato stella):

```yaml
Camera:
  name: "botanic_gray_stereo"
  setup: "stereo"
  model: "perspective"
  fx: <fx/2 da calibração>   # imagens 960x600 no bag
  fy: <fy/2>
  cx: <cx/2>
  cy: <cy/2>
  k1: <k1>
  k2: <k2>
  p1: <p1>
  p2: <p2>
  k3: 0.0
  focal_x_baseline: <fx/2 * baseline_m>
  fps: 10
  cols: 960
  rows: 600
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
StereoRectifier:
  model: "perspective"
  K_left: [...]   # da calibração
  D_left: [...]
  R_left: [...]
  K_right: [...]
  D_right: [...]
  R_right: [...]
```
Os `<…>` são valores lidos da calibração do dataset (mesmos usados no Task 13 Step 5). Se as imagens do bag já vierem retificadas, remover `StereoRectifier` e zerar distorção.

- [ ] **Step 5: Build e smoke**

```bash
bash scripts/build_stella.sh
.venv/bin/python -m ofd.run_vo --method stella --seq-dir data/extracted/1018-00_smoke \
  --settings configs/botanic/stella.yaml --out data/runs/1018-00_smoke/stella
scripts/test.sh tests/test_run_vo.py -q
```
Expected: `frames.csv` ~1200 linhas, maioria `ok=1`, `reproj_err` finito.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_stella.sh tools/vo_runners/stella_stereo_log.cc configs/*/stella.yaml patches/stella
git commit -m "feat(stella): build nativo com commits fixos, patch de indicadores, runner estéreo em tempo real sem loop"
```

---

### Task 15: Contrato, teste ponta a ponta sintético e pipeline real

**Files:**
- Create: `ofd/contract.py`, `scripts/run_sequence.sh`, `docs/RESULTS_smoke.md`
- Test: `tests/test_contract.py`, `tests/test_e2e_synthetic.py` (**nunca pulado**), `tests/test_pipeline_contract.py` (saída real; pulado se não existir)

**Interfaces:**
- Consumes: tudo acima.
- Produces:
  - `contract.check(df: DataFrame, schema: dict, max_age_ms=100.0) -> None` — levanta `AssertionError` com mensagem clara se: colunas ≠ schema (mesma ordem); vazamento (`schema.assert_no_leak`); `t` não estritamente crescente; para cada método e linha válida: `qw ≥ 0`, `0 ≤ age_ms ≤ max_age_ms`, `src_ts ≤ t`, `dt_ms > 0`, nenhuma feature NaN (exceto `*_var_H`).
  - `data/output/<seq>.parquet|csv`, `data/output/schema.json`, `data/output/metrics.csv`, `docs/RESULTS_smoke.md`.

- [ ] **Step 1: Teste do contrato** — `tests/test_contract.py`

```python
import numpy as np
import pytest
from ofd import contract, schema
from tests.test_build_dataset import fake_seq
from ofd import build_dataset


def built(tmp_path):
    seq, runs = fake_seq(tmp_path)
    return build_dataset.build_sequence(seq, runs, {m: np.eye(4) for m in schema.METHODS}, "botanic", "survey")


def test_contract_ok(tmp_path):
    contract.check(built(tmp_path), schema.build_schema(schema.METHODS))


def test_contract_catches_future_source(tmp_path):
    df = built(tmp_path)
    k = df.index[df["kissicp_valid"] == 1][0]
    df.loc[k, "kissicp_src_ts"] = df.loc[k, "t"] + 1
    with pytest.raises(AssertionError, match="causal"):
        contract.check(df, schema.build_schema(schema.METHODS))


def test_contract_catches_negative_qw(tmp_path):
    df = built(tmp_path)
    k = df.index[df["stella_valid"] == 1][0]
    df.loc[k, "stella_qw"] = -0.5
    with pytest.raises(AssertionError, match="qw"):
        contract.check(df, schema.build_schema(schema.METHODS))
```

- [ ] **Step 2: Implementar `ofd/contract.py`**

```python
"""Output contract checks shared by the synthetic E2E test and the real-output test."""
import numpy as np

from ofd import schema as sch


def check(df, schema, max_age_ms=100.0):
    assert list(df.columns) == list(schema), "colunas diferentes do schema"
    sch.assert_no_leak(schema)
    t = df["t"].to_numpy(np.int64)
    assert np.all(np.diff(t) > 0), "t não é estritamente crescente"
    for m in sch.METHODS:
        v = df[df[f"{m}_valid"] == 1]
        assert (v[f"{m}_qw"] >= 0).all(), f"{m}: qw < 0"
        assert v[f"{m}_age_ms"].between(0, max_age_ms).all(), f"{m}: age_ms fora de [0, {max_age_ms}]"
        assert (v[f"{m}_src_ts"] <= v["t"]).all(), f"{m}: pose não causal (src_ts > t)"
        assert (v[f"{m}_dt_ms"] > 0).all(), f"{m}: dt_ms <= 0"
        feats = [c for c, r in schema.items() if r == "feature" and c.startswith(f"{m}_") and not c.endswith("_var_H")]
        bad = [c for c in feats if v[c].isna().any()]
        assert not bad, f"{m}: features NaN em linhas válidas: {bad}"
```

Run: `scripts/test.sh tests/test_contract.py -q` → `3 passed`.

- [ ] **Step 3: Teste ponta a ponta sintético** — `tests/test_e2e_synthetic.py` (sem dados reais, sem skip): 4 métodos falsos com comportamentos distintos → `build_dataset` → `write_outputs` → `evaluate_sequence` → `contract.check`.

```python
import json
import numpy as np
import pandas as pd
from ofd import build_dataset, contract, evaluate, schema, se3, tracks

MS = 1_000_000


def test_e2e(tmp_path):
    seq, runs = tmp_path / "ext", tmp_path / "runs"
    seq.mkdir()
    n = 450                                                  # 45 s a 10 Hz, 1 m/s
    end = (10**18 + np.arange(n) * 100 * MS).astype(np.int64)
    pd.DataFrame({"ts_ns": end - 100 * MS, "end_ns": end}).to_csv(seq / "lidar_stamps.csv", index=False)
    gt = np.stack([np.eye(4)] * n)
    for i in range(n):
        gt[i][0, 3] = 0.1 * i
    se3.save_tum(seq / "gt.tum", end, gt)
    rng = np.random.default_rng(0)
    for m, kind in schema.METHODS.items():
        ts = end - (30 * MS if kind == "vo" else 0)       # VO: câmera 30 ms antes do fim do scan
        Ts = gt.copy()
        ok = np.ones(n, int)
        if m == "stella":
            ok[200:220] = 0                                  # perde tracking 2 s
        if m == "orbslam3":
            Ts[:, 0, 3] *= 1.05                              # erro de escala 5%
        if m == "kissicp":
            Ts[:, 1, 3] += rng.normal(0, 0.01, n)            # ruído lateral
        cols = schema.VO_IND if kind == "vo" else schema.LO_IND
        ind = pd.DataFrame({"ts_ns": ts, **{c: rng.random(n) for c in cols}})
        tracks.write_run(runs / m, ts[ok == 1], Ts[ok == 1], pd.DataFrame({"ts_ns": ts, "ok": ok, "map_id": 0}),
                         ind, {"method": m, "uses_imu": m == "fastlio"})
    T = {m: np.eye(4) for m in schema.METHODS}
    df = build_dataset.build_sequence(seq, runs, T, "synthetic", "survey")
    sch = schema.build_schema(schema.METHODS)
    contract.check(df, sch)
    build_dataset.write_outputs(df, sch, tmp_path / "out", "syn")
    assert json.loads((tmp_path / "out/schema.json").read_text()) == sch
    met = evaluate.evaluate_sequence(seq, runs, df, T).set_index("method")
    assert met.loc["fastlio", "ate_rmse"] < 1e-6 and met.loc["fastlio", "coverage"] > 0.99
    assert met.loc["stella", "n_failures"] == 1 and met.loc["stella", "n_resets"] == 1
    assert met.loc["stella", "coverage"] < met.loc["fastlio", "coverage"]
    assert met.loc["orbslam3", "ate_rmse"] > 0.1
    assert (met["eligible_frac"] <= 1.0).all()
    np.testing.assert_allclose(df.loc[df["fastlio_valid"] == 1, "fastlio_vx"], 1.0, atol=1e-6)
    np.testing.assert_allclose(df["gt_vx"].dropna(), 1.0, atol=1e-6)
```

Run: `scripts/test.sh tests/test_e2e_synthetic.py -q` → `1 passed`. (Se falhar, o defeito está nas Tasks 3–8: corrigir lá, não aqui.)

- [ ] **Step 4: `scripts/run_sequence.sh`**

```bash
#!/usr/bin/env bash
# uso: scripts/run_sequence.sh <dataset: botanic|rellis> <seq_name> <bag> [start_s duration_s] [gt_tum]
set -euo pipefail
cd "$(dirname "$0")/.."
DS=$1; SEQ=$2; BAG=$3; START=${4:-}; DUR=${5:-}; GT=${6:-}
PY=.venv/bin/python; C=configs/$DS
EXT=data/extracted/$SEQ; RUNS=data/runs/$SEQ
WIN=(); [ -n "$START" ] && WIN+=(--start "$START" --duration "$DUR")
GTA=(); [ -n "$GT" ] && GTA+=(--gt-tum "$GT")
$PY -m ofd.extract --bag "$BAG" --config $C/dataset.yaml --out $EXT "${WIN[@]}" "${GTA[@]}"
$PY -m ofd.run_kissicp --seq-dir $EXT --out $RUNS/kissicp
$PY -m ofd.lidar_indicators --seq-dir $EXT --run-dir $RUNS/kissicp --config $C/dataset.yaml --method kissicp
read -r LID IMU < <($PY -c "import yaml;d=yaml.safe_load(open('$C/dataset.yaml'))['topics'];print(d['lidar'],d['imu'])")
$PY -m ofd.run_fastlio --bag "$BAG" --ros2-bag "${BAG%.bag}_ros2" --fastlio-config $C/fastlio.yaml \
  --seq-dir $EXT --out $RUNS/fastlio --topics "$LID" "$IMU" "${WIN[@]}"
$PY -m ofd.lidar_indicators --seq-dir $EXT --run-dir $RUNS/fastlio --config $C/dataset.yaml --method fastlio
$PY -m ofd.run_vo --method orbslam3 --seq-dir $EXT --settings $C/orbslam3.yaml --out $RUNS/orbslam3 --rate 1.0
$PY -m ofd.run_vo --method stella --seq-dir $EXT --settings $C/stella.yaml --out $RUNS/stella --rate 1.0
$PY -m ofd.build_dataset --seq-dir $EXT --runs-dir $RUNS --config $C/dataset.yaml --out data/output
$PY -m ofd.evaluate --seq-dir $EXT --runs-dir $RUNS --table data/output/$SEQ.parquet --config $C/dataset.yaml
```

- [ ] **Step 5: Teste sobre a saída real** — `tests/test_pipeline_contract.py` (complementa o sintético; pode ser pulado quando não há saída):

```python
import json
from pathlib import Path
import pandas as pd
import pytest
from ofd import contract

OUT = Path("data/output")


@pytest.mark.skipif(not (OUT / "schema.json").exists(), reason="sem saída real do pipeline")
def test_real_outputs_respect_contract():
    sch = json.loads((OUT / "schema.json").read_text())
    for p in OUT.glob("*.parquet"):
        contract.check(pd.read_parquet(p), sch)
```

- [ ] **Step 6: Smoke BotanicGarden** (trecho de 120 s do 1018-00):

```bash
bash scripts/run_sequence.sh botanic 1018-00_smoke data/raw/botanic/1018-00.bag 0 120 data/raw/botanic/1018-00_gt.tum
scripts/test.sh -q
```
Expected: todos os testes passam (incluindo `test_real_outputs_respect_contract`, agora não pulado); `metrics.csv` com 4 linhas.

- [ ] **Step 7: Sanidade** — no 1018-00 **completo** (sem start/duration): ATE do FAST-LIO na mesma ordem de grandeza do reportado no paper do BotanicGarden para FAST-LIO2. Se discrepar > 3×, investigar extrínseca IMU↔LiDAR e `timestamp_unit` antes de seguir.

- [ ] **Step 8: Smoke RELLIS** — conforme veredito do Task 9 (A: com GT; B: sem GT; C: não roda na etapa supervisionada).

- [ ] **Step 9: `docs/RESULTS_smoke.md`** — tabela do `metrics.csv` (ATE, eligible_frac, coverage, n_failures, n_resets, longest_s, longest_m, RPE) por método/sequência + observações (deskew usado, `uses_imu`, `matched_frac` do FAST-LIO, problemas encontrados). Em seguida liberar BotanicGarden 1018-13 (e RELLIS 00000 se veredito A/B) e rodar `run_sequence.sh` completo em cada.

- [ ] **Step 10: Commit**

```bash
git add ofd/contract.py scripts/run_sequence.sh tests/test_contract.py tests/test_e2e_synthetic.py tests/test_pipeline_contract.py docs/RESULTS_smoke.md
git commit -m "feat: contrato de saída, teste ponta a ponta sintético e pipeline real"
```

---

## Ordem de execução sugerida

Execução nativa e sequencial, com **revisão (pausa + revisor) nos marcos**:

1. Tasks 1–4 → **revisão 1** (convenções de pose e causalidade).
2. Tasks 5–8 → **revisão 2** (indicadores, schema, métricas). Rodar também o Step 1–3 da Task 15 (contrato + E2E sintético) aqui, pois só depende do núcleo.
3. Em paralelo ao núcleo: Task 9 (download pequeno do RELLIS) e início dos builds das Tasks 12–14 (spike de dependências; não dependem de dados). Download do BotanicGarden 1018-00.
4. Task 10 → **revisão 3** (extração real: `scans.csv`, `deskew`, pares estéreo).
5. Tasks 11–12 → **revisão 4** (LiDAR: `matched_frac`, fitness, ATE do FAST-LIO).
6. Tasks 13–14 → **revisão 5** (VOs: build, patches, tempo real, sem loop).
7. Task 15 Steps 4–10 (pipeline real, sanidade, resultados).
