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
