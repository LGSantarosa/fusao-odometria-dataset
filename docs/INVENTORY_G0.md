# Inventário G0 — sequências externas do BotanicGarden

**Data do inventário:** 29/10/2026

**Fonte consultada:** catálogo oficial do BotanicGarden no commit
[`84c4806`](https://github.com/robot-pesg/BotanicGarden/tree/84c4806428ca16c154238e263a7f8bf828bf58e1)

**Estado:** inventário catalográfico concluído; elegibilidade estrutural e `k` final pendentes.

> **Emenda pré-triagem — 29/10/2026.** Antes de baixar ou inspecionar qualquer bag, foram acrescentados: agrupamento
> por dia, limite da alegação a novas sequências, permanência de toda sequência aprovada independentemente do
> desempenho posterior das odometrias e equivalência obrigatória de proveniência/formato do GT. Nenhum dado externo
> foi aberto para produzir esta emenda.

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

| Sequência | Grupo no catálogo oficial | VLIO público | GT público | Arquivo local | Decisão estrutural |
|---|---|---:|---:|---:|---|
| `1005-00` | sete amostras principais | sim | sim | não | pendente |
| `1005-01` | sete amostras principais | sim | sim | não | pendente |
| `1005-05` | tabela pública adicional | sim | sim | não | pendente |
| `1005-07` | sete amostras principais | sim | sim | não | pendente |
| `1006-01` | sete amostras principais | sim | sim | não | pendente |
| `1006-03` | tabela pública adicional | sim | sim | não | pendente |
| `1008-01` | tabela pública adicional | sim | sim | não | pendente |
| `1008-03` | sete amostras principais | sim | sim | não | pendente |

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

## 7. Decisão G0 e próximo gate

- **G0-A — existência catalográfica:** aprovado; existem oito candidatas públicas novas com GT anunciado.
- **G0-B — elegibilidade estrutural:** pendente; nenhum bag foi inspecionado.
- **`k` final:** pendente; `0 <= k <= 8` até a triagem cega.
- **grupos de dia:** três (`1005`, `1006`, `1008`); todos precisam estar representados no teste confirmatório.
- **status confirmatório:** ainda não concedido; depende de G0-B, representação dos três dias e gate de viabilidade
  estatística do piloto.

O próximo passo seguro é implementar e testar a triagem estrutural e o modo cego G1 sem dados externos. Depois disso,
os bags podem ser adquiridos, hasheados e classificados sem executar odometrias nem expor GT numérico.
