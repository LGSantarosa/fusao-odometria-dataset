# Resultados — modelo de fusão (protocolo `docs/protocol_fusion_model.md`)

## Fase 1 — execução de 19/10/2026 invalidada por defeito de implementação

**Situação: inválida.** As duas dobras rodaram até o fim sem falha, mas a padronização violou a seção 5 do protocolo
(linhas com o método inválido não recebiam 0 em todas as entradas desse método). As seleções desta execução **não
podem ser usadas** na fase 2. O defeito foi corrigido com teste (abaixo); a fase 1 precisa ser repetida após a revisão
da correção e de uma lacuna do protocolo. Nenhuma métrica foi calculada na sequência de teste de nenhuma dobra.

**Execução.** Código `3c34457` (fase 0 aprovada), árvore limpa, uma dobra por vez, nada mais em paralelo.

| Dobra | Treino | Comando | Início → fim | Duração | Memória máx. | Saída |
|---|---|---|---|---:|---:|---|
| A | 1018-00 (1299 linhas com GT) | `python -m ofd.fusion_run phase1 --fold A` | 13:10 → 14:34 | 1 h 24 min | 0,52 GB | código 0 |
| B | 1018-13 (1936 linhas com GT) | `python -m ofd.fusion_run phase1 --fold B` | 14:35 → 16:39 | 2 h 05 min | 0,54 GB | código 0 |

Integridade estrutural (as duas dobras): 595 registros em `cv.csv` (B1–B4: 5 cada; B6: 35; F1 e F2: 270 cada),
subdobras 0–4, sementes 0–2, nenhuma execução falha, nenhuma perda não finita; `selected.json` com a dobra e a
sequência de treino corretas.

Artefatos preservados para auditoria, renomeados para não serem usados por engano (fora do git):

| Arquivo | SHA-256 |
|---|---|
| `data/analysis/fusion/phase1_invalid_3c34457/A/cv.csv` | `bc48ecac8acdb8c91ec27d078d936c6af0c9aa94c32267743407a3c31f3b7bda` |
| `data/analysis/fusion/phase1_invalid_3c34457/A/selected.json` | `039dc5ecebaeda2c647c096f7375ebf19909b94fc6cf9e3951f9ff5ee7fef510` |
| `data/analysis/fusion/phase1_invalid_3c34457/B/cv.csv` | `37be3bfc85811501ba987628df87c9b0c6ac4412b37467a467b2eec52b1789e3` |
| `data/analysis/fusion/phase1_invalid_3c34457/B/selected.json` | `3bae353b488cfd5915ffb54c157d7ff9e0b180f996584558b37be08f7285cba6` |
| `data/analysis/fusion/phase1_invalid_3c34457/logs/phase1_A.log` | `4c721cdd179383df30ec2d86e4c5882f568861f8e4590e57937b5c4afe64b96e` |
| `data/analysis/fusion/phase1_invalid_3c34457/logs/phase1_B.log` | `9e0308d2468c92b824fc78676a92cc4a01a2f562a852466e58791bd40beb73ed` |

**Sintoma.** A perda de validação da configuração escolhida de B6 e F2 ficou na casa dos milhares (A: 2215 e 7437;
B: 6659 e 4789), contra 0,3–1,9 nos baselines e em F1. A perda explode só na subdobra 4 (fim de cada sequência):

| Dobra | Família | Perda por subdobra (0 / 1 / 2 / 3 / 4) |
|---|---|---|
| A | B6 | 0,535 / 0,441 / 0,470 / 0,387 / 11074,9 |
| A | F2 | 0,380 / 0,350 / 0,460 / 0,255 / 37182,7 |
| B | B6 | 0,290 / 0,883 / 0,546 / 0,158 / 33294,8 |
| B | F2 | 0,271 / 0,936 / 0,636 / 0,173 / 23941,2 |

**Causa (defeito de implementação).** No dataset, linhas com o método inválido ainda trazem `dt_ms`, `age_ms` e a
variância móvel com valores antigos (ex.: a idade de uma pose do FAST-LIO depois que ele deixa de estimar). O
`Standardizer` só imputava valores ausentes (NaN), e esses valores entravam padronizados: `fastlio_dt_ms` chegou a 56
857σ (A) e 64 502σ (B) nas linhas inválidas do bloco final; `fastlio_age_ms`, a 19 970σ e 12 002σ. Colunas afetadas
(linhas com GT em que o método é inválido mas a coluna tem valor, 1018-00 / 1018-13): `orbslam3_dt_ms` 321/297,
`orbslam3_age_ms` 322/298, `stella_dt_ms` 321/263, `stella_age_ms` 322/264, `fastlio_dt_ms` 198/119, `fastlio_age_ms`
198/120 e as variâncias móveis dos três métodos (8–10). Os dados sintéticos da fase 0 tinham NaN nessas posições, por
isso os testes não detectaram o problema. Como as entradas de todas as famílias aprendidas passam pela padronização, a
execução inteira fica inválida, não só B6 e F2.

**Correção (com teste).** `Standardizer.transform` passa a atribuir 0 a todas as entradas de um método nas linhas em
que ele é inválido (exceto `valid`), como diz a seção 5. Teste novo:
`tests/test_fusion_data.py::test_invalid_method_rows_are_imputed_even_when_raw_values_exist` (falhou antes da
correção com valores de até 3,7 × 10²⁰). Suíte: 282 testes.

**Lacuna do protocolo (decidida em 20/10/2026: clipe em ±10, emenda na seção 5 e no §14 do protocolo).** Depois da correção, medindo só nos dados de
treino de cada dobra, os maiores valores padronizados nos blocos de validação ficam entre 4σ e 62σ, exceto
`kissicp_dt_ms` na subdobra 4 do 1018-13: 1636σ numa linha válida. A coluna é quase constante no treino (100,9 ms,
σ ≈ 0,0016) e o protocolo só trata desvio exatamente zero. No treino completo, colunas com escala menor que 0,01:
1018-00 — `fastlio_dt_ms` 0,0018, `kissicp_dt_ms` 0,0018, `kissicp_wx` 0,0092 e as variâncias móveis do FAST-LIO
e do KISS-ICP (0,0010 e 0,0006); 1018-13 — as variâncias móveis do FAST-LIO e do KISS-ICP (0,0013 e 0,0007). Sem
uma regra pré-registrada, modelos lineares (B6) e F2 podem extrapolar nessas colunas. Possíveis emendas, a decidir
antes da nova execução: limitar os valores padronizados a ±k; impor uma escala mínima por coluna; ou manter o texto
atual e registrar a limitação.

**Seleções desta execução (inválidas; só para auditoria).** A: Bsel Stella, B6 α = 1000, F1 64 × 2 com decaimento
1e-3 (14 épocas), F2 16 × 2 com 1e-2 (388 épocas). B: Bsel FAST-LIO, B6 α = 100, F1 32 × 1 com 1e-4 (44 épocas),
F2 16 × 2 com 1e-2 (484 épocas).

**Próximo passo:** correção revisada e lacuna resolvida pela emenda de 20/10/2026; falta a nova execução da fase 1
nas duas dobras com o código corrigido e o clipe. A fase 2 continua bloqueada.
