# Resultados externos — abertura única G1 e H1'

**Data:** 04/11/2026. **Predições cegas:** commit
`991aa2a2d6ec85eda5fda9db4db3a0311be67a81`. **Análise derivada:** commit
`0a94f76951726e3d3c09e741ee602153e4d6ddcb`. **Protocolo:**
`docs/amendment_phase4_hypothesis.md`, registrado no commit `2b71407` antes de qualquer processamento externo.

## 1. Resposta principal

**A H1' foi negativa.** A CNN-W congelada não reduziu o RMSE angular em relação à média simples B5/T1 nas oito
sequências externas. A melhora relativa pré-registrada,
`Delta_s = 1 - RMSE_omega(CNN,s) / RMSE_omega(B5,s)`, teve:

- mediana geral de **-3,63%**;
- mediana de **-0,90%** no dia 1005, **-4,69%** no dia 1006 e **-6,68%** no dia 1008;
- somente **1 de 8** sequências favorável à CNN;
- todas as métricas angulares definidas.

A regra exigia mediana estritamente positiva no conjunto e separadamente em cada dia. Nenhuma das quatro condições
foi satisfeita. O sinal negativo significa erro maior da CNN, pois perdas menores são melhores.

Também não houve uma troca favorável escondida nas guardas descritivas. Em relação à B5, a CNN teve, por sequência,
mediana de **1,92% mais RMSE linear** e **14,15% mais RPE translacional de 10 m**. Portanto, a conclusão direta é:

> No teste externo, a CNN não reproduziu o ganho angular observado no desenvolvimento e ainda aumentou, em mediana,
> o erro linear e a deriva translacional de 10 m.

Isso rejeita a alegação confirmatória sobre a CNN selecionada. Não demonstra que toda fusão aprendida seja inviável e
não autoriza escolher outro modelo depois da abertura como nova hipótese confirmatória.

## 2. Integridade da abertura

O job cego começou em 03/11/2026 às 17:09:27-03:00 e terminou suas etapas cegas em 04/11/2026 às 02:49:06-03:00.
Antes da abertura, a auditoria registrou:

- `HEAD` e manifestos no commit `991aa2a`, com árvore Git limpa;
- oito tabelas no schema exclusivamente cego, sem GT, alvos, erros ou métricas;
- tabelas de features e predições alinhadas, e ambos os manifestos verificados por hash;
- exatamente 18 saídas: B5, T1, T2 e cinco sementes de CNN, STEP e MLP-W; nenhuma LSTM;
- os oito GTs com modo `000` e ausência de diretório ou marcador de abertura.

Depois da autorização explícita do autor, o comando já auditado foi executado uma única vez. A abertura começou às
10:12:32-03:00 e terminou às 10:29:16-03:00, sem falha. Foram produzidas 144 linhas de métricas
(18 preditores x 8 sequências), sem métrica primária ausente. Os oito arquivos originais de GT foram novamente
lacrados com modo `000` ao final.

O B5 e o T1 são numericamente idênticos no suporte de GT nas cinco métricas calculadas. O T1 é o comparador oficial da
H1'; o nome B5 é mantido nas tabelas para corresponder à notação da emenda.

## 3. Decisão confirmatória por sequência

O valor da CNN é a média dos RMSEs das cinco sementes, e não a métrica de um ensemble de predições. O desvio padrão
(`DP`) também é entre as cinco métricas de semente e não entra na decisão.

| Sequência | B5/T1 RMSE angular | CNN RMSE angular | DP CNN | Delta | Favorável |
|---|---:|---:|---:|---:|:---:|
| 1005-00 | 0,03521 | 0,03578 | 0,00020 | -1,60% | não |
| 1005-01 | 0,02504 | 0,02400 | 0,00038 | +4,13% | sim |
| 1005-05 | 0,03124 | 0,03130 | 0,00014 | -0,20% | não |
| 1005-07 | 0,04889 | 0,05373 | 0,00127 | -9,90% | não |
| 1006-01 | 0,03960 | 0,04130 | 0,00050 | -4,27% | não |
| 1006-03 | 0,03128 | 0,03288 | 0,00041 | -5,11% | não |
| 1008-01 | 0,03916 | 0,04033 | 0,00031 | -2,99% | não |
| 1008-03 | 0,04741 | 0,05233 | 0,00052 | -10,38% | não |

Unidade do RMSE angular: rad/s. Os valores não arredondados usados na decisão estão em
`h1_prime_by_sequence.csv`.

## 4. Comparações descritivas por sequência

As redes são agregadas pela média da métrica nas cinco sementes. B5 e T2 são determinísticos. Valores menores são
melhores.

### RMSE angular (rad/s)

| Sequência | B5 | CNN | STEP | MLP-W | T2 |
|---|---:|---:|---:|---:|---:|
| 1005-00 | 0,03521 | 0,03578 | 0,03524 | 0,03621 | 0,03239 |
| 1005-01 | 0,02504 | 0,02400 | 0,02362 | 0,02533 | 0,02365 |
| 1005-05 | 0,03124 | 0,03130 | 0,03092 | 0,03175 | 0,02977 |
| 1005-07 | 0,04889 | 0,05373 | 0,05067 | 0,05512 | 0,04471 |
| 1006-01 | 0,03960 | 0,04130 | 0,04071 | 0,04193 | 0,03731 |
| 1006-03 | 0,03128 | 0,03288 | 0,03247 | 0,03386 | 0,02915 |
| 1008-01 | 0,03916 | 0,04033 | 0,04040 | 0,04146 | 0,03644 |
| 1008-03 | 0,04741 | 0,05233 | 0,05032 | 0,05300 | 0,04231 |

### RMSE linear (m/s)

| Sequência | B5 | CNN | STEP | MLP-W | T2 |
|---|---:|---:|---:|---:|---:|
| 1005-00 | 0,1558 | 0,1565 | 0,1546 | 0,1558 | 0,1551 |
| 1005-01 | 0,1292 | 0,1319 | 0,1283 | 0,1365 | 0,1320 |
| 1005-05 | 0,1404 | 0,1347 | 0,1330 | 0,1408 | 0,1472 |
| 1005-07 | 0,1629 | 0,1687 | 0,1667 | 0,1696 | 0,1641 |
| 1006-01 | 0,1592 | 0,1649 | 0,1619 | 0,1657 | 0,1625 |
| 1006-03 | 0,1510 | 0,1536 | 0,1496 | 0,1548 | 0,1567 |
| 1008-01 | 0,1810 | 0,1817 | 0,1805 | 0,1843 | 0,1871 |
| 1008-03 | 0,1676 | 0,1782 | 0,1714 | 0,1760 | 0,1711 |

### RPE translacional de 10 m (m)

| Sequência | B5 | CNN | STEP | MLP-W | T2 |
|---|---:|---:|---:|---:|---:|
| 1005-00 | 0,2837 | 0,3356 | 0,3136 | 0,3461 | 0,3067 |
| 1005-01 | 0,3103 | 0,3639 | 0,3458 | 0,3872 | 0,3356 |
| 1005-05 | 0,2880 | 0,3256 | 0,3207 | 0,3431 | 0,3148 |
| 1005-07 | 0,2703 | 0,3207 | 0,3288 | 0,3463 | 0,2921 |
| 1006-01 | 0,2518 | 0,2807 | 0,2740 | 0,2977 | 0,2703 |
| 1006-03 | 0,2840 | 0,3257 | 0,3155 | 0,3361 | 0,3078 |
| 1008-01 | 0,2725 | 0,3035 | 0,2973 | 0,3134 | 0,2935 |
| 1008-03 | 0,2694 | 0,3061 | 0,2984 | 0,3163 | 0,2904 |

## 5. Agregação por dia

Cada célula é a mediana das sequências do dia depois da agregação das sementes.

### RMSE angular (rad/s)

| Dia | B5 | CNN | STEP | MLP-W | T2 |
|---|---:|---:|---:|---:|---:|
| 1005 | 0,03323 | 0,03354 | 0,03308 | 0,03398 | 0,03108 |
| 1006 | 0,03544 | 0,03709 | 0,03659 | 0,03790 | 0,03323 |
| 1008 | 0,04329 | 0,04633 | 0,04536 | 0,04723 | 0,03937 |

### RMSE linear (m/s)

| Dia | B5 | CNN | STEP | MLP-W | T2 |
|---|---:|---:|---:|---:|---:|
| 1005 | 0,1481 | 0,1456 | 0,1438 | 0,1483 | 0,1511 |
| 1006 | 0,1551 | 0,1593 | 0,1558 | 0,1602 | 0,1596 |
| 1008 | 0,1743 | 0,1799 | 0,1760 | 0,1801 | 0,1791 |

### RPE translacional de 10 m (m)

| Dia | B5 | CNN | STEP | MLP-W | T2 |
|---|---:|---:|---:|---:|---:|
| 1005 | 0,2859 | 0,3306 | 0,3248 | 0,3462 | 0,3108 |
| 1006 | 0,2679 | 0,3032 | 0,2947 | 0,3169 | 0,2890 |
| 1008 | 0,2709 | 0,3048 | 0,2979 | 0,3148 | 0,2919 |

## 6. Agregação geral e leitura descritiva

A coluna de valor é a mediana das oito métricas por sequência. Cada `Delta` é calculado por sequência contra a B5 e
depois resumido pela mediana; por isso ele não precisa coincidir com a razão entre os dois valores agregados.

| Modelo | RMSE angular | Delta angular | Favoráveis | RMSE linear | Delta linear | RPE 10 m | Delta RPE |
|---|---:|---:|---:|---:|---:|---:|---:|
| B5 | 0,03719 | — | — | 0,1575 | — | 0,2781 | — |
| CNN | 0,03805 | -3,63% | 1/8 | 0,1607 | -1,92% | 0,3231 | -14,15% |
| STEP | 0,03782 | -2,97% | 2/8 | 0,1583 | +0,45% | 0,3145 | -10,93% |
| MLP-W | 0,03883 | -5,87% | 0/8 | 0,1607 | -3,29% | 0,3396 | -18,73% |
| T2 | 0,03441 | +6,88% | 8/8 | 0,1596 | -2,15% | 0,3001 | -8,08% |

Descritivamente, o T2 apresentou RMSE angular menor que a B5 nas oito sequências, com melhora relativa mediana de
6,88%. Esse contraste não era a H1' e não deve ser promovido a confirmação posterior à abertura. STEP teve RMSE linear
ligeiramente menor em mediana (+0,45% no `Delta`), mas aumentou o RPE translacional de 10 m em todas as sequências.
MLP-W não teve sequência favorável contra B5 em nenhuma das três métricas da tabela.

Como informação suplementar, a CNN aumentou em mediana o RPE rotacional de 10 m em 17,97% e o ATE em 44,37% contra
B5. As tabelas completas também preservam `rpe_r_10m` e `ate_rmse`; essas métricas não entram na decisão da H1'.

## 7. Desenvolvimento versus teste externo

No gate de desenvolvimento, a CNN havia reduzido o RMSE angular contra B5/T1 em 20,0% e 11,3% nas duas dobras, mas
aumentado o RMSE linear. Nas oito sequências externas, o ganho angular não se repetiu: o `Delta` mediano mudou para
-3,63%, e só uma sequência foi favorável.

Esse contraste é o resultado científico central: uma vantagem angular forte nas duas sequências de desenvolvimento
não se generalizou para dias externos, apesar do congelamento dos modelos, cinco sementes, processamento cego e regra
de decisão definida antes da abertura. A separação desenvolvimento/teste impediu que o padrão inicial fosse
apresentado como evidência geral.

## 8. Análise reprodutível e artefatos

`ofd.mc_external` foi acrescentado depois da abertura exclusivamente para automatizar as regras já congeladas na
emenda, recalcular as métricas primárias e produzir as guardas secundárias. O código não escolhe modelos, métricas ou
limiares e consome somente os artefatos imutáveis da abertura; ele não lê os bags lacrados. Antes da execução, seus
testes e os testes relacionados a avaliação e abertura passaram (32/32). A análise recusou árvore Git suja e foi
executada no commit `0a94f76`. Depois da geração do relatório, a suíte completa passou (370 testes; uma advertência de
depreciação do Python, sem falha).

| Artefato | SHA-256 |
|---|---|
| Auditoria pré-abertura | `59150634fe0fe4193cacdd3baa5b9fbfcb5ff2e298faf6e0f0724b403ecf7073` |
| Marcador `UNLOCK_STARTED` | `0442f0d5e99f705d6a97138bb72dc01b53ea1a27ad60c3e257b6bed170c2d5b2` |
| Manifesto da abertura | `db4ad6e127ec653893a08577df6f3afa668ecdc6784b1ea57725b8adb1f90328` |
| `prediction_metrics.csv` da abertura | `4607c9f0512c1096afa7939d68cedb54f5d045bc32dc96b78e4d8262383c1150` |
| `source_metrics.csv` da abertura | `8d0672a9890c28ea5944d8d1cfc220031e6409c0b5260f8a95189f516ead0041` |
| `per_seed_metrics.csv` | `2f2a407f7195e36629608a3010ce1d05ef2c32b3588a887ca939c05b7bf369e5` |
| `per_sequence_metrics.csv` | `8f9090ad2d3edf863e75bf5d8eee8510b57851de0d54927993faf82973e815d2` |
| `h1_prime_by_sequence.csv` | `764f1f8c6042a53beeea054fd252b23977c0af86e7182f5b39cc98f1b6b1f62e` |
| `h1_prime_decision.json` | `763001a7966c2bf9415718b1496b9fcf7b07ea0b75fb88dcb498159f831cb79c` |
| `descriptive_by_day.csv` | `8148f2a30ec9f676ec61912e06d458e83618568f9bdbb13f4c319e0fc7cb6163` |
| `descriptive_overall.csv` | `caad45e6d921177f4d6f2cdeb4deb8ca4a48b16392bbc318b4aa5ebbe6780270` |

Os dados completos ficam em `data/blind_g1/unlock/` e `data/blind_g1/external_results/`, ambos ignorados pelo Git. O
manifesto `result_manifest.json` liga as tabelas ao manifesto de abertura, à emenda e ao commit do analisador.

## 9. Alcance da conclusão

O estudo comparou todos os modelos congelados nas mesmas oito corridas externas, com as mesmas entradas e o mesmo GT.
O resultado permite afirmar que **a CNN escolhida não superou a média simples no RMSE angular externo sob a regra
pré-registrada**. As comparações com STEP, MLP-W e T2 são descritivas; H2 e H3 continuam sem teste confirmatório, e não
se usa “melhor modelo”, “superioridade geral” ou “sem degradação”.
