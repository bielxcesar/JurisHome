# Autenticação em duas etapas (2FA)

## Como funciona

O JurisHome usa senha e um código TOTP de seis dígitos. No cadastro, o servidor gera o segredo e um QR Code. A pessoa lê o QR Code com um aplicativo autenticador e informa o primeiro código para ativar a conta. O QR Code é gerado localmente; não há serviço remoto de QR Code.

O autenticador guarda o segredo e gera os códigos no próprio dispositivo. O servidor valida o código correspondente. Essa integração segue o formato `otpauth://` e o padrão [RFC 6238](https://www.rfc-editor.org/rfc/rfc6238); não é uma chamada a uma API externa.

## Componentes

| Componente | Uso |
| --- | --- |
| FastAPI | Rotas HTTP para cadastro, login, ativação e validação do 2FA. |
| PyOTP (`pyotp==2.9.0`) | Geração do segredo e validação dos códigos. |
| `qrcode[pil]==8.2` | Geração local do QR Code em PNG. |
| Fernet (`cryptography`) | Cifragem do segredo TOTP antes de gravá-lo no banco. |
| Aplicativo autenticador | Guarda o segredo e gera códigos TOTP sem precisar de conexão com a Internet. |

As dependências estão em `requirements.txt`. Instale-as no mesmo ambiente Python que executa o Uvicorn:

```bash
python -m pip install -r requirements.txt
```

## Parâmetros

- Segredo Base32 exclusivo para cada conta.
- Código de seis dígitos, com período de 30 segundos e algoritmo SHA-1, conforme os padrões do PyOTP.
- Emissor exibido no aplicativo: `JurisHome`; identificador: e-mail da conta.
- O servidor aceita até dois períodos de diferença para compensar o relógio do dispositivo. Mantenha data e hora automáticas ativadas no celular.

## Cadastro e ativação

`POST /api/auth/cadastro` cria a conta e inicia a configuração obrigatória do autenticador.

Exemplo de requisição:

```json
{
  "nome": "Nome da pessoa",
  "email": "aluno@exemplo.com",
  "senha": "SenhaSegura123",
  "confirmar_senha": "SenhaSegura123",
  "consentimento_lgpd": true
}
```

Os valores acima são ilustrativos. A resposta `201 Created` contém `configuracao_token`, `segredo` e `qr_code`. Trate esses campos como credenciais: não os registre em logs nem os compartilhe. O QR Code é uma imagem PNG codificada em Data URI; a tela também mostra a chave manual.

Depois de cadastrar a conta no aplicativo, confirme o primeiro código em `POST /api/auth/2fa/ativar-cadastro`:

```json
{
  "desafio_token": "<configuracao_token recebido no cadastro>",
  "codigo": "123456",
  "lembrar_conectado": false
}
```

O código deve ser enviado como texto com seis dígitos. Em caso de sucesso, a conta é ativada e o servidor define o cookie `jurishome_access_token`.

## Login

1. `POST /api/auth/login` recebe e-mail e senha. Se estiverem corretos, retorna um `desafio_token` temporário; a sessão ainda não está autenticada.
2. `POST /api/auth/2fa/validar` recebe esse token e o código atual do autenticador. Em caso de sucesso, libera a sessão.

O desafio do login expira em cinco minutos. A sessão dura 30 minutos, ou 14 dias quando `lembrar_conectado` é `true`. O cookie é `HttpOnly` e usa `SameSite=Lax`; configure `COOKIE_SECURE=true` quando a aplicação estiver servida por HTTPS.

## Recuperação de senha

A recuperação confirma a identidade pelo código TOTP e não envia e-mail:

1. `POST /api/auth/recuperacao/iniciar` recebe o e-mail e retorna um desafio com mensagem neutra.
2. `POST /api/auth/recuperacao/validar` recebe o e-mail, o desafio e o código TOTP. Se forem válidos, retorna `token_redefinicao`.
3. `POST /api/auth/recuperacao/alterar` recebe o token e a nova senha com sua confirmação.

O desafio expira em dez minutos; o token para alterar a senha, em cinco minutos.

## Erros e bloqueio

| HTTP | Situação |
| --- | --- |
| `400` | Código inválido durante a ativação inicial ou senhas diferentes. |
| `401` | Credenciais, código ou desafio inválidos ou expirados. |
| `409` | E-mail já cadastrado. |
| `422` | Requisição inválida; o código deve ter seis dígitos. |
| `423` | Conta temporariamente bloqueada após tentativas inválidas. |
| `503` | Dependência de 2FA ou criptografia indisponível, ou segredo impossível de decifrar. |

Após cinco tentativas inválidas, a conta fica bloqueada por 15 minutos. As operações de autenticação são registradas na auditoria sem incluir senha, segredo TOTP ou código de verificação.

## Proteção do segredo

O segredo é cifrado antes de ser gravado. A chave Fernet é derivada da variável `JurisHome_senha`; mantenha essa chave privada e estável. Se trocar o valor, os segredos já salvos não poderão ser decifrados. Todas as instâncias que compartilham o banco precisam usar a mesma chave.

Use HTTPS em produção. Durante a configuração, o navegador recebe o segredo ou o QR Code para cadastrá-lo no autenticador. Não coloque tokens em URLs, logs ou armazenamento persistente do navegador.

## Limitação conhecida

O servidor aceita o mesmo código TOTP mais de uma vez durante o período em que ele é válido. O projeto não grava o último período aceito para impedir reutilização. Essa limitação deve ser considerada antes de usar o sistema com contas reais.

## Código relacionado

- `routes/auth.py`: cadastro, validação do TOTP e recuperação de senha.
- `auth/security.py`: tokens, hash de senha e cifragem do segredo.
- `templates/2fatores.html` e `static/js/auth.js`: tela e chamadas da interface.
- `tests/test_autenticacao.py` e `tests/test_security.py`: testes do fluxo.

Consulte também a [documentação oficial do PyOTP](https://pyauth.github.io/pyotp/).
