# JurisHome

Aplicação web acadêmica para consultar conteúdos jurídicos, pesquisar no acervo, navegar por categorias e usar um glossário. O sistema tem cadastro de estudantes, autenticação em duas etapas e um painel administrativo para feedbacks e auditoria.

## O que funciona

- Cadastro de estudante e login com senha e código de aplicativo autenticador (TOTP).
- Pesquisa, filtros, listagem de matérias aprovadas e glossário jurídico.
- Consulta opcional de instituição pelo código e-MEC.
- Envio de feedback pelo estudante; resposta e organização dos atendimentos pelo administrador.
- Consulta dos registros de auditoria pelo administrador.

O projeto não tem tela para cadastrar ou editar matérias, não envia e-mail para recuperação de senha, não oferece login Google e não faz upload de imagens para o Cloudinary. A recuperação de senha confirma o código do autenticador. A consulta e-MEC depende de serviços externos.

## Requisitos

- Python 3.11 recomendado. Python 3.12 ou superior também é aceito; nessa versão a consulta de instituição usa diretamente a API pública do CAU/BR.
- Git e conexão com a Internet para baixar o projeto e as dependências.

## Executar no Windows

No PowerShell:

```powershell
git clone https://github.com/bielxcesar/JurisHome.git
cd JurisHome

py -3.11 -m venv venv

.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt

.\venv\Scripts\python.exe setup_local.py

.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

Abra http://127.0.0.1:8000. A documentação interativa da API fica em http://127.0.0.1:8000/docs.

## Executar no Linux ou macOS

```bash
git clone https://github.com/bielxcesar/JurisHome.git
cd JurisHome
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python setup_local.py
python -m uvicorn main:app --reload
```

## Banco de dados

Por padrão, `setup_local.py` cria um `.env` com uma chave aleatória e configura o SQLite em `jurishome_local.db`. O arquivo `.env` não é sobrescrito se já existir. As tabelas são criadas ao iniciar a aplicação; o projeto não usa Alembic e não atualiza automaticamente tabelas existentes.

PostgreSQL é opcional. Instale e inicie o serviço, crie o banco e altere `DATABASE_URL` no `.env`:

```powershell
psql -U postgres -c "CREATE DATABASE juris_home;"
```

Use `postgresql+psycopg2://postgres:SUA_SENHA@localhost:5432/juris_home` como valor de `DATABASE_URL` e reinicie o servidor. Não execute `seed.py` em PostgreSQL: o script aceita apenas SQLite.

## Contas e conteúdo de demonstração

O projeto não cria uma senha administrativa padrão. Com o ambiente virtual ativado, execute:

```powershell
.\venv\Scripts\python.exe criar_admin.py
```

No Linux/macOS, execute `python criar_admin.py` com o ambiente virtual ativado.
Informe o e-mail e a senha quando solicitado. No primeiro login, configure o aplicativo autenticador e confirme o código. Para testar o perfil de estudante, crie uma conta pela tela de cadastro.

Opcionalmente, execute o seed para inserir três matérias e dois feedbacks fictícios identificados como demonstração. No Windows:

```powershell
.\venv\Scripts\python.exe seed.py
```

No Linux/macOS, com o ambiente virtual ativado, use `python seed.py`. O script pode ser repetido sem duplicar esses registros.

## Testes

Com o ambiente virtual ativado:

```bash
python -m unittest discover -s tests -v
python -m pip check
```

No Windows, use `venv\Scripts\python.exe` no lugar de `python`.

## Observações

- A consulta e-MEC precisa de Internet. Se os serviços externos estiverem indisponíveis, o cadastro continua sem preencher a instituição.
- Os registros do seed são fictícios e não devem ser apresentados como notícia, lei, decisão judicial ou orientação jurídica real.
- A retenção de dados é executada manualmente por `python manutencao_lgpd.py`; para aplicar alterações, use `python manutencao_lgpd.py --executar` após revisar o resultado.
- O funcionamento com PostgreSQL deve ser testado em uma instalação com esse serviço disponível. O caminho local recomendado para demonstração usa SQLite.

## Equipe

- Pedro Henrique Harada Pecegueiro — [GitHub](https://github.com/Pedro-Pecegueiro)
- Erick Santos Barbosa — [GitHub](https://github.com/ErickSantosBarbosa04)
- Gabriel Agustín Fernández Alves — [GitHub](https://github.com/bielxcesar)
