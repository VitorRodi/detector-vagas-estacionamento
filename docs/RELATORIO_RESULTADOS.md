# Relatório de resultados

`gerar_relatorio.py` transforma uma pasta de resultados do detector em **um único
arquivo HTML** que funciona sem internet. O documento reúne método, quadros,
duração, regiões, contagens finais, evolução das contagens, mudanças de estado,
confirmações iniciais e, quando existir, a avaliação com rótulos (issue #20).

O gerador usa somente a biblioteca padrão do Python: não depende de OpenCV, Qt
ou NumPy e não acrescenta dependências. Ele apenas lê os arquivos de entrada e
não abre o navegador. A integração de um botão no aplicativo será feita depois.

## Gerar o relatório

Primeiro produza uma análise completa, por exemplo com o mapa de 71 regiões:

```powershell
.\.venv\Scripts\python.exe executar_exemplo.py --completo
.\.venv\Scripts\python.exe gerar_relatorio.py --resultados resultados/carpark --saida resultados/relatorio.html
```

Em Linux, use `.venv/bin/python`. Abra `resultados/relatorio.html` em qualquer
navegador; o arquivo pode ser copiado, enviado ou impresso sem a pasta original.
A pasta `resultados/` é ignorada pelo Git, então o relatório não é versionado.

| Opção | Uso |
| --- | --- |
| `--resultados` | Obrigatória. Pasta com `ocupacao.csv`, `eventos.csv` e `resumo.json`. |
| `--saida` | Arquivo `.html` a gerar. Padrão: `resultados/relatorio.html`. A pasta é criada se necessário. |

O comando termina com código 0 e informa o arquivo gravado. Se a análise for
rejeitada, termina com código 1, explica o motivo e não grava nada. Um relatório
anterior no mesmo caminho é preservado nesse caso: confira a mensagem antes de
apresentar um arquivo antigo. A gravação é atômica (arquivo temporário na mesma
pasta, seguido de substituição), de modo que uma falha não deixa HTML pela metade.

Com os resultados do vídeo de demonstração, a geração leva cerca de 0,1 s e o
arquivo tem aproximadamente 23 KB.

## Uso em código

```python
from gerar_relatorio import generate_report, write_report

html = generate_report('resultados/carpark')   # valida e retorna o HTML, sem gravar
destino = write_report('resultados/carpark', 'resultados/relatorio.html')
```

- `generate_report(pasta)`: função testável principal. Retorna o documento como
  texto. É determinística: as mesmas entradas produzem exatamente o mesmo HTML.
- `write_report(pasta, saida)`: valida, gera e grava; retorna o `Path` gravado.
  Exige extensão `.html` ou `.htm`.
- `load_results(pasta)` e `render_report(resultados)`: separam leitura e
  validação da montagem do HTML, caso o painel queira exibir dados validados.

Todas levantam `ValueError` com mensagem em português quando a pasta está
incompleta, interrompida ou inconsistente; falhas do sistema de arquivos chegam
como `OSError`. O futuro botão do painel deve tratar as duas exceções e exibir a
mensagem ao usuário.

## Arquivos lidos

| Arquivo | Obrigatório | Uso |
| --- | --- | --- |
| `resumo.json` | Sim | Método, fonte, quadros, FPS, duração, regiões, contagem final, eventos e interrupção. |
| `ocupacao.csv` | Sim | Estado de cada região em cada quadro; base da evolução e das transições. |
| `eventos.csv` | Sim | Conferido contra as transições observadas em `ocupacao.csv`. |
| `avaliacao.json` | Não | Métricas exibidas como estão no arquivo, somente as presentes. |

Os demais arquivos da pasta (`ultimo_quadro.png`, `video_anotado.mp4`) não são
lidos. Nenhum arquivo de entrada é criado, alterado ou removido.

## Conferências antes de gerar

O relatório só é produzido se todas as condições abaixo forem atendidas:

1. `resumo.json` existe, é JSON válido sem campos duplicados nem `NaN`, e tem
   `interrompido_pelo_usuario: false`. Execuções interrompidas são rejeitadas.
   Como o detector apaga o resumo ao iniciar e só o grava ao terminar, um resumo
   ausente indica análise inacabada ou invalidada.
2. Método `texture` ou `reference`; fonte `video`, `camera` ou `imagem`; FPS
   positivo e duração igual a quadros ÷ FPS (imagem: um quadro, sem FPS nem duração).
3. `ocupacao.csv` tem o cabeçalho do método informado (`densidade_textura` ou
   `fracao_alterada`, seguido de `motivo`) e exatamente seis campos por linha.
4. Os quadros aparecem em blocos consecutivos de 0 até o último informado no
   resumo, sem lacunas, inversões ou quadros extras.
5. Cada quadro contém exatamente as mesmas regiões do quadro 0, sem repetição, e
   o total de regiões coincide com `vagas_monitoradas`.
6. Estados válidos (`livre`, `ocupada`, `indefinida`), medida finita entre 0 e 1
   e `tempo_video_s` compatível com quadro ÷ FPS.
7. `eventos.csv` contém exatamente as transições observadas em `ocupacao.csv`,
   nem mais nem menos, e o total coincide com `eventos_confirmados`.
8. A contagem do último quadro coincide com `contagem_final` do resumo.
9. Se existir, `avaliacao.json` deve ter métricas reconhecidas com tipos válidos
   e coerência interna: definidas + indefinidas = amostras, matriz somando as
   definidas e cobertura igual a definidas ÷ amostras, quando esses campos existem.

As mensagens de erro citam o arquivo e a linha, por exemplo:
`ocupacao.csv: o quadro 7 não contém todas as regiões (1 ausente(s))`.

## Como interpretar

**Resumo da análise.** Método, fonte, quadros processados, regiões monitoradas,
decisões registradas (quadros × regiões) e eventos. A **duração estimada da
fonte** é quadros ÷ FPS informado pela fonte; em câmera, esse FPS pode diferir do
real. O tempo de execução do resumo não aparece, porque inclui exportação e
eventual exibição e não mede o algoritmo isoladamente.

**Contagem final.** Estados do último quadro. **Somente regiões livres contam
como vagas disponíveis**: regiões em análise não foram confirmadas como livres
nem como ocupadas e ficam fora dessa conta. O relatório lista as regiões em
análise com o motivo gravado pelo detector ou, sem motivo, informa se a região
nunca foi confirmada ou se aguardava a confirmação de um novo estado. O texto
fala em regiões porque o resumo não distingue vagas de áreas de revisão conjunta.

**Evolução das contagens.** Calculada quadro a quadro a partir de
`ocupacao.csv`, sem amostragem. O gráfico SVG mostra as três contagens em degraus
sobre o tempo do vídeo, com eixo vertical de zero ao total de regiões, legenda e
rótulos finais. Ao passar o mouse sobre o gráfico, o navegador mostra o intervalo
e as três contagens. A tabela logo abaixo traz os mesmos valores em intervalos de
quadros consecutivos com contagens constantes.

**Mudanças de estado e confirmações iniciais.** Todas as regiões começam em
análise. A **confirmação inicial** é o primeiro evento de cada região, quando ela
deixa esse estado inicial. As **mudanças de estado** são todos os eventos
seguintes, inclusive entradas e saídas de Em análise causadas pela revisão
conjunta. As duas seções ficam separadas para que a inicialização não pareça
movimento no estacionamento. Regiões que nunca deixaram Em análise aparecem como
"sem confirmação em toda a análise".

**Avaliação.** Com `avaliacao.json`, o relatório mostra somente as métricas
presentes no arquivo, sem recalcular nada, e explica que elas comparam o detector
com os rótulos fornecidos para aquela análise. Valores `null` aparecem como "Não
calculada". Sem o arquivo, a seção mostra **Sem avaliação rotulada** e nenhuma
medida de acerto. Uma pasta processada somente com `detector.py`, sem
`avaliar.py`, cai nesse caso.

**Conferências e limites.** Resume as verificações aprovadas e os limites da
interpretação.

### Exemplo com o vídeo de demonstração

Com `executar_exemplo.py --completo`, o relatório apresenta: textura, 679 quadros,
28,29 s estimados a 24 FPS, 71 regiões e 48.209 decisões. A contagem final é de
15 livres, 54 ocupadas e 2 em análise (V70 e V71, possível ocupação de duas vagas
pelo mesmo veículo); portanto, 15 vagas disponíveis confirmadas. Dos 76 eventos,
69 são confirmações iniciais no quadro 4 e 7 são mudanças de estado (V01, V02,
V03 e quatro alternâncias da V55). V70 e V71 nunca recebem estado confirmado. A
avaliação mostra 197 pares rotulados, 95,43% de cobertura e 93,91% de
concordância total. Esses números descrevem o mesmo clipe usado para calibrar
regiões e limiares e não comprovam precisão em outros estacionamentos.

## Segurança e portabilidade

- Todo texto vindo dos arquivos (identificadores, motivos, nota da avaliação e
  nome da pasta) é escapado antes de entrar no HTML.
- O documento não contém scripts, imagens, fontes, folhas de estilo ou links
  externos. Os estilos ficam em um único bloco `<style>`, e uma política
  `Content-Security-Policy` com `default-src 'none'` bloqueia carregamentos.
- Nenhum caminho absoluto é gravado: a pasta aparece apenas pelo nome final
  (por exemplo, `carpark`).
- As fontes Sora e Manrope são usadas se estiverem instaladas; caso contrário, o
  navegador usa as fontes do sistema. Não há incorporação de arquivos de fonte.
- As cores seguem o sistema visual do aplicativo. No gráfico, os tons das linhas
  foram ajustados e conferidos para daltonismo; a identificação também usa
  legenda, rótulos de texto e a tabela, sem depender só da cor.
- O layout se adapta a telas estreitas e possui estilo de impressão.

## Limitações

- O relatório não compara os quadros com o vídeo original. Para a demonstração,
  `executar_exemplo.py` confere os 679 quadros esperados; em outras fontes, uma
  leitura encerrada antes do fim sem interrupção do usuário não é detectável aqui.
- A avaliação não é recalculada a partir dos rótulos; apenas tipos e coerência
  interna são conferidos.
- Aceita o formato atual do detector (`metodo` no resumo e coluna `motivo`).
  Pastas geradas por versões antigas precisam ser reprocessadas.
- Para manter o arquivo leve, as tabelas exibem até 200 intervalos, 500 mudanças
  e 100 regiões por lista, avisando quando há mais. O gráfico considera todos os
  quadros, agrupando degraus menores que meio pixel. Os CSVs continuam sendo a
  fonte completa.
- Motivos e notas aparecem como estão nos arquivos, apenas escapados.
- Não há modo escuro nem ícones de estado; os estados combinam texto e cor.

## Testes

`tests/test_relatorio.py` cria pequenas pastas reais com CSVs e JSONs no formato
do detector, sem mocks, e cobre: relatório com e sem avaliação, métricas parciais
e nulas, regiões em análise fora das vagas disponíveis, separação entre mudanças
e confirmações iniciais, evolução calculada dos dados, 28 casos de arquivos
incompletos ou inconsistentes, análise interrompida pela função e pelo comando,
identificadores e textos com HTML, ausência de recursos externos e de caminhos
locais, preservação dos arquivos de entrada e do relatório anterior. Um teste
ponta a ponta executa `detector.py`, `avaliar.py` e `gerar_relatorio.py` em um
vídeo sintético; ele é ignorado se o OpenCV não estiver instalado.

```console
python -m unittest discover -s tests -v
```
