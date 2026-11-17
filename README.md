# Monitoramento de vagas de estacionamento

[![Testes do projeto](https://github.com/VitorRodi/detector-vagas-estacionamento/actions/workflows/testes.yml/badge.svg)](https://github.com/VitorRodi/detector-vagas-estacionamento/actions/workflows/testes.yml)

Projeto acadêmico de Robótica e Visão Computacional da Unochapecó, docente Wagner Titon. Grupo: Vitor Rodi, Pedro Toigo, Bruno Fell Antunes e Edson Leandro Soares.

## Problema e situação atual

A proposta é facilitar a consulta à disponibilidade de vagas a partir de uma câmera fixa. O aplicativo apresenta uma gravação de terceiros com **71 regiões cadastradas: 69 vagas e duas áreas centrais de ocupação ambígua**, cada uma com um retângulo, identificador e estado. Ilhas, corredores e regiões fora do enquadramento ficam fora da contagem. A van central é acompanhada por duas regiões que ficam em análise quando um objeto claro atravessa ambas.

![Aplicativo com as 71 regiões marcadas](assets/aplicativo.png)

A demonstração está implementada, mas a investigação de campo, as gravações próprias e a avaliação em vídeos independentes ainda precisam ser realizadas. Não foi medida redução de tempo de procura. O vídeo final do grupo ainda precisa ser gravado e publicado no YouTube, com participação verbal dos quatro integrantes e duração de até dez minutos.

## Abrir o aplicativo no Windows

Com Python 3.10 ou mais recente instalado, extraia o projeto e dê dois cliques em **[INICIAR_APLICATIVO.bat](INICIAR_APLICATIVO.bat)**. O iniciador cria `.venv` e instala as dependências se necessário; essa primeira instalação precisa de internet. Aguarde o processamento dos 679 quadros e clique em **Reproduzir**. Depois da instalação, a demonstração funciona com os arquivos locais, sem internet.

Alternativa pelo terminal na raiz do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
.\.venv\Scripts\python.exe aplicativo.py
```

Para abrir uma análise completa já salva, use:

```powershell
.\.venv\Scripts\python.exe aplicativo.py --usar-resultados
```

A janela oferece contadores sincronizados, filtros, seleção de vagas pelo vídeo ou pela lista com rolagem, histórico, busca, velocidade, tela cheia e exportação ZIP. As marcações usam verde para livre, vermelho para ocupada e amarelo para em análise. No mapa completo, as etiquetas ficam compactas; a vaga selecionada mostra seu estado por extenso.

Para usar outra gravação, abra **Vídeos e vagas → Adicionar vídeo**, desenhe as vagas com o mouse e clique em **Salvar e analisar**. O editor ocupa o próprio painel principal. Retângulos, quatro pontos, movimento dos cantos, exclusão, desfazer e perfis salvos permitem preparar outro estacionamento sem editar código. O cadastro é manual e exige câmera fixa e conferência da detecção. Veja [o guia do editor](docs/EDITOR_DE_VAGAS.md).

**Apresentar** ou F11 abre a tela cheia. Esc sai da tela cheia; no monitoramento normal, pausa a reprodução; no editor, cancela o gesto atual. O filtro altera somente a lista: os contadores continuam incluindo as 71 regiões na demonstração. Veja [o guia do aplicativo](docs/APLICATIVO.md).

## Tecnologias e funcionamento

Python, NumPy e OpenCV fazem o processamento; PySide6/Qt implementa a janela nativa. Não há rede neural, treinamento ou pesos externos. Há dois experimentos:

| Modo | Regiões | Medida | Execução |
|---|---:|---|---|
| Mapa completo, padrão do aplicativo | 71 regiões | Densidade de textura dentro de cada vaga | `executar_exemplo.py --completo` |
| Experimento anterior por referência | 5 | Fração de pixels diferentes de uma referência vazia | `executar_exemplo.py` |

No mapa completo, o vídeo não contém um quadro em que todas as vagas estejam vazias. Comparar todas as regiões com o último quadro faria carros parados parecerem vagas livres. Por isso, o modo completo usa tons de cinza, suavização, limiarização adaptativa, mediana e dilatação para medir textura. Dois limiares e cinco quadros consecutivos confirmam o estado. Essa heurística depende do enquadramento e pode confundir pedestres, sombras, marcas do piso e veículos com pouca textura.

As regiões e os parâmetros foram escolhidos no mesmo clipe usado para avaliar. Os resultados são exploratórios e **não demonstram precisão em outros estacionamentos**. O índice de textura não é probabilidade de ocupação. A técnica por referência vazia continua disponível e exige que todas as regiões nela cadastradas estejam vazias na referência.

## Executar sem a interface

Instale `requirements.txt` para usar somente os programas OpenCV. Com as dependências instaladas:

```powershell
.\.venv\Scripts\python.exe executar_exemplo.py --completo
.\.venv\Scripts\python.exe executar_exemplo.py --completo --show
```

A segunda opção abre a janela simples do OpenCV: espaço pausa e Q/Esc encerra. Para demonstrar a interface completa, use `aplicativo.py`.

Para repetir o experimento anterior de cinco regiões em outra pasta de saída:

```powershell
.\.venv\Scripts\python.exe executar_exemplo.py --output resultados/referencia
```

Em Linux, crie o ambiente com `python3 -m venv .venv` e use `.venv/bin/python`. A janela precisa de sessão gráfica; no Ubuntu, instale também `libegl1`. O modo completo sem `--show` não abre janela.

## Dados, mapa e resultados

O arquivo [carPark.mp4](dados/terceiros/carPark.mp4) contém 679 quadros, 24 FPS, resolução de 1100 × 720 e duração aproximada de 28,29 segundos. Foi obtido do repositório de [Harsh Bafna](https://github.com/harshbafnaa/car-parking-detection). A fonte, a declaração de licença disponível, a revisão e os limites de atribuição estão em [FONTES_MIDIA.md](docs/FONTES_MIDIA.md).

O mapa está em [vagas_completas_carpark.json](dados/terceiros/vagas_completas_carpark.json). São seis colunas de regiões; os identificadores V01–V05 preservam as posições do experimento anterior. V06–V68 completam o mapa inicial. V69 é a vaga acima da V59; V70 e V71 acompanham a van central. Cada região registra setor, linha e coordenadas. Consulte [MAPA_COMPLETO.md](docs/MAPA_COMPLETO.md) para o procedimento e as limitações.

A execução completa gera **48.209 decisões**. No quadro 60, há 12 estados livres, 57 ocupados e dois em análise; no último quadro, 15 livres, 54 ocupados e dois em análise. Esses números são saídas do detector, não prova de funcionamento em campo.

A amostra rotulada tem 197 pares de quadro e região, cobrindo as 71 regiões em dois quadros e a amostra anterior. Foram 185 concordantes, nove indefinidos e três divergentes: **93,91% de concordância total e 95,43% de cobertura**. Regiões e limiares foram calibrados neste mesmo vídeo. A matriz e os erros estão documentados em [MAPA_COMPLETO.md](docs/MAPA_COMPLETO.md). O relatório anterior de cinco vagas está preservado em [EXPERIMENTO_REAL.md](docs/EXPERIMENTO_REAL.md).

## Exportações e parâmetros

As saídas padrão ficam em `resultados/carpark/`: `ocupacao.csv`, `eventos.csv`, `resumo.json`, `avaliacao.json`, `ultimo_quadro.png` e `video_anotado.mp4`. O aplicativo exporta esses resultados em ZIP. Eles representam a análise completa, independentemente do filtro ou instante exibido.

CSV de ocupação: `quadro`, `tempo_video_s`, `vaga`, `estado`, `densidade_textura` e `motivo` no modo completo. O motivo explica a abstenção das duas regiões centrais. No modo por referência, a medida é `fracao_alterada`, seguida de `motivo`. O resumo registra o método e o total de vagas. Eventos incluem confirmações iniciais e mudanças posteriores; o histórico da janela omite a inicialização.

No modo completo, a configuração usa bloco adaptativo 25, constante 16, mediana 5 × 5, dilatação 3 × 3 e margem interna de três pixels. Os pares de revisão usam componentes claros conexos com brilho mínimo 180 e presença em pelo menos 8% de cada região do par. Essa regra não reconhece semanticamente veículos nem detecta automaticamente toda ocupação atravessada: o par central foi cadastrado manualmente.

Os limiares gerais são livre até 0,11 e ocupada a partir de 0,12. V06 e V18 têm limiares locais 0,05/0,065 por conterem vans com superfícies lisas; continuam podendo mudar de estado conforme a imagem. Entre os limiares, mantém-se o estado anterior; sem confirmação, permanece em análise. Em imagem estática, o estado é calculado imediatamente.

Os resultados antigos são invalidados ao iniciar uma nova execução. Vídeo interrompido não deve ser avaliado como completo. O tempo do resumo inclui processamento, exportação e eventual exibição/pausa; não é um benchmark isolado do algoritmo.

## Testar e repetir a simulação

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe demo.py
.\.venv\Scripts\python.exe detector.py --source dados/video_simulado.mp4 --reference dados/referencia_vazia.png --config dados/vagas_demo.json --output resultados/video
.\.venv\Scripts\python.exe verificar_demo.py
```

A suíte completa tem 115 testes. Instale `requirements-app.txt` para incluir os testes reais de widgets Qt; com somente `requirements.txt`, os testes de Qt são omitidos. A suíte cobre textura, referência, confirmação temporal, avaliação, exportação, reprodução, erros, cancelamento, rolagem, ambiguidade, importação de vídeos, revisões de perfis, edição pelo mouse, duplicação de vagas, persistência de rascunhos, integração dos serviços e geração do relatório HTML. GitHub Actions executa em Windows e Linux e repete os vídeos simulado, completo e anterior.

Os serviços de [duplicação de vagas](docs/DUPLICACAO.md) e [rascunhos locais](docs/RASCUNHOS.md) estão implementados e testados de forma independente. A ligação desses serviços aos controles do editor ainda é uma etapa posterior; o painel atual mantém rascunhos somente durante a sessão.

As revisões cruzadas estão registradas em [revisão da duplicação](docs/REVISAO_DUPLICACAO.md) e [revisão dos rascunhos](docs/REVISAO_RASCUNHOS.md), com testes dos mapas duplicados no detector e da recuperação de rascunhos para salvar perfis. A recuperação rejeita texto Unicode inválido antes de tentar salvar um perfil.

A simulação tem 240 quadros e seis vagas: 1.408 de 1.440 decisões concordantes, 24 indefinidas na inicialização e oito divergentes durante a confirmação temporal. A concordância de 97,78% descreve somente essa simulação.

## Gerar relatório dos resultados

Depois de concluir uma análise, execute:

```powershell
.\.venv\Scripts\python.exe gerar_relatorio.py --resultados resultados/carpark --saida resultados/relatorio.html
```

O HTML funciona sem internet e reúne contagens, evolução ao longo do vídeo e mudanças de estado. A avaliação aparece somente quando a pasta contém `avaliacao.json`; nos demais casos, informa Sem avaliação rotulada. O comando lê os resultados existentes e pode apontar para a pasta de uma revisão de perfil local. O guia [RELATORIO_RESULTADOS.md](docs/RELATORIO_RESULTADOS.md) explica a geração e a interpretação. O relatório é gerado pelo comando acima; a inclusão de um botão no painel fica para uma etapa posterior.

## Gravar e cadastrar outro estacionamento

Siga [COLETA_REAL.md](docs/COLETA_REAL.md) e mantenha câmera, foco, resolução e posição fixos. Para cadastrar pelo aplicativo, use [Vídeos e vagas](docs/EDITOR_DE_VAGAS.md). Os perfis locais ficam em `perfis/`, ignorada pelo Git, e cada vídeo recebe seu próprio mapa. O mapa incluído serve somente à filmagem de demonstração.

O modo anterior por referência vazia continua disponível pelo terminal e exige um quadro com todas as vagas cadastradas vazias; a extração requer confirmação humana:

```powershell
.\.venv\Scripts\python.exe extrair_referencia.py --video dados/reais/video_real.mp4 --quadro 0 --output dados/reais/referencia.png --confirmar-vagas-vazias
.\.venv\Scripts\python.exe calibrar.py --reference dados/reais/referencia.png --output dados/reais/vagas.json
.\.venv\Scripts\python.exe detector.py --source dados/reais/video_real.mp4 --reference dados/reais/referencia.png --config dados/reais/vagas.json --output resultados/real --show
```

Troque o quadro zero por um índice visualmente conferido. Na calibração, clique quatro cantos, N confirma, U desfaz, S salva e Esc cancela. Para câmera local, use `--source 0`. Câmera física e calibração manual por mouse ainda dependem do ensaio no equipamento do grupo. Os limiares do modo por textura precisam ser recalibrados e avaliados em outra sequência antes de usar outro local.

## Organização e entrega

- `detector.py`: os dois métodos, confirmação temporal, anotação e exportação.
- `aplicativo.py`, `app/` e `INICIAR_APLICATIVO.bat`: janela nativa e iniciador.
- `executar_exemplo.py`: processamento e avaliação dos exemplos reais.
- `calibrar.py`, `extrair_referencia.py`, `demo.py`, `avaliar.py`: preparação e avaliação.
- `dados/terceiros/`: vídeo, mapas, rótulos e registro de origem.
- `tests/` e `.github/workflows/`: testes locais e automáticos.
- [ROTEIRO_VIDEO.md](docs/ROTEIRO_VIDEO.md): apresentação planejada em 8 minutos e 40 segundos.
- [ENTREGA.md](docs/ENTREGA.md): exigências e conferência dos links finais.

A coleta própria, a avaliação independente e o vídeo do YouTube com os quatro integrantes continuam pendentes. As tarefas são acompanhadas nas [issues](https://github.com/VitorRodi/detector-vagas-estacionamento/issues).
