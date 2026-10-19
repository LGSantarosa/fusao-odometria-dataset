# Resultados — variabilidade entre execuções das VOs (protocolo `docs/protocol_vo_repeat.md`)

## Fase 1 — repetibilidade, decidida antes de abrir métricas de erro — 16/10/2026

Código: `084243d` (protocolo `e682f15`). Execuções: `python -m ofd.run_vo_repeat --reps 1,2,3` (24 execuções, uma por
vez, ordem intercalada da seção 4, `--rate 1.0`), em `data/runs/<seq>/<método>_r<k>`; registros e logs em
`data/analysis/vo_repeat/logs/` (`phase1_driver.log` e `<seq>_<método>_r<k>.{json,log}`). Análise:
`python -m ofd.vo_repeat --out data/analysis/vo_repeat/phase1` (`decisions.json`, `<seq>_<método>_{runs,pairs}.csv`).
Nenhuma métrica de erro (GT) foi calculada ou consultada.

**Execução.** 24/24 com código de saída 0, `status: finished`, tentativa 1, e válidas pela seção 5.1. Razão entre a
duração de relógio e a da sequência: 1,02 a 1,14, exceto a primeira execução da fase (1018-00/ORB-SLAM3 r1: 1,32;
r2 e r3: 1,07 e 1,08). Carga média de 1 min no início das execuções: 0,90 a 5,94 (16 núcleos), sem outro experimento
em paralelo; houve uso interativo da máquina (navegador) durante a fase.

**Hashes distintos entre as 3 execuções.** `poses_causal.tum` e `indicators.csv`: 3 em todas as combinações.
`state.csv`: 1 em todas, exceto 00000/ORB-SLAM3 (2).

**Componentes A, B e C** (máximo sobre os 3 pares; B e C no frame `cam_left`, sem GT):

| Combinação | A idêntico nos 3 pares | B máx. t (m) | B máx. r (°) | C máx. t (m) | C máx. r (°) | Decisão |
|---|---|---:|---:|---:|---:|---|
| 1018-00 / ORB-SLAM3 | sim | 0,149 | 2,38 | 0,239 | 2,51 | variável |
| 1018-00 / Stella | sim | 0,057 | 0,42 | 0,210 | 0,55 | variável |
| 1018-13 / ORB-SLAM3 | sim | 0,092 | 0,43 | 0,202 | 0,53 | variável |
| 1018-13 / Stella | sim | 0,154 | 1,96 | 1,580 | 2,34 | variável |
| rellis_example / ORB-SLAM3 | sim | 0,041 | 0,16 | 0,091 | 0,63 | variável |
| rellis_example / Stella | sim | 0,069 | 0,34 | 0,065 | 0,38 | variável |
| 00000 / ORB-SLAM3 | **não** (r3) | 0,548 | 4,87 | 25,29 | 8,59 | variável |
| 00000 / Stella | sim | 0,299 | 0,43 | 8,010 | 3,94 | variável |

- Componente A: em 7 combinações, `ok` e a segmentação foram idênticos nas três execuções. No 1018-13/ORB-SLAM3 as três
  execuções têm as mesmas 2 falhas e os mesmos 2 reinícios. No 00000/ORB-SLAM3, a execução 3 teve 1 falha e 1 reinício
  ausentes nas execuções 1 e 2, com 35 quadros de `ok` divergente (diferença de cobertura de 1,1 ponto percentual);
  as sobreposições foram comparadas separadamente (C com 2 sobreposições).
- B e C ficaram acima dos limiares (1 mm e 0,01°) em todos os pares, por várias ordens de grandeza. C mede a diferença
  acumulada entre execuções a partir de uma âncora comum; não é erro em relação ao GT.

**Decisão (seção 6):** as 8 combinações são variáveis. Pela regra, todas passam a dez execuções (r4–r10 em todas as
combinações, ~2 h 40 min em tempo real), e as métricas da fase 2 serão reportadas como distribuição sobre as dez.
**O escalonamento não foi iniciado:** aguarda revisão desta fase.

## Escalonamento para dez execuções (r4–r10) — 16/10/2026

Liberado após a revisão da fase 1. Execuções: `python -m ofd.run_vo_repeat --reps 4-10 --from-decisions
data/analysis/vo_repeat/phase1/decisions.json` (56 execuções, mesma ordem intercalada; registros com `repo_commit`
`a8bb1bd`, que difere de `084243d` só na documentação). Análise: `python -m ofd.vo_repeat --from-decisions
data/analysis/vo_repeat/phase1/decisions.json --out data/analysis/vo_repeat/phase1_escalated` (r1–r10, 45 pares por
combinação). Nenhuma métrica de erro (GT) foi calculada ou consultada.

**Execução.** 56/56 com código de saída 0, `status: finished`, tentativa 1; as 80 execuções (r1–r10) são válidas pela
seção 5.1. Razão relógio/sequência em r4–r10: 1,02 a 1,13. Carga média de 1 min no início: 2,8 a 8,3 (16 núcleos),
acima da faixa da fase 1 em algumas execuções (máximo em 00000/Stella r5, 1018-13/Stella r7, rellis_example/Stella r9
e 1018-13/ORB-SLAM3 r7, todas entre 7,3 e 8,3), sem outro experimento em paralelo.

**Hashes distintos entre as 10 execuções.** `poses_causal.tum` e `indicators.csv`: 10 em todas as combinações.
`state.csv`: 1 em seis combinações; 3 em 1018-13/ORB-SLAM3 e 6 em 00000/ORB-SLAM3.

**Componentes A, B e C** (máximo e mediana sobre os 45 pares; B e C no frame `cam_left`, sem GT):

| Combinação | A idêntico (pares) | B máx. t (m) | B máx. r (°) | C máx. t (m) | C máx. r (°) | C mediana t (m) | C mediana r (°) | Decisão |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1018-00 / ORB-SLAM3 | 45/45 | 0,207 | 3,49 | 0,540 | 6,03 | 0,219 | 2,60 | variável |
| 1018-00 / Stella | 45/45 | 0,072 | 0,49 | 0,309 | 0,74 | 0,184 | 0,50 | variável |
| 1018-13 / ORB-SLAM3 | **22/45** | 0,250 | 2,14 | 0,405 | 2,37 | 0,201 | 0,66 | variável |
| 1018-13 / Stella | 45/45 | 0,186 | 2,34 | 1,929 | 2,68 | 0,755 | 1,04 | variável |
| rellis_example / ORB-SLAM3 | 45/45 | 0,088 | 1,36 | 0,398 | 1,39 | 0,121 | 0,58 | variável |
| rellis_example / Stella | 45/45 | 0,199 | 0,35 | 0,256 | 0,54 | 0,065 | 0,23 | variável |
| 00000 / ORB-SLAM3 | **10/45** | 0,686 | 4,87 | 33,12 | 11,39 | 4,664 | 3,98 | variável |
| 00000 / Stella | 45/45 | 1,950 | 0,50 | 10,27 | 4,14 | 5,451 | 2,49 | variável |

- Componente A, só no ORB-SLAM3:
  - 1018-13: r1–r5, r8 e r9 têm 2 falhas e 2 reinícios (3 segmentos); r6, r7 e r10 têm 3 e 3 (4 segmentos).
    Diferença de cobertura até 2,0 pontos percentuais.
  - 00000: falhas/reinícios por execução — 0 (r1, r2, r6, r7, r10), 1 (r3, r4, r5, r9) e 3 (r8). Diferença de
    cobertura até 3,3 pontos percentuais; até 102 quadros de `ok` divergente (pares com r8).
  - Em todos os pares, B e C tiveram comparações definidas (B ≥ 1.500 e C ≥ 1.503 incrementos/poses no 1018-13;
    ≥ 2.926/2.931 no 00000), com até 3 e 5 sobreposições, respectivamente.
- B e C ficaram acima dos limiares (1 mm e 0,01°) em todos os 360 pares; o menor B máx. t foi 10,3 mm
  (rellis_example/Stella) e o menor C máx. t, 14,1 mm (idem).

**Decisão (seção 6):** as 8 combinações seguem variáveis com dez execuções. As métricas da fase 2 serão reportadas
como distribuição sobre r1–r10 (estatísticas da seção 7). **A fase 2 não foi iniciada:** exige liberação separada.

**Revisão — 19/10/2026.** Escalonamento aprovado. O revisor recalculou os 45 pares das oito combinações (máximos,
medianas, contagens de A e limites de B/C coincidem com esta seção), conferiu os 56 registros r4–r10 (carga inicial
2,82–8,27; razão relógio/sequência 1,017–1,134) e rodou os testes da implementação (70 aprovados). Carga da máquina:
r4–r10 não são invalidadas nem repetidas, porque o protocolo não fixou limiar, todas as execuções ficaram abaixo de 8,3
com 16 CPUs, sem outro experimento pesado, e parte da carga inicial é residual da execução anterior. A fase 2 não terá
limiar de carga, pois opera só sobre as saídas r1–r10 já produzidas; a reprodutibilidade é controlada por hashes das
entradas, commit, ambiente e testes, mantida a regra de não rodar outro experimento pesado em paralelo. Os três valores
extremos (B máx. t de 00000/Stella, C máx. t de 00000/ORB-SLAM3 e de 1018-13/Stella) ficam só como descrição.

**Liberação da fase 2, em duas etapas:** (1) implementar o orquestrador e o gerador de relatório da fase 2 — já existem
componentes reutilizáveis e testados (`ofd.evaluate`, `describe()`, `indicator_medians()`), mas a integração ponta a
ponta, a geração das tabelas da seção 7 e seus testes específicos precisam ser implementados e revisados antes da
execução; (2) rodar sobre r1–r10 nas 8 combinações, com a execução oficial reportada à parte (seção 8).
