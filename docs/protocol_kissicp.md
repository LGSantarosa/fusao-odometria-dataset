# Protocolo — erro do KISS-ICP no BotanicGarden 1018-13 e efeito da compensação temporal (*deskew*)

**Registrado em:** 15/10/2026, antes de qualquer execução nova do KISS-ICP. Até o commit deste documento, nenhum
resultado novo do KISS-ICP foi consultado (bloqueio voluntário). Alterações posteriores a este protocolo devem ser
registradas como emendas datadas, com justificativa, sem reescrever o texto original.

## 1. Contexto e caráter de cada evidência

Configuração atual: KISS-ICP 1.3.0, `deskew = False` nos dois datasets, `max_range = 100 m`, demais parâmetros no padrão
da biblioteca (voxel = `max_range / 100` = 1,0 m).

| Evidência | Situação | Caráter neste protocolo |
|---|---|---|
| 1018-00, D0 e D1 | já conhecida: ATE 0,132 m nas duas; RPE/quadro 2,45 cm (D0) e 4,09 cm (D1) | anterior / replicação |
| RELLIS (trecho de 60 s), D0 e D1 | já conhecida: com D1 o percurso diverge das rodas (+16%) | exploratória |
| 1018-13, D0 | já conhecida: ATE 1,83 m em 201 m; RPE a 10 m 0,250 m / 3,06° | motivação de Q1 |
| 1018-13, D1–D4 | **desconhecida** | **componente prospectivo principal** |
| RELLIS 00000 | sem GT (veredito C) | exploratória; nunca decide configuração |

## 2. Perguntas

- **Q1.** Que regime de movimento ou região explica o erro do KISS-ICP no 1018-13? Como 201 m e 115 m não são
  comparáveis por uma razão de ATE, Q1 é respondida por métricas normalizadas e localizadas (seção 6), separando
  "trajetória mais longa" de "região ou regime de movimento mais difícil".
- **Q2.** Por que habilitar o *deskew* piorou o KISS-ICP no 1018-00 e no RELLIS?

## 3. Hipóteses e previsões

| Hipótese | Enunciado | Previsão que a distingue |
|---|---|---|
| H1 — distorção não compensada | Com D0, a distorção intra-varredura degrada o registro, sobretudo em rotação | D4 melhora em relação a D0, e a melhora concentra-se nos scans com maior ωΔt |
| H2 — tempo por ponto incorreto | O campo `t` não representa a ordem física de aquisição (ordem, origem ou sentido) | D3 melhora em relação a D1; se D2 melhora em relação a D1, o sentido está invertido |
| H3 — degenerescência geométrica | Parte do 1018-13 tem pouca estrutura para o registro ponto-a-ponto | os trechos de maior erro coincidem com as medidas de H3 (seção 7), independentemente de ωΔt; sem manipulação da geometria, só se pode concluir "compatível com degenerescência" |
| H4 — não determinismo | Variação entre execuções explica parte do erro | testada pela regra da seção 5, antes de qualquer agregação |
| H5 — modelo de movimento | O tempo está correto, mas a compensação interna usa `last_delta` (movimento do scan anterior; `kiss_icp.py:43`) e falha sob aceleração angular ou mudança brusca de movimento | D1 e D3 pioram nos mesmos trechos (maior Δω entre scans), enquanto D4 melhora |
| H6 — nuvens já compensadas | As nuvens foram compensadas antes da extração; uma segunda compensação gera sobrecompensação | D0 permanece melhor, e D1, D3 e D4 pioram proporcionalmente ao movimento; afirmar H6 exige também evidência do publicador ou da configuração do sensor |

A normalização atual (`ofd/pointtime.py:29`) preserva o sentido temporal, mas leva cada scan para [0, 1] pelo mínimo e
máximo do campo. Por isso, D2 testa a inversão do sentido, e D3 testa se o campo representa a ordem física de aquisição.

## 4. Condições (ablação controlada da compensação temporal)

| Condição | Tempo por ponto | Compensação | Papel |
|---|---|---|---|
| D0 | — | nenhuma (`deskew = False`) | referência (configuração atual) |
| D1 | campo original `t`, normalizado para [0, 1] | interna do KISS-ICP (`last_delta`) | candidata |
| D2 | 1 − t | interna do KISS-ICP | candidata (teste de inversão) |
| D3 | reconstruído pela geometria e ordem de disparo, sem usar `t` | interna do KISS-ICP | candidata (teste de H2) |
| D4 | campo original `t` | **externa**: cada ponto levado ao fim do scan com a pose do GT interpolada; *deskew* interno desligado | **apenas controle diagnóstico positivo** |

**D3 — reconstrução geométrica.** Para cada ponto, azimute θ = atan2(y, x) no frame do sensor; tempo
t_geo = (s · (θ_início − θ)) mod 2π / 2π, onde s é o sentido de rotação e θ_início é o azimute do primeiro ponto na
ordem de armazenamento da mensagem. O sentido de rotação de cada sensor (VLP-16, OS1-64) é tomado da documentação do
fabricante e registrado antes da execução; se a documentação não for conclusiva, D3 não é executado para aquele sensor
e isso é reportado. Antes da execução de D3, mede-se a concordância entre t_geo e t (correlação e |Δ| mediano por
scan), como diagnóstico do campo; essa medida não altera as condições.

**D4 — compensação assistida por GT.** O GT do BotanicGarden tem ~10 Hz (intervalo mediano de 100,86 ms). A pose em
cada instante de ponto é obtida por interpolação em SE(3) entre poses de GT consecutivas (hipótese de movimento
uniforme entre elas), e o ponto é levado ao frame do fim do scan. Scans sem poses de GT ao redor ficam sem compensação
e são contados. Limitações: (i) não é uma trajetória contínua perfeita, só uma compensação sob interpolação;
(ii) usa o mesmo GT da avaliação, o que favorece a condição; (iii) herda o campo `t`. Por isso, D4 **nunca** é candidata
ao pipeline nem estimativa imparcial de desempenho: serve só como controle positivo, para saber se compensar com
movimento conhecido melhora o registro. Regra adicional fixada agora: se o diagnóstico de D3 indicar discordância
material entre t_geo e t (correlação < 0,99 ou |Δ| mediano > 1 ms do período), executa-se também D4′, igual a D4 com
t_geo.

Sequências: D0–D4 no 1018-13 e no 1018-00 (GT); D0–D3 no RELLIS (trecho de 60 s e 00000), sem D4 por falta de GT.

## 5. Repetibilidade (H4) antes de qualquer agregação

1. Executar três vezes cada condição em cada sequência.
2. Comparar o hash SHA-256 das trajetórias (`poses_causal.tum`) e o máximo ΔSE(3) entre repetições (translação em m,
   rotação em graus), pose a pose.
3. Hashes idênticos → método determinístico neste ambiente; usar uma execução e **não** produzir intervalos
   artificiais.
4. Hashes diferentes, mas ΔSE(3) máximo < 1 mm e < 0,01° → numericamente equivalente; usar a primeira execução e
   reportar o ΔSE(3).
5. Variação acima disso → interromper a análise e, antes de ver qualquer métrica de erro, passar a dez execuções por
   condição; as métricas passam a ser reportadas como média e desvio-padrão, e os critérios da seção 8 aplicam-se às
   médias.

## 6. Métricas (Q1 e comparação entre condições)

Todas as condições são avaliadas exatamente nos mesmos pares de GT: a interseção dos pares válidos em todas as
condições da sequência.

- RPE translacional e rotacional por quadro e em janelas de 10 m (inclusive a série ao longo da trajetória).
- ATE (métrica secundária).
- Erro acumulado por 100 m: erro translacional relativo (%) e rotacional (°/100 m) sobre todas as subsequências de
  100 m.
- Primeiros 100 m de cada sequência (1018-00 e 1018-13): ATE e erro por 100 m, comparáveis entre sequências.
- Erro rotacional acumulado ao longo da trajetória (ângulo de rotação entre a estimativa e o GT após o alinhamento).
- Regime de movimento por scan, a partir do GT: vΔt, ωΔt e |Δω| entre scans consecutivos; o RPE por quadro é
  estratificado por quantis desses regressores.

## 7. Medidas de estrutura para H3 (definidas antes dos resultados)

Por scan, na condição D0:
- número de pontos e número de voxels ocupados (voxel de 1,0 m, o mesmo do KISS-ICP);
- `fitness`, `inlier_rmse` e `unmatched_ratio` (já calculados por `ofd.lidar_indicators`);
- menor autovalor e número de condição da matriz de informação 6×6 do registro ponto-a-ponto (JᵀJ, com
  J = [I, −[p]×] nas correspondências entre o scan registrado e o mapa local até 3σ), quando for possível obtê-las
  pela API do KISS-ICP;
- caso contrário: razões de linearidade, planaridade e espalhamento (autovalores da PCA) da nuvem subamostrada.

Sem manipulação da geometria, H3 só pode ser descrita como "compatível com degenerescência", nunca como causa
demonstrada.

## 8. Critérios de decisão

**Promoção ao pipeline** (só D1, D2 ou D3; nunca D4). A condição deve, em relação a D0, **separadamente no 1018-00 e no
1018-13**:
- reduzir em pelo menos 5% o RPE translacional **e** o rotacional em janelas de 10 m;
- não piorar o ATE em mais de 5%;
- não reduzir a cobertura nem aumentar as falhas.

O RELLIS permanece exploratório e não decide a configuração. Se nenhuma condição atender a todos os itens, D0 é mantida.

**Atribuição de causa** (só por intervenção, nunca só por correlação):
- H1: D4 melhor que D0, com a melhora concentrada no quantil superior de ωΔt.
- H2: D3 melhor que D1 (com D2 melhor que D1, o sentido está invertido).
- H5: D4 melhor que D0, enquanto D1 e D3 pioram nos mesmos trechos, associados aos maiores |Δω|.
- H6: D0 melhor que D1, D3 e D4, com piora crescente com o movimento; só se afirma H6 se houver também evidência do
  publicador ou da configuração do sensor de que as nuvens foram compensadas. Sem isso, "compatível com H6".
- H3: apenas "compatível com degenerescência" (seção 7).
- H4: pela regra da seção 5.

Resultados que não se encaixem em nenhum padrão são reportados como tais, e a causa permanece em aberto.

## 9. Implementação e validação antes da execução

As condições D1–D4 e as métricas das seções 6 e 7 serão implementadas como opções do executor do KISS-ICP e de um
script de análise, validadas em dados sintéticos com distorção e tempos conhecidos antes de qualquer execução sobre os
dados reais. Os resultados entram em `docs/RESULTS_kissicp.md` (registro operacional) e no relato acadêmico, com a
distinção entre evidência anterior, componente prospectivo e análise exploratória.

## 10. Registro de implementação — 15/10/2026 (após o registro, antes das execuções reais)

Esta seção registra decisões previstas pela seção 9; não altera hipóteses, métricas ou critérios. A implementação foi
iniciada sem executar D1–D4 sobre as sequências reais e sem consultar novos resultados do KISS-ICP.

**Sentido de rotação usado por D3.** Ambos os sensores giram no sentido horário quando vistos de cima:

- VLP-16: o manual do fabricante, revisão F, Figura 9-1, define o azimute crescente no sentido horário; a seção 9.3.5
  confirma que os azimutes crescem com a ordem temporal dos disparos. Fonte:
  <https://data.ouster.io/downloads/velodyne/user-manual/vlp-16-user-manual-revf.pdf>.
- OS1-64: a documentação oficial declara explicitamente rotação horária vista de cima, equivalente a velocidade
  angular negativa sobre Z. Fonte:
  <https://static.ouster.dev/sensor-docs/image_route1/image_route3/sensor_data/sensor-data.html>.

O valor `clockwise` fica versionado em `configs/{botanic,rellis}/dataset.yaml` e é gerado por
`tools/make_configs.py`; D3/D4′ recusam execução sem um sentido válido.

**Semântica temporal de D4.** O instante de cada ponto é reconstruído como
`header + t_min + t_norm × span`, usando `scans.csv`. Isso preserva o caso do VLP-16, em que o header está próximo do
fim do scan e os tempos relativos são predominantemente negativos. A transformação aplicada é
`p_L(fim) = inv(T_W_L(fim)) T_W_L(t) p_L(t)`. Se o GT não envolver o scan inteiro, o scan fica sem compensação e é
contado separadamente, conforme o protocolo.

**Arquivos e validação sintética.** As condições puras estão em `ofd/kissicp_conditions.py`; o runner registra condição,
tipo de compensação, sentido de rotação, diagnóstico `t` × `t_geo` e scans externos compensados/não compensados. As
métricas pareadas, repetibilidade, regimes de movimento e fallback de estrutura por PCA estão em
`ofd/kissicp_analysis.py`. Os testes sintéticos cobrem sentido temporal, tempos negativos relativos ao header,
distorção SE(3) conhecida, D0–D4′, pares comuns de GT, promoção e medidas de estrutura.

O executor recebe `--condition D0|D1|D2|D3|D4|D4prime`; o sentido de rotação vem do `dataset.yaml`, podendo ser
sobrescrito explicitamente por `--rotation-direction`. Depois que as repetições forem liberadas pelo protocolo, a
análise é executada sem chamar o estimador, por exemplo:

```bash
python -m ofd.kissicp_analysis --seq-dir data/extracted/<seq> \
  --run D0=data/runs/<seq>/kissicp_D0 --run D1=data/runs/<seq>/kissicp_D1 \
  --repetitions D0=<rep1>,<rep2>,<rep3> --out data/analysis/kissicp/<seq>
```
