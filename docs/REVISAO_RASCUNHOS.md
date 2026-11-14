# Revisão cruzada do serviço de rascunhos

Revisão da [issue #24](https://github.com/VitorRodi/detector-vagas-estacionamento/issues/24)
sobre a `main` em `e397caf`, que já incorpora os PRs #21 e #22.

## Código e contrato revisados

| Referência | O que foi conferido |
| --- | --- |
| [`app/rascunhos.py:71`](../app/rascunhos.py#L71) | Versão 1 e campos obrigatórios, coerência de resolução, IDs, polígonos, limiares e referências dos grupos de ambiguidade. O mapa admite lista de vagas vazia. |
| [`app/rascunhos.py:162`](../app/rascunhos.py#L162) | Validação antes da escrita, temporário no mesmo diretório, `flush`, `fsync`, fechamento e substituição por `os.replace`. Uma falha de gravação preserva o ativo anterior. |
| [`app/rascunhos.py:186`](../app/rascunhos.py#L186) | Ausência retorna `None`. Erros de leitura geram `OSError`. Conteúdo inválido gera `ValueError` e fica disponível para recuperação manual. |
| [`app/rascunhos.py:207`](../app/rascunhos.py#L207) | O arquivamento reserva um nome exclusivo e move o ativo sem reinterpretar os bytes. Em falha de substituição, conserva o ativo e tenta remover a reserva. |
| [`app/perfis.py:26`](../app/perfis.py#L26) e [`:92`](../app/perfis.py#L92) | `probe_video` lê o primeiro quadro e os metadados do vídeo. `ProfileStore.save` valida nome, resolução e mapa com o detector antes de gravar a revisão e publicar o manifesto. |
| [`tests/test_rascunhos.py`](../tests/test_rascunhos.py) e [`docs/RASCUNHOS.md`](RASCUNHOS.md) | Contrato público e 22 testes unitários, incluindo falhas de escrita parcial, sincronização, leitura e arquivamento. Os novos testes usam perfis reais. |

## Evidências de integração

- Um vídeo AVI de 12 quadros foi criado em diretório temporário. O fluxo
  `DraftStore.save → DraftStore.load → ProfileStore.save` preservou o nome com
  acentos, a geometria, os limiares locais e os demais campos do mapa.
  O perfil reaberto validou o vídeo e o hash do mapa salvo.
- O mapa da demonstração foi recuperado e salvo como perfil temporário, usando
  apenas o primeiro quadro do vídeo original. O mapa salvo coincide com o
  original, incluindo as 71 regiões, setor e linha, limiares locais e o grupo
  de ambiguidade V70/V71 com seus parâmetros e motivo. O JSON original
  permaneceu idêntico byte a byte.
- Um rascunho sem vagas foi recuperado com o ID do perfil de origem. O
  detector rejeitou o salvamento com `Cadastre pelo menos uma vaga.` e os
  arquivos do perfil e do rascunho permaneceram intactos. Ao cadastrar uma
  vaga e recuperar novamente, o mesmo perfil recebeu uma nova revisão.
- Uma falha simulada de `os.replace`, somente durante o arquivamento, conservou
  o rascunho ativo, o manifesto, as duas revisões reais e os resultados da
  revisão anterior. Repetir o arquivamento sem a falha moveu os mesmos bytes
  e preservou os arquivos do perfil.

## Defeito reproduzido e correção

Um JSON pode ter bytes UTF-8 válidos e ainda conter o escape ASCII `\ud800`.
Ao decodificar esse escape isolado em um campo textual do mapa, o Python gera
um substituto Unicode sem par. A versão original validava a codificação em
`save()`, mas `load()` aceitava o valor decodificado.

Para reproduzir, salve um perfil válido e um rascunho associado. Atribua
`chr(0xd800)` a `config['spaces'][0]['observacao']` e substitua o ativo pelo
resultado de `json.dumps(draft, ensure_ascii=True).encode('utf-8')`. Antes da
correção, `DraftStore.load()` retornava esse mapa. A chamada seguinte a
`ProfileStore.save(..., existing=previous)` lançava
`UnicodeEncodeError: surrogates not allowed`. O manifesto continuava apontando
para a revisão anterior, mas uma segunda pasta de revisão vazia era criada.

A verificação de serialização e codificação UTF-8 agora faz parte de
`_validate`, que serve tanto para gravação quanto para recuperação. O teste
`test_recovery_rejects_unpaired_surrogate_in_map_metadata` reproduziu a falha
antes da mudança. Com a correção, `load()` lança `ValueError`, o arquivo
inválido continua intacto e pode ser arquivado byte a byte. O teste também
confere que o perfil já salvo e seus arquivos continuam iguais.

## Comandos e resultados

Os comandos foram executados na raiz do repositório, no Windows, com as
dependências de `requirements-app.txt` no ambiente virtual de testes.

| Comando | Resultado observado |
| --- | --- |
| `python -m unittest discover -s tests -p test_integracao_rascunhos.py -v` antes da correção | 5 executados, 1 falha. A recuperação aceitou o escape isolado e o teste reportou `ValueError not raised`. |
| `python -m unittest discover -s tests -p test_integracao_rascunhos.py -v` após a correção | 5 passaram em 0,292 s. |
| `python -m unittest discover -s tests -v` com `QT_QPA_PLATFORM=offscreen` | 97 passaram em 47,840 s, incluindo os testes Qt, sem falhas nem pulos. |

## Limitações

O rascunho pode conter nome incompleto e mapa vazio. A etapa de salvar um
perfil exige nome válido, vídeo disponível e ao menos uma vaga com geometria
aceita pelo detector. O serviço de rascunhos guarda o índice de quadro e o ID
do perfil de origem, cuja disponibilidade deve ser conferida pelo chamador.
O fluxo testado usa o primeiro quadro como referência.

Os testes cobrem falhas observáveis de leitura, validação e substituição por
meio da integração e da suíte unitária existente. A durabilidade em queda de
energia e a gravação concorrente ficam fora da garantia. O salvamento do
perfil e o arquivamento são duas operações independentes. O mapa completo foi
validado ao criar o perfil, sem rodar a análise dos 679 quadros nesse teste.
