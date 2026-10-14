# Dataset de Odometrias para Fusão VO/LO — Design

**Data:** 2026-10-14
**Contexto:** artigo do Edvaldo (1º autor, mestrado PUCPR, orientador Prof. Marco Teixeira) sobre fusão
adaptativa de odometria visual e LiDAR. Parte do Luiz: **gerar o dataset de entrada do modelo de fusão**.
**Prazo alvo:** submissão de meados de dezembro/2026 (a de 25/10 é considerada inviável pelo orientador).

## 1. Objetivo

Rodar 2 odometrias visuais + 2 odometrias LiDAR sobre datasets públicos de ambientes não estruturados
e produzir um **dataset derivado** com, por instante de tempo:

- pose incremental (ΔX) estimada por cada uma das 4 odometrias;
- indicadores de qualidade de cada fonte (dissertação §4.3.3);
- pose incremental do Ground Truth (rótulo para a loss geométrica da §4.4.4);

mais as trajetórias completas (formato TUM) e as métricas ATE/RPE de cada odometria isolada (baseline do artigo).

**Fora do escopo:** o modelo de ML de fusão (LSTM/CNN) — fica com o Edvaldo/orientador; aqui só a entrada.

## 2. Decisões

| Item | Escolha | Motivo |
|---|---|---|
| Datasets | **BotanicGarden** (SJTU, jardim botânico, China) + **RELLIS-3D** (off-road, Texas) | Ambos têm sequências contínuas com estéreo + LiDAR + IMU + GT. WildScenes e GOOSE (citados na dissertação) são datasets de segmentação — não garantem sequência contínua de câmera; ficam fora. |
| VO 1 | **ORB-SLAM3** (modo estéreo) | Pedido do orientador; já na dissertação. |
| VO 2 | **Stella VSLAM** (modo estéreo) | Pedido do orientador. |
| LO 1 | **FAST-LIO2** (port ROS 2 já em `Controle_robo_livox/ros2_packages/FAST_LIO`) | Já instalado; suporta VLP16 e Ouster64. |
| LO 2 | **KISS-ICP** | ICP puro (o indicador "fitness ICP" é natural), instalação via pip, sem ROS. LeGO-LOAM (citado na dissertação) é ROS 1 only — inviável em Ubuntu 24.04/Jazzy. |
| Modo das VOs | estéreo **sem IMU** | Mantém VO "visual pura" vs LO; evita que a VO herde robustez do IMU e mascare a degradação visual que o modelo deve aprender. |
| LiDAR usado | BotanicGarden: **Velodyne VLP16**; RELLIS-3D: **Ouster OS1-64** | Os mesmos LiDARs para FAST-LIO e KISS-ICP → comparação justa. |
| Execução | VOs e KISS-ICP **offline** (arquivos extraídos); FAST-LIO via `ros2 bag play` | Determinismo e velocidade; ROS só onde é inevitável. |
| Bags ROS 1 | convertidos com `rosbags` (pip) | Não precisa de ROS 1 instalado. |
| Docker | não usado | Usuário sem permissão no socket; tudo nativo em Ubuntu 24.04 + ROS 2 Jazzy. |

Sequências iniciais (MVP): BotanicGarden **1018-00** (13 GB) e **1018-13** (21 GB); RELLIS-3D **00000** (full-stack merged, 23 GB).
Ampliar depois de o pipeline funcionar ponta a ponta.

## 3. Arquitetura

```
odom-fusion-dataset/
  third_party/            # ORB_SLAM3, stella_vslam (+ patches de log), builds
  patches/                # diffs aplicados nos algoritmos (logging de indicadores)
  configs/<dataset>/      # calibração/yaml por algoritmo e dataset
  ofd/                    # pacote Python
    extract.py            # bag -> imagens estéreo + nuvens + GT (TUM) + timestamps
    run_orbslam3.py       # executa binário e coleta trajetória + log de indicadores
    run_stella.py
    run_fastlio.py        # bag play + gravação de /Odometry e log
    run_kissicp.py        # API Python do KISS-ICP + indicadores
    indicators.py         # fitness/inlier_rmse ICP (Open3D) e dinamicidade, comuns às LOs
    align.py              # sincronização temporal + transformação para frame comum
    build_dataset.py      # monta a tabela final
    evaluate.py           # ATE/RPE por método (evo)
  data/raw/ data/extracted/ data/runs/ data/output/   # fora do git
  tests/
```

Cada unidade lê/escreve arquivos em `data/` — dá para reexecutar uma etapa isolada sem refazer as anteriores.

## 4. Fluxo de dados

1. **extract**: bag → `images/left|right/<ts>.png`, `clouds/<ts>.bin`, `gt.tum`, `calib.yaml`.
2. **run_***: cada algoritmo → `data/runs/<seq>/<metodo>/traj.tum` + `indicators.csv` (ts, colunas próprias).
3. **align**: todas as trajetórias são levadas ao frame do LiDAR (extrínsecas do dataset) e reamostradas
   na grade de tempo do LiDAR (10 Hz) por interpolação (SLERP para rotação). Frames em que o método
   perdeu o tracking ficam com `valid=0` (não interpolar através de falhas).
4. **build_dataset**: por sequência, `data/output/<seq>.parquet` (+ `.csv`), uma linha por passo k:
   - `t`, `seq`, `dataset`
   - `gt_dx, gt_dy, gt_dz, gt_qx, gt_qy, gt_qz, gt_qw` (ΔX do GT entre k-1 e k)
   - para cada método m ∈ {orbslam3, stella, fastlio, kissicp}: `m_dx..m_qw`, `m_valid`, `m_err_t`, `m_err_r`
     (erro de translação/rotação do ΔX contra o GT — facilita a loss e a análise)
   - indicadores VO (por método visual): `m_inliers`, `m_reproj_err`, `m_tracked_ratio`
   - indicadores LO (por método LiDAR): `m_fitness`, `m_inlier_rmse`, `m_n_points`
   - `dynamicity`: razão de pontos sem correspondência após o registro (scan k vs k-1) +
     variância móvel (janela H) do fitness e do erro de reprojeção.
5. **evaluate**: `data/output/metrics.csv` com ATE (alinhamento SE3) e RPE (Δ=1 m e Δ=1 frame) por método/sequência + plots.

## 5. Indicadores — origem

- **ORB-SLAM3**: patch em `Tracking` para logar por frame `mnMatchesInliers`, nº de features, erro de
  reprojeção médio dos inliers (calculado com a pose otimizada), estado do tracking.
- **Stella VSLAM**: patch/callback no tracking para logar nº de landmarks rastreados, inliers do pose
  optimizer, erro de reprojeção médio, estado.
- **FAST-LIO / KISS-ICP**: indicadores calculados **de forma uniforme** em `indicators.py` a partir da pose
  estimada: registro scan k → k-1 com a ΔX do método e `open3d.pipelines.registration.evaluate_registration`
  (fitness, inlier_rmse). Mesma métrica para as duas LOs → comparáveis. Adicionalmente, nº de pontos efetivos
  do FAST-LIO quando disponível no log.

## 6. Erros e falhas

- Perda de tracking da VO: registrada como `valid=0`; reinicialização do mapa não é "costurada" — o ΔX
  daquele passo é inválido, os seguintes voltam a ser válidos (ΔX é relativo, então funciona).
- Cada etapa falha alto (exceção) se arquivo de entrada faltar; logs por execução em `data/runs/.../log.txt`.
- Execuções guardam a config usada e o commit/patch do algoritmo para reprodutibilidade.

## 7. Testes

- Unitários (pytest) para `align` (interpolação, troca de frame, ΔX), `indicators` (nuvens sintéticas com
  transformação conhecida) e `build_dataset` (schema/colunas, sem NaN em linhas válidas).
- Teste de fumaça: 60 s de uma sequência atravessando todo o pipeline.
- Sanidade: ATE do FAST-LIO no BotanicGarden deve ficar na ordem do reportado no paper do dataset.

## 8. Riscos

- **Build do ORB-SLAM3 em Ubuntu 24.04** (OpenCV 4.6, Pangolin, C++17) — conhecido por precisar de patches.
  Mitigação: compilar sem viewer se necessário.
- **GT do RELLIS-3D** vem de SLAM/INS, não de RTK puro — documentar como limitação; BotanicGarden tem GT
  de ~1 cm (scanner Leica) e é o dataset principal.
- **Download** (OneDrive/Google Drive, 13–83 GB por sequência) pode ser lento/limitado.
- **RAM 15 GB**: rodar um algoritmo por vez.
