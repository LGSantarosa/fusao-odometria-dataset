# Resultados do piloto formal — fase 3

**Data:** 03/11/2026. **Código executado:** commit
`aaae00d7461b0c7ac612b5806f06151a4e223bd7`. **Escopo:** somente as sequências de desenvolvimento `1018-00` e
`1018-13`, em LOSO D-A/D-B, conforme `docs/amendment_phase3_pilot.md`. O teste externo permaneceu lacrado e não foi
processado (`external_test_authorized: false`).

## 1. Integridade e completude

O manifesto foi criado com a árvore Git limpa e registra o mesmo commit executado. Antes do T2, o executor voltou a
conferir a árvore limpa e a igualdade entre o manifesto e o `HEAD`; o T2 terminou normalmente às 15:55:56-03:00.

- `alpha.json`, `window.json`, `grid.json` e `t2.json` são JSONs válidos e foram gravados atomicamente;
- a grade contém 72 configurações, 432 jobs internos, 432 jobs finais e 144 orçamentos de dobra;
- nenhuma execução interna ou final falhou, nenhum orçamento ficou ausente e nenhuma perda agregada ficou nula;
- na grade, 50 de 2.160 subexecuções internas foram marcadas como saturadas porque o melhor checkpoint foi o teto de
  8.000 atualizações; na seleção de `W`, 1 de 90 subexecuções foi marcada como saturada. O teto não foi ampliado;
- os orçamentos agregados da grade variaram de 50 a 5.800 atualizações;
- o T2 contém as 15 combinações previstas e 30 resultados por dobra, todos com perda finita.

## 2. Parâmetros congelados antes da grade

### Pα

| α | Perda LOSO média |
|---:|---:|
| 0,1 | 0,837364 |
| 0,2 | 0,729613 |
| 0,3 | 0,648934 |
| 0,5 | 0,524989 |
| 0,7 | 0,438679 |
| 1,0 | 0,395738 |

**Escolha:** `α = 1,0`. Foi a menor perda e, portanto, também satisfaz a regra de empate que favorece o maior α dentro
de 1% do mínimo.

### Janela

A MLP-W de referência usou largura 32, uma camada e `weight_decay = 1e-3`.

| W | Perda LOSO média |
|---:|---:|
| 5 | 0,381031 |
| 10 | 0,411238 |
| 20 | 0,393124 |

**Escolha:** `W = 5`. Foi a menor perda e também a menor janela elegível pela regra de empate.

## 3. Grade de modelos

A tabela mostra a configuração selecionada em cada família depois de aplicar a regra pré-fixada: perda até 1% do
mínimo da família e, entre as elegíveis, menos parâmetros. Os orçamentos A/B são as medianas arredondadas para cima das
subdobras e sementes.

| Família | Configuração selecionada | W | Perda | Parâmetros | Orçamento A/B |
|---|---|---:|---:|---:|---:|
| STEP | largura 32, 1 camada, `weight_decay = 1e-2` | 1 | 0,350675 | 1.956 | 3.800 / 2.800 |
| MLP-W | largura 64, 1 camada, `weight_decay = 1e-3` | 5 | 0,364851 | 18.244 | 600 / 400 |
| CNN-W | 16 canais, 1 camada, kernel 3, `weight_decay = 1e-2` | 5 | 0,362930 | 2.772 | 2.000 / 1.600 |
| LSTM-W | oculto 32, 1 camada, `weight_decay = 1e-2` | 5 | 0,359634 | 11.652 | 1.000 / 1.000 |

As escolhas de STEP, CNN e LSTM não são necessariamente os mínimos brutos: configurações menores ficaram dentro de 1%
e venceram pelo desempate de complexidade. A MLP-W selecionada coincide com seu mínimo bruto.

**Escolha temporal:** CNN-W. A perda selecionada da CNN (0,362930) está dentro de 1% da perda selecionada da LSTM
(0,359634), e a CNN tem 2.772 parâmetros contra 11.652 da LSTM. Assim, a CNN vence exatamente pelo desempate
pré-fixado de menor número de parâmetros.

## 4. T2

O mínimo bruto da grade foi `q_scale = 3`, `r_scale = 1`, com perda 0,403630. A configuração escolhida foi
`q_scale = 1`, `r_scale = 0,3`, com perda 0,403675: ela está dentro de 1% do mínimo e vence pela regra pré-fixada de
escalas mais próximas de 1 (`|log10 q|` e depois `|log10 r|`).

## 5. Interrupção operacional

O piloto formal sofreu uma interrupção operacional por queda de energia por volta das 10:22 de 03/11/2026. Os
artefatos atômicos `alpha.json` (α = 1,0) e `window.json` (W = 5), já concluídos antes da interrupção, foram preservados.
A grade de modelos não havia produzido artefato final; seus resultados parciais (4/432 jobs internos, só em memória) não
foram reaproveitados, e a etapa foi reiniciada integralmente às 10:35:12, com o mesmo commit (`aaae00d`) e manifesto. O
T2 ainda não havia começado. O marcador correspondente está em
`data/analysis/model_comparison/formal_phase3/grid.log`, linha 41.

## 6. Artefatos e hashes

Os artefatos brutos permanecem sob `data/analysis/model_comparison/formal_phase3/` e são ignorados pelo Git. Estes
SHA-256 vinculam o relatório aos arquivos produzidos:

| Artefato | SHA-256 |
|---|---|
| `manifest.json` | `1efa97eed47dcbccd8a2a171e4b6a06be1af81ea3898d7ebbae6585ef889af37` |
| `alpha.json` | `fa851735c942245d88dae63fba0db6d707b5e856c54827738c6b6e5d50837005` |
| `window.json` | `f7c51c879a03f07b0230bc51f2705d28417bd02161430b84d23442ec7d664028` |
| `grid.json` | `3677c06f1c66970350df20777483dd67cdbefb5657874be6c0704139eedbd9b9` |
| `t2.json` | `012230c7ef7fafd46ba362e430ad161a23a7cace3f0e4953028c1d929240ea18` |
| `grid.log` | `d11363eab6bfd922a909d3a247ded71965ce34ed21d460cacdff148f046ab803` |
| `t2.log` | `0565d2f858f2976060e4de3c1ca76f1ac8f68e025b40cbcb5989a0dd706bb1e6` |

## 7. Alcance da conclusão

Este piloto fixa `α`, `W`, as configurações por família, a escolha temporal e as escalas do T2 para as etapas seguintes.
Os números são exploratórios, pois foram obtidos apenas nas duas sequências de desenvolvimento já vistas. Eles não são
evidência confirmatória e não autorizam a abertura ou o processamento das oito sequências externas.
