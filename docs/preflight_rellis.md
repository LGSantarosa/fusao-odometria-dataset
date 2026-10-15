# Preflight do GT do RELLIS-3D — 2026-10-14

## Dados examinados
- Exemplo full-stack (`example_merged.bag.zip` → `example_filtered.bag`, 8,9 GB): 60,0 s, início 1581791678 (2020-02-15),
  599 scans `/os1_cloud_node/points` a 10 Hz sem lacunas (> 150 ms: 0), 648 pares `/nerian/{left,right}/image_raw`,
  IMUs `/imu/data` e `/os1_cloud_node/imu`, `/vectornav/*`, odometria de rodas.
- Poses (`Rellis_3D_lidar_poses_20210614.zip`): `Rellis-3D/0000{0..4}/poses.txt`, formato KITTI 3×4 por linha,
  **sem timestamps**; uma linha por scan Ouster da sequência (00000: 2847, 00001: 2318/2319, 00002: 4147, 00003: 2184,
  00004: 2058/2059). `calib.txt` = identidades. README: "file containing the poses of every scan"; correção de poses
  em 06/2021. A origem do `poses.txt` (SLAM vs. INS) não é declarada no README → tratada como `gt_quality: slam`.

## Tentativa de mapeamento amostra → poses
Sem timestamps, o casamento monotônico por tempo (`ofd/matching.py`) não se aplica. Tentou-se localizar os 60 s do
exemplo dentro das sequências por correlação de perfis a 10 Hz (janela deslizante de 599 amostras):

| Sinal | 00000 | 00001 | 00002 | 00003 | 00004 |
|---|---|---|---|---|---|
| velocidade (rodas) — corr / 2º pico | 0,880 / 0,817 | 0,844 / 0,796 | 0,907 / 0,879 | 0,678 / 0,479 | 0,957 / 0,867 |
| guinada (IMU) — corr / 2º pico | 0,337 / 0,255 | 0,321 / 0,299 | 0,588 / 0,361 | 0,359 / 0,328 | 0,597 / 0,480 |

Nenhum pico é único e forte (velocidade quase constante ≈ 0,93 m/s; guinada com correlação ≤ 0,6). **O exemplo não é
mapeável** — provavelmente nem pertence às 5 sequências anotadas.

## Veredito: **B**
- Smoke de 60 s do RELLIS roda **sem métricas de GT** (`gt.tum` vazio → `gt_*` NaN).
- Liberar **somente** a sequência 00000 (full-stack merged, 23 GB). Lá o mapeamento é por ordem: verificar que o nº de
  mensagens `/os1_cloud_node/points` == 2847 (linhas do `poses.txt`) e que não há lacunas > 150 ms; casar a k-ésima
  linha com o k-ésimo scan. Se a contagem divergir → veredito **C** (RELLIS fora da etapa supervisionada).
- `gt_quality: slam` (origem não declarada; possivelmente correlacionada com métodos LiDAR).

## Investigação da associação 00000 — 2026-10-15

**Gatilho.** `python -m ofd.rellis_gt` recusou o 00000: **2849 scans no bag != 2847 linhas no `poses.txt`**. A regra
de parada (veredito C) foi suspensa, não alterada, até haver evidência de uma associação única. `ofd.rellis_gt` não foi
modificado.

**Critérios fixados antes da análise.** Aceitar um mapeamento somente se: (1) rodas, IMU e FAST-LIO apontarem o mesmo
par de scans descartados (±1 scan); (2) a escolha for estável em reamostragem por blocos; (3) houver evidência forte
contra o 2º candidato (preferencialmente ΔBIC > 10); (4) não houver mudança sistemática de fase antes/depois dos
descartes. FAST-LIO só confirma (escolher com ele e avaliar seu RPE com o mesmo mapeamento seria circular).
Qualquer falha → veredito C; `gt_quality` permanece `slam` em qualquer caso.

**Dados.** `20200213_trail_2.bag` (zip `00000_20210224.zip`, 42,5 GB), 284,9 s. Sinais: `/os1_cloud_node/points`
(stamp do header), `/warthog_velocity_controller/odom` (20 Hz, twist), `/imu/data` Microstrain (50 Hz),
`/vectornav/IMU` (96 Hz); FAST-LIO do pipeline sem GT (`data/runs/00000/fastlio`, patch de QoS, 99,89% dos scans).
Código: `tools/rellis_assoc.py`; testes sintéticos `tests/test_rellis_assoc.py`; saída
`data/analysis/rellis_assoc/{signals.npz,result.json,cost_*.npy}`.

**Método.**
- Candidatos: todos os C(2849, 2) = 4.056.976 pares (i < j) de scans não associados; a pose k vai ao k-ésimo scan de
  B \ {i, j}. Custo de cada par em O(1) por somas de prefixo (deslocamento 0 antes de i, 1 entre i e j, 2 depois de j);
  validado contra cálculo direto em 28 pares (inclusive bordas e descartes adjacentes) e por recuperação de descartes
  conhecidos em 11 cenários sintéticos.
- Assinaturas por intervalo de pose (k → k+1) contra o sinal entre os scans associados:
  IMU: vetor de rotação da pose (frame do LiDAR) rotacionado por R_SL (Wahba) vs. ∫ω − bias·Δt;
  rodas: avanço e guinada da pose vs. ∫v e ∫ω_z com escalas ajustadas por mínimos quadrados;
  FAST-LIO: rotação e translação relativas entre os scans associados, por índice de scan (sem relógio).
- Resíduos normalizados por σ robusto (MAD, piso de 5% do maior componente); custo = χ². Como todos os candidatos têm o
  mesmo nº de parâmetros, ΔBIC = Δχ². Conjunto de avaliação fixo: só entram intervalos de pose com dado do sensor sob
  qualquer candidato (as rodas começam 0,25 s após o 1º scan).
- Reamostragem: 200 réplicas por blocos de 100 intervalos. Fase: τ (−150..+150 ms) em janelas de 300 intervalos.

**Resultados.**

QA dos timestamps: 2849 scans, ordem do bag == ordem dos headers, estritamente crescentes, 0 duplicatas, intervalos de
99,28 a 100,93 ms (mediana 99,996 ms), nenhuma lacuna > 150 ms. Os 2 scans a mais não decorrem de defeito temporal.

Movimento (das poses): o robô fica praticamente parado nas poses 0–~95 (0,01–0,07 m/s; ~0,03 °/s) e nas últimas ~40;
início do movimento (v > 0,2 m/s por 10 intervalos) na pose 95.

| Sensor | Melhor par (i, j) | Stamps dos descartes (ns) | Δχ² desl. 2 / 1 / 0 globais | Conjunto ΔBIC < 10 | 2º colocado (excluídos empates) | Reamostragem |
|---|---|---|---|---|---|---|
| Rodas | (115, 116) | 1581624664070994944, …4664171013888 | 4,5 / 5 509,7 / 9 877,4 | i ∈ [0, 116], j ∈ [1, 117] (6 903 pares) | (114, 116), ΔBIC 0,85 | par ±1: 72%; mais frequente (115,116) 135/200 |
| Microstrain | (16, 27) | 1581624654171511808, …4655271053824 | 0,1 / 488 561,6 / 911 577,2 | i ∈ [0, 106], j ∈ [1, 107] (5 778) | (16, 28), ΔBIC 0,01 | par ±1: 11%; (0,1) 56/200 |
| VectorNav | (15, 16) | 1581624654071478016, …4654171511808 | 0,0 / 259 102,6 / 652 475,8 | i ∈ [0, 106], j ∈ [1, 107] (5 778) | (15, 63), ΔBIC 0,004 | par ±1: 8%; (0,1) 57/200 |
| FAST-LIO (confirmação) | (9, 2738) | 1581624653470862848, …4926362868736 | 131 886,7 / 5,1 / 71 649,9 | i ∈ [0, 106], j ∈ [2590, 2848] (27 353) | (9, 2824), ΔBIC 0,46 | par ±1: 3,5%; (67,2738) 64/200 |

(Δχ² desl. k: custo do mapeamento com deslocamento global k — (0,1), (0,N−1), (N−2,N−1) — menos o do melhor par.)

Fase: Microstrain e VectorNav com τ constante ao longo do trecho em movimento (janelas: 0..+12 ms e −18..−6 ms) → sem
mudança de fase durante o movimento. Rodas: τ no limite da grade (+150 ms; +400 ms numa grade de ±400 ms) → latência
grande ou não modelada; as rodas não servem para o alinhamento absoluto.

**Degenerescência deslocamento × latência.** Com τ livre (trecho em movimento, poses 120..M−60), as IMUs não distinguem o
deslocamento global: Microstrain desl. 2/1/0 → τ* = +4/+104/+204 ms, Δχ² = 0/2,3/2,1; VectorNav → τ* = −12/+88/+188 ms,
Δχ² = 0/4,8/6,3. A preferência das IMUs pelo deslocamento 2 depende, portanto, da hipótese de latência ~0 entre os
stamps da IMU e do LiDAR. O FAST-LIO, indexado por scan, não tem essa dependência e prefere o deslocamento 1 (Δχ² de
131 887 contra o deslocamento 2). As duas leituras só se reconciliam se os stamps das IMUs estiverem ~100 ms atrasados
em relação ao stamp da nuvem — hipótese *post hoc*, não testada.

**Avaliação dos critérios.**
1. Mesmo par (±1) entre rodas, IMU e FAST-LIO: **falha** — (115,116), (16,27)/(15,16) e (9,2738); nem o deslocamento no
   trecho em movimento coincide (IMU/rodas: 2; FAST-LIO: 1).
2. Estabilidade em reamostragem: **falha** para o par (8–72%); o par não é identificável dentro dos trechos parados.
3. ΔBIC > 10 contra o 2º candidato: **falha** — margens de 0,004 a 0,85.
4. Fase: sem mudança dentro do movimento nas IMUs; inconclusivo nas rodas e não aplicável ao FAST-LIO.

**Decisão: veredito C mantido.** O RELLIS-3D 00000 fica como dado não rotulado/avaliação exploratória; `ofd.rellis_gt`
continua recusando a sequência. Fica registrado: a associação dentro do movimento é localmente rígida (nenhum
descarte durante o movimento em nenhum sensor), mas o deslocamento global (1 ou 2 scans) não é determinado sem uma
hipótese temporal.

**Riscos de viés.** (a) Protocolo e critérios fixados antes da análise; a métrica de classe "descartes antes do início
do movimento" e o teste de degenerescência foram acrescentados depois de ver os primeiros resultados e são
exploratórios. (b) A versão inicial contava intervalos sem dado como custo zero, o que torna o Δχ² incomparável entre
candidatos; foi corrigida (conjunto de avaliação fixo) antes dos números acima. (c) `gt_quality: slam`: o `poses.txt`
pode vir de um SLAM LiDAR e favorecer o FAST-LIO, mas isso não afeta a associação por índice, só a escala dos resíduos.
(d) A reconciliação por latência de ~100 ms não foi testada e não deve ser usada para aceitar o mapeamento.

**Possível evidência adicional (não executada; exigiria novo protocolo).** Registro direto das nuvens brutas com o
`poses.txt` (consistência geométrica entre scans b+s e b+s+Δ para s ∈ {0, 1, 2}), que não depende de relógio nem de
odometria; e a IMU interna do Ouster (`/os1_cloud_node/imu`), que compartilha o relógio da nuvem.
