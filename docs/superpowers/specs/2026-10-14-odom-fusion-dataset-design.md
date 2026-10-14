# Dataset de Odometrias para Fusão VO/LO — Design

**Data:** 2026-10-14 (rev. 2 — incorpora revisão: vazamento de GT, causalidade, FAST-LIO como LIO,
timestamps por ponto, contrato de frames, cobertura)
**Contexto:** artigo do Edvaldo (1º autor, mestrado PUCPR, orientador Prof. Marco Teixeira) sobre fusão
adaptativa de odometria visual e LiDAR. Parte do Luiz: **gerar o dataset de entrada do modelo de fusão**.
**Prazo alvo:** submissão de meados de dezembro/2026 (a de 25/10 é considerada inviável pelo orientador).

## 1. Objetivo

Rodar 2 odometrias visuais + 2 odometrias baseadas em LiDAR sobre datasets públicos de ambientes não
estruturados e produzir um **dataset derivado** com, por instante de tempo:

- pose incremental (ΔT) **causal** estimada por cada uma das 4 odometrias;
- indicadores de qualidade de cada fonte (dissertação §4.3.3), calculados só com passado;
- pose incremental do Ground Truth (rótulo para a loss geométrica da §4.4.4);

mais as trajetórias completas (formato TUM) e as métricas ATE/RPE + cobertura de cada odometria isolada
(baseline do artigo).

**Fora do escopo:** o modelo de ML de fusão — fica com o Edvaldo/orientador; aqui só a entrada.

## 2. Decisões

| Item | Escolha | Motivo |
|---|---|---|
| Datasets | **BotanicGarden** (SJTU, jardim botânico, China) — **principal**; **RELLIS-3D** (off-road, Texas) — secundário | Ambos têm sequências contínuas com estéreo + LiDAR + IMU + GT. WildScenes não confirma sequência contínua de câmera e GOOSE é dataset de segmentação; ficam fora. |
| VO 1 | **ORB-SLAM3**, estéreo, **sem IMU, loop closure desligado** | Pedido do orientador. Sem loop closure = odometria pura e causal. |
| VO 2 | **Stella VSLAM**, estéreo, **sem IMU, loop closure desligado** | Pedido do orientador. |
| LIO | **FAST-LIO2** (port ROS 2 em `Controle_robo_livox/ros2_packages/FAST_LIO`) | Já instalado. **É LiDAR-inercial (fortemente acoplado), não LO pura** — registrado como `uses_imu=true`; tratado no artigo como limitação/ablação. |
| LO | **KISS-ICP** | LO pura (ICP), instalação via pip, sem ROS. LeGO-LOAM é ROS 1 only — inviável em Ubuntu 24.04/Jazzy. |
| LiDAR | BotanicGarden: **Velodyne VLP16**; RELLIS-3D: **Ouster OS1-64** | Mesmo LiDAR para FAST-LIO e KISS-ICP. |
| Execução | VOs e KISS-ICP **offline** (arquivos extraídos); FAST-LIO via `ros2 bag play` | Determinismo; ROS só onde é inevitável. |
| Bags ROS 1 | convertidos com `rosbags` (pip) | Não precisa de ROS 1. |
| Docker | não usado | Usuário sem permissão no socket; tudo nativo (Ubuntu 24.04 + ROS 2 Jazzy). |

**Ordem de download (economia):** 0) só `poses.txt`/arquivos de poses do RELLIS (174 MB) + exemplo de 60 s
(4,2 GB) → **preflight do mapeamento de GT** (§9); 1) BotanicGarden **1018-00** (13 GB) → smoke tests;
2) só depois RELLIS **00000** (23 GB) e BotanicGarden **1018-13** (21 GB). Downloads completos ficam
retidos até o preflight passar.
Extração multiplica o volume (PNG/NPZ) — monitorar disco (569 GB livres).

## 3. Arquitetura

```
odom-fusion-dataset/
  third_party/            # ORB_SLAM3, stella_vslam (+ patches de log), builds
  patches/                # diffs aplicados nos algoritmos
  configs/<dataset>/      # calibração/yaml por algoritmo e dataset
  ofd/                    # pacote Python
    extract.py            # bag -> imagens estéreo + nuvens (todos os campos) + GT (TUM) + timestamps
    run_orbslam3.py       # executa binário, coleta poses causais + log de indicadores
    run_stella.py
    run_fastlio.py        # bag play + gravação de /Odometry
    run_kissicp.py        # API Python do KISS-ICP
    indicators.py         # fitness/inlier_rmse/unmatched_ratio (Open3D), comuns às LOs
    align.py              # sincronização, troca de frame, ΔT, segmentos
    build_dataset.py      # tabela final + schema
    evaluate.py           # ATE/RPE + cobertura por método (evo)
  data/raw/ data/extracted/ data/runs/ data/output/   # fora do git
  tests/
```

Cada unidade lê/escreve arquivos em `data/` — dá para reexecutar uma etapa isolada.

## 4. Contrato de poses e frames

- **Convenção:** `T_W_B` = pose do corpo B no mundo W (matriz 4×4, B→W). Incremento:
  **ΔT_k = T_{k-1}⁻¹ · T_k**, logo a translação de ΔT está expressa **no frame do corpo em k-1**.
- **Frame comum:** o corpo de referência é o **frame do LiDAR** usado (VLP16 / OS1-64). Uma pose estimada no
  frame do sensor S é convertida por conjugação com a extrínseca `T_L_S` (S→L):
  `T_W_L = T_W_S · T_L_S⁻¹`, equivalente para incrementos: `ΔT_L = T_L_S · ΔT_S · T_L_S⁻¹`.
  O frame mundo de cada método é arbitrário; como só ΔT entra no dataset, ele não precisa ser alinhado.
- **Quaternion:** (qx, qy, qz, qw) com **qw ≥ 0** (sinal normalizado).
- **Sincronização (estritamente causal):** grade de tempo = timestamps do LiDAR (10 Hz). Para cada método e
  passo k usa-se a **última pose com `src_ts ≤ t_k`**; **sem interpolação** (nenhum uso de pose posterior a
  t_k). Válido só se `0 ≤ age_ms ≤ max_age_ms` (configurável; padrão **100 ms** = um período da câmera a
  10 Hz nos bags do BotanicGarden — 50 ms invalidaria passos de métodos sem falha). Colunas:
  `m_src_ts`, `m_age_ms = t_k − m_src_ts`, e **`m_dt_ms` = src_ts(k) − src_ts(k−1)** (intervalo efetivamente
  coberto pelo ΔT do método, que pode diferir entre métodos e do GT). Se as duas poses de origem forem a
  mesma (`m_dt_ms = 0`) → `m_valid=0`.
- **GT na grade:** o GT é rótulo (não entra no modelo), então **pode** ser interpolado (linear + SLERP) entre
  poses vizinhas. `gt_d*` = ΔT do GT entre t_{k−1} e t_k. Para `m_err_t/m_err_r`, o GT é interpolado nos
  **mesmos instantes de origem do método** (src_ts(k−1), src_ts(k)), para comparar intervalos idênticos.
- **Causalidade:** para as VOs, a pose usada é a **retornada pelo tracking no próprio frame** (logada pelo
  patch no momento do `Track*`), nunca o arquivo de trajetória final reotimizado. FAST-LIO (`/Odometry`) e
  KISS-ICP já são causais.
- **GT:**
  - BotanicGarden: `gt_poses` do dataset, que já **rastreia o frame do VLP16** (aplicar a relação hand-eye
    indicada na documentação se necessário). A precisão de ~11 mm é **do mapa levantado (Leica RTC360)**, não
    uma garantia direta por pose.
  - RELLIS-3D: **`poses.txt`** (poses por scan do Ouster). É derivado de SLAM — referência menos confiável
    e **possivelmente correlacionada com métodos LiDAR(-inerciais)**. Coluna `gt_quality = survey|slam`.
    A origem exata do `poses.txt` é verificada na implementação e documentada. `/vectornav/Odom` (GNSS/INS
    sem RTK) **não** é usado como GT.

## 5. Fluxo de dados

1. **extract**: bag → `images/left|right/<ts_ns>.png`, `clouds/<ts_ns>.npz` (**todos os campos**: x, y, z,
   intensity, ring e tempo por ponto quando existirem), `gt.tum`, `calib.yaml`, `meta.json`
   com a **semântica do tempo por ponto**: `point_time_field` (ex.: `time`, `t`), `point_time_unit`
   (s, ns, …), `point_time_ref` (`scan_start` | `scan_end` | `absolute`) e o intervalo observado
   [min, max] por scan. `extract` converte para o formato esperado pelo KISS-ICP (tempos por ponto
   normalizados em [0, 1] ao longo do scan) e valida: duração do scan ≈ 100 ms (10 Hz) e tempos monotônicos
   por ring/azimute. Se a semântica não puder ser determinada ou falhar na validação → `deskew=false`.
   O que foi usado é registrado em `run.json`.
2. **run_***: cada algoritmo → `data/runs/<seq>/<metodo>/poses_causal.tum`, `indicators.csv`, `state.csv`
   (estado do tracking por frame), `run.json` (config, commit/patch, `uses_imu`, `deskew`).
3. **align**: segmentação por método (`segment_id` incrementa a cada perda/reinicialização de tracking ou
   troca de mapa), conversão para o frame do LiDAR, reamostragem na grade (regras da §4), ΔT.
   **Toda transição entre segmentos é inválida**: o ΔT que cruza segmentos tem `m_valid=0`.
4. **build_dataset**: `data/output/<seq>.parquet` (+ `.csv`) e `data/output/schema.json`.
5. **evaluate**: `data/output/metrics.csv` + plots.

## 6. Schema da tabela final

Uma linha por passo k. Cada coluna tem um **papel** declarado em `schema.json`:
`metadata` | `feature` (pode ser entrada do modelo) | `target` (rótulo) | `evaluation` (só análise).

| Coluna | Papel |
|---|---|
| `t`, `seq`, `dataset`, `gt_quality` | metadata |
| `m_src_ts`, `m_age_ms`, `m_segment_id`, `m_uses_imu` | metadata |
| `m_dt_ms` | feature |
| `m_dx, m_dy, m_dz, m_qx, m_qy, m_qz, m_qw` (ΔT do método) | feature |
| `m_valid` | feature |
| VO: `m_inliers`, `m_n_features`, `m_reproj_err`, `m_tracked_ratio` | feature |
| LO/LIO: `m_fitness`, `m_inlier_rmse`, `m_unmatched_ratio`, `m_n_points` | feature |
| `m_fitness_var_H`, `m_reproj_err_var_H` (variância móvel **causal**, janela H só de passado) | feature |
| `gt_dx … gt_qw` (ΔT do GT) | **target** |
| `m_err_t`, `m_err_r` (erro do ΔT do método vs GT) | **evaluation** — nunca entrada do modelo |

`unmatched_ratio` (antes "dinamicidade"): fração de pontos do scan k sem correspondência no scan k-1 após o
registro com o ΔT do método. Reflete objetos dinâmicos **mas também** oclusão, vegetação, mudança de FoV e
erro de registro — o nome evita sugerir mais do que mede.

## 7. Indicadores — origem

- **ORB-SLAM3**: patch em `Tracking` para logar por frame, no momento do tracking: pose `Tcw`, estado,
  `mnMatchesInliers`, nº de features, erro de reprojeção médio dos inliers com a pose otimizada, id do mapa
  ativo (→ `segment_id`).
- **Stella VSLAM**: idem — pose retornada por `feed_stereo_frame`, estado do tracker, nº de landmarks
  rastreados, inliers do pose optimizer, erro de reprojeção médio, id/reset do mapa.
- **FAST-LIO / KISS-ICP**: calculados **uniformemente** em `indicators.py`: registro scan k → k-1 com o ΔT
  do método e `open3d.pipelines.registration.evaluate_registration` (fitness, inlier_rmse) +
  `unmatched_ratio`. Mesma métrica nas duas → comparáveis.

## 8. Falhas e avaliação

- Perda de tracking / reinicialização / troca de mapa → novo `segment_id`; ΔT da transição inválido.
- `metrics.csv` por método/sequência: **ATE** (alinhamento SE3 por segmento) e **RPE** (Δ=1 frame e
  Δ=10 m), **e também** cobertura (% de passos válidos), nº de falhas/reinicializações, maior trecho contínuo
  (s e m). Um método só é comparado por ATE junto com sua cobertura.
- **Segmentos para ATE:** só entram segmentos com **≥ 30 s e ≥ 20 m percorridos (no GT)**; os menores contam
  como não cobertos. ATE da sequência = **média ponderada pelo nº de poses** dos segmentos elegíveis
  (RMSE agregado: √(Σ nᵢ·RMSEᵢ² / Σ nᵢ)). Reporta-se também a fração da trajetória coberta por segmentos
  elegíveis — evita ATE artificialmente baixo por muitos segmentos pequenos alinhados separadamente.
- Cada etapa falha alto se faltar entrada; logs em `data/runs/.../log.txt`; `run.json` garante
  reprodutibilidade.

## 9. Testes

- Unitários (pytest): `align` (convenção ΔT, conjugação com extrínseca, qw ≥ 0, tolerância/age, invalidação
  entre segmentos), `indicators` (nuvens sintéticas com transformação conhecida), `build_dataset` (schema com
  papel para toda coluna; nenhuma coluna `evaluation`/`target` marcada como `feature`; sem NaN em linhas
  válidas), variância móvel causal (mudar o futuro não altera o valor em k).
- **Preflight de GT do RELLIS:** o bag de exemplo de 60 s garante sensores, mas `poses.txt` é indexado por
  scan da sequência completa. Antes de qualquer download grande, provar o mapeamento amostra→pose
  (timestamps do bag vs índices/tempos do `poses.txt` / arquivos de scan). Se não existir mapeamento, o smoke
  de 60 s vai até o schema **sem métricas de GT**, e o end-to-end completo do RELLIS espera a sequência 00000.
- Smoke test: exemplo de 60 s do RELLIS (sujeito ao preflight) e trecho do 1018-00 atravessando todo o
  pipeline.
- Testes de `extract` para tempo por ponto: unidade/referência sintéticas (scan_start, scan_end, absoluto)
  → mesma normalização [0, 1].
- Sanidade: ATE do FAST-LIO no BotanicGarden na ordem do reportado no paper do dataset.

## 10. Riscos

- **Build do ORB-SLAM3 em Ubuntu 24.04** (OpenCV 4.6, Pangolin, C++17) — costuma exigir patches. Mitigação:
  compilar sem viewer.
- **Stella VSLAM**: verificar estado de manutenção e build em 24.04 antes de comprometer prazo.
- **GT do RELLIS-3D** derivado de SLAM — avaliação principal no BotanicGarden.
- **FAST-LIO usa IMU** — comparação VO × LIO não é só de sensor; documentado como limitação.
- **Download** (OneDrive/Google Drive) pode ser lento/limitado.
- **RAM 15 GB**: um algoritmo por vez.
