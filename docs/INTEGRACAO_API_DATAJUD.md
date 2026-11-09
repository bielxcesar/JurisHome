# Integração da API Pública DataJud

## Objetivo

O glossário oferece uma consulta opcional de metadados públicos de processos judiciais. O usuário informa o número CNJ e seleciona o tribunal. A busca não altera nem substitui os termos locais do glossário.

## Fluxo

1. O navegador envia o número do processo e o alias do tribunal para `POST /api/glossario/datajud`.
2. O backend valida o formato do número CNJ e aceita somente aliases listados pela documentação oficial.
3. O backend envia uma consulta `match` ao endpoint do tribunal em `https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search` com o cabeçalho `Authorization: APIKey ...`.
4. A resposta é limitada a 1 MB, reduzida a campos de metadados pedagógicos e devolvida sem dados de partes. O número e o tribunal não são armazenados pelo JurisHome.

O serviço oficial expõe consultas Elasticsearch por tribunal; por isso, o número CNJ deve conter 20 algarismos e o usuário deve escolher o tribunal correspondente. Verifique os endpoints disponíveis em [Endpoints da API Pública DataJud](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/) e a forma de consulta em [exemplo oficial por número de processo](https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo1/).

## Chave pública

O backend lê `DATAJUD_API_KEY` do ambiente. O `setup_local.py` copia a chave pública atual indicada pela wiki oficial para um `.env` novo, que está ignorado pelo Git. Se você já tinha `.env`, a rotina o preserva; nesse caso, copie a linha `DATAJUD_API_KEY` do `.env.example` para o `.env`. O CNJ pode alterar essa chave; quando uma consulta retornar indisponibilidade, confira a versão vigente em [Acesso à API Pública](https://datajud-wiki.cnj.jus.br/api-publica/acesso/) e atualize somente essa variável.

A chave publicada pelo CNJ é uma chave pública compartilhada, não uma credencial privada do JurisHome. Ainda assim, ela é mantida no servidor para evitar enviar o cabeçalho de autenticação ao navegador.

## Campos exibidos e privacidade

O JurisHome exibe número, tribunal, grau, classe, órgão julgador, data de ajuizamento, assuntos e até oito movimentações. Não solicita CPF, e-mail ou senha para a busca, não a registra no banco e não devolve dados de partes do resultado da API. Somente processos públicos podem aparecer; segredo de justiça não deve ser consultável nesta interface.

## Fonte, uso e limites

O DataJud fornece metadados da Base Nacional de Dados do Poder Judiciário. A interface identifica o Conselho Nacional de Justiça e o DataJud como fontes, conforme os [termos oficiais de uso](https://datajud-wiki.cnj.jus.br/api-publica/termo-uso/). A API pode ficar indisponível, ter dados incompletos ou ser atualizada depois da consulta; confirme sempre as informações na fonte oficial. O usuário também deve observar o termo de uso da API, inclusive suas condições de finalidade e redistribuição.

## Referências técnicas

- Rota e validação: `routes/glossario.py`.
- Consulta externa, lista permitida de tribunais e filtragem da resposta: `services/datajud.py`.
- Formulário e apresentação segura com `textContent`: `templates/glossario.html` e `static/js/datajud.js`.
- Configuração local: `DATAJUD_API_KEY` em `.env` (não versionar o `.env`).
