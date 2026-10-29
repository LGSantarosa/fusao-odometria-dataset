# Resposta ao quarto parecer — comparação de modelos

**Data:** 29/10/2026

**Documento revisado:** `docs/PLAN_model_comparison.md`

**Estado:** viés de memória de Pα corrigido; nenhuma pendência estrutural restante além de G0.

## 1. Memória de Pα nos blocos internos

O problema foi aceito. Embora o estado anterior não carregue o alvo, ele pode carregar predições in-sample e tornar as
primeiras linhas de validação otimistas.

Foi definido:

- `ε = 0,01` como peso residual máximo;
- `M_α = ⌈ln(ε) / ln(1 − α)⌉` para `0 < α < 1`, e zero para `α = 1`;
- campo receptivo `R = W + H − 1`;
- embargo anterior `E_antes = max(E_gt, R + M_α)`;
- embargo posterior `E_depois = max(E_gt, R)`.

O lado posterior não recebe `M_α` porque Pα é causal. Um candidato de `α` que inviabilize estruturalmente alguma
subdobra será rejeitado por regra anterior à consulta das métricas.

Também foi adicionado um teste que altera, de forma limitada, o prefixo anterior ao embargo e exige que a diferença no
estado do filtro na primeira linha avaliada respeite o limite `ε`, além da tolerância numérica.

## 2. Inicialização de Pα

Antes da primeira predição válida, a saída permanece zero. Ao chegar a primeira predição válida, o filtro é inicializado
diretamente nela (`y'_k = y_k`). A mistura exponencial começa no próximo instante válido. Isso evita o transiente criado
por misturar movimento real com um estado zero artificial.

Pα só é reiniciado na fronteira entre sequências, não em lacunas de GT ou de fontes.

## 3. Orçamento de atualizações

O plano agora declara explicitamente que transportar `optimizer.step()` é uma regra pré-fixada de orçamento, não uma
equivalência entre treinos de tamanhos diferentes. O ótimo pode crescer com mais dados; essa limitação será reportada e
não motivará ajuste depois do teste externo.

## 4. Estado final desta etapa

As decisões estruturais estão fechadas. Permanecem para o protocolo os números já listados na terceira resposta. O
único bloqueio anterior a esse preenchimento é G0: inventário e quantidade de sequências novas com GT.

Nenhum modelo foi executado e nenhum dado externo foi aberto nesta revisão.
