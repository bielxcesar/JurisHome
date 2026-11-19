<div align="center">

# ⚖️ JurisHome

**Plataforma acadêmica para consulta, curadoria e pesquisa de conteúdo jurídico**

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/) 
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) 
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/) 
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)

</div>

## 📌 Sobre o projeto

O **JurisHome** é uma plataforma web desenvolvido para ser a casa de estudo do pessoal de DIREITO

A plataforma centraliza informações jurídicas confiáveis em um ambiente organizado para estudantes, com navegação por áreas do Direito, matérias curadas, glossário, consulta legislativa, gamificação e recursos educacionais.

## 🌐 Aplicação hospedada

**Repositório:** https://github.com/bielxcesar/JurisHome

**Acesse a aplicação:** https://jurishome.up.railway.app/


## ✨ Funcionalidades

- Cadastro e autenticação de usuários com suporte a 2FA/TOTP.
- Perfis separados para estudantes e administradores.
- Navegação e pesquisa de matérias por categoria e status.
- Cadastro editorial de matérias em quatro etapas.
- Aprovação administrativa de matérias e controle por administrador principal.
- Glossário jurídico com busca, exemplos e referências.
- Consulta de legislação por meio da integração com a API do Senado Federal.
- Canal de feedback com respostas administrativas.
- Históricos de atividade e registros de auditoria.
- Juridle diário com questões do glossário.
- Área recreativa com curiosidades jurídicas.
- Perfil editável com foto, instituição e área de interesse.
- Recursos voltados à privacidade e à LGPD.
- Páginas de erro padronizadas e proteção contra acessos indevidos.

## 🛠️ Tecnologias

| Tecnologia | Uso no projeto |
|---|---|
| Python 3 | Linguagem principal |
| FastAPI | API e gerenciamento das rotas |
| SQLAlchemy | Integração e modelagem do banco de dados |
| PostgreSQL | Banco de dados de produção |
| SQLite | Base utilizada nos testes |
| Jinja2 | Renderização das páginas HTML |
| HTML, CSS e JavaScript | Interface e interações no navegador |
| JWT | Sessões de autenticação |
| TOTP / PyOTP | Segundo fator de autenticação |

## 📁 Estrutura principal

```text
JurisHome/
├── auth/          # Segurança e autenticação
├── data/          # Dados utilizados pela aplicação
├── docs/          # Integrações e documentação técnica
├── model/         # Modelos SQLAlchemy
├── routes/        # Rotas da aplicação
├── services/      # Regras de negócio e serviços
├── static/        # CSS, JavaScript e imagens
├── templates/     # Páginas Jinja2
├── tests/         # Testes automatizados
├── main.py        # Inicialização da aplicação
├── database.py    # Configuração do banco principal
└── requirements.txt
```

## 🚀 Executando localmente

### Pré-requisitos

- Python 3.11 ou superior
- Git
- PostgreSQL, ou SQLite para desenvolvimento/testes

### 1. Clonar o repositório

```bash
git clone https://github.com/bielxcesar/JurisHome.git
cd JurisHome
```

### 2. Criar o ambiente virtual

**Windows — PowerShell:**

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux ou macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar as dependências

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configurar as variáveis de ambiente

Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

No Windows, use:

```powershell
Copy-Item .env.example .env
```

Configure no `.env`:

```dotenv
DATABASE_URL=
JurisHome_senha=
TOTP_ENCRYPTION_KEY=
COOKIE_SECURE=false
PUBLIC_ORIGIN=http://localhost:8000
```

- `DATABASE_URL`: URL do banco PostgreSQL ou SQLite.
- `JurisHome_senha`: chave usada pela aplicação.
- `TOTP_ENCRYPTION_KEY`: chave para proteger os dados do autenticador.
- `COOKIE_SECURE`: use `true` somente quando o site estiver em HTTPS.
- `PUBLIC_ORIGIN`: URL pública ou local exata da aplicação.

Nunca envie chaves reais ou credenciais para o repositório.

### 5. Criar o primeiro administrador

```bash
python criar_admin.py
```

Informe nome, e-mail e senha. A primeira conta criada será o administrador principal (`root`).

### 6. Iniciar o servidor

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Acesse:

- Aplicação: http://127.0.0.1:8000
- Swagger administrativo: http://127.0.0.1:8000/docs

A documentação Swagger é restrita a administradores.

## 🧪 Testes

Os testes usam SQLite em memória e não dependem do banco utilizado pela aplicação.

**Windows — PowerShell:**

```powershell
$env:DATABASE_URL = 'sqlite://'
Remove-Item Env:FEEDBACK_DATABASE_URL -ErrorAction SilentlyContinue
python -m unittest discover -s tests -v
```

**Linux ou macOS:**

```bash
DATABASE_URL='sqlite://' python -m unittest discover -s tests -v
```

## 🔐 Segurança

O projeto inclui controles como:

- Senhas armazenadas com hash bcrypt.
- Autenticação por JWT em cookies HttpOnly.
- Segundo fator de autenticação TOTP.
- Proteção contra origem cruzada em operações de escrita.
- Limitação de tentativas de autenticação e cadastro.
- Validação e limite de tamanho das entradas HTTP.
- Consultas SQLAlchemy com parâmetros vinculados.
- Cabeçalhos de segurança, HSTS em produção HTTPS e tratamento padronizado de erros.
- Controle de permissões entre usuários, suporte administrativo e administrador principal.

## ⚖️ Privacidade e LGPD

A documentação da rotina de dados e privacidade está disponível em [`docs/lgpd/`](docs/lgpd/).

Ela contém o inventário de dados, bases de tratamento, retenção, direitos dos titulares, fornecedores e procedimentos operacionais. Consultá-la e revisá-la sempre que telas, integrações ou serviços de hospedagem forem alterados.

## 📚 Documentação adicional

- [`docs/INTEGRACAO_API_SENADO.md`](docs/INTEGRACAO_API_SENADO.md)
- [`docs/INTEGRACAO_API_2FA.md`](docs/INTEGRACAO_API_2FA.md)
- [`docs/REFATORACAO_SEGURANCA.md`](docs/REFATORACAO_SEGURANCA.md)
- [`docs/lgpd/`](docs/lgpd/)

## 👥 Equipe

- [Pedro Henrique Harada Pecegueiro](https://github.com/Pedro-Pecegueiro)
- [Erick Santos Barbosa](https://github.com/ErickSantosBarbosa04)
- [Gabriel Agustín Fernández Alves](https://github.com/bielxcesar)
