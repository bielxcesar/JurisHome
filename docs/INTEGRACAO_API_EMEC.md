# Integração com o e-MEC

## Objetivo

No cadastro do JurisHome, o usuário pode informar o código e-MEC de uma instituição de ensino. O sistema consulta esse código e mostra os dados encontrados antes da criação da conta.

Essa consulta é opcional. O resultado serve apenas para conferir a instituição e não é salvo automaticamente no perfil.

## Rota utilizada

```http
GET /api/universidades/emec/{codigo_emec}
```

O código deve ser um número inteiro maior que zero. Na tela de cadastro, o campo aceita até dez dígitos.

Exemplo com a aplicação local:

```http
GET http://127.0.0.1:8000/api/universidades/emec/521
```

A rota pode ser usada antes do login porque faz parte do cadastro.

## Como a consulta funciona

O backend tenta consultar os dados pelo pacote `emec-api`. Se essa fonte estiver indisponível ou não devolver uma instituição, o sistema tenta a API pública de Instituições de Ensino Superior do CAU/BR.

Endereço usado na segunda consulta:

```text
https://gisserver.caubr.gov.br/server/rest/services/CEF_IES_PUBLICO_2022/FeatureServer/0/query
```

A API do CAU/BR recebe o código e-MEC e devolve os dados da instituição em JSON. O JurisHome seleciona os campos necessários e entrega uma resposta no mesmo formato, independentemente da fonte que respondeu.

## Dados enviados

A consulta envia somente o código e-MEC digitado. Nome, e-mail, senha, código do autenticador e outros dados da conta não são enviados.

Na fonte de contingência, o sistema solicita estes campos:

```text
ies_cdg_mec_ies, ies_nome, ies_sigla, ies_campus,
ies_municipio, ies_uf, curso_situacao
```

As coordenadas geográficas não são solicitadas.

## Resposta

Formato ilustrativo de resposta (os valores abaixo não são o resultado de uma consulta real):

```json
{
  "codigo_emec": 123,
  "nome": "NOME DA INSTITUIÇÃO",
  "sigla": "SIGLA",
  "situacao": "SITUAÇÃO INFORMADA PELA FONTE",
  "campus": [
    {
      "codigo": "CODIGO_DO_CAMPUS",
      "cidade": "CIDADE",
      "uf": "UF"
    }
  ],
  "fonte": "FONTE QUE RESPONDEU À CONSULTA"
}
```

O campo `fonte` permite identificar qual serviço respondeu. A resposta apresenta no máximo vinte campi.

## Possíveis erros

| Código | Motivo |
| --- | --- |
| `200` | A instituição foi encontrada. |
| `422` | O código está ausente, não é numérico ou é menor que 1. |
| `503` | As fontes externas não responderam ou não localizaram a instituição. |

A consulta ao CAU/BR possui limite de dez segundos. Se o serviço externo estiver fora do ar, o usuário ainda pode continuar o cadastro sem consultar a instituição.

## Arquivos relacionados

- `routes/auth.py`: consulta das fontes e montagem da resposta;
- `templates/cadastro.html`: campo do código e-MEC;
- `static/js/auth.js`: chamada ao endpoint e exibição do resultado;
- `requirements.txt`: dependência `emec-api` usada no Python 3.11;
- `tests/test_autenticacao.py`: testes da integração.

## Como testar

Com o servidor em execução, a rota pode ser chamada pela tela de cadastro ou pela documentação do FastAPI:

```text
http://127.0.0.1:8000/docs
```

Para executar os testes automatizados:

```bash
python -m unittest discover -s tests -v
```

O teste pela tela precisa de conexão com a Internet. O JurisHome não mantém uma lista local de instituições nem cria uma resposta fictícia quando os serviços externos falham.

## Privacidade

O código consultado não é salvo em uma tabela própria. Se a fonte externa, os campos enviados ou o uso dessa informação forem alterados, esta documentação e a Política de Privacidade também deverão ser revisadas.
