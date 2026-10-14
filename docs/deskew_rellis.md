# KISS-ICP + deskew no RELLIS-3D — evidência para desligar (2026-10-14)

Exemplo de 60 s (`example_filtered.bag`), Ouster OS1-64, campo `t` (uint32 ns, relativo ao início do scan).
A extração valida 100% dos scans (span ≈ 100 ms, tempo monotônico por ring, uma virada por ring;
azimute × t com correlação −1 no ring 0, coerente com a rotação do OS1). Mesmo assim:

| KISS-ICP | percurso 60 s | std do passo | vs FAST-LIO: \|Δt\| mediana / p90 | corr vx | corr wz |
|---|---|---|---|---|---|
| deskew = True (t) | 66,9 m | 6,8 cm | 5,1 / 14,1 cm | 0,674 | 0,751 |
| deskew com 1 − t | 59,7 m | 5,6 cm | — | — | — |
| deskew = False | 57,7 m | 5,3 cm | 2,8 / 5,9 cm | 0,871 | 0,902 |

Referências independentes: FAST-LIO ≈ 51,2 m em 95% dos passos (≈ 56 m extrapolado); odometria de rodas
0,93 m/s × 60 s ≈ 56 m. Sem deskew o KISS-ICP concorda com ambas; com deskew diverge.

Causa raiz **não identificada** (suspeita: semântica do `t` do driver Ouster antigo usado no RELLIS vs.
convenção do deskew do KISS-ICP, que normaliza os tempos internamente e usa o meio do scan como referência).
Decisão: `kissicp_deskew: false` no RELLIS (config), registrado em `run.json`. No BotanicGarden a escolha
será feita com GT (RPE com e sem deskew).
