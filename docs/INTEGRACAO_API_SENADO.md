# Integração com a API de Dados Abertos do Senado Federal

## Objetivo

O Glossário permite consultar dados básicos de uma lei federal ou lei complementar informando o tipo da norma, o número e o ano. A consulta complementa o catálogo de termos jurídicos do JurisHome e apresenta a ementa e, quando a fonte retorna o endereço, um link para o texto oficial.

A API é mantida pelo Senado Federal, tem acesso público e oferece respostas em JSON e XML. A documentação oficial está em [Dados Abertos Legislativos — Senado Federal](https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html).

## Fluxo no JurisHome

1. O usuário informa o tipo (Lei ou Lei Complementar), o número e o ano na página `/glossario`.
2. O navegador envia esses três campos em JSON para `POST /api/glossario/legislacao`.
3. O backend valida os valores e consulta a lista de normas no Senado:

   ```text
   GET https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=LEI&numero=13105&ano=2015
   ```

4. Se a lista contiver uma norma, o backend usa o identificador retornado para consultar seus detalhes:

   ```text
   GET https://legis.senado.leg.br/dadosabertos/legislacao/{id}.json
   ```

5. O backend devolve ao navegador os campos necessários para mostrar a identificação da norma, sua ementa, a data de assinatura e o link oficial, quando disponível.

O navegador não acessa diretamente o serviço do Senado. A chamada externa é feita pelo backend, em `services/legislacao_senado.py`, e a interface é controlada por `static/js/legislacao-senado.js`.

## Campos e validação

- `tipo`: `LEI` ou `LCP` (lei complementar).
- `numero`: de um a oito algarismos.
- `ano`: número entre 1800 e 2100.

O backend limita o host externo ao domínio oficial do Senado, usa HTTPS, aguarda no máximo 12 segundos por resposta e lê no máximo 1 MB por chamada. Não encaminha nome, e-mail, identificador de conta ou sessão à API.

## Exemplo de chamada interna

```http
POST /api/glossario/legislacao
Content-Type: application/json

{
  "tipo": "LEI",
  "numero": "13105",
  "ano": 2015
}
```

Exemplo de resposta resumida:

```json
{
  "encontrado": true,
  "norma": {
    "nome": "Lei nº 13.105 de 16/03/2015",
    "tipo": "LEI-n",
    "numero": "13105",
    "ano": "2015",
    "ementa": "Código de Processo Civil.",
    "data_assinatura": "16/03/2015",
    "apelido": "...",
    "url_documento": "https://normas.leg.br/?urn=urn:lex:br:federal:lei:2015-03-16;13105"
  },
  "fonte": "Dados Abertos do Senado Federal",
  "fonte_url": "https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html"
}
```

Os dados apresentados são normalizados a partir de `ListaDocumento.documentos.documento` e, na consulta de detalhes, `DetalheDocumento.documentos.documento[].identificacao`. O link exibido só é aceito quando usa HTTPS e o domínio `normas.leg.br`.

## Respostas e indisponibilidade

- Se a norma não for localizada, a API interna responde com `encontrado: false`; a interface orienta conferir tipo, número e ano.
- Valores inválidos são recusados com HTTP 422.
- Se a busca no Senado falhar, exceder o tempo limite ou retornar uma resposta inválida, o backend responde HTTP 503 com uma mensagem simples.
- Se a busca funcionar, mas a consulta opcional de detalhes falhar, ainda são exibidos os dados da lista; o link oficial pode ficar indisponível.

A documentação do Senado informa que a API aplica limites de requisição e que períodos de alta demanda podem causar respostas HTTP 503. Por isso, o JurisHome mostra uma mensagem de indisponibilidade e permite tentar novamente; não armazena uma cópia dos resultados.

## Persistência e dados enviados

A busca é transitória: o JurisHome não salva os parâmetros nem os resultados em tabelas. A API externa recebe somente tipo, número e ano da norma. Nenhum dado de cadastro é necessário para a consulta.

O catálogo local do Glossário é mantido em `data/glossario.json`. Ele contém definições, exemplos e referências; a pesquisa desse catálogo funciona sem depender da conexão externa. A API do Senado é usada apenas pelo formulário separado de consulta de legislação.

## Como consultar manualmente

Com o projeto em execução, abra `http://127.0.0.1:8000/glossario` e informe, por exemplo:

- Tipo: **Lei**
- Número: **13105**
- Ano: **2015**

O resultado deve identificar o Código de Processo Civil. Consulte o link oficial para ler a norma e conferir sua redação vigente. A disponibilidade e os dados atuais são responsabilidade da fonte oficial.

## Arquivos relacionados

- `routes/glossario.py`: validação e rota interna `POST /api/glossario/legislacao`.
- `services/legislacao_senado.py`: chamadas HTTP, leitura da resposta e tratamento de falhas.
- `templates/glossario.html`: formulário e campos de resultado.
- `static/js/legislacao-senado.js`: envio do formulário e exibição segura dos dados.
- `data/glossario.json`: catálogo de termos mantido pelo JurisHome.
