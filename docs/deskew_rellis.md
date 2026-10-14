# KISS-ICP + deskew no RELLIS-3D — evidência para desligar (2026-10-14, rev. 2)

Exemplo de 60 s (`example_filtered.bag`), Ouster OS1-64, campo `t` (uint32 ns, relativo ao início do scan).
A extração valida 100% dos scans (span ≈ 100 ms, tempo monotônico por ring, uma virada por ring;
azimute × t com correlação −1 no ring 0, coerente com a rotação do OS1; direção 0 → 1 como o KISS-ICP espera).

**Referência temporal do deskew do KISS-ICP 1.3.0 (verificado numericamente):** os pontos são compensados para o
**fim do scan** (t = 1 inalterado; t = 0 recebe o deslocamento inteiro do intervalo). Coerente com a pose do
KISS-ICP ser carimbada em `end_ns` no dataset.

| KISS-ICP | percurso 60 s | std do passo | vs. FAST-LIO (1 execução estável): \|Δt\| med / p90 | corr vx | corr wz |
|---|---|---|---|---|---|
| deskew = True (t) | 66,9 m | 6,8 cm | 5,1 / 14,1 cm | 0,674 | 0,751 |
| deskew com 1 − t | 59,7 m | 5,6 cm | — | — | — |
| deskew = False | 57,7 m | 5,3 cm | 2,8 / 5,9 cm | 0,871 | 0,902 |

**Evidência independente principal: odometria das rodas** — 0,93 m/s × 60 s ≈ 56 m. Sem deskew o KISS-ICP fica
próximo dela; com deskew diverge (+16%). A comparação com o FAST-LIO usa **uma** execução estável dele (95,5% dos
scans casados) e é secundária: o FAST-LIO no RELLIS ainda não está validado (não determinístico; ver ledger).

Causa raiz do pior desempenho com deskew: **desconhecida**.
Decisão: `kissicp_deskew: false` no RELLIS (config), registrado em `run.json`. No BotanicGarden a escolha será
feita com GT (RPE com e sem deskew).

## BotanicGarden 1018-00 (VLP16, COM GT) — confirmação

| KISS-ICP | ATE | RPE/frame (t / r) | RPE 10 m (t / r) |
|---|---|---|---|
| deskew = True | 0,132 m | 4,09 cm / 0,302° | 0,215 m / 1,77° |
| deskew = False | 0,132 m | 2,45 cm / 0,219° | 0,195 m / 1,73° |

O deskew piora o RPE em dois datasets com LiDARs diferentes (Ouster OS1-64 e Velodyne VLP16). Hipótese **não
verificada**: as nuvens publicadas pelos drivers já estariam compensadas de movimento, e recompensar degrada.
Decisão: `kissicp_deskew: false` também no BotanicGarden.
