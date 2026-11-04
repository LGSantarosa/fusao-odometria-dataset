# Síntese central do projeto de mestrado

**Estado:** formulação de trabalho registrada em 04/11/2026 após o fechamento do teste externo cego. Este documento
explica o projeto para leitores que não acompanharam sua execução e orienta a organização da dissertação e a discussão
com o orientador. Ele não cria nova hipótese experimental nem altera resultados concluídos.

## 1. O projeto em poucas palavras

Um robô pode estimar seu movimento de várias maneiras. Uma câmera acompanha elementos visuais; um LiDAR compara a
geometria de nuvens de pontos; uma IMU mede acelerações e rotações. Cada método funciona bem em algumas condições e
mal em outras. A câmera pode perder rastreamento por falta de textura ou iluminação; o LiDAR pode encontrar pouca
geometria útil; a IMU pode ficar indisponível ou acumular erro.

O objetivo deste mestrado é investigar se essas estimativas podem ser combinadas para produzir uma odometria mais
confiável. Em vez de depender de uma única fonte, o sistema recebe quatro estimativas de movimento e tenta decidir
como aproveitá-las ao longo do tempo.

Foram estudadas quatro fontes de odometria:

- **ORB-SLAM3**, baseada principalmente em imagens;
- **Stella VSLAM**, também baseada em imagens;
- **FAST-LIO2**, que combina LiDAR e IMU;
- **KISS-ICP**, baseada em LiDAR.

O projeto comparou desde soluções simples, como calcular a média das fontes disponíveis, até redes neurais capazes de
usar uma pequena janela do histórico. A pergunta não era apenas “qual modelo produz o menor número?”, mas se uma
solução aprendida continuaria funcionando em sequências e dias que não participaram do desenvolvimento.

## 2. Tese central

> Em ambientes naturais, a fusão causal de odometrias heterogêneas exige mais do que aumentar a complexidade do
> modelo. Embora modelos aprendidos possam apresentar ganhos durante o desenvolvimento, esses ganhos podem não se
> repetir em outros dias. Baselines simples e clássicos, avaliados por um pipeline cego e reproduzível, são essenciais
> para distinguir uma melhoria que realmente se generaliza de um resultado ajustado às sequências conhecidas.

“Baselines” são métodos de referência contra os quais uma solução nova precisa ser comparada. Neste trabalho, eles
incluem a média simples e o filtro de Kalman; não são adversários artificiais feitos apenas para a rede vencer.

Em linguagem direta: uma rede neural mais sofisticada não é automaticamente uma solução melhor. Neste projeto, as
redes aprenderam padrões úteis nos dados usados durante o desenvolvimento, mas a principal vantagem observada nessa
fase desapareceu quando os modelos foram avaliados em dias externos.

## 3. O que significa “fusão causal”

“Fusão” é a combinação das estimativas das diferentes odometrias. “Causal” significa que, em cada instante, o sistema
só pode usar informações disponíveis naquele instante ou no passado. Ele não pode consultar medições futuras para
melhorar uma decisão anterior.

Essa restrição é importante porque o objetivo é representar uma situação real de navegação. Um método que usa o
futuro pode ser útil para corrigir uma trajetória depois da missão, mas não pode ser executado da mesma forma por um
robô que precisa decidir enquanto se movimenta.

O pipeline registra, para cada fonte:

- a velocidade estimada;
- se a estimativa está válida;
- há quanto tempo ela foi produzida;
- o intervalo temporal usado para calculá-la;
- indicadores de rastreamento e qualidade disponíveis.

Assim, os modelos não recebem apenas as velocidades das quatro fontes. Eles também recebem informações que permitem
identificar quando uma fonte está atrasada, indisponível ou possivelmente degradada.

## 4. O que foi construído

### 4.1 Pipeline de dados

Foi construído um pipeline que executa as quatro odometrias, sincroniza suas saídas e produz uma tabela comum. O
pipeline possui contratos automáticos para conferir timestamps, frames, tipos de coluna, validade e ausência de dados
indevidos.

O *ground truth* (GT) é a referência usada para saber qual era o movimento real do robô. Ele é necessário para medir
os erros, mas não pode entrar como informação dos modelos. O projeto separa explicitamente:

- **features:** informações que o modelo pode usar;
- **alvos:** movimento de referência usado durante o treinamento;
- **avaliação:** erros calculados somente depois das predições.

Essa separação reduz o risco de vazamento, isto é, de o resultado parecer bom porque alguma informação do GT chegou
indevidamente ao treinamento ou à seleção do modelo.

### 4.2 Estratégias comparadas

Foram comparadas estratégias de complexidade crescente:

- **B5/T1 — média causal:** média das fontes válidas naquele instante;
- **T2 — filtro de Kalman:** filtro clássico que combina as medições usando um modelo de persistência da velocidade e
  estimativas de incerteza;
- **STEP:** rede que calcula pesos para as fontes usando apenas o instante atual;
- **MLP-W:** rede que recebe uma janela curta do histórico;
- **CNN-W:** rede convolucional causal que procura padrões temporais nessa janela.

Também foi considerada uma LSTM durante a seleção. A CNN foi escolhida como representante temporal porque obteve
desempenho próximo com menos parâmetros, conforme uma regra definida antes do teste externo.

## 5. Como evitamos escolher o resultado depois de vê-lo

O estudo separou os dados em dois papéis.

### Desenvolvimento

As sequências `1018-00` e `1018-13` foram usadas para implementar, treinar e escolher configurações. Nelas foram
definidos a janela temporal, os modelos, seus tamanhos, os orçamentos de treinamento e os parâmetros do Kalman.

Essas duas sequências eram conhecidas. Por isso, seus resultados servem para desenvolvimento, mas não são evidência
independente de generalização.

### Teste externo

O teste usou oito outras sequências, pertencentes aos dias 1005, 1006 e 1008. Antes de consultar seus GTs:

1. o código e as configurações foram congelados;
2. os modelos foram treinados apenas nos dados de desenvolvimento;
3. os pesos foram salvos e protegidos por hashes;
4. as oito sequências foram processadas sem acesso ao GT;
5. as predições foram gravadas e auditadas;
6. somente depois disso os oito GTs foram abertos uma única vez.

Um hash funciona como uma impressão digital do arquivo. Se qualquer peso, configuração, feature ou predição fosse
alterado depois do congelamento, a verificação detectaria a mudança.

Esse procedimento cego impede que alguém veja o resultado externo e, em seguida, ajuste o modelo, escolha outra
semente ou troque a métrica até obter uma conclusão favorável.

## 6. O que esperávamos encontrar

A pergunta inicial era ampla: um modelo temporal deveria superar a média simples e o modelo por passo nos erros de
velocidade linear e angular, sem degradar a trajetória.

Antes do teste externo, um gate de viabilidade mostrou que essa hipótese original já não era compatível com os dados
de desenvolvimento. A CNN perdeu para o modelo STEP nas duas métricas e perdeu para a média simples no erro linear.
Esse resultado foi registrado como negativo, sem alterar os números.

Ainda no desenvolvimento, apareceu um padrão mais específico: a CNN reduzia consideravelmente o erro angular contra
a média simples. Antes de processar as sequências externas, esse padrão originou uma hipótese mais estreita, chamada
H1':

> A CNN selecionada reduz o erro de velocidade angular em relação à média simples nas sequências externas.

A origem dessa hipótese foi declarada: ela foi formulada depois de observar o desenvolvimento, mas antes de consultar
qualquer resultado das oito sequências externas.

## 7. Como o resultado foi medido

O principal número foi o RMSE, uma medida que resume a magnitude típica do erro. Quanto menor, melhor.

Foram calculados:

- **RMSE linear**, em metros por segundo: erro na velocidade de translação;
- **RMSE angular**, em radianos por segundo: erro na velocidade de rotação;
- **RPE de 10 m**, em metros: quanto a trajetória deriva localmente ao longo de deslocamentos de 10 metros;
- **ATE**, em metros: diferença global entre a trajetória estimada e a trajetória de referência.

As redes foram treinadas com cinco sementes. Uma semente controla a inicialização aleatória do treinamento. Usar cinco
sementes ajuda a verificar se o resultado depende de uma inicialização especialmente favorável. Para cada sequência,
foi calculada a métrica de cada semente e depois usada a média dessas cinco métricas.

A H1' só seria considerada positiva se a CNN tivesse melhora angular mediana:

- no conjunto das oito sequências; e
- separadamente nos dias 1005, 1006 e 1008.

Não bastava ganhar em uma sequência isolada ou compensar um dia ruim com outro dia bom.

A mediana é o valor central depois de ordenar os resultados. Ela reduz a influência de uma única sequência muito boa
ou muito ruim, mas não transforma as oito sequências em observações independentes.

## 8. Resultado principal

A H1' foi **negativa**.

- A CNN teve erro angular menor que a média simples em apenas **1 das 8 sequências**.
- Considerando as oito sequências, seu erro angular foi **3,63% maior em mediana**.
- As medianas dos três dias também foram desfavoráveis à CNN.
- O erro linear da CNN foi **1,92% maior em mediana**.
- A deriva translacional de 10 m foi **14,15% maior em mediana**.

Portanto, não ocorreu uma situação em que a CNN melhorou a rotação ao custo de uma pequena piora na translação. No
teste externo, a melhora angular observada durante o desenvolvimento também desapareceu.

Isso não significa que redes neurais nunca funcionem para fusão de odometrias. Significa que, com os modelos, dados,
configurações e ambiente deste estudo, a CNN selecionada não demonstrou a generalização esperada.

## 9. Por que o resultado negativo é importante

Durante o desenvolvimento, a CNN havia reduzido o erro angular contra a média em aproximadamente 20,0% e 11,3% nas
duas dobras. Se o trabalho terminasse nessa etapa, seria possível concluir incorretamente que o histórico aprendido
produzia uma melhoria robusta.

O teste externo mostrou o contrário. A vantagem não se repetiu nos outros dias. Isso evidencia a diferença entre:

- **ajustar-se às sequências conhecidas**; e
- **generalizar para sequências que não influenciaram as escolhas do modelo**.

O resultado negativo, portanto, não representa uma falha do projeto. Ele é uma descoberta produzida pelo desenho
experimental. O processamento cego cumpriu exatamente sua função: impedir que um padrão promissor, porém restrito ao
desenvolvimento, fosse apresentado como conclusão geral.

## 10. O que aconteceu com o Kalman

Em uma comparação descritiva, o T2/Kalman apresentou erro angular menor que a média simples nas oito sequências
externas, com redução relativa mediana de 6,88%. Ao mesmo tempo, seu erro linear foi 2,15% maior e seu RPE de 10 m foi
8,08% maior em mediana.

A formulação correta é:

> Descritivamente, o filtro de Kalman apresentou menor erro angular que a média simples nas oito sequências externas,
> indicando uma direção promissora, mas ainda não confirmatória.

Esse cuidado é necessário porque a superioridade do Kalman não foi registrada como hipótese antes da abertura. Depois
de ver o teste, não é cientificamente correto transformar o modelo que apresentou o padrão mais interessante em novo
“vencedor confirmatório”. Para testar essa possibilidade, seriam necessários novo protocolo e dados independentes.

## 11. Contribuições do mestrado

### Contribuição técnica

Um pipeline causal, verificável e reproduzível para combinar odometrias visuais, LiDAR e LiDAR-inerciais, incluindo
disponibilidade e indicadores de qualidade das fontes.

### Contribuição experimental

Uma comparação controlada entre média simples, filtragem clássica e modelos aprendidos, com separação entre
desenvolvimento e teste, cinco sementes, congelamento de artefatos e abertura única dos GTs.

### Contribuição científica

Evidência de que aumentar a complexidade e usar histórico aprendido não garantiu generalização entre dias nas
condições estudadas. O trabalho mostra também que baselines simples e clássicos precisam ser tratados como
comparadores fortes, e não como referências fáceis de superar.

## 12. Narrativa da dissertação

A dissertação não precisa ser organizada como “uma rede foi treinada e venceu os baselines”. A narrativa mais fiel e
mais interessante é:

> Foi construída uma forma rigorosa de investigar fusão de odometrias heterogêneas e verificou-se que o aumento de
> complexidade aprendida não garantiu generalização entre dias nas condições estudadas.

O projeto reúne engenharia, metodologia experimental e evidência científica. Ele não entrega apenas um modelo: entrega
um processo capaz de mostrar quando uma melhoria aparente não resiste a uma avaliação externa.

## 13. Alcance e limitações

A conclusão vale para:

- as quatro fontes, os modelos e as configurações avaliados;
- as sequências utilizadas do BotanicGarden;
- os três dias externos estudados;
- a mesma plataforma, o mesmo ambiente e as métricas registradas.

Ela não permite concluir que:

- toda fusão aprendida é inferior;
- o Kalman é sempre melhor;
- os resultados se repetirão em qualquer ambiente ou robô;
- as oito sequências representam oito condições completamente independentes, pois pertencem a apenas três dias.

Outra limitação é que cada odometria visual teve uma realização oficial por sequência externa. As cinco sementes
medem a variabilidade do treinamento das redes, mas não a variabilidade de reexecutar as fontes visuais.

## 14. Decisão ainda necessária para o mestrado

O núcleo experimental está concluído e fornece uma resposta clara à pergunta testada. A próxima decisão, a ser tomada
com o orientador, é se esse conjunto já é suficiente para a defesa ou se alguma validação adicional é obrigatória.

Um novo experimento só deve ser realizado se responder a uma lacuna real da dissertação. Ele não deve servir para
substituir, corrigir ou procurar um resultado mais favorável que o teste externo já obtido. Possíveis extensões — como
testar novamente o Kalman, separar explicitamente translação e rotação ou avaliar outro ambiente — devem usar novo
protocolo e dados independentes, ou ser apresentadas como trabalhos futuros.
