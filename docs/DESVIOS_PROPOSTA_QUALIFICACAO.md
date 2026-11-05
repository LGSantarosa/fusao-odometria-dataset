# Correspondência entre a proposta de qualificação e o trabalho executado

**Estado:** levantamento de 05/11/2026, preparado para a reunião de resultados. Compara o projeto de dissertação
apresentado na qualificação (*Uma Abordagem de Fusão de Odometria Visual e LiDAR para Navegação Robusta de Robôs Móveis
em Ambientes Dinâmicos*, PUCPR, 29/07/2026) com o que foi executado neste repositório. Não cria hipótese, não altera
resultado e não autoriza análise nova sobre as sequências externas já abertas.

Cada item indica a seção da proposta, a situação e a justificativa. A origem da justificativa é marcada como:

- **[registrada]:** já constava em documento ou commit anterior a este levantamento, com a referência indicada;
- **[nova]:** formulada neste levantamento a partir de argumento técnico; deve ser validada pelo autor e pelo orientador
  antes de entrar na dissertação.

## 1. Resumo

| # | Item da proposta | Seção | Situação | Origem |
|---:|---|---|---|---|
| 1 | Comparar odometrias visuais e LiDAR (RQ1) | 1.3, 1.4.2 | executado | — |
| 2 | Testar se ponderação/fusão supera fontes isoladas (RQ2, H1) | 1.3, 1.5 | executado | — |
| 3 | Indicadores: *inliers*/*outliers* e erro de reprojeção | 4.3.3 | executado | — |
| 4 | Indicador: *fitness* do ICP/NDT | 4.3.3 | executado | — |
| 5 | Indicador: dinamicidade do ambiente | 4.3.3 | proxy relacionado executado; construto não medido diretamente | [registrada] |
| 6 | Modelo temporal de confiabilidade com pesos por fonte | 4.3.4, 4.4 | executado | — |
| 7 | Arquitetura fixa (LSTM 64→32, densa 16, *dropout* 0,2) | 4.4 | substituída por seleção em grade | [registrada] |
| 8 | LSTM bidirecional | 4.4 | não adotada | [registrada] |
| 9 | Saída softmax com duas fontes (VO, LO) | 4.4.3 | executado com quatro fontes | [registrada] |
| 10 | Saída sigmoid independente por fonte | 4.4.3 | não executado | [nova] |
| 11 | Perda ponderada pelo erro de cada sensor | 4.4.4 | substituída pela perda da estimativa fundida | [nova] |
| 12 | Seleção dura (uma fonte por instante) | 4.3.5, Alg. 1 | não executado como modo dinâmico; Bsel como seleção fixa | [nova] |
| 13 | Modo "fortemente acoplado" do Algoritmo 1 | 4.5 | fora do escopo | [nova] |
| 14 | Fusão clássica (EKF) como referência | 4.5 | substituído por filtro de Kalman de velocidade (T2) | [registrada] |
| 15 | Normalização das entradas (MinMax ou Standard) | 4.4.1 | executado (padronização) | — |
| 16 | Datasets WildScenes, RELLIS-3D, GOOSE | 4.1 | substituídos por BotanicGarden (+ RELLIS descritivo) | [registrada] |
| 17 | GT por RTK-GPS ou GNSS-INS | 4.3.6 | GT do BotanicGarden (levantamento) | [registrada] |
| 18 | ORB-SLAM3 como VO | 4.2, 5.1 | executado (+ Stella VSLAM) | [registrada] |
| 19 | LeGO-LOAM como LO | 5.1 | substituído por KISS-ICP e FAST-LIO2 | [registrada] |
| 20 | Métricas ATE e RPE | 4.3.6, 5.1 | executado; RMSE de velocidade como primária | [registrada] |
| 21 | Análises qualitativas | resumo, 1.3 | parcial | [nova] |
| 22 | Mitigação da ameaça interna (QoS) | 1.6.2 | executado | [registrada] |
| 23 | Mitigação da ameaça externa (lacuna de realidade) | 1.6.3 | executado (dados reais) | — |
| 24 | Cenários internos com pessoas | resumo | não executado | [nova] |

Leitura do quadro:

- **executados integralmente ou ampliados:** itens 1–4, 6, 9, 15, 18, 20, 22 e 23;
- **substituídos, com motivo registrado:** itens 7, 8, 14, 16, 17 e 19;
- **substituído, com justificativa formulada neste levantamento:** item 11 (perda);
- **correspondência parcial:** item 5 (dinamicidade medida apenas por proxy não específico) e item 21 (análises
  qualitativas);
- **não executados, com justificativa técnica:** itens 10, 12 e 13;
- **omissão de escopo:** item 24 (cenários internos com pessoas).

A única omissão explícita de escopo é o item 24. A ausência de medida direta de dinamicidade (item 5) permanece, além
disso, como limitação de construto.

## 2. Justificativas

### 2.1 Perguntas e hipótese

**1. RQ1 — comparação das odometrias.** Executada com ORB-SLAM3 e Stella VSLAM (visuais, estéreo, sem IMU, sem
fechamento de loop), KISS-ICP (LiDAR) e FAST-LIO2 (LiDAR-inercial), com erro, cobertura e continuidade por sequência
(`docs/RELATO_ACADEMICO_PIPELINE.md` §2.3 e resultados por sequência; `docs/RESULTS_sequences.md`). As fontes
isoladas também entram como baselines B1–B4 nos estudos de fusão.

**2. RQ2/H1 — fusão contra fontes isoladas.** Testada duas vezes. No estudo pré-registrado de duas sequências, a
ponderação aprendida (F1) superou a melhor fonte isolada e a regressão ridge na velocidade angular, mas não na linear,
e o resultado confirmatório foi negativo pela regra fixada (`docs/RESULTS_fusion_model.md`). No teste externo cego em
oito sequências, a CNN temporal não superou a média causal das fontes (`docs/RESULTS_phase4_external.md`). A H1 da
proposta tem, portanto, resposta experimental; a resposta não é a esperada.

### 2.2 Indicadores de qualidade

**3–4. *Inliers*, erro de reprojeção e *fitness*.** Executados. VO: `inliers`, `n_features`, `reproj_err`,
`tracked_ratio`. LO: `fitness`, `inlier_rmse`, `unmatched_ratio`, `n_points`, calculados uniformemente para KISS-ICP e
FAST-LIO2 (`ofd/schema.py`; `docs/RELATO_ACADEMICO_PIPELINE.md` §2.5).

**5. Dinamicidade.** [registrada] Correspondência parcial. A proposta sugere inferi-la pela razão de pontos dinâmicos
ou pela variância temporal dos scores. Foram implementados um proxy relacionado — a razão de pontos sem correspondência
(`unmatched_ratio`) — e variâncias móveis causais do erro de reprojeção e do *fitness* (`*_var_H`). O proxy não é
específico: pontos sem correspondência também resultam de oclusão, vegetação, mudança do campo de visão ou erro de
registro, e por isso o indicador não recebeu o nome "dinamicidade" (`docs/RELATO_ACADEMICO_PIPELINE.md` §§2.5 e 4.1).
O construto "dinamicidade do ambiente" não foi medido diretamente e permanece como limitação de construto.

### 2.3 Modelo

**6. Modelo temporal de confiabilidade.** Executado. As cabeças W de STEP, MLP-W, CNN-W e LSTM-W produzem pesos por
fonte e combinam as velocidades estimadas, exatamente na forma de seleção suave descrita no §4.3.5 da proposta
(`ofd/mc_models.py`).

**7. Arquitetura fixa.** [registrada] A proposta fixava uma LSTM 64→32 com densa de 16 unidades. O trabalho escolheu
largura, número de camadas e regularização por validação interna em grade pré-registrada, e comparou famílias
(MLP, CNN, LSTM) em igualdade de condições. Fixar a arquitetura antes de ver qualquer dado é aceitável, mas impede
saber se um resultado negativo decorre da família ou do tamanho escolhido; a seleção em grade elimina essa explicação
alternativa. A LSTM foi avaliada e não foi escolhida: a CNN empatou dentro de 1% com menos parâmetros
(`docs/RESULTS_phase3_pilot.md`).

**8. LSTM bidirecional.** [registrada] A camada bidirecional lê quadros futuros da janela e torna a estimativa não
causal: o resultado do instante k depende de dados posteriores a k, o que é incompatível com odometria em tempo real e
infla o desempenho offline. A própria proposta reconhece que a versão unidirecional é a indicada para tempo real
estrito (§4.4). O plano manteve a BiLSTM apenas como exploratória, fora da alegação principal
(`docs/PLAN_model_comparison.md` §§1, 3.5 e 11).

**9. Softmax com duas fontes.** [registrada] Generalizada para quatro fontes, com máscara: fontes inválidas no
instante recebem peso zero e os pesos das válidas somam 1. A máscara trata explicitamente a ausência de uma
odometria, situação que a softmax de duas saídas da proposta não prevê (`ofd/mc_models.py`, linha da `masked_fill`).

**10. Sigmoid independente.** [nova] Não executada. Pesos sigmoid não precisam matematicamente somar 1, mas a
normalização é necessária para preservar a interpretação da saída como combinação convexa das estimativas; após
normalizados, eles representam o mesmo conjunto de combinações que a softmax, e a diferença fica restrita à
parametrização. O caso que a sigmoid pretende capturar — todas as fontes ruins ao mesmo tempo — não tem saída útil sem
uma fonte reserva ou um mecanismo de rejeição, que a proposta não define. A confiabilidade por fonte poderia ser
aprendida como variável latente, mas sem rótulo ou critério adicional ela não seria identificável nem calibrada como
confiabilidade; a própria proposta reconhece, no §4.4.4, que não há peso ideal anotado. Pode ser executada como ablação
exploratória no desenvolvimento, sem alegação de generalização.

**11. Perda ponderada por sensor.** [nova] A perda proposta, `W_VO·Erro(ΔX_VO, ΔX_GT) + W_LO·Erro(ΔX_LO, ΔX_GT)`, é
linear nos pesos. Se pesos não negativos que somam 1 pudessem ser escolhidos livremente em cada amostra, seu mínimo
estaria em um vértice: peso 1 para a fonte de menor erro e 0 para as demais. Com uma rede parametrizada por indicadores,
que não observa o erro verdadeiro e compartilha parâmetros entre instantes, esse extremo não é necessariamente atingido
em cada instante; ainda assim, a função objetivo não contém termo que recompense a complementaridade entre os erros das
fontes, isto é, o caso em que a média de duas estimativas imperfeitas é mais precisa que qualquer uma delas. A perda
adotada mede o erro da estimativa fundida em relação ao GT, corresponde à formulação textual do mesmo parágrafo da
proposta ("calcular o erro da pose final gerado pelos pesos aplicados") e pode recompensar tanto seleção quanto
combinação (`docs/protocol_fusion_model.md` §7).

**12. Seleção dura.** [nova] Não executada como modo dinâmico. A softmax pode aproximar a seleção dura, atribuindo
peso próximo de 1 a uma fonte quando isso reduz o erro, embora não a atinja exatamente com logits finitos. O *argmax*
não é diferenciável e exigiria outro mecanismo apenas se usado durante o treinamento; aplicá-lo na inferência sobre
pesos já aprendidos é possível. A troca abrupta entre fontes introduz descontinuidades na velocidade estimada, o que
pode degradar o RPE, métrica que a própria proposta adota para detectar saltos nas transições (§4.3.6); a posição
integrada não é necessariamente descontínua. A melhor fonte isolada escolhida no treino (Bsel) foi mantida como
referência de seleção fixa (`docs/protocol_fusion_model.md` §6). Pode ser executada como ablação exploratória no
desenvolvimento, aplicando *argmax* aos pesos dos modelos congelados.

**13. Modo "fortemente acoplado" do Algoritmo 1.** [nova] No Algoritmo 1, o modo forte aparece como uma operação sobre
as transformações estimadas (linha 16), mas acoplamento forte, na acepção usual, combina medidas brutas dos sensores
num mesmo estimador, e não as saídas de odometrias já calculadas. O trabalho é, por construção, de acoplamento fraco:
combina as saídas de quatro odometrias. Acoplamento forte visual–LiDAR exigiria um estimador próprio sobre imagens,
nuvens e IMU, que é outro projeto. O FAST-LIO2 é internamente um sistema LiDAR–IMU fortemente acoplado, mas isso não
executa o modo forte visual–LiDAR proposto; apenas indica que uma das quatro fontes pertence a essa classe.

**14. EKF como referência clássica.** [registrada] Substituído por um filtro de Kalman de velocidade (T2): estado de
seis velocidades com dinâmica de persistência, atualizado pelas fontes válidas, com hiperparâmetros escolhidos no
desenvolvimento (`docs/PLAN_model_comparison.md` §2, G2). Não é o EKF sobre poses descrito na proposta, mas cumpre o
mesmo papel de referência clássica de fusão fraca e opera sobre a mesma representação que os modelos aprendidos. No
teste externo, T2 teve RMSE angular menor que a média em 8/8 sequências; o resultado é descritivo, pois essa
comparação não foi registrada como confirmatória (`docs/RESULTS_phase4_external.md`).

**15. Normalização.** Executada por padronização ajustada só no treino, com tratamento de fontes inválidas e recorte
em ±10 desvios (`docs/protocol_fusion_model.md` §5 e emenda de 20/10).

### 2.4 Dados

**16. Datasets.** [registrada] WildScenes e GOOSE foram substituídos pelo BotanicGarden porque o estudo exigia
sequências contínuas com imagens estéreo, nuvens de pontos, IMU, calibração entre sensores e trajetória de referência
compatível com avaliação quadro a quadro; o BotanicGarden atende a esses requisitos de forma direta
(`docs/RELATO_ACADEMICO_PIPELINE.md` §2.2). O RELLIS-3D foi processado, mas a origem metrológica do `poses.txt` não é
declarada e a associação entre poses e varreduras não foi validada; por isso o dataset permaneceu apenas descritivo,
sem métricas de erro (`docs/preflight_rellis.md`; `docs/ESTADO.md`).

**17. GT.** [registrada] O GT do BotanicGarden deriva de levantamento com scanner Leica RTC360, não de RTK-GPS ou
GNSS-INS. A precisão de cerca de 11 mm informada pelos autores refere-se ao mapa e não é garantia independente para
cada pose; isso é declarado como limitação (`docs/RELATO_ACADEMICO_PIPELINE.md` §2.2).

### 2.5 Algoritmos de odometria

**18. ORB-SLAM3.** Executado, com o Stella VSLAM como segunda odometria visual por pedido do orientador
(`docs/superpowers/specs/2026-10-14-odom-fusion-dataset-design.md`). Ambos sem IMU e sem fechamento de loop, para que
as poses representem odometria causal.

**19. LeGO-LOAM.** [registrada] A implementação oficial do LeGO-LOAM, usada como referência, é baseada em ROS 1 e
catkin e foi testada em Indigo, Kinetic e Melodic; não é diretamente compatível com o ambiente nativo congelado deste
trabalho, Ubuntu 24.04 com ROS 2 Jazzy (`docs/superpowers/specs/2026-10-14-odom-fusion-dataset-design.md`, §2). Portá-la
e validá-la introduziria uma etapa adicional fora do pipeline adotado. Por isso, foi substituída pelo KISS-ICP como
odometria LiDAR pura e complementada pelo FAST-LIO2 como odometria LiDAR-inercial. A substituição é operacional e não
implica desempenho inferior do LeGO-LOAM no ambiente-alvo: o artigo original o apresenta para veículos terrestres em
terreno variável, com experimentos em vegetação e trilha florestal (Shan e Englot, 2018, §IV.B). O uso de IMU pelo FAST-LIO2 é tratado como ameaça ao
construto: comparações com ele são entre sistemas de odometria, não entre modalidades puras
(`docs/RELATO_ACADEMICO_PIPELINE.md` §2.3).

### 2.6 Avaliação e validade

**20. Métricas.** [registrada] ATE e RPE foram calculados. As métricas primárias dos estudos de fusão foram o RMSE
vetorial das velocidades linear e angular, que corresponde ao alvo do modelo (`docs/PLAN_model_comparison.md` §7.1).
O RPE de 10 m foi tratado como guarda de trajetória e o ATE como secundário, por depender do trecho e do alinhamento
global (`docs/PLAN_model_comparison.md` §7.2; `docs/amendment_phase4_hypothesis.md` §3). Isso responde à ameaça ao
construto da proposta (§1.6.1): nenhuma métrica isolada foi tomada como indicador de robustez.

**21. Análises qualitativas.** [nova] Parcial. Há análises descritivas de cobertura, falhas e trechos por sequência,
mas não um conjunto sistemático de figuras de trajetória com comentários. Pode ser produzido a partir das predições já
gravadas, sem nova abertura de GT e sem afetar resultado algum.

**22. Ameaça interna (QoS).** [registrada] A proposta propõe mitigar atrasos de infraestrutura com QoS. Foi
exatamente o que ocorreu: a assinatura de nuvens do FAST-LIO2 passou a usar QoS confiável, eliminando saltos isolados
de uma varredura (commit `2c35918`). As demais odometrias rodaram offline sobre arquivos extraídos, sem dependência de
temporização de rede.

**23. Ameaça externa (lacuna de realidade).** Todo o trabalho usou dados reais de robôs em campo; não houve simulação.

**24. Cenários internos com pessoas.** [nova] Não executado. O resumo da proposta menciona espaços internos com pessoas,
mas as questões de pesquisa, os datasets escolhidos e os resultados esperados (§5.1) tratam de ambientes externos não
estruturados. Nenhum dataset com GT interno e dinâmico foi processado. Entra como limitação e trabalho futuro; nenhuma
conclusão é estendida a ambientes internos.

## 3. Pendências que podem ser executadas sem violar o protocolo

As variações abaixo podem ser executadas apenas nas sequências de desenvolvimento (1018-00 e 1018-13), como ablação
exploratória, sem uso das oito sequências externas já abertas:

- seleção dura por *argmax* sobre os pesos dos modelos congelados (item 12);
- saída sigmoid normalizada (item 10);
- figuras qualitativas de trajetória a partir das predições já gravadas (item 21).

Qualquer alegação confirmatória sobre essas variações exigiria novo protocolo e dados independentes.
