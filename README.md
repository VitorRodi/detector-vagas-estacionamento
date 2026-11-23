# Monitoramento de vagas de estacionamento

**GitHub:** [VitorRodi/detector-vagas-estacionamento](https://github.com/VitorRodi/detector-vagas-estacionamento)

[![Testes do projeto](https://github.com/VitorRodi/detector-vagas-estacionamento/actions/workflows/testes.yml/badge.svg)](https://github.com/VitorRodi/detector-vagas-estacionamento/actions/workflows/testes.yml)

Aplicativo de desktop para analisar a ocupação de vagas em gravações com câmera fixa. O usuário cadastra as regiões na imagem; o programa calcula seus estados, sincroniza os resultados com o vídeo e exporta os registros.

Projeto de Robótica e Visão Computacional da Unochapecó, professor Wagner Titon. Integrantes: **Vitor Rodi, Pedro Toigo, Bruno Fell Antunes e Edson Leandro Soares**.

![Monitoramento com vídeo, marcações, contadores e lista de vagas](assets/aplicativo.png)

## Início rápido no Windows

1. Baixe o projeto em **Code → Download ZIP** ou clone o repositório.
2. Extraia o ZIP e entre na pasta que contém `aplicativo.py`, `INICIAR_APLICATIVO.bat`, `app/` e `dados/`.
3. Com Python 3.10 ou mais recente instalado, dê dois cliques em **[INICIAR_APLICATIVO.bat](INICIAR_APLICATIVO.bat)**.
4. Aguarde a análise do vídeo e clique em **Reproduzir**.

O iniciador cria `.venv` e instala as dependências. A primeira instalação precisa de internet; depois, aplicativo, processamento e relatório funcionam com arquivos locais. Extraia o projeto antes de executar e preserve as pastas de dados, fontes e ícones.

Alternativa pelo PowerShell, na raiz do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
.\.venv\Scripts\python.exe aplicativo.py
```

Para reutilizar uma análise completa já salva:

```powershell
.\.venv\Scripts\python.exe aplicativo.py --usar-resultados
```

A opção `--usar-resultados` exige os resultados da demonstração em `resultados/carpark/`. Em uma cópia nova do GitHub, abra sem a opção ou execute `executar_exemplo.py --completo` primeiro. Os resultados gerados não são versionados.

## Recursos disponíveis

| Recurso | Funcionamento atual |
|---|---|
| Monitoramento | Vídeo, contagens de livres/ocupadas/em análise e uma marcação por região |
| Reprodução | Pausa, reinício, busca por quadro, velocidade e tela cheia |
| Consulta | Filtro por estado, seleção no vídeo ou na lista e histórico de mudanças |
| Editor integrado | Importar vídeo, desenhar retângulos ou quatro pontos, mover cantos, excluir, desfazer e refazer |
| Perfis locais | Guardar mapas por estacionamento, criar revisões e reabrir análises completas compatíveis |
| Exportação | ZIP com arquivos disponíveis da análise; perfis locais incluem mapa e referência |
| Relatório HTML | Gerado por comando, funciona offline e reúne contagens, gráfico, eventos e avaliação quando existente |
| Duplicação de vagas | Serviço `app/duplicacao.py`, implementado e testado; integração aos controles do editor pendente |
| Persistência de rascunhos | Serviço `app/rascunhos.py`, implementado e testado; recuperação automática no painel pendente |

O painel atual mantém o rascunho durante a sessão. Para persistir o cadastro de um estacionamento, use **Salvar e analisar**. O relatório HTML também ainda não possui um botão dedicado na interface.

## Utilizar o monitoramento

- **Verde:** livre. **Vermelho:** ocupada. **Amarelo:** em análise. Texto e cor identificam os estados.
- A lista tem rolagem. Selecionar uma vaga destaca a região correspondente e mostra a medida de textura e, quando existente, o motivo da análise.
- O filtro altera a lista; os contadores continuam considerando todas as regiões do mapa ativo.
- Clicar no histórico leva ao quadro da mudança confirmada. As confirmações iniciais ficam fora desse painel.
- **Apresentar / F11** alterna tela cheia. **Esc** sai dela; no monitoramento normal pausa, e no editor cancela o gesto atual.
- **Marcações** mostra ou oculta os polígonos. **Exportar resultados** grava um ZIP da análise completa, independentemente do quadro exibido.

A demonstração abre pausada no quadro 60, aproximadamente dois segundos após o início. Ao terminar o vídeo, Reproduzir reinicia a gravação. O guia detalhado está em [APLICATIVO.md](docs/APLICATIVO.md).

## Cadastrar outro vídeo

O mapa incluído vale para o vídeo de demonstração. Outro estacionamento exige cadastro próprio; o aplicativo não descobre automaticamente todas as vagas de uma nova filmagem.

1. Abra **Vídeos e vagas → Adicionar vídeo** e selecione uma gravação local com câmera fixa.
2. Dê um nome ao estacionamento e escolha um quadro em que as divisões estejam visíveis.
3. Desenhe cada vaga com **Retângulo** ou **4 pontos**. Em **Mover / ajustar**, arraste o interior ou os cantos da região.
4. Use **Conferir neste quadro** e compare com a imagem. Confira vagas livres e ocupadas em diferentes instantes; ajuste os limiares gerais se necessário.
5. Clique em **Salvar e analisar**. O programa salva o perfil e processa o vídeo escolhido.

![Editor de marcações dentro do painel principal](assets/editor-vagas.png)

**Voltar** e a navegação mantêm o rascunho enquanto o aplicativo está aberto. Sem alterações em um perfil salvo, **Abrir análise** reutiliza resultados compatíveis; uma edição cria outra revisão, com resultados separados. O botão **Demonstração** retorna ao exemplo incluído.

O vídeo permanece no local original. Os perfis ficam em `perfis/`, ignorada pelo Git, e contêm `perfil.json`, revisões de `mapa.json`, `referencia.png` e seus resultados. Mover ou substituir a gravação exige novo cadastro e conferência. O programa verifica tamanho/data do vídeo e hash do mapa antes de reutilizar a análise.

A prévia de um quadro não aplica confirmação temporal. Vídeos próprios não recebem os rótulos nem as métricas da demonstração: a página Sobre informa **Sem avaliação rotulada**. Veja [EDITOR_DE_VAGAS.md](docs/EDITOR_DE_VAGAS.md).

## Tecnologias e classificação

Python, NumPy e OpenCV implementam o processamento; PySide6/Qt implementa a janela nativa. Não há rede neural treinada, pesos externos, servidor ou API necessária ao funcionamento.

| Método | Uso | Medida |
|---|---|---|
| `texture` | Mapa completo e perfis do editor | Densidade de textura dentro de cada polígono |
| `reference` | Experimento anterior de cinco regiões e linha de comando | Fração de pixels diferentes de uma referência vazia |

No modo por textura, cada quadro passa por tons de cinza, suavização gaussiana 3 × 3, limiarização adaptativa invertida, mediana 5 × 5 e dilatação 3 × 3. A medida é calculada na máscara interna da região. Dois limiares e cinco quadros consecutivos confirmam estados; entre os limiares, o estado anterior é preservado. O percentual é um índice de textura, sem interpretação de probabilidade de ocupação.

Na demonstração completa: bloco adaptativo 25, constante 16, margem interna de três pixels e limiares livre ≤ 0,11 / ocupada ≥ 0,12. V06 e V18 usam limiares locais 0,05/0,065, ajustados às vans de superfície lisa. Novos perfis começam com margem de um pixel e limiares 0,11/0,12; precisam de conferência por local.

O experimento por referência exige um quadro com todas as regiões cadastradas vazias. No modo completo, a referência fornece resolução e formato: seus pixels não são tratados como fundo vazio global.

## Demonstração e resultados

O arquivo `dados/terceiros/carPark.mp4` tem 679 quadros, 24 FPS, resolução de 1100 × 720 e duração aproximada de 28,29 s. Foi obtido do repositório de [Harsh Bafna](https://github.com/harshbafnaa/car-parking-detection). Origem, revisão, hash e limites da declaração de licença estão em [FONTES_MIDIA.md](docs/FONTES_MIDIA.md). A filmagem não foi produzida pelo grupo.

O mapa completo contém **71 regiões: 69 vagas e duas áreas centrais de revisão**. Ilhas e corredores ficam fora do cadastro. V69 é a vaga acima de V59. V70 e V71 abrangem a van central; quando um mesmo componente claro atravessa o par, ambas ficam em análise, com o motivo gravado. A regra usa brilho mínimo 180 e presença em pelo menos 8% de cada máscara. É uma heurística para grupos cadastrados, sem reconhecimento semântico de veículos ou detecção geral de infrações.

| Medida | Resultado do exemplo completo |
|---|---:|
| Quadros / regiões | 679 / 71 |
| Decisões registradas | 48.209 |
| Quadro 60: livres / ocupadas / análise | 12 / 57 / 2 |
| Último quadro: livres / ocupadas / análise | 15 / 54 / 2 |
| Amostras rotuladas | 197 |
| Concordantes / indefinidas / divergentes | 185 / 9 / 3 |
| Concordância total | 93,91% |
| Cobertura | 95,43% |
| Acurácia somente entre decisões definidas | 98,40% |

Esses resultados usam o mesmo clipe de calibração e cadastro. A amostra não mede generalização nem acerto de todas as decisões do vídeo. Há falsas mudanças em V55 durante passagem de pessoas/sombras, além de divergências próximas às saídas de veículos. Os detalhes estão em [MAPA_COMPLETO.md](docs/MAPA_COMPLETO.md). O experimento anterior está em [EXPERIMENTO_REAL.md](docs/EXPERIMENTO_REAL.md).

## Processar pelo terminal

Na raiz, com as dependências instaladas:

```powershell
.\.venv\Scripts\python.exe executar_exemplo.py --completo
```

Para exibir também a janela simples do OpenCV:

```powershell
.\.venv\Scripts\python.exe executar_exemplo.py --completo --show
```

Nessa janela, espaço pausa e Q/Esc encerra. Para o aplicativo completo, use `aplicativo.py`. A execução anterior de cinco regiões deve usar outra pasta para preservar os resultados completos:

```powershell
.\.venv\Scripts\python.exe executar_exemplo.py --output resultados/referencia
```

Somente os programas de processamento exigem `requirements.txt`; a interface e os testes Qt exigem `requirements-app.txt`.

### Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/python aplicativo.py
```

A janela precisa de sessão gráfica. No Ubuntu, instale `libegl1` se faltar a biblioteca EGL. Para processar sem abrir janela, use `.venv/bin/python executar_exemplo.py --completo`.

## Gerar o relatório HTML

Depois de concluir uma análise:

```powershell
.\.venv\Scripts\python.exe gerar_relatorio.py --resultados resultados/carpark --saida resultados/carpark/relatorio.html
```

Abra `resultados/carpark/relatorio.html` no navegador. O HTML funciona offline e reúne resumo, contagens finais, evolução, eventos e avaliação quando disponível. O gerador usa somente a biblioteca padrão do Python, preserva as entradas e não abre o navegador automaticamente.

Para outro perfil, substitua `--resultados` pela pasta de resultados de sua revisão. Sem `avaliacao.json`, o relatório informa **Sem avaliação rotulada**. A geração rejeita análises interrompidas e inconsistências nos arquivos esperados, preservando uma saída anterior em caso de erro. Veja [RELATORIO_RESULTADOS.md](docs/RELATORIO_RESULTADOS.md).

## Arquivos gerados

| Arquivo | Conteúdo |
|---|---|
| `ocupacao.csv` | Um estado por quadro e região, medida e motivo |
| `eventos.csv` | Confirmações iniciais e mudanças posteriores |
| `resumo.json` | Método, quadros, regiões, duração, contagens e conclusão da execução |
| `avaliacao.json` | Comparação com rótulos, quando há avaliação disponível |
| `ultimo_quadro.png` | Último quadro anotado |
| `video_anotado.mp4` | Vídeo processado com marcações |
| `relatorio.html` | Relatório opcional gerado pelo comando próprio |

Na demonstração, a pasta padrão é `resultados/carpark/`. Os perfis locais têm uma pasta por revisão. O exportador ZIP do aplicativo inclui os seis arquivos conhecidos da análise quando presentes; o HTML opcional é gerado e compartilhado separadamente. Em perfis locais, o ZIP inclui também `mapa.json` e `referencia.png`.

No modo completo, o CSV contém `quadro`, `tempo_video_s`, `vaga`, `estado`, `densidade_textura` e `motivo`. Em `reference`, a medida é `fracao_alterada`, seguida de `motivo`. O motivo registra, por exemplo, a abstenção do par central.

Ao iniciar outra análise, o detector invalida os resumos antigos. A interface só habilita a reprodução depois de conferir a conclusão esperada. O tempo do resumo inclui processamento, exportação e eventual exibição ou pausa; não é um benchmark isolado do algoritmo.

## Testes e simulação reproduzível

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

A versão atual tem **115 testes**. Com `requirements-app.txt`, a suíte inclui widgets Qt reais; com somente `requirements.txt`, os testes de Qt são omitidos. GitHub Actions verifica Python 3.13 em Windows e Linux, executando testes, simulação e os dois experimentos do vídeo externo.

Para repetir o cenário simulado de seis vagas:

```powershell
.\.venv\Scripts\python.exe demo.py
.\.venv\Scripts\python.exe detector.py --source dados/video_simulado.mp4 --reference dados/referencia_vazia.png --config dados/vagas_demo.json --output resultados/video
.\.venv\Scripts\python.exe verificar_demo.py
```

A simulação tem 240 quadros e 1.440 decisões: 1.408 concordantes, 24 indefinidas na inicialização e oito divergentes durante confirmação temporal. A concordância de 97,78% vale somente para o cenário simulado.

## Organização dos arquivos

| Caminho | Responsabilidade |
|---|---|
| `aplicativo.py` / `INICIAR_APLICATIVO.bat` | Entrada da interface / iniciador Windows |
| `detector.py` | Classificação, confirmação temporal e exportação |
| `app/janela.py`, `componentes.py`, `estilo.qss` | Janela, desenho e aparência |
| `app/editor.py`, `perfis.py` | Editor visual e perfis por vídeo |
| `app/modelo.py`, `reproducao.py` | Validação dos resultados e reprodução sincronizada |
| `app/duplicacao.py`, `rascunhos.py` | Serviços de duplicação e persistência de rascunhos |
| `gerar_relatorio.py` | Gerador de relatório HTML offline |
| `executar_exemplo.py`, `avaliar.py` | Execução e avaliação das demonstrações |
| `demo.py`, `verificar_demo.py` | Geração e conferência da simulação |
| `calibrar.py`, `extrair_referencia.py` | Cadastro e referência do modo anterior |
| `dados/terceiros/` | Filmagem, mapas, rótulos e metadados de origem |
| `tests/`, `.github/workflows/` | Testes e integração contínua |

Os contratos dos serviços estão em [DUPLICACAO.md](docs/DUPLICACAO.md) e [RASCUNHOS.md](docs/RASCUNHOS.md). Fontes e licenças locais ficam em `app/fonts/` e devem acompanhar a distribuição.

## Condições de uso e limitações

A câmera deve permanecer fixa, sem mudança de enquadramento ou resolução depois do cadastro. Iluminação, sombras, pedestres, oclusões e veículos lisos podem provocar erros. A textura não identifica semanticamente automóveis. Outro vídeo exige marcação manual e conferência de parâmetros; não há indicação automática confiável para qualquer estacionamento.

A demonstração e sua avaliação são exploratórias. Não há validação independente em estacionamento do grupo nem medição de redução do tempo de procura. As duas áreas centrais em análise não entram nas vagas disponíveis.

O modo anterior por referência vazia exige que as regiões estejam vazias no quadro escolhido. Seu procedimento está em [COLETA_REAL.md](docs/COLETA_REAL.md); para cadastrar pela interface por textura, siga [EDITOR_DE_VAGAS.md](docs/EDITOR_DE_VAGAS.md). Em ambos, preserve câmera e resolução e use uma sequência independente para avaliar.

## Solução de problemas

- **Instalação:** execute os comandos no terminal para ler o erro completo; confira Python, acesso à internet e escrita na pasta do projeto.
- **Resultados ausentes ou incompatíveis:** abra sem `--usar-resultados` para processar novamente. No perfil local, confirme a gravação e o mapa.
- **Vídeo movido ou substituído:** selecione-o novamente no editor e confira o cadastro. O perfil anterior referencia o caminho original.
- **Busca de quadro falhou:** a reprodução pausa e informa o erro. Confira o arquivo ou tente outra gravação válida.
- **Contagem incorreta:** confira os polígonos, o quadro escolhido, sombras e limiares. Aumentar o número de regiões não elimina a necessidade de avaliação visual.
- **Relatório recusado:** conclua o processamento e confira `resumo.json`, `ocupacao.csv` e `eventos.csv`. Uma saída antiga preservada não representa uma geração bem-sucedida.
