# Roteiro pronto para gravar

Tempo planejado: **8 minutos e 40 segundos**, com margem de 1 minuto e 20 segundos até o limite de dez minutos. Os tempos são referências de ensaio: uma parte mais curta pode encerrar antes. Todos os quatro integrantes devem falar com a própria voz e compreender sua parte.

Este roteiro usa a demonstração atual: aplicativo nativo, editor no próprio painel e relatório HTML. A filmagem é de terceiros, com fonte documentada em [FONTES_MIDIA.md](FONTES_MIDIA.md). A coleta própria e a avaliação independente continuam pendentes. Se o grupo realizou investigação de campo depois desta versão, substituir a explicação do contexto pelos fatos realmente registrados.

## Divisão das quatro partes

| Tempo aproximado | Integrante | Conteúdo | Tela principal |
|---|---|---|---|
| 0:00–1:30 | Vitor Rodi | Integrantes, problema, contexto e objetivo | Capa curta e aplicativo com o estacionamento pausado |
| 1:30–3:10 | Pedro Toigo | Solução, tecnologias, método e contribuição | Marcações, detector.py e app/duplicacao.py |
| 3:10–5:55 | Edson Leandro Soares | Demonstração prática e contribuição | Reprodução, contadores, filtro, histórico, van e editor |
| 5:55–7:10 | Bruno Fell Antunes | Relatório funcionando | Comando de geração, HTML, gráfico e eventos |
| 7:10–8:40 | Bruno Fell Antunes | Resultados, dificuldades, limites e conclusão | Avaliação, GitHub Actions e repositório |

A divisão reserva menos de dois minutos ao problema e à solução, quatro minutos à demonstração e cerca de um minuto e meio aos resultados e à conclusão. A fala deve acompanhar as ações na tela, em linguagem natural.

## Preparação antes de gravar

1. Usar a mesma versão da main nos quatro trechos. Instalar as dependências e ensaiar o aplicativo no computador da gravação.
2. Preparar uma capa de até cinco segundos, dentro do tempo do Vitor: título, disciplina, Unochapecó, professor Wagner Titon e nomes completos dos quatro integrantes.
3. Preparar resultados, aplicativo e relatório, na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe executar_exemplo.py --completo
.\.venv\Scripts\python.exe aplicativo.py --usar-resultados
.\.venv\Scripts\python.exe gerar_relatorio.py --resultados resultados/carpark --saida resultados/carpark/relatorio.html
```

4. Abrir resultados/carpark/relatorio.html no navegador e deixar os arquivos citados e o repositório prontos para alternar.
5. Gravar em orientação horizontal, com microfone testado e texto legível. A captura principal mostra o programa funcionando; uma câmera pequena com o rosto é opcional. A participação verbal dos quatro é obrigatória.
6. Fechar notificações e telas pessoais. Podem gravar quatro clipes e juntar na ordem da tabela, ou usar o mesmo computador com a narração de cada integrante.
7. Ensaiar os cliques do Edson. Para abreviar uma espera de processamento, mostrar o início e o resultado da execução e usar a legenda **“Processamento do vídeo — espera abreviada”**. O corte não representa velocidade medida do algoritmo.

## 1. Vitor — problema e apresentação, 0:00–1:30

**Na tela:** capa por até cinco segundos; depois aplicativo em Monitoramento, com o estacionamento pausado e as regiões visíveis. Colocar uma legenda pequena: “Gravação de terceiros — fonte documentada no repositório”.

**Fala sugerida:**

> Olá, professor. Nosso grupo é formado por Vitor Rodi, Pedro Toigo, Bruno Fell Antunes e Edson Leandro Soares. Este é nosso projeto de Robótica e Visão Computacional: o monitoramento de vagas de estacionamento.
>
> O problema que escolhemos abordar é a dificuldade de visualizar onde existem vagas disponíveis. Em um estacionamento, o motorista pode precisar percorrer os corredores para encontrar um espaço, enquanto quem administra o local também precisa de uma visão da ocupação.
>
> Delimitamos a proposta a partir da análise desse cenário: usar uma imagem com câmera fixa, cadastrar as regiões das vagas e apresentar a disponibilidade de forma centralizada.
>
> Para desenvolver e demonstrar o protótipo, usamos esta gravação de terceiros, cuja fonte está registrada no repositório. A demonstração permite acompanhar o comportamento do programa; a coleta própria e a avaliação em outros estacionamentos são etapas que ainda precisam ser realizadas.
>
> Nosso objetivo é indicar quais regiões estão livres, ocupadas ou precisam de análise. Agora o Pedro vai explicar como a solução foi construída.

Se houve observação ou entrevista realmente feita pelo grupo, inserir local, situação observada e como isso ajudou a definir o problema. Este roteiro não pressupõe pesquisa no campus nem redução de tempo já medida.

## 2. Pedro — solução e método, 1:30–3:10

**Na tela:** aplicativo com as regiões cadastradas; trecho de [detector.py](../detector.py), na função Detector.process; depois cerca de dez segundos de [app/duplicacao.py](../app/duplicacao.py), em duplicate_spaces. Destacar trechos legíveis, sem rolar o arquivo inteiro. Pode usar um esquema: imagem → textura por região → confirmação temporal → estado e contagem.

**Fala sugerida:**

> A solução usa Python, OpenCV e NumPy para processar as imagens. A interface é uma janela nativa feita com PySide6, baseada em Qt.
>
> Primeiro cadastramos as regiões das vagas na imagem. O programa transforma cada quadro em tons de cinza, suaviza a imagem e aplica limiarização adaptativa, filtro de mediana e dilatação. Depois mede a proporção de textura dentro de cada região.
>
> Usamos dois limiares para decidir entre livre e ocupada. No vídeo, uma nova classificação precisa se repetir por cinco quadros antes de ser confirmada. Isso reduz mudanças provocadas por variações muito rápidas.
>
> Esse método não usa uma rede neural treinada e não reconhece semanticamente um carro. O percentual mostrado é um índice de textura, não uma probabilidade de ocupação.
>
> Uma dificuldade foi que muitos carros continuam parados até o final da gravação. Por isso, o último quadro não poderia servir como fundo vazio para todas as vagas. O modo completo usa textura; o experimento anterior por referência vazia também foi preservado.
>
> Na minha contribuição, implementei o serviço de duplicação de vagas, com novos identificadores e validação dos limites da imagem. Também revisei a recuperação de rascunhos para salvar perfis. A duplicação está pronta como serviço e sua ligação aos controles do painel é uma etapa posterior. O Edson vai mostrar o aplicativo funcionando.

## 3. Edson — demonstração prática, 3:10–5:55

**Sequência de ações para ensaiar:**

| Momento aproximado do trecho | Ação | Explicação |
|---|---|---|
| Primeiros 15 s | Mostrar a análise pronta no quadro 60; se mostrar Reprocessar, abreviar apenas a espera com a legenda indicada | 71 regiões: 69 vagas e duas áreas de revisão; 12 livres, 57 ocupadas e 2 em análise |
| Próximos 30 s | Reproduzir o clipe até o fim | Contagem acompanha os estados; final com 15 livres, 54 ocupadas e 2 em análise |
| Próximos 25 s | Pausar, aplicar Somente livres, selecionar V01 e voltar a um evento V03 pelo histórico | Correspondência entre lista, região e quadro da confirmação |
| Próximos 15 s | Selecionar V70 ou V71 e mostrar a van central | Amarelo é análise, fora da disponibilidade |
| Próximos 45 s | Vídeos e vagas → Demonstração · criar uma cópia; nomear o ensaio; escolher Mover / ajustar; selecionar V69, ajustar um canto e Desfazer; usar Conferir neste quadro | Cadastro no mesmo painel, geometria manual e conferência pontual |
| Próximos 20 s | Salvar e analisar, abreviando a espera se preciso; depois Demonstração na lateral | Perfil separado e retorno à análise original |
| Restante | Mostrar brevemente app/rascunhos.py ou sua documentação e passar a fala ao Bruno | Contribuição de persistência e integração futura |

A fala acompanha os cliques. A cópia do mapa usa a mesma filmagem: isso não é uma nova coleta. Adicionar vídeo permite escolher outra gravação e cadastrar seu próprio mapa.

**Fala sugerida:**

> Aqui temos o aplicativo em execução. A demonstração acompanha 71 regiões: 69 vagas cadastradas e duas áreas centrais de revisão. Neste quadro, o detector indica 12 regiões livres, 57 ocupadas e duas em análise.
>
> Vou reproduzir a gravação. Os retângulos e os contadores acompanham os resultados calculados para cada quadro. Ao final, temos 15 livres, 54 ocupadas e duas em análise.
>
> Podemos filtrar as vagas livres, selecionar uma região e voltar a uma alteração pelo histórico. O histórico mostra o quadro em que o classificador confirmou a mudança, que pode diferir do instante da saída física completa do veículo.
>
> Nesta área central, a van atravessa duas regiões. As duas ficam amarelas e o detalhe explica o motivo da análise conjunta. Amarelo não significa vaga disponível.
>
> Para cadastrar um estacionamento, usamos Vídeos e vagas. Vou demonstrar com uma cópia deste mapa: seleciono uma região, ajusto seu canto, desfaço a alteração e confiro a classificação do quadro. Também é possível desenhar retângulos ou marcar quatro pontos. Ao salvar, o programa cria um perfil separado e analisa o mapa escolhido.
>
> Minha contribuição inclui o serviço de rascunhos, com validação, gravação atômica e recuperação dos dados, além dos testes de integração da duplicação com o detector. A recuperação automática ao reabrir o painel ainda precisa ser conectada à interface. Agora o Bruno vai mostrar o relatório dos resultados.

**Conferir durante o ensaio:**

- O clipe incluído mostra saídas de V01, V02 e V03. Para demonstrar uma entrada de carro estacionando, usar uma simulação identificada ou uma coleta própria que contenha essa situação.
- O filtro altera a lista; os contadores continuam cobrindo o mapa inteiro.
- Azul no editor indica cadastro. As cores de classificação aparecem ao conferir o quadro.
- Persistência de rascunhos e duplicação foram entregues como serviços; seus novos controles ainda precisam ser conectados ao painel. O rascunho atual do editor permanece durante a sessão.
- Voltar à demonstração original antes da parte do Bruno: o relatório e a avaliação usarão os resultados com rótulos conferidos. Um novo perfil não herda essa avaliação.

## 4. Bruno — relatório, resultados e conclusão, 5:55–8:40

**Na tela, nesta ordem:**

1. Executar o comando e mostrar a confirmação de gravação:

```powershell
.\.venv\Scripts\python.exe gerar_relatorio.py --resultados resultados/carpark --saida resultados/carpark/relatorio.html
```

2. Abrir o HTML no navegador. Mostrar contagem final, gráfico de evolução e tabela de mudanças de estado. O HTML é um relatório exportado; a interface principal continua sendo o aplicativo nativo.
3. A partir de cerca de 7:10, mostrar a seção de avaliação: 197 amostras, concordância e cobertura.
4. Mostrar brevemente uma execução aprovada no GitHub Actions e o histórico de contribuições. Isso comprova testes de software e participação, sem substituir a demonstração prática.
5. Encerrar com o repositório e os nomes do grupo.

**Fala sugerida:**

> Minha contribuição foi o gerador de relatório HTML. Ele usa os arquivos de ocupação, eventos e resumo, além da avaliação quando ela existe. O relatório funciona sem internet e reúne os resultados em um único arquivo.
>
> Vou executar o comando e abrir a saída. Aqui aparecem as contagens finais, a evolução ao longo da gravação e as mudanças de estado. As confirmações iniciais ficam separadas das alterações posteriores. As regiões em análise não são contadas como vagas disponíveis.
>
> O gerador também confere se os dados estão completos e coerentes antes de criar o relatório. Para um vídeo sem rótulos de avaliação, ele informa Sem avaliação rotulada, em vez de atribuir uma precisão que não foi medida.
>
> Na amostra desta demonstração, temos 197 pares de quadro e região: 185 concordantes, nove indefinidos e três divergentes. Isso representa 93,91% de concordância total e 95,43% de cobertura.
>
> Esses números descrevem somente a amostra deste vídeo, que também foi usado para ajustar o mapa e os parâmetros. Eles não representam uma precisão garantida em outros estacionamentos ou em todos os quadros do clipe.
>
> As principais limitações são sombras, passagem de pessoas, veículos com superfícies lisas e mudanças de iluminação ou enquadramento. No próprio exemplo, a região V55 apresenta falsas mudanças durante passagem de pessoas e sombras. A câmera precisa ficar fixa e cada novo local exige cadastro e conferência.
>
> A versão apresentada também passou por 115 testes automatizados em Windows e Linux. Esses testes verificam o comportamento do software; a validação da visão em campo exige outras gravações e rótulos independentes.
>
> Como próximos passos, queremos realizar uma coleta própria, avaliar outras condições e conectar os serviços de duplicação e recuperação de rascunhos aos controles do editor.
>
> Concluímos que o protótipo permite acompanhar estados de vagas e consultar os resultados de uma gravação de forma organizada. O código, as dependências e as instruções estão neste repositório público. Obrigado.

## Números para as legendas

| Medida | Valor na demonstração |
|---|---:|
| Quadros processados | 679 |
| Duração estimada da fonte | 28,29 s |
| Regiões | 71: 69 vagas e 2 áreas de revisão |
| Decisões de estado | 48.209 |
| Quadro 60: livres / ocupadas / análise | 12 / 57 / 2 |
| Último quadro: livres / ocupadas / análise | 15 / 54 / 2 |
| Amostras rotuladas | 197 |
| Concordantes / indefinidas / divergentes | 185 / 9 / 3 |
| Concordância total / cobertura | 93,91% / 95,43% |
| Testes automatizados de software nesta versão | 115 |

A matriz detalhada e os limites estão em [MAPA_COMPLETO.md](MAPA_COMPLETO.md). O FPS informado pelo vídeo não mede a velocidade do algoritmo; a duração da fonte também não é o tempo de execução.

## Tela final e entrega

Texto sugerido para a tela final:

```text
Monitoramento de vagas de estacionamento
Vitor Rodi · Pedro Toigo · Bruno Fell Antunes · Edson Leandro Soares
Unochapecó — Robótica e Visão Computacional — Wagner Titon
GitHub: github.com/VitorRodi/detector-vagas-estacionamento
```

Depois de editar, conferir duração abaixo de dez minutos, voz audível dos quatro, texto legível, programa funcionando e origem da filmagem identificada. Slides são apoio à demonstração. As afirmações devem corresponder aos dados realmente observados e à versão gravada.

Publicar no YouTube como público ou não listado. Depois, preencher o link verdadeiro no README e em [ENTREGA.md](ENTREGA.md). Testar YouTube e GitHub em janela sem login antes de entregar os dois endereços ao professor.
