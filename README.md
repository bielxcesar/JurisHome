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

*Nota sobre o escopo:* O cadastro de matérias está disponível na área administrativa. As imagens são reduzidas no navegador, convertidas para JPEG e codificadas em Base64; o backend recebe o JSON e armazena as imagens em campos de texto do banco. A publicação depende de aprovação do administrador principal. Login via Google e recuperação de senha por e-mail não estão implementados; a recuperação atual usa o aplicativo autenticador.

### Como funciona o cadastro de matéria

1. O administrador abre `/nova-materia` e segue quatro etapas: chamada da Home; texto da matéria; imagens e créditos; revisão final. Pode usar um título curto na Home e outro título na leitura. Os campos são mantidos ao avançar e voltar entre as etapas.
2. O navegador reduz as imagens para até 800 × 800 pixels, preservando a proporção, e gera JPEG com qualidade 0,7. O resultado é codificado como Data URL em Base64 e enviado em JSON para `/criar-materia`.
3. O backend verifica o acesso administrativo, a existência da categoria e o conteúdo real das imagens. Aceita JPEG, PNG ou WebP, limita cada imagem a 1 MB decodificado e 16 milhões de pixels de entrada, e normaliza o resultado para JPEG de até 800 × 800 pixels antes de persistir nos campos de texto do conteúdo.
4. A matéria é vinculada ao administrador autenticado e salva com status `em_analise`. Apenas o administrador principal pode aprová-la; a listagem pública retorna somente conteúdos aprovados.

A prévia da revisão é renderizada pelo servidor em `/api/admin/materias/preview`, sem publicar nem gravar uma matéria. Usa a mesma formatação da leitura e é aberta pelo botão “Visualizar modelo completo” em uma nova aba, mantendo o cadastro na aba original. O passo 4 preserva também o cartão da chamada da Home. Base64 é uma codificação; a compactação ocorre na redução e conversão para JPEG. Créditos, legendas, descrições, largura e posição das imagens internas são persistidos em `conteudo_editorial`, junto da chamada da Home e das opções de formatação. O crédito da capa continua em `fonte_imagem`. Links de créditos aparecem com o domínio resumido, mantendo o endereço completo clicável e disponível no título do link.

As áreas do Direito são inicializadas automaticamente pelo catálogo em `services/categorias.py`, preservando categorias e identificadores existentes. Ao selecionar uma área, o formulário mostra suas tags predefinidas. O servidor inclui e salva essas tags mesmo quando elas não são enviadas pelo navegador; o preview usa a mesma configuração e a matéria exibe as tags ao final. A mudança de categoria na edição atualiza as tags automáticas e preserva as tags adicionais que não pertenciam ao conjunto anterior.

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


### Home e exploração do acervo

As páginas iniciais de administradores e estudantes usam o mesmo conteúdo editorial em `_home_conteudo.html`, com destaques, atalhos coloridos para categorias e cartões das publicações recentes. As categorias levam a `/categorias?categoria=...`, com o filtro já selecionado, e as matérias levam à página de leitura. O catálogo público de áreas está em `/api/categorias`.

O Canto recreativo oferece cartões compactos para Juridle e Curiosidades. O Juridle em `/juridle` tem rodadas reais de cinco perguntas do glossário: cada pergunta tem quatro alternativas, conferidas pelo servidor. Rodadas e respostas ficam em `juridle_rodadas`; repetir a mesma resposta não duplica pontos. Uma rodada ativa por conta pode ser retomada em até 24 horas. O nível começa em 1 e sobe a cada dez acertos; a sequência conta acertos consecutivos; a frequência conta dias seguidos com uma rodada concluída, no horário de Brasília; uma rodada perfeita concede uma coroa. Não há moedas ou ranking de pessoas.

A Home mostra “Em alta” com leituras reais dos últimos sete dias: no máximo uma leitura por estudante, matéria e dia; visitas administrativas não contam. As contagens começam com a implantação, sem histórico inventado. O espaço `/conhecimento` organiza atalhos de estudo, e `/curiosidades` reúne conceitos do glossário.

O cadastro de administradores está disponível em `/admin/tabela-noticias` somente para o administrador principal. Novas contas são de suporte, sem permissão de principal, e precisam configurar 2FA no primeiro acesso. Páginas exclusivas de outro perfil retornam 404, tanto para administradores quanto para leitores.

O leitor pode salvar nome, instituição, área de interesse e foto no perfil. Atendimentos permitem complementos do próprio autor, voltam à fila administrativa e aparecem em avisos na Home. Novos protocolos têm proteção contra envio repetido e limite de cinco por dez minutos por usuário.

Consulte [o acompanhamento do PFC](docs/PFC_ACOMPANHAMENTO.md) para prioridades, critérios de conclusão e roteiro de demonstração.


### Manutenção de administradores pelo root

Em **Tabelas / Notícias → Gestão de usuários**, somente o administrador principal vê **Editar** e **Excluir** nas contas administrativas de suporte. A edição abre uma página no estilo Perfil, com nome, e-mail, 2FA, sessões ativas e quantidade de matérias. É possível alterar nome/e-mail, definir nova senha, encerrar sessões e exigir nova configuração do autenticador. Alterações de e-mail, senha ou 2FA revogam as sessões anteriores; permissões de principal não podem ser alteradas por esse formulário.

Para excluir, o root precisa digitar o nome completo exatamente como exibido. O servidor valida novamente o nome e as permissões. A exclusão remove o acesso e a conta da listagem, limpa suas credenciais e preserva o identificador técnico em `administradores_excluidos`, mantendo as matérias e a auditoria. A conta principal não pode ser editada nem excluída por esse fluxo. As alterações são registradas na auditoria; senhas e segredos do autenticador não são enviados ao navegador.


### Regra de root único

O banco permite no máximo uma conta com `e_root_admin = true`, inclusive antes da ativação do 2FA. O índice único `uq_usuarios_root_unico` impede um segundo root por inserção, promoção ou gravações concorrentes. O script `criar_admin.py` cria o primeiro administrador como root. Quando já existe um root, cria as contas seguintes como administradores de suporte. O painel também cria somente administradores de suporte; o cadastro público cria somente leitores. Reexecutar o script com o e-mail do root não altera a conta existente.

Na inicialização, a aplicação instala/verifica o índice em bancos existentes e recusa iniciar se houver duplicidade legada. A autenticação também bloqueia privilégios root quando detecta mais de uma conta principal. A duplicidade não é corrigida escolhendo uma pessoa automaticamente.

Para corrigir uma base legada, identifique explicitamente o root legítimo e execute primeiro a simulação:

```powershell
python corrigir_root.py --email root@example.com
python corrigir_root.py --email root@example.com --aplicar
```

A aplicação rebaixa os outros roots, revoga suas sessões e registra a correção na auditoria, preservando contas e matérias. A correção e a instalação do índice ocorrem na mesma transação. SQLite e PostgreSQL usam índice de expressão; MySQL exige suporte a índices funcionais. Em um banco incompatível, a aplicação não inicia sem a proteção.


### Páginas de erro

Páginas inexistentes, acessos a telas de outro perfil e navegação em telas protegidas sem sessão válida retornam 404 com uma explicação genérica. A renovação de uma sessão com cookie de refresh continua disponível. As APIs preservam suas respostas JSON e códigos próprios; isso mantém o funcionamento de login, validação de formulários e tratamento de erros pelo frontend.

A página `erro.html` apresenta explicação e orientação para 400, 401, 403, 404, 405, 408, 409, 413, 422, 429, 500, 502, 503, 504 e 505. Falhas não tratadas retornam 500 sem stack trace, consulta SQL ou mensagens internas ao visitante. Uma referência de atendimento permite relacionar o erro ao registro técnico. A página não depende de CDN ou consulta ao banco, funciona sem JavaScript para voltar ao início e respeita o tema salvo.

Para conferir a apresentação, acesse `/erro/404`, `/erro/500` ou `/erro/505`. Esses endereços devolvem o código HTTP correspondente. Erros produzidos antes de a requisição chegar à aplicação (por exemplo, servidor desligado, negociação HTTP ou falha no proxy de hospedagem) precisam de tratamento no navegador ou na infraestrutura; a aplicação não consegue interceptá-los.


### Editor de matérias por etapas

O editor oferece negrito (`**texto**`), itálico (`_texto_`), destaque (`==texto==`), títulos de seção (`## título`), citações (`> texto`), listas (`- item`) e conversão da seleção para maiúsculas. A barra de ferramentas insere essas marcações no trecho selecionado. Cada linha não vazia representa um bloco; as imagens podem aparecer antes do texto (posição 0), depois de um bloco ou no final. O servidor escapa HTML e só produz os elementos permitidos pela formatação, sem executar HTML arbitrário enviado no corpo.

O cadastro novo mantém a etapa de análise e a aprovação pelo principal. Matérias antigas sem configuração editorial continuam sendo lidas como texto simples. A tabela adicional é criada na inicialização; não é necessário apagar ou recriar matérias existentes.

O envio exige o aceite explícito das regras editoriais (versão 2026-10-30): veracidade, imparcialidade, linguagem formal, privacidade, direitos de uso e revisão. A API recusa aceite ausente, falso ou com versão desatualizada, inclusive em chamadas diretas. O aceite é registrado na auditoria junto da conta, da matéria, da data e da versão, na mesma transação da criação. A prévia dispensa aceite e não grava conteúdo.
