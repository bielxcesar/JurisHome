<div align="center">

# ⚖️ JurisHome

**Plataforma Web Acadêmica para Consulta, Curadoria e Pesquisa de Conteúdo Jurídico**

  <img alt="Python 3.12" src="https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img alt="SQLAlchemy" src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white"/>
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white"/>
  <img alt="Tailwind CSS" src="https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white"/>
  <img alt="Swagger" src="https://img.shields.io/badge/Swagger-85EA2D?style=for-the-badge&logo=swagger&logoColor=black"/>

</div>

<br/>

## 📌 Sobre o Projeto

O **JurisHome** é uma plataforma web desenvolvida como **Projeto de Final de Curso (PFC)** do bacharelado em **Engenharia de Software** da **Universidade de Mogi das Cruzes (UMC)**. 

O sistema foi concebido para resolver a alta dispersão de informações na rotina acadêmica dos estudantes de Direito, oferecendo um ambiente centralizado com fontes verificadas, linguagem didática e categorização por áreas do conhecimento jurídico.

<details>
 <summary><b>🔍 Clique para ler sobre a Problemática e Solução</b></summary>

Estudar Direito exige pesquisa constante. Seja para preparar aulas, montar peças práticas ou acompanhar alterações legislativas, os estudantes perdem horas valiosas navegando por múltiplos portais sem garantia da veracidade ou atualização do conteúdo.

Em pesquisa realizada com acadêmicos, evidenciou-se a frustração com o excesso de abas abertas, o vocabulário excessivamente rebuscado para iniciantes e layouts confusos. O **JurisHome** nasce para unificar e traduzir esse acervo de forma fluida e confiável.
</details>

---

## 🚀 Funcionalidades Entregues

- 🔒 **Autenticação Segura & Múltiplos Perfis**: Cadastro de estudantes, login com senha e segundo fator de autenticação por aplicativo (2FA/TOTP).
- 📚 **Acervo Organizado & Pesquisa**: Navegação, filtros e listagem de matérias aprovadas.
- 📖 **Glossário Jurídico (Funcionalidade 4)**: Página dedicada com 25 termos introdutórios, explicações simples, exemplos e referências legais (CPC e CF). A busca é inteligente (ignora acentos e maiúsculas) e funciona mesmo sem JavaScript.
- 🏛️ **Integração e-MEC**: Consulta opcional da instituição de ensino pelo código e-MEC (usando a API pública do CAU/BR).
- 💬 **Canal de Feedback e Auditoria**: Envio de dúvidas e sugestões pelos alunos, com painel administrativo para respostas, organização de atendimentos e consulta de registros de auditoria.
- 🛡️ **Privacidade (LGPD)**: Rotina de retenção e manutenção de dados disponível no sistema.

*Nota sobre o escopo:* Nesta versão de entrega, as funções de cadastro/edição de novas matérias, recuperação de senha por e-mail, login via Google e upload de imagens (Cloudinary) não estão ativas na interface.

---

## 💻 Como Executar o Projeto Localmente

**Pré-requisitos:**
- Python 3.11 ou superior.
- Git e conexão com a internet.

### Passo 1: Baixar e Preparar o Ambiente

No seu terminal, baixe o projeto e entre na pasta:
```bash
git clone [https://github.com/bielxcesar/JurisHome.git](https://github.com/bielxcesar/JurisHome.git)
cd JurisHome
```
Crie o ambiente virtual e ative:

Windows (PowerShell):
```bash
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
```
Linux ou macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```
### Passo 2: Instalação e Configuração
Instale as dependências necessárias:
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
Rode o arquivo de configuração. Ele criará automaticamente o seu arquivo .env com uma chave segura e preparará o banco de dados local (SQLite):
```bash
python setup_local.py
```

### Passo 3: Criar Contas e Dados de Teste
O projeto não vem com uma senha administrativa padrão. Para criar o seu acesso de Administrador, rode:
```bash
python criar_admin.py
```

(Informe o e-mail e a senha desejada. No primeiro login, o sistema pedirá para configurar o aplicativo autenticador).

Para carregar os 25 termos do glossário, 3 matérias e feedbacks de demonstração para não começar com a plataforma vazia, rode o alimentador:
```bash
python seed.py
```

### Passo 4: Iniciar o Servidor
```bash
python -m uvicorn main:app --reload
```
Acesse http://127.0.0.1:8000 no seu navegador. A documentação interativa da API (Swagger) fica em http://127.0.0.1:8000/docs.

---

### Banco de Dados (Avançado)
Por padrão, o projeto roda perfeitamente em SQLite (jurishome_local.db). Caso deseje utilizar o PostgreSQL, crie o banco manualmente no seu serviço local, abra o arquivo .env gerado e altere a linha do banco para o formato:
DATABASE_URL=postgresql+psycopg2://postgres:SUA_SENHA@localhost:5432/juris_home
(Atenção: O script seed.py foi feito apenas para alimentar o banco local SQLite).



### Validação e Testes
Para rodar a bateria de testes automatizados do sistema, certifique-se de que o ambiente virtual está ativo e execute:
```bash
python -m unittest discover -s tests -v
```

## Equipe

- Pedro Henrique Harada Pecegueiro — [GitHub](https://github.com/Pedro-Pecegueiro)
- Erick Santos Barbosa — [GitHub](https://github.com/ErickSantosBarbosa04)
- Gabriel Agustín Fernández Alves — [GitHub](https://github.com/bielxcesar)
