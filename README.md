# odom-fusion-dataset

> **RASCUNHO — não publicado.** Itens marcados **PENDENTE** dependem de decisão do professor/equipe e não devem ser
> lidos como definitivos.

Dataset derivado para **fusão de odometrias**: saídas sincronizadas de quatro métodos de odometria (dois visuais e
dois por LiDAR), com indicadores de qualidade, máscaras de validade e ground truth, sobre sequências públicas do
BotanicGarden e do RELLIS-3D. Inclui o pipeline reproduzível que gera o dataset e o código do primeiro experimento de
fusão (protocolo pré-registrado).

**Primeiro experimento de fusão (20/10/2026):** o resultado confirmatório foi negativo pela regra pré-registrada — o
modelo aprendido não superou todos os baselines nas duas componentes. Descritivamente, a ponderação aprendida (F1)
melhorou consistentemente a velocidade angular, e a média simples superou a odometria isolada selecionada nas duas
dobras. Detalhes em `docs/RESULTS_fusion_model.md`.

## Estado

| Marco | Estado | Data | Evidência |
|---|---|---:|---|
| Builds reprodutíveis dos quatro métodos | Concluído | 14–15/10/2026 | `scripts/build_*.sh`, `patches/`, `8e27ad1`, `cea3e84`, `763edfd`, `2c35918` |
| Quatro sequências processadas | Concluído | 15/10/2026 | `docs/RESULTS_sequences.md`, `f0b7ea7` |
| Dataset derivado v1.0.0 | Concluído | 19/10/2026 | tag `dataset-v1.0.0`, `docs/dataset_manifest.json` |
| Schema e contrato de 121 colunas | Validado | 19/10/2026 | `data/output/schema.json`, `tests/test_pipeline_contract.py` |
| Protocolo de fusão pré-registrado | Concluído | 19/10/2026 | `docs/protocol_fusion_model.md`, `44bc961` |
| Fase 1 inicial | Invalidada e preservada | 19/10/2026 | `docs/RESULTS_fusion_model.md` |
| Correção e clipe ±10 | Concluído | 20/10/2026 | `eaf4983`, `77d70ba` |
| Fase 1 repetida e revisada | Aprovada | 20/10/2026 | `0ca8afc` |
| Fase 2 confirmatória | Concluída — resultado negativo pela regra pré-registrada | 20/10/2026 | executada com `0ca8afc`, sem ajustes |
| Registro final dos resultados | Concluído | 20/10/2026 | `docs/RESULTS_fusion_model.md`, relato §3.8, `cff68f7`, `299197f` |
| Licenças de origem | Termos levantados; autorização de redistribuição pendente | 20/10/2026 | seção *Licenças* |
| README público e ficha do dataset | Em elaboração | — | este arquivo, `docs/DATASHEET.md` |
| `CITATION.cff` e autoria | **PENDENTE — decisão do professor/equipe** | — | `CITATION.cff.template` |
| Hospedagem no OneDrive da PUC | **PENDENTE** | — | link institucional |
| Validação do escopo pelo professor | Pendente | — | duas sequências confirmatórias com GT |
| Preparação do artigo | Planejado | dez/2026 | conferência a definir |

## Conteúdo

| Sequência | Origem | Linhas | Duração | GT | Uso |
|---|---|---:|---:|---|---|
| `1018-00` | BotanicGarden | 1466 | ≈ 148 s | sim (scanner Leica) | confirmatório |
| `1018-13` | BotanicGarden | 2071 | ≈ 209 s | sim (scanner Leica) | confirmatório |
| `rellis_example` | RELLIS-3D | 599 | ≈ 60 s | não | exploratório |
| `00000` | RELLIS-3D | 2849 | ≈ 285 s | não validado (ver ficha) | exploratório |

Métodos: **ORB-SLAM3** e **Stella VSLAM** (visual estéreo), **FAST-LIO2** (LiDAR-inercial) e **KISS-ICP** (LiDAR).
Uma linha por scan do LiDAR (≈ 10 Hz); para cada método, velocidade em se(3), validade, idade, intervalo e
indicadores de qualidade; alvo `gt_vx … gt_wz`. Detalhes de colunas, proveniência e limitações em
[`docs/DATASHEET.md`](docs/DATASHEET.md).

## Download

**PENDENTE — link institucional (OneDrive da PUC).** Os arquivos e seus SHA-256 estão em
[`docs/dataset_manifest.json`](docs/dataset_manifest.json); confira depois de baixar:

```bash
sha256sum -c <(python -c "import json; m=json.load(open('docs/dataset_manifest.json')); \
  print('\n'.join(f\"{f['sha256']}  data/output/{f['path']}\" for f in m['files']))")
```

## Leitura

O **Parquet é o formato canônico**; o CSV é cópia de conveniência.

```python
import pandas as pd

df = pd.read_parquet("data/output/1018-13.parquet")
# CSV: obrigatório o dtype, senão o pandas lê seq "00000" como 0
df_csv = pd.read_csv("data/output/00000.csv", dtype={"seq": "string"})

feats = [c for c, r in pd.read_json("data/output/schema.json", typ="series").items() if r == "feature"]
valid = df["fastlio_valid"] == 1                     # use sempre a máscara de validade de cada método
```

## Reproduzir

Requisitos: Ubuntu 24.04, ROS 2 Jazzy, Python 3.12. Ambiente: `scripts/setup_env.sh` (cria `.venv` com
`requirements.lock`). Builds: `scripts/build_*.sh`. Uma sequência:

```bash
scripts/run_sequence.sh <botanic|rellis> <seq> <bag> [início duração] [gt: bag ou .tum]
python -m tools.dataset_manifest --check        # confere a saída contra o manifesto
scripts/test.sh -q                              # suíte de testes
```

Histórico de decisões e evidências: `docs/RELATO_ACADEMICO_PIPELINE.md` e os protocolos/resultados em `docs/`.

## Licenças

Três camadas, tratadas separadamente:

1. **Código deste repositório — PENDENTE — decisão do professor/equipe** (política da PUC). Restrição a considerar:
   `tools/vo_runners/orbslam3_stereo_log.cc` liga com o ORB-SLAM3 (GPLv3) e `patches/` modifica código GPL
   (ORB-SLAM3 GPLv3, FAST-LIO GPLv2); esses arquivos herdam as condições da GPL ao serem distribuídos,
   independentemente da licença escolhida para o restante.
2. **Dados derivados — PENDENTE — decisão do professor/equipe.** Ficam condicionados às origens: o RELLIS-3D é
   CC BY-NC-SA 3.0 (atribuição, uso não comercial, mesma licença), e o BotanicGarden não declara licença, apenas
   "provided for academic purposes". Recomenda-se consultar os autores do BotanicGarden antes de redistribuir
   derivados dele.
3. **Datasets e métodos de origem** (não redistribuídos aqui; obtenha-os nas fontes):

| Componente | Licença | Atribuição |
|---|---|---|
| BotanicGarden | não declarada; "provided for academic purposes" | Liu et al., *IEEE RA-L* 9(3), 2024, doi:10.1109/LRA.2024.3359548 |
| RELLIS-3D | CC BY-NC-SA 3.0 | Jiang et al., arXiv:2011.12954, 2020 |
| ORB-SLAM3 | GPLv3 | Campos et al., *IEEE T-RO*, 2021 |
| Stella VSLAM | BSD 2-Clause | stella-cv (fork do OpenVSLAM) |
| FAST-LIO2 | GPLv2 | Xu et al., *IEEE T-RO*, 2022 |
| KISS-ICP | MIT | Vizzo et al., *IEEE RA-L*, 2023 |

## Citação

**PENDENTE — autoria e referência do artigo.** O `CITATION.cff` será gerado de `CITATION.cff.template` quando autoria,
licença, data e links estiverem decididos. Cite também os datasets de origem.

## Contato

**PENDENTE.**
