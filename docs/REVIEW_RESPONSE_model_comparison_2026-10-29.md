# Resposta ao parecer externo — comparação de modelos

**Data:** 29/10/2026

**Documento revisado:** `docs/PLAN_model_comparison.md`

**Estado:** parecer recebido antes de qualquer novo protocolo ou execução de teste.

## 1. Verificações independentes

O alerta sobre abertura prematura do teste foi confirmado no código:

- `scripts/run_sequence.sh` termina chamando `python -m ofd.evaluate`;
- `ofd.extract.extract` inclui o tópico configurado de GT entre os tópicos lidos, mesmo sem argumento explícito de GT;
- `ofd.build_dataset.build_sequence` materializa `gt_*` e `*_err_*`;
- `ofd.evaluate.main` atualiza `data/output/metrics.csv` e imprime as métricas.

Conclusão: o pipeline atual não pode processar uma sequência confirmatória ainda cega. O plano revisado transforma a
implementação de um fluxo sem GT, seguida de abertura única com hashes, em bloqueio anterior ao protocolo.

## 2. Pontos aceitos e incorporados

- novos dados com GT e a quantidade de sequências são uma condição de viabilidade, não detalhe posterior;
- inclusão de baseline temporal sem aprendizado e comparador clássico de Kalman;
- hipótese principal hierárquica, com CNN/LSTM escolhida só na validação interna;
- F1 renomeada como MLP por passo com histórico resumido implícito `H = 10`;
- cabeça W temporal usa histórico para calcular pesos, mas combina somente twists atuais;
- LSTM principal usa janela fixa e reset compatível entre treino e inferência;
- contexto pode conter linhas sem GT, mas somente o endpoint com GT contribui para supervisão;
- campo receptivo explícito `R = W + H − 1`, purga posterior e embargo de alvo;
- mesmo orçamento de 18 configurações para cada família neural e teto de parâmetros pré-fixado;
- ablações reportam cobertura e métricas globais/condicionais;
- perda de fonte zera `valid` e todas as features da fonte;
- RPE de 10 m entra como guarda de não inferioridade;
- desvio entre sementes deixa de ser limiar de relevância prática;
- variabilidade das odometrias visuais passa a exigir repetição controlada ou limitação explícita;
- BiLSTM, cabeça D e ablações amplas saem do núcleo confirmatório.

## 3. Ajustes de interpretação

### Número de sequências

`k ≥ 5` não é uma garantia geral de suficiência. Com cinco sequências, um teste de sinais exato atinge α = 0,05 apenas
na alternativa unilateral e somente com as cinco favoráveis (`p = 0,03125`). Um teste bilateral exige no mínimo seis
sequências para unanimidade. O plano registra essa aritmética sem transformar o mínimo em análise de poder.

### Orçamento de busca

As 18 configurações iguais serão exigidas para as famílias neurais comparadas. Baselines clássicos não receberão
configurações artificiais apenas para alcançar o mesmo número; suas grades serão pequenas, justificadas e congeladas.
Como `1018-00` e `1018-13` foram declaradas desenvolvimento, janela e teto de parâmetros podem ser estudados nesse
piloto, mas os resultados dele não serão confirmatórios e tudo será congelado antes de processar o teste externo.

### MLP por passo

O histórico implícito de F1/F2 está apenas nas estatísticas causais `*_var_H`, não em uma janela completa das 56
features. A MLP com janela continua necessária para separar acesso ao contexto de efeito da arquitetura.

## 4. Escopo mínimo após o parecer

O núcleo confirmatório passa a ser:

1. F1/MLP-W por passo;
2. EMA-B5 e Kalman causal;
3. MLP-W com a mesma janela;
4. um candidato escolhido entre CNN 1D-W e LSTM-W;
5. H1 contra F1 e filtragem clássica, seguida de H2 contra MLP-W de janela;
6. RMSE linear/angular com margem prática e guarda de RPE.

Fontes isoladas permanecem descritivas. Cabeça D, BiLSTM, leave-one-source-out e perda de FAST-LIO2 permanecem
exploratórias.

## 5. Questões ainda abertas

1. Quantas sequências novas com GT existem sem análise anterior?
2. Quem custodiará o GT ou executará a abertura única?
3. Qual formulação e grade do Kalman serão usadas?
4. Quais margens de melhora e não inferioridade têm relevância prática?
5. As VOs serão repetidas ou tratadas como uma única realização oficial?
6. Haverá aumento de treino por remoção aleatória de fontes?
7. Existe hardware-alvo que justifique uma pergunta de implantação?

Até essas questões serem resolvidas, o veredito permanece **revisar antes do protocolo**. Se não houver novas
sequências com GT em número compatível com a regra escolhida, o estudo será explicitamente exploratório.
