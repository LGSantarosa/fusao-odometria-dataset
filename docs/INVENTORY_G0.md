# Inventário G0 — sequências externas do BotanicGarden

**Data do inventário:** 29/10/2026

**Fonte consultada:** catálogo oficial do BotanicGarden no commit
[`84c4806`](https://github.com/robot-pesg/BotanicGarden/tree/84c4806428ca16c154238e263a7f8bf828bf58e1)

**Estado:** inventário catalográfico concluído; 8/8 candidatas triadas e aprovadas (seções 10 e 11); `k = 8`.

> **Emenda pré-triagem — 29/10/2026.** Antes de baixar ou inspecionar qualquer bag, foram acrescentados: agrupamento
> por dia, limite da alegação a novas sequências, permanência de toda sequência aprovada independentemente do
> desempenho posterior das odometrias e equivalência obrigatória de proveniência/formato do GT. Nenhum dado externo
> foi aberto para produzir esta emenda.

> **Emenda de custódia — 29/10/2026.** No PC que guarda os dados do desenvolvimento, verificou-se que o
> `GT_pose_qnew.zip` baixado para `1018-00`/`1018-13` também contém o GT de cinco candidatas. Os arquivos foram
> isolados sem abertura do conteúdo; evidência e procedimento estão na seção 8. A seção 4 passa a distinguir bag e GT
> locais.

## 1. Resultado executivo

O catálogo oficial contém 33 sequências. Dez delas possuem links públicos tanto para o `VLIO-rosbag` quanto para o
GT. Duas, `1018-00` e `1018-13`, já foram abertas e usadas no desenvolvimento. Restam, portanto, **oito candidatas
públicas novas**:

- `1005-00`, `1005-01`, `1005-05` e `1005-07`;
- `1006-01` e `1006-03`;
- `1008-01` e `1008-03`.

Esse número torna possível planejar um teste externo com `k >= 5`, mas **não fecha G0**. Nenhum dos oito bags está
presente localmente e a compatibilidade real de tópicos, tipos, timestamps e cobertura ainda não foi verificada. O
valor de `k` será o número de candidatas que passarem pela triagem estrutural cega definida na seção 3; não será
escolhido por erro de odometria, aparência da trajetória ou conveniência posterior.

Como todas as candidatas pertencem ao BotanicGarden e usam a mesma plataforma e conjunto de sensores, a alegação
máxima sustentada por esse teste será **generalização para novas sequências, de outras datas, no mesmo local e na
mesma plataforma**. Não foi verificado se as rotas repetem trechos de `1018-00` ou `1018-13`, pois isso exigiria abrir
as poses ou imagens de trajetória bloqueadas. Portanto, o estudo não usará a expressão “percursos não vistos” nem
alegará generalização para outro local, outro robô ou outro conjunto de sensores.

### 1.1 Agrupamento por dia

As oito candidatas não representam oito condições de coleta claramente independentes:

| Dia | Sequências candidatas | Quantidade |
|---|---|---:|
| `1005` | `1005-00`, `1005-01`, `1005-05`, `1005-07` | 4 |
| `1006` | `1006-01`, `1006-03` | 2 |
| `1008` | `1008-01`, `1008-03` | 2 |

Sequências do mesmo dia podem compartilhar iluminação, estado do jardim e trechos de rota. A sequência continuará
sendo a unidade da regra principal, mas o protocolo também exigirá, para cada contraste e métrica primária, efeito
favorável na mediana das sequências de **cada um dos três dias**. A pretensão confirmatória exige ao menos uma
sequência elegível em `1005`, `1006` e `1008`; se um dia inteiro não passar pela triagem, o estudo será exploratório ou
o protocolo será revisto antes de qualquer abertura.

Essa condição por dia é uma verificação de robustez, não um novo teste com poder adequado: há somente três grupos e a
dependência residual dentro deles permanece como limitação. Para referência, se as oito sequências forem elegíveis, o
teste de sinais unilateral sob a hipótese nula produz `p = 0,00390625` para 8/8 favoráveis, `p = 0,03515625` para pelo
menos 7/8 e `p = 0,14453125` para pelo menos 6/8. Esses valores não corrigem a dependência intradia.

## 2. Barreira cega aplicada neste inventário

Foram consultados somente:

- nomes das sequências e disponibilidade de links no catálogo oficial;
- especificações nominais dos sensores, nomes e tipos esperados dos tópicos;
- nomes das calibrações publicadas e chaves de extrínsecas por sequência;
- presença local de arquivos candidatos e espaço disponível em disco.

Não foram baixados ou abertos bags externos ou arquivos de GT. Não foram vistas imagens de trajetórias, poses, valores
de movimento, features, saídas de odometria, ATE, RPE ou qualquer outra métrica de erro. Nenhuma odometria ou modelo de
fusão foi executado. O inventário não altera o conjunto de desenvolvimento.

## 3. Critérios estruturais congelados antes da inspeção dos bags

Uma candidata pública será elegível somente se satisfizer **todos** os itens abaixo. A triagem poderá ler nomes, tipos,
contagens e timestamps, mas descartará os payloads de GT e não produzirá estatísticas de movimento.

1. A sequência não é `1018-00` nem `1018-13` e nunca foi usada para escolha de modelo ou hipótese.
2. O `VLIO-rosbag` e o GT oficial estão acessíveis, têm hash registrado e pertencem à mesma sequência. A proveniência
   nominal do GT deve ser o mesmo processo do desenvolvimento — localização no mapa de levantamento do BotanicGarden
   produzido com o scanner Leica —, no frame do VLP-16 e no mesmo esquema canônico de timestamp, posição e quaternion.
   Recipientes TUM e `PoseStamped` só serão equivalentes se a conversão for estrutural e sem transformação estimada a
   partir da trajetória. Proveniência ou esquema incompatível reprova a sequência para o teste confirmatório.
3. O bag contém mensagens não vazias e com os tipos esperados em
   `/dalsa_gray/left/image_raw`, `/dalsa_gray/right/image_raw`, `/velodyne_points` e `/imu/data`.
4. Os timestamps de cada tópico são finitos e monotônicos. Câmeras estéreo, LiDAR, IMU e GT possuem pelo menos 30 s de
   interseção temporal; o limiar de 30 s reutiliza o mínimo de segmento já fixado no pipeline, em vez de ser escolhido
   depois de conhecer as candidatas.
5. Resolução/codificação das imagens, campos estruturais da nuvem e esquema da IMU são aceitos pelos quatro pipelines
   congelados. A calibração necessária está disponível e sua associação à sequência é inequívoca.
6. A triagem emite somente `aprovada` ou um código estrutural de reprovação previamente enumerado. Não expõe poses de
   GT, distribuições de features, trajetória, erro ou resultado de método.
7. Todas as sequências aprovadas entram no teste. Não haverá seleção por duração acima do mínimo, tipo de movimento,
   iluminação, forma da rota ou desempenho preliminar.
8. Depois da aprovação estrutural, a sequência permanece no teste mesmo que ORB-SLAM3 ou Stella não inicialize, um
   método encerre com falha própria ou qualquer fonte tenha cobertura baixa ou nula. Validade e cobertura passam a ser
   resultados reportados; nunca são critérios para remover a sequência ou trocar a realização oficial.

Falha de download ou link indisponível será registrada como `indisponível`, separada de reprovação estrutural. Uma
sequência indisponível não poderá ser substituída depois de observar qualquer resultado externo; a regra de reposição,
se necessária, deverá ser fixada no protocolo antes da abertura.

Os códigos de decisão ficam congelados antes da implementação de G1:

| Código | Classe | Significado |
|---|---|---|
| `APPROVED` | aprovação | todos os contratos estruturais foram satisfeitos |
| `DATA_UNAVAILABLE` | disponibilidade | bag ou GT oficial inacessível; não é reprovação estrutural |
| `IDENTITY_MISMATCH` | reprovação | bag, GT ou manifesto não pertence à sequência declarada |
| `HASH_MISMATCH` | reprovação | hash difere do manifesto de aquisição |
| `REQUIRED_TOPIC_MISSING` | reprovação | falta câmera esquerda/direita, LiDAR ou IMU |
| `TOPIC_TYPE_MISMATCH` | reprovação | tipo ROS incompatível com o contrato |
| `EMPTY_TOPIC` | reprovação | tópico obrigatório sem mensagens |
| `TIMESTAMP_INVALID` | reprovação | timestamp não finito ou não monotônico |
| `COMMON_OVERLAP_LT_30S` | reprovação | interseção temporal de sensores e GT menor que 30 s |
| `PAYLOAD_SCHEMA_INCOMPATIBLE` | reprovação | resolução, codificação ou campos estruturais incompatíveis |
| `CALIBRATION_MISSING` | reprovação | calibração necessária ausente ou ambígua |
| `GT_PROVENANCE_MISMATCH` | reprovação | origem nominal do GT difere do processo Leica usado no desenvolvimento |
| `GT_FORMAT_MISMATCH` | reprovação | frame ou esquema canônico de pose/timestamp incompatível |

G1 poderá emitir vários códigos estruturais para a mesma sequência, mas não valores que revelem trajetória,
distribuições ou desempenho.

## 4. Candidatas públicas ainda não usadas

| Sequência | Grupo no catálogo oficial | VLIO público | GT público | Bag local | GT local | Decisão estrutural |
|---|---|---:|---:|---:|---:|---|
| `1005-00` | sete amostras principais | sim | sim | sim | lacrado | `APPROVED` |
| `1005-01` | sete amostras principais | sim | sim | sim | lacrado | `APPROVED` |
| `1005-05` | tabela pública adicional | sim | sim | sim | lacrado | `APPROVED` |
| `1005-07` | sete amostras principais | sim | sim | sim | lacrado | `APPROVED` |
| `1006-01` | sete amostras principais | sim | sim | sim | lacrado | `APPROVED` |
| `1006-03` | tabela pública adicional | sim | sim | sim | lacrado | `APPROVED` |
| `1008-01` | tabela pública adicional | sim | sim | sim | lacrado | `APPROVED` |
| `1008-03` | sete amostras principais | sim | sim | sim | lacrado | `APPROVED` |

“Lacrado” significa presente em `data/sealed/botanic_gt/`, sem permissão de leitura e não aberto (seção 8).

O README oficial lista os mesmos tópicos usados por `configs/botanic/dataset.yaml`: estéreo cinza, VLP-16, Xsens e
GT. Ele também publica intrínsecas e extrínsecas e possui chaves de alinhamento para as sequências públicas; isso
estabelece compatibilidade **nominal**, não substitui a inspeção dos bags.

## 5. Sequências fora do teste externo atual

### Já abertas — somente desenvolvimento

- `1018-00`;
- `1018-13`.

### Catalogadas, mas sem download público confirmado

O catálogo de trajetórias também nomeia 23 sequências cujos dados devem ser solicitados aos autores:

- `1005-02`, `1005-03`, `1005-04`, `1005-06`;
- `1006-00`, `1006-02`, `1006-04`, `1006-05`, `1006-06`;
- `1008-00`, `1008-02`;
- `1018-01` a `1018-12`.

Elas não integram o `k` planejado. Poderão ser consideradas apenas em uma emenda anterior ao pré-registro, após
confirmação de acesso ao bag e ao GT e sob os mesmos critérios cegos. As figuras de trajetória do catálogo não serão
usadas para escolher quais solicitar.

## 6. Compatibilidade nominal e limitação operacional

O catálogo oficial descreve câmera estéreo DALSA, VLP-16 a 10 Hz e IMU Xsens, além de bags com visão reduzida a
960 x 600 a 10 Hz. Esses nomes, resolução e tópicos coincidem com a configuração BotanicGarden atual. Essa checagem
serve apenas para justificar a aquisição; frequências, campos e cobertura observados continuam pendentes.

Na data do inventário havia 139 GiB livres no volume local e nenhum dos oito bags. Os indicadores de tamanho publicados
mostram que o conjunto completo ocupa centenas de gigabytes, portanto não é seguro iniciar a aquisição integral nesse
volume. É necessário definir um destino com capacidade suficiente ou um fluxo auditável de aquisição e arquivamento
sequência a sequência. Nenhum download volumoso será iniciado implicitamente.

No PC que guarda os dados de desenvolvimento, o volume local tinha 431 GiB livres em 29/10/2026. Isso permite um
fluxo sequência a sequência, mas não a aquisição integral simultânea.

## 7. Decisão G0 e próximo gate

- **G0-A — existência catalográfica:** aprovado; existem oito candidatas públicas novas com GT anunciado.
- **G0-B — elegibilidade estrutural:** aprovado; 8/8 candidatas triadas aprovadas (`1005-00`, `1005-01`, `1005-07`,
  `1006-01`, `1008-03` na seção 10; `1005-05`, `1006-03`, `1008-01` na seção 11).
- **`k` final:** `k = 8`; aprovadas permanecem no teste (critério 8).
- **grupos de dia:** três (`1005`, `1006`, `1008`), com 4, 2 e 2 sequências aprovadas.
- **status confirmatório:** ainda não concedido; depende de G0-B, representação dos três dias e gate de viabilidade
  estatística do piloto.

A triagem estrutural foi implementada (seção 9) e aplicada às oito candidatas (seções 10 e 11). Próximo passo:
implementar o restante do modo cego G1 sem dados externos, antes de qualquer extração das sequências aprovadas.

## 8. Custódia do GT já presente localmente (emenda de 29/10/2026)

### 8.1 Achado

O arquivo `data/raw/botanic/GT_pose_qnew.zip`, baixado em 14/10/2026 para obter o GT de `1018-00` e `1018-13`, contém
sete bags de GT. Foram listados apenas os nomes do arquivo compactado e do diretório extraído:

- desenvolvimento: `gt_1018_00_qnew.bag`, `gt_1018_13_qnew.bag`;
- candidatas: `gt_1005_00_qnew.bag`, `gt_1005_01_qnew.bag`, `gt_1005_07_qnew.bag`, `gt_1006_01_qnew.bag`,
  `gt_1008_03_qnew.bag`.

O GT de `1005-05`, `1006-03` e `1008-01` não faz parte desse arquivo. A primeira versão do inventário, feita em outra
máquina, não sabia da existência desses cinco arquivos.

### 8.2 Evidência de não abertura

O volume é montado com `relatime`: uma leitura atualiza o `atime` sempre que o valor anterior tem mais de 24 h ou não é
posterior ao `mtime`. Os cinco bags candidatos preservavam `atime = mtime` iguais à data de criação no arquivo
compactado (01/06/2024), restaurada pelo `unzip`. Os bags de `1018-00` e `1018-13` mostravam leituras em 14/10/2026 e
15/10/2026. Assim, não há registro de leitura dos cinco GTs candidatos desde a extração.

| Arquivo | Bytes | `atime` = `mtime` |
|---|---:|---|
| `gt_1005_00_qnew.bag` | 812080 | 2024-06-01 19:37:40 -0300 |
| `gt_1005_01_qnew.bag` | 639998 | 2024-06-01 19:39:38 -0300 |
| `gt_1005_07_qnew.bag` | 753839 | 2024-06-01 19:44:20 -0300 |
| `gt_1006_01_qnew.bag` | 1025804 | 2024-06-01 19:46:14 -0300 |
| `gt_1008_03_qnew.bag` | 862398 | 2024-06-01 19:33:42 -0300 |

Essa evidência é circunstancial: `atime` é metadado alterável e não prova a ausência de leitura por outro meio. O
`atime` do `.zip` registra 29/10/2026 13:33:10, causado por `unzip -l` durante este levantamento. Esse comando lê
somente o diretório central do arquivo (nomes e tamanhos) e não descompacta nenhum membro.

### 8.3 Isolamento

Em 29/10/2026, os cinco bags candidatos e o `GT_pose_qnew.zip` foram movidos por renomeação no mesmo sistema de
arquivos, sem cópia nem leitura, para `data/sealed/botanic_gt/` (fora do git). As permissões dos arquivos passaram a
`000`. Tamanhos, `atime` e `mtime` foram conferidos depois do movimento e permaneceram iguais. Os dois GTs de
desenvolvimento continuam em `data/raw/botanic/GT_pose_qnew/GT_pose_qnew/`.

Ainda não foram calculados hashes desses cinco arquivos, pois isso exige lê-los. O hash e a verificação de
proveniência e esquema (critério 2 da seção 3) serão feitos pela triagem cega. Nenhuma ferramenta do pipeline poderá
ler `data/sealed/`; somente a triagem estrutural e a abertura única de G1 poderão restaurar a permissão de leitura, e
cada restauração deverá ser registrada. O uso de um custodiante externo continua preferível e em aberto (seção 12 do
plano).

## 9. Implementação da triagem estrutural (29/10/2026)

A triagem está em `ofd/g0_triage.py`, com testes em `tests/test_g0_triage.py`. A referência estrutural congelada é
`configs/botanic/g0_reference.json` (sha256 `12a80e15f61225d920b8c32e9ef67a4ebfd5228ff7b0af559885129b8f67b947`),
gerada pelo subcomando `reference` a partir de `1018-00` e `1018-13`. Os dois pares precisam produzir assinaturas
idênticas, e produziram.

As interpretações operacionais abaixo foram fixadas antes de qualquer candidata ser baixada ou triada:

- **Leitura cega:** de cada mensagem é lido apenas o `std_msgs/Header` (stamp e `frame_id`) direto dos bytes ROS1. Em
  imagens e nuvens são lidos também os campos estruturais (dimensões, codificação, `PointField`s, `point_step` e
  comprimento de `data`). Nenhum payload é desserializado: um teste substitui `AnyReader.deserialize` por uma função
  que falha e exige aprovação. Os bytes de pose do GT nunca são interpretados, e tópicos de tipo inesperado não têm o
  conteúdo interpretado.
- **Critério 5 (payload aceito pelos pipelines):** igualdade exata com a referência de desenvolvimento em tipo ROS,
  md5 da definição, resolução, codificação, `step`, endianness, `PointField`s (nome, offset, tipo e contagem) e
  `point_step`, além de comprimento de `data` coerente em todas as mensagens. É um critério conservador: os quatro
  pipelines congelados foram validados apenas nessa assinatura.
- **Critério 4 (timestamps):** stamps de header estritamente crescentes por tópico, na ordem de gravação do bag. A
  interseção comum é `min(últimos) − max(primeiros)` entre câmera esquerda, câmera direita, LiDAR, IMU e GT, e precisa
  ter pelo menos 30 s.
- **Critério 2 (GT):** o contêiner precisa ser ROS1 bag com `/gt_poses` `geometry_msgs/PoseStamped`, o mesmo md5 de
  definição e `frame_id` `/velodyne` em todas as mensagens. A proveniência é declarada no manifesto de aquisição pela
  liberação oficial e precisa constar em `accepted_releases` (hoje somente `GT_pose_qnew`). Um GT em outro contêiner
  (por exemplo, TUM) não recebe decisão: a triagem exige uma emenda prévia definindo a equivalência estrutural.
- **Identidade:** os nomes do bag e do GT devem seguir `{dia}_{num}_VLIO.bag` e `gt_{dia}_{num}_qnew.bag`, e a data
  local (UTC+8) do primeiro stamp dos sensores e do GT deve coincidir com o dia da sequência. A regra foi conferida nos
  bags de desenvolvimento (18/10, horário de Pequim).
- **Hashes:** a triagem calcula md5 e sha256 dos dois arquivos e os grava na saída, onde passam a ser o hash
  registrado. Todo hash declarado no manifesto de aquisição (por exemplo, o md5 do catálogo) precisa coincidir; um
  algoritmo desconhecido invalida o manifesto.
- **Calibração:** os três arquivos usados por `tools/make_configs.py` (`calib_chain.yaml`, `dalsa_gray0_down.yaml`,
  `dalsa_gray1_down.yaml`) devem existir no diretório declarado e ter o mesmo sha256 da calibração que gerou as
  configurações congeladas.
- **Saída:** somente `seq`, decisão, códigos na ordem congelada, hashes, commit, sha256 da referência, versão e
  horário. A triagem de candidatas exige árvore git limpa. Com `--unseal`, a leitura do GT lacrado é liberada só durante
  a execução, a permissão `000` é restaurada mesmo em caso de falha e as duas ações ficam em `CUSTODY.log`, ao lado do
  arquivo.

**Verificação nos dados de desenvolvimento:** `1018-00` e `1018-13` foram triadas com a referência acima e saíram
`APPROVED`.

## 10. Resultado da triagem das cinco candidatas com GT local (29/10/2026)

### 10.1 Aquisição

O registro SJTU (`scidata.sjtu.edu.cn/records/kfjy8-ex881`) publica o md5 de cada bag; os md5 de `1018_00_VLIO.bag` e
`1018_13_VLIO.bag` nesse registro coincidem com os calculados localmente. O download pela SJTU foi abandonado: o servidor
aceita no máximo três conexões por IP, não aceita `Range` e derrubou as conexões repetidamente; nenhum arquivo foi
concluído (registro em `data/raw/botanic/g0_download.log`). Os cinco bags foram baixados dos links OneDrive do catálogo
oficial com `tools/fetch_onedrive.py`. Nome e tamanho de cada arquivo no OneDrive coincidem com o registro SJTU; cada
bag foi aceito somente após conferência do md5 da SJTU e do sha256 do OneDrive, ambos declarados em
`configs/botanic/g0_acquisition/<seq>.json`.

### 10.2 Execução abortada

A primeira execução (commit `51e99fa`) abortou nas cinco sequências com `ManifestError`: o campo `onedrive` do
manifesto foi interpretado como hash declarado. O erro ocorreu depois do cálculo dos hashes dos arquivos e antes de
qualquer leitura de headers; nenhuma decisão, contagem ou timestamp foi produzido e os hashes calculados foram
descartados. A correção (`f0bb112`) só torna explícitos os campos de metadados do manifesto e inclui um teste de
regressão; não altera critério nem referência.

### 10.3 Decisões

Execução com commit `f0bb112`, árvore limpa e referência sha256 `12a80e15…`:

| Sequência | Dia | Decisão | md5 do bag | sha256 do GT (registrado pela triagem) |
|---|---|---|---|---|
| `1005-00` | `1005` | `APPROVED` | `49d45853bc0fca326120fffe281badd3` | `6f0b16379f547ad314206f6a755b3a8830a229a7b0db28631a364f8f31f15dc5` |
| `1005-01` | `1005` | `APPROVED` | `9aed8283836ac148359532e52a0887dd` | `f8a218312e4b8166b19ef97b5f4c01c9d84bec74bb1a449998ee8795d914f893` |
| `1005-07` | `1005` | `APPROVED` | `eb8ace84af1fb47a5bb78392acb6ae1f` | `d922c4b1431c812e7e0830b96b39cec8c2fb88095eb4a2777901be36978a1099` |
| `1006-01` | `1006` | `APPROVED` | `cb427d7aac23fb03d35ee435e2b66e5a` | `e5327844e8e34aa6cee1665d8d8dadf58260bc61af747da6b7f8934283209cdb` |
| `1008-03` | `1008` | `APPROVED` | `c8887c91a3e6d98bb79e3e71843b0b25` | `a070acce630560c8aea4a376fef39cc299fa1426c4103a364b371e916459133b` |

Saídas completas em `data/analysis/model_comparison/g0_triage/<seq>.json`. A saída da triagem contém somente os campos
da seção 9; nenhuma contagem, duração, trajetória ou métrica foi vista.

### 10.4 Custódia

`data/sealed/botanic_gt/CUSTODY.log` registra dez pares `unseal_read`/`reseal`: cinco da execução abortada (20:52–21:10
UTC) e cinco da execução válida (21:10–21:48 UTC). Ao final, os cinco GTs permanecem com permissão `000`. Nessas
leituras os GTs foram hasheados e somente os headers foram interpretados.

### 10.5 Consequência

Com cinco aprovadas e os três dias representados, a condição mínima de G0 para um teste com `k >= 5` está satisfeita.
O status confirmatório continua dependente das três sequências restantes (que, se aprovadas, entram obrigatoriamente),
do modo cego G1 completo (extração, tabela, predição e abertura) e do gate de viabilidade do piloto.

## 11. Emenda de proveniência do GT da tabela adicional (30/10/2026, antes da triagem)

### 11.1 Aquisição

Em 30/10/2026, os bags e GTs de `1005-05`, `1006-03` e `1008-01` foram baixados dos links OneDrive da tabela adicional
do catálogo oficial (commit `84c4806`), com `tools/fetch_onedrive.py` no commit `735bbc2`. Essas sequências não constam
do registro SJTU, portanto não há md5 publicado: cada arquivo foi aceito somente após conferência do tamanho e do sha256
informados pelo OneDrive, declarados em `configs/botanic/g0_acquisition/<seq>.json`. Os GTs foram gravados diretamente
em `data/sealed/botanic_gt/`, lacrados (`000`) logo após a conferência e registrados como `acquire_seal` em
`CUSTODY.log`. Na aquisição, o conteúdo dos GTs só foi lido para calcular hashes; nada foi interpretado.

### 11.2 Decisão

O critério 2 exige que a liberação oficial do GT conste em `accepted_releases` (hoje somente `GT_pose_qnew`). Para as
três sequências, a liberação declarada no manifesto passa a ser `GT_pose_qnew`, com base em evidência exclusivamente
catalográfica, obtida sem abrir os arquivos:

- os links de GT vêm da linha `GT-pose` do mesmo catálogo oficial que publica `GT_pose_qnew`;
- os nomes no OneDrive seguem o padrão `gt_{dia}_{num}_qnew.bag` da liberação `GT_pose_qnew`, inclusive o sufixo
  `qnew`;
- o contêiner é ROS1 bag (extensão `.bag`), com tamanho da mesma ordem do GT das cinco candidatas já triadas
  (834–934 kB contra 640–1026 kB).

Essa decisão é nominal. Ela não dispensa a verificação estrutural: a triagem continua exigindo `/gt_poses`
`geometry_msgs/PoseStamped` com o mesmo md5 de definição e `frame_id` `/velodyne` em todas as mensagens, e qualquer
divergência reprova a sequência com `GT_FORMAT_MISMATCH`. Critérios, referência (`12a80e15…`) e código da triagem não
mudam. Conforme o critério 8, sequências aprovadas entram no teste independentemente do desempenho posterior.

### 11.3 Decisões

Execução com commit `0a40f3c` (emenda já registrada), árvore limpa e referência sha256 `12a80e15…`:

| Sequência | Dia | Decisão | md5 do bag | sha256 do GT (registrado pela triagem) |
|---|---|---|---|---|
| `1005-05` | `1005` | `APPROVED` | `7250ca42d48385255def3e60999cda5d` | `33d9650b82135c2b8818932da693523811906699124d7037989dbb4de45dc1ca` |
| `1006-03` | `1006` | `APPROVED` | `e868179b8a65e80ac98b564f8a2a0236` | `2d507e1344da2dbb8763f96971f9d9ea902e95f7084acc903768a3f8737cf3dd` |
| `1008-01` | `1008` | `APPROVED` | `67661524c357b03308f66da48c8881cb` | `9e8a64b2f440dd7ac95399795187b20769f204da50001a7573e91a0a34c0d7db` |

Os sha256 dos bags e dos GTs calculados pela triagem coincidem com os do OneDrive declarados nos manifestos. Saídas
completas em `data/analysis/model_comparison/g0_triage/<seq>.json`; nenhuma contagem, duração, trajetória ou métrica foi
vista.

### 11.4 Custódia

`CUSTODY.log` registra, para cada um dos três GTs, `acquire_seal` (aquisição) e um par `unseal_read`/`reseal` (triagem,
14:06–14:30 UTC). Ao final, os oito GTs candidatos permanecem com permissão `000`.

### 11.5 Consequência

G0-B está concluído com `k = 8`: quatro sequências de `1005`, duas de `1006` e duas de `1008`. O status confirmatório
continua dependente do modo cego G1 completo (extração, tabela, predição e abertura) e do gate de viabilidade do piloto.
