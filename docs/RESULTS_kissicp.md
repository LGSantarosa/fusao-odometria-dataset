# Resultados — investigação do KISS-ICP (protocolo `docs/protocol_kissicp.md`)

## Fase 1 — repetibilidade (H4), decidida antes de abrir métricas de erro — 15/10/2026

Código: `14e9830`. Execuções: 3 repetições por condição e sequência (54 + 6 de D4′), 3 em paralelo, em
`data/runs/<seq>/kissicp_<C>_r<k>`; script `data/analysis/kissicp/logs/run_one.sh`, lista de tarefas em
`data/analysis/kissicp/logs/jobs*.txt`, saída da auditoria em `data/analysis/kissicp/h4_repeatability.txt`.
Nenhuma métrica de erro (ATE, RPE, erro por 100 m) foi calculada ou consultada nesta fase.

| Sequência | Condições | Hashes distintos entre as 3 repetições | máx. ΔSE(3) | Decisão |
|---|---|---|---|---|
| 1018-00 | D0, D1, D2, D3, D4, D4′ | 1 em cada condição | ≤ 7,4·10⁻¹⁵ m, 0° | determinístico |
| 1018-13 | D0, D1, D2, D3, D4, D4′ | 1 em cada condição | ≤ 8,2·10⁻¹⁵ m, 0° | determinístico |
| rellis_example | D0, D1, D2, D3 | 1 em cada condição | ≤ 7,3·10⁻¹⁵ m, 0° | determinístico |
| 00000 | D0, D1, D2, D3 | 1 em cada condição | ≤ 4,1·10⁻¹⁴ m, 0° | determinístico |

(ΔSE(3) não nulo com hashes idênticos é arredondamento do cálculo de inv(A)·A.)

**Decisão H4:** o KISS-ICP 1.3.0 é determinístico neste ambiente em todas as condições. Conforme a seção 5, usa-se a
repetição 1 de cada condição, sem intervalos artificiais e sem escalonar para dez execuções. H4 é rejeitada como
explicação do erro.

**Verificações de implementação (sem métricas de erro).**
- As condições produzem trajetórias distintas entre si (hashes diferentes em todas as sequências).
- D0 reproduz bit a bit a saída oficial `data/runs/<seq>/kissicp` nas quatro sequências.

**Diagnóstico t × t_geo (D3, sentido horário) e regra de D4′.**

| Sequência | correlação mediana | \|Δ\| mediano (ms) | scans |
|---|---:|---:|---:|
| 1018-00 | 0,950 | 0,42 | 1466 |
| 1018-13 | 0,950 | 0,43 | 2071 |
| rellis_example | 0,943 | 0,68 | 599 |
| 00000 | 0,960 | 0,64 | 2849 |

A correlação ficou abaixo de 0,99 em todas as sequências, o que aciona a regra pré-registrada: D4′ foi executado no
1018-00 e no 1018-13 (3 repetições, determinístico, trajetória distinta de D4). O |Δ| mediano ficou abaixo de 1 ms.

**Cobertura de D4/D4′:** scans compensados pelo GT / sem GT ao redor (não compensados, contados à parte):
1018-00 1299 / 167; 1018-13 1936 / 135.
