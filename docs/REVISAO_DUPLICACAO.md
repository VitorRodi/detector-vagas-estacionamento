# Revisão cruzada da duplicação de vagas — issue #23

Revisor: Edson Leandro Soares. Data: 14/11/2026.
Branch: `edson/revisao-duplicacao`.
Base revisada: `e397caf58e8675b03f5ab70480bc23c48dabbf19` de `origin/main`,
após a incorporação dos PRs #21 (rascunhos) e #22 (duplicação de Pedro).

## Parecer e escopo

**Não foi encontrado defeito reproduzível na duplicação para entradas que
respeitam o contrato documentado.** Os seis novos testes de integração passaram
na primeira execução sobre o serviço existente, sem alterações em
`app/duplicacao.py`. Não houve correção de produção nem ciclo de teste falhando
antes e passando depois de uma correção. A exceção de limite descrita abaixo é
um comportamento esperado, não um defeito.

Esta entrega acrescenta somente `tests/test_integracao_duplicacao.py` e este
relatório. A interface, o detector, os perfis, os testes unitários existentes,
o README e os workflows não foram modificados pela revisão.

## Código e contrato revisados

As linhas abaixo referem-se à base identificada acima.

| Arquivo / linhas | O que foi conferido | Achado |
| --- | --- | --- |
| `app/duplicacao.py:6–27` | Assinatura, inteiros, quantidade, resolução e seleção | Dimensões positivas, 1–50 cópias, deslocamento não nulo; seleção precisa existir. |
| `app/duplicacao.py:29–31,41,46` | Geração de IDs | Novos IDs após o maior sufixo `V[0-9]+`, com pelo menos dois dígitos, sem renumerar existentes. |
| `app/duplicacao.py:33–39` | Deslocamento e limites | Cópia `i` usa a origem mais `i*(dx,dy)`; qualquer vértice fora dos pixels válidos rejeita o lote. |
| `app/duplicacao.py:40–48` | Cópia profunda e metadados | Cada adição copia profundamente a origem; o retorno copia também as regiões existentes. Limiares e metadados aninhados são preservados. |
| `app/duplicacao.py:43–44` | Setor e linha | `setor` e `linha` são removidos apenas das novas regiões, conforme contrato; as existentes mantêm os valores. |
| `tests/test_duplicacao.py:21–110` | Cobertura unitária existente | Já cobre aritmética, IDs com lacunas/zeros, 50 cópias, limites, argumentos e isolamento; não foi necessário repetir sua matriz de casos. |
| `docs/DUPLICACAO.md:7–49,77–110` | Pré-condições, retorno, consumidor futuro e limites | O serviço recebe mapa previamente validado; integração com canvas e grupos de ambiguidade continua separada. |
| `detector.py:31–107` | Consumidor da configuração | Valida resolução, geometria, IDs e limiares; cria máscaras e estado temporal próprios por região. |
| `detector.py:129–167` | Processamento | Produz um resultado por região, usa limiares locais e confirma estados independentemente. |
| `tests/test_textura.py`, `tests/test_detector.py` | Cobertura prévia do consumidor | Serviram de referência para os quadros controlados; os novos casos atravessam a fronteira duplicação → configuração → detector. |

## Evidências dos seis testes novos

Todos usam o `duplicate_spaces` e o `Detector` reais, sem mocks. A configuração
tem resolução 240 × 120, imagem uniforme BGR `uint8` de intensidade 120,
`analysis_inset=1`, `stable_frames=2`, parâmetros explícitos de textura e
referência, lista de grupos de ambiguidade vazia e metadados de cadastro.
As únicas variações visuais são barras escuras determinísticas, limitadas ao
interior de uma região. Não há vídeo externo, câmera, disco, rede ou aleatoriedade
nos novos testes.

1. **Configuração completa e cardinalidade.** Partindo de `V01` e `V09`, duas
   cópias de `V01` com `dx=60, dy=0` geram `V10` e `V11`. O retorno entra em
   `config['spaces']`; o detector constrói as máscaras e devolve exatamente os
   quatro IDs nessa ordem, uma ocorrência de cada. Regiões sem textura ficam
   livres. Setor/linha originais permanecem; novas regiões não os recebem.
   Construir/processar não insere estado no mapa JSON nem modifica a entrada.
2. **Uso efetivo dos limiares locais.** A cópia `V10` recebe barras escuras.
   Com limiares locais `.05/.065`, é ocupada; removendo os campos locais e
   mantendo os gerais `.75/.90`, a mesma medida resulta livre. O teste também
   faz o contraponto para `free_ratio`: uma origem com valores locais
   `.75/.90` é duplicada, enquanto os gerais são `.05/.065`; a cópia é livre.
   Se apenas o limiar livre local fosse ignorado, a medida ficaria entre os
   limiares e o resultado seria indefinido. Ambos os métodos, `texture` e
   `reference`, são exercitados sem substituir o algoritmo.
3. **Estado independente por região.** Primeiro, um detector do mapa original
   confirma `V01` ocupada. Um novo detector recebe o mapa duplicado: o primeiro
   quadro ainda retorna todos indefinidos, sem herdar a confirmação anterior.
   Após confirmar a origem ocupada, a textura muda para `V10`. São exigidos
   dois quadros para confirmar a origem livre e a cópia ocupada; `V09` e `V11`
   continuam livres. O detector original segue funcionando independentemente.
4. **Edição de uma cópia.** Os pontos, limiares, setor/linha e metadados
   aninhados de `V10` são alterados. A entrada, as regiões existentes retornadas
   e `V11` permanecem intactas. Tanto o mapa editado quanto o original ainda
   constroem um detector e produzem a quantidade esperada de resultados.
5. **Falha sem mapa parcial.** Com `dx=100, dy=0, copies=2`, a primeira cópia
   estaria em `x=110..150`, mas a segunda chegaria a `x=250`, além do último
   pixel 239. O `ValueError` identifica a cópia 2. A atribuição
   `config['spaces'] = duplicate_spaces(...)` não ocorre; a lista ativa mantém
   a identidade e o conteúdo anteriores. O detector já aberto e outro
   reconstruído desse mapa devolvem os mesmos resultados anteriores, sem
   uma primeira cópia aplicada parcialmente.
6. **Translação nas bordas e máscaras reais.** Deslocamentos diagonais positivos
   e negativos põem uma cópia exatamente em `(239,119)` ou `(0,0)`.
   O detector aceita ambos os mapas e produz três regiões livres. O foco é a
   aceitação da geometria e das máscaras pelo consumidor, complementando os
   testes unitários de limites já existentes.

Medidas observadas no quadro de `V10`, com os limiares locais `.05/.065` e os
gerais `.75/.90`:

| Método | Medida de V10 | Com limiares locais | Somente gerais | Outras três regiões |
| --- | --- | --- | --- | --- |
| `texture` | 0,17751479289940827 | ocupada | livre | livres, medida 0 |
| `reference` | 0,1893491124260355 | ocupada | livre | livres, medida 0 |

Essas medidas são índices do algoritmo sobre dados sintéticos, não probabilidade
de ocupação nem evidência de precisão em um estacionamento real. Os testes
comparam os intervalos e a igualdade da medida entre configurações; não exigem
esses decimais específicos em outras plataformas.

## Comandos e resultados reais

Executados a partir da raiz do checkout, em Windows, com Python 3.14.3,
NumPy 2.5.4, OpenCV 4.13.0 (pacote `opencv-python==4.13.0.92`) e as dependências
de `requirements-app.txt`, incluindo PySide6-Essentials 6.12.0.

| Comando | Resultado |
| --- | --- |
| `git status --porcelain=v1` antes da tarefa | Vazio; checkout sem alterações locais pendentes. |
| `git fetch origin` | Referências remotas atualizadas; PRs #21/#22 já incorporados. |
| `git switch main` e `git pull --ff-only origin main` | Avanço de `fbfecbc` para `e397caf`, sem conflito. |
| `git switch -c edson/revisao-duplicacao` | Branch criada a partir da main atualizada. |
| `git config user.name` / `git config user.email` | Edson Leandro Soares / edson.soares@unochapeco.edu.br. |
| `python -m unittest discover -s tests -p test_integracao_duplicacao.py -v` | 6 testes aprovados; última execução em 0,030 s, sem falhas nem omissões. |
| `python -m unittest discover -s tests -v` | 98 testes aprovados em 65,779 s, sem falhas, erros ou testes omitidos; inclui os 6 novos casos e os testes reais de Qt. |

O executável do ambiente isolado foi usado para os comandos Python. Na execução
completa, o diretório `Scripts` desse ambiente foi colocado no `PATH` e
`QT_QPA_PLATFORM=offscreen`, para incluir os testes reais de Qt sem interação.
A coleta adicional das medidas da tabela usou `python -c` importando a fixture
`DuplicacaoDetectorTests`, duplicando o mapa e processando o mesmo quadro com e
sem os campos de limiares locais. Os valores registrados acima são a saída
observada, não uma estimativa.

## Problemas, correções e limitações

Nenhum defeito confirmado foi encontrado dentro das pré-condições revisadas.
Por isso, **não foi alterado `app/duplicacao.py`** nem proposta uma correção
especulativa. Não há reprodução de defeito ou melhoria opcional implementada.

As seguintes limitações já pertencem ao contrato e continuam válidas:

- A entrada precisa conter polígonos válidos e IDs únicos. A duplicação não
  revalida um mapa arbitrário ou corrompido; a validação final pelo detector
  continua necessária. Estruturas internas de `Detector.spaces`, com máscaras
  e estado temporal, não são a entrada prevista para a função.
- Não há detecção de sobreposição entre vagas, correção de perspectiva,
  recalibração automática de limiares nem inferência de setor/linha. A cópia
  conserva o formato; sua adequação à nova posição exige conferência humana.
- Os grupos de ambiguidade ficam fora de `spaces` e não são duplicados. Os
  novos testes usam grupos vazios; não validam criação automática de grupos.
- O caso de falha demonstra a atribuição somente após retorno completo. Não
  comprova integração com widgets, seleção, desfazer/refazer, persistência em
  disco ou atualização do contador interno de IDs do canvas, todos fora da tarefa.
- Os IDs são únicos dentro do mapa recebido; não há coordenação global entre
  chamadas concorrentes ou mapas diferentes.
- Os testes são locais e determinísticos. Não medem desempenho nem precisão de
  campo e não substituem uma avaliação com gravações independentes.

## Explicação para apresentação

A duplicação trabalha somente com a geometria e os dados de cadastro. Ela
calcula novas posições e IDs, preserva os limiares por cópia profunda e só
retorna depois que todo o lote passou pelos limites. O detector recebe esse
novo mapa, cria sua própria máscara e estado por região e mede cada área
separadamente. O teste que move a textura da origem para uma cópia demonstra
que copiar o cadastro não significa copiar a ocupação. O teste de limite
demonstra que uma operação rejeitada deixa o mapa anterior em funcionamento.
