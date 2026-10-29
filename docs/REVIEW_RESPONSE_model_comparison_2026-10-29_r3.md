# Resposta ao terceiro parecer — comparação de modelos

**Data:** 29/10/2026

**Documento revisado:** `docs/PLAN_model_comparison.md`

**Estado:** últimos esclarecimentos estruturais incorporados; próxima revisão somente após G0 e preenchimento dos
números do protocolo.

## 1. Perda de treino e perda de seleção

Foi adotado o fluxo sugerido:

- F1-R, MLP-W, CNN-W e LSTM-W treinam sem Pα;
- Pα fica fora do gradiente e só entra na validação/inferência;
- configurações, CNN versus LSTM e orçamento de atualizações são escolhidos pela perda padronizada depois de Pα;
- o filtro percorre causalmente a sequência completa a partir de estado zero e a perda é recortada nos endpoints
  elegíveis, sem reset artificial no começo de um bloco com GT.

Isso alinha o critério de seleção às saídas usadas por H1/H2 sem transformar Pα em parte treinável da rede.

## 2. Orçamento em atualizações, não épocas

O número de épocas não será transportado entre conjuntos de tamanhos diferentes. Cada execução registrará chamadas a
`optimizer.step()` com lote 64:

1. blocos internos selecionam o checkpoint pela perda pós-Pα e registram suas atualizações cumulativas;
2. o treino da dobra usa a mediana arredondada para cima de todas as combinações de bloco e semente;
3. o treino final em `1018-00 + 1018-13` usa a mediana arredondada para cima dos dois orçamentos de dobra e para
   exatamente nesse número de atualizações, mesmo no meio de uma época;
4. atualizações e épocas efetivas são ambas reportadas.

## 3. F1 retreinado

Os artefatos de F1 do primeiro experimento permanecem somente como registro histórico. O comparador de H1 passa a ser
**F1-R**, treinado do zero no novo pipeline com:

- o mesmo LOSO de desenvolvimento;
- normalização restrita ao treino;
- 18 configurações, sementes e orçamento de atualizações comparáveis;
- treino sem Pα e seleção depois de Pα;
- treino final nas duas sequências de desenvolvimento.

Assim, H1 não compara um candidato novo com um artefato treinado sob outra divisão ou regra.

## 4. Assimetria conservadora de α

`α` será escolhido uma vez para otimizar B5 no desenvolvimento. O mesmo valor será aplicado a F1-R, MLP-W, CNN-W e
LSTM-W sem reotimização por modelo.

Essa assimetria favorece deliberadamente o comparador e torna o teste conservador. A escolha será declarada no
protocolo; resultados posteriores dos modelos aprendidos não poderão provocar outro `α`.

## 5. Estado após esta rodada

A estrutura científica está fechada. Restam:

- inventário G0 e decisão confirmatório versus exploratório;
- valores candidatos e finais de `W` e `α`;
- formulação/grade de T2;
- margens `δ_v`, `δ_ω` e `δ_RPE`;
- `k`, regra por sequência e gate de viabilidade;
- sementes, teto de parâmetros e orçamento máximo de atualizações.

Nenhum modelo foi executado e nenhum dado externo foi aberto nesta revisão.
