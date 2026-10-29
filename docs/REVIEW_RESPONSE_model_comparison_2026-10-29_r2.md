# Resposta ao segundo parecer — comparação de modelos

> **Nota posterior:** a terceira revisão substituiu o comparador F1-W por F1-R retreinado, definiu seleção depois de
> Pα e trocou, no §3 abaixo, o transporte do número de épocas pelo número de atualizações do otimizador. Ver
> `docs/REVIEW_RESPONSE_model_comparison_2026-10-29_r3.md`.

**Data:** 29/10/2026

**Documento revisado:** `docs/PLAN_model_comparison.md`

**Estado:** decisões estruturais incorporadas antes do protocolo e sem abertura de dados novos.

## 1. Cabeça W versus suavização clássica

O conflito apontado foi aceito. Uma cabeça W que combina somente twists atuais não será colocada, na hipótese principal,
contra um método que suaviza sem receber a mesma possibilidade.

Decisão:

- definir uma pós-filtragem EMA comum Pα;
- escolher `α` uma vez com B5 no desenvolvimento;
- aplicar exatamente o mesmo Pα a B5, F1-W, MLP-W, CNN-W e LSTM-W;
- manter as saídas sem Pα como análise secundária;
- manter T2/Kalman como sistema clássico separado.

H1 passa a comparar CNN/LSTM-W + Pα contra F1-W + Pα e B5 + Pα. Uma eventual superioridade confirmatória sobre
T2/Kalman será H3 condicional, somente se o gate de viabilidade mostrar poder suficiente; caso contrário, será
descritiva.

## 2. Janela comum

`W` não fará parte das 18 configurações de cada família. Ela será escolhida uma única vez no piloto pelo LOSO da MLP-W,
entre valores pré-declarados e com desempate pela menor janela. Depois será imposta a MLP-W, CNN-W e LSTM-W.

Isso impede que H2 compare modelos com contextos diferentes e torna a MLP-W um controle conservador, porque a própria
MLP participa da escolha de `W`.

## 3. Validação de desenvolvimento

Foi adotada a recomendação de usar LOSO como critério principal:

- D-A treina em `1018-00` e valida em `1018-13`;
- D-B faz o inverso;
- perdas são agregadas sobre as duas dobras e sementes;
- Pα, `W`, T2, configurações e CNN versus LSTM são escolhidos somente nesse desenvolvimento.

Blocos temporais dentro da sequência de treino servem apenas para escolher épocas e detectar instabilidade, com a
purga e o embargo previstos no plano. O modelo externo final será treinado nas duas sequências pelo número de épocas
derivado por regra congelada dos blocos internos.

## 4. Viabilidade da hipótese

A conjunção de duas métricas, dois comparadores, margem prática e guarda de RPE continua rigorosa e pode ter pouco poder.
Antes do pré-registro serão feitos:

1. piloto LOSO para verificar direção e magnitude dos efeitos nas duas dobras;
2. análise de sensibilidade da regra completa para o `k` realmente disponível;
3. decisão de prosseguir, simplificar ou rotular o estudo como exploratório.

As margens serão definidas por relevância prática e não reduzidas para aumentar artificialmente a chance de aprovação.
Com somente duas dobras, o piloto é diagnóstico e não uma estimativa confiável de poder.

## 5. Pontos menores resolvidos

- a realização principal das VOs será a oficial do dataset v1 ou, em sequência nova, a primeira execução completa do
  pipeline congelado que passar critérios operacionais sem GT;
- repetições de VO serão apenas sensibilidade e nunca substituirão a realização principal;
- o título de trabalho foi neutralizado para não presumir superioridade sobre suavização clássica;
- linhas sem nenhuma fonte usam retenção causal da última predição e zero antes da primeira válida, como no protocolo
  anterior.

## 6. Pendências numéricas

A estrutura está decidida, mas o protocolo ainda precisa fixar:

- candidatos e valor final de `W`;
- grade e valor de `α`;
- formulação e grade de T2;
- margens `δ_v`, `δ_ω` e `δ_RPE`;
- `k`, regra exata por sequência e limiar de viabilidade;
- número de épocas, sementes e teto de parâmetros.

G0 continua sendo o bloqueio principal: sem novas sequências com GT, o estudo não receberá status confirmatório.
