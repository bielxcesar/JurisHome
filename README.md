<div align="center">

# ⚖️ JurisHome

**Plataforma Web para Centralização, Curadoria e Pesquisa de Conteúdo Jurídico**

  <img alt="Python 3.12" src="https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img alt="SQLAlchemy" src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white"/>
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white"/>
  <img alt="Tailwind CSS" src="https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white"/>
  <img alt="Swagger" src="https://img.shields.io/badge/Swagger-85EA2D?style=for-the-badge&logo=swagger&logoColor=black"/>
  <img alt="Railway" src="https://img.shields.io/badge/Railway-131415?style=for-the-badge&logo=railway&logoColor=white"/>

</div>

<br/>

## 📌 Sobre o Projeto

O JurisHome é uma plataforma web criada para facilitar o acesso a conteúdos jurídicos confiáveis, oferecendo aos estudantes uma experiência de consulta e aprendizado mais simples, organizada e segura.

O sistema foi concebido para resolver a alta dispersão de informações na rotina acadêmica dos estudantes de Direito, oferecendo um ambiente centralizado com fontes verificadas, linguagem didática e categorização por áreas do conhecimento jurídico.

---

## 🚀 Principais Funcionalidades

- 🔒 **Autenticação Segura & Múltiplos Perfis**: Cadastro com distinção entre **Estudantes** e **Administradores**, suporte a login via Google OAuth 2.0 e segundo fator de autenticação (2FA/TOTP).
- 🛡️ **Curadoria de Conteúdo**: Sistema de aprovação em etapas — matérias submetidas passam pelo status `EM_ANALISE` antes de ficarem visíveis publicamente.
- 📚 **Acervo Organizado**: Navegação e busca inteligente por Doutrinas, Legislações e Acórdãos divididos por **Categorias** (ex: Direito Penal) e **Subtemas**.
- 📖 Glossário Jurídico: Consulta de termos jurídicos em linguagem simples, com busca, filtro por letra inicial, exemplos práticos e referências oficiais para apoiar estudantes iniciantes.
- 🖼️ **Otimização de Mídias**: Integração com Cloudinary CDN para armazenamento de imagens, mantendo o banco de dados leve.
- 💬 **Canal de Feedback**: Envio direto de dúvidas, sugestões e relatórios de uso pelos alunos.

---

## 🛠️ Arquitetura e Tecnologias

A aplicação segue uma **Arquitetura Monolítica em Camadas** no Back-end, separando Apresentação, Lógica de Negócio e Persistência de Dados.

- **Back-end**: Python 3.12, FastAPI, SQLAlchemy (ORM), PyJWT, Bcrypt.
- **Front-end**: HTML5, JavaScript (SPA), Tailwind CSS.
- **Banco de Dados**: PostgreSQL (Hospedado no Railway).
- **Serviços de Terceiros**: Google OAuth 2.0, Cloudinary (CDN).
- **Infraestrutura & Gestão**: Git/GitHub, Railway, Figma, Jira, Swagger UI.

---

<details>
 <summary><b>🔍 Clique para ler Problemática é Solução</b></summary>

## 📄 Problemática é Solução

Estudar Direito exige pesquisa constante. Seja para preparar aulas, montar peças práticas ou acompanhar alterações legislativas, os estudantes perdem horas valiosas navegando por múltiplos portais sem garantia da veracidade ou atualização do conteúdo.

Em pesquisa realizada com acadêmicos de Direito, evidenciou-se a frustração com o excesso de abas abertas, o vocabulário excessivamente rebuscado para iniciantes e layouts confusos. O **JurisHome** nasce para unificar e traduzir esse acervo de forma fluida e confiável.

</details>

---

## 💻 Como Executar o Projeto Localmente


### Pré-requisitos
- **Python 3.12+** instalado.
- Git instalado.

### Passo a Passo

**Clone o repositório:**
```bash
git clone https://github.com/bielxcesar/JurisHome.git
cd JurisHome
```

**Crie e ative o ambiente virtual no Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**No Linux ou macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Instale as dependências:**
```bash
pip install -r requirements.txt
```

**Configure o ambiente local:**

Crie um arquivo `.env` na raiz do projeto. `JurisHome_senha` é obrigatória;
sem `DATABASE_URL`, a aplicação usa automaticamente o SQLite local.

```dotenv
JurisHome_senha=troque-por-uma-chave-local-segura
# DATABASE_URL=postgresql://usuario:senha@localhost:5432/jurishome
# CLOUDINARY_URL=sua_url_cloudinary
```

**Carregue as matérias e categorias de demonstração:**
```bash
python seed.py
```

O seed pode ser executado novamente sem duplicar os três conteúdos demonstrativos.

**Inicie o servidor local:**
```bash
python -m uvicorn main:app --reload
```

---

<details>
  
   <summary><b>👥Desenvolvedores</b></summary>

## Projeto desenvolvido por:
- **Pedro Henrique Harada Pecegueiro** — [GitHub](https://github.com/Diego251Fagundes)
- **Erick Santos Barbosa** — [GitHub](https://github.com/ErickSantosBarbosa04)
- **Gabriel Agustín Fernández Alves** — [GitHub](https://github.com/Pedro-Pecegueiro)
</details>



