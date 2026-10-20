# Ficha do dataset — odom-fusion-dataset v1.0.0

> **RASCUNHO.** Itens **PENDENTE** dependem de decisão do professor/equipe.

## 1. Motivação

Cada odometria tem um ponto fraco: a visual degrada com variação de iluminação e baixa textura; a por LiDAR, em
rotações rápidas e ambientes degenerados. O dataset registra, no mesmo instante e de forma causal, as estimativas de
quatro métodos e seus indicadores de qualidade, para treinar e avaliar algoritmos que ponderem ou fundam essas fontes.

- **Autoria/financiamento:** **PENDENTE — decisão do professor/equipe.**
- **Versão:** `dataset-v1.0.0` (tag do repositório; commit de geração `1d9a555`, schema SHA-256 `696acd40…f094`).

## 2. Composição

Uma linha por varredura do LiDAR (≈ 10 Hz); 121 colunas com papel explícito (`schema.json`):

| Papel | Colunas | Conteúdo |
|---:|---:|---|
| `metadata` | 44 | `t` (ns, fim da varredura), `seq`, `dataset`, `gt_quality`; por método: `src_ts`, `segment_id`, `uses_imu` e o incremento rígido `dx dy dz qx qy qz qw` |
| `feature` | 56 | por método: velocidade em se(3) `vx vy vz wx wy wz` (m/s, rad/s), `valid`, `dt_ms`, `age_ms`, indicadores de qualidade e a variância móvel causal (janela H = 10) de um indicador |
| `target` | 6 | `gt_vx … gt_wz`: velocidade do GT no mesmo intervalo |
| `evaluation` | 15 | incremento do GT `gt_dx … gt_qw`; por método, `err_t` e `err_r` (nunca usar como entrada) |

Indicadores: VOs (ORB-SLAM3, Stella) — `inliers`, `n_features`, `reproj_err`, `tracked_ratio`; LiDAR (FAST-LIO,
KISS-ICP) — `fitness`, `inlier_rmse`, `unmatched_ratio`, `n_points`.

Sequências e arquivos: ver README e `docs/dataset_manifest.json` (bytes, SHA-256, linhas, intervalo de `t`). O
Parquet é canônico; o CSV exige `dtype={"seq": "string"}`.

## 3. Convenções

- Pose `T_W,B`; incremento `ΔT_k = T_{k−1}⁻¹ T_k`, com translação no referencial do corpo no instante anterior. Corpo
  = LiDAR; estimativas de outros sensores são conjugadas pelas extrínsecas do dataset.
- Quatérnio `(qx, qy, qz, qw)` com `qw ≥ 0`. Velocidade `v_k = log(ΔT_k) / Δt_k`.
- **Causalidade:** para cada método usa-se a pose mais recente com timestamp ≤ `t`, aceita só se a idade estiver no
  limite do dataset; sem interpolação das odometrias. Só o GT é interpolado (é rótulo, não entrada).
- **Validade:** quando `m_valid = 0`, as demais colunas do método podem conter valores antigos (`dt_ms`, `age_ms`,
  variância móvel). Use sempre a máscara.

## 4. Coleta e processamento

Dados brutos de terceiros (não redistribuídos): BotanicGarden (estéreo, Velodyne VLP-16, IMU Xsens, GT de scanner
Leica) e RELLIS-3D (estéreo Nerian, Ouster OS1-64, IMU). Cada método roda separadamente com versões e patches fixados
(`scripts/build_*.sh`, `patches/`); o pipeline extrai o bag, executa os métodos, sincroniza causalmente, monta a
tabela e valida o contrato (`scripts/run_sequence.sh`, `tests/test_pipeline_contract.py`). Decisões e evidências:
`docs/RELATO_ACADEMICO_PIPELINE.md`.

## 5. Usos recomendados

- Fusão/ponderação de odometrias e estimação de confiabilidade por fonte, com divisão por sequência (sem embaralhar
  linhas de uma mesma sequência entre treino e teste).
- **Avaliação quantitativa só nas sequências BotanicGarden** (`1018-00`, `1018-13`). As do RELLIS-3D servem a
  análises descritivas.

## 6. Limitações conhecidas

- **Só duas sequências com GT**, do mesmo dataset e sensores: não sustentam alegação de generalização entre ambientes
  ou plataformas.
- **RELLIS-3D sem GT validado:** o `poses.txt` não pôde ser associado aos scans com segurança (`docs/preflight_rellis.md`);
  as colunas `gt_*` são NaN e `gt_quality = slam` é só o atributo de origem.
- **VOs variáveis entre execuções** (`docs/RESULTS_vo_repeat.md`): o dataset usa uma realização oficial; a variabilidade
  está documentada como distribuição.
- **KISS-ICP sem deskew** (`deskew=False`, `docs/RESULTS_kissicp.md`); erro maior no `1018-13`, associado a rotação rápida.
- **FAST-LIO só estima onde a IMU cobre** (no BotanicGarden a Xsens não cobre o início e o fim das sequências).
- **No RELLIS, a cobertura das VOs** fica limitada pela entrega irregular da câmera em relação à grade de 10 Hz.
- A divisão por `dt` amplifica o ruído em intervalos curtos; `dt_ms` está entre as entradas para que o modelo possa
  identificá-los.

## 7. Distribuição e manutenção

- **Hospedagem:** **PENDENTE — OneDrive institucional da PUC** (link no README).
- **Licença dos dados derivados:** **PENDENTE — decisão do professor/equipe**, condicionada às origens (RELLIS-3D
  CC BY-NC-SA 3.0; BotanicGarden sem licença declarada, "for academic purposes"). Ver README, seção *Licenças*.
- **Manutenção/contato:** **PENDENTE.** Versões novas recebem nova tag e novo manifesto.
