# JurisHome — acompanhamento do PFC

Atualizado em 30/10/2026. As caixas marcadas indicam entregas implementadas e verificadas nesta revisão; os itens abertos são próximos passos.

## Urgente

- [x] Separar Home de administrador e leitor no servidor, inclusive nos endereços alternativos. Acesso a páginas de outro perfil retorna 404 sem revelar a tela protegida.
- [x] Implementar Juridle: cinco perguntas, quatro alternativas, explicações, fonte e histórico pessoal.
- [x] Persistir progresso por usuário e permitir retomar uma rodada em até 24 horas.
- [x] Contar sequência de acertos; um erro zera a sequência atual e preserva o recorde.
- [x] Contar frequência por dias consecutivos com rodada concluída, no horário de Brasília.
- [x] Conceder uma coroa ao acertar as cinco perguntas; nível 1 mais um nível a cada dez acertos.
- [x] Validar a resposta no backend, ocultar o gabarito futuro e impedir pontuação duplicada por repetição ou duas abas.

## Importante

- [x] Completar cadastro de administrador no painel: somente o principal cadastra; novas contas não são principais e exigem 2FA no primeiro acesso.
- [x] Aplicar navegação e padrão visual compartilhados ao leitor, preservando suas permissões.
- [x] Salvar instituição e área de interesse; enviar a foto pelo formulário; mostrar a data real de cadastro.
- [x] Permitir que o autor complemente seu atendimento, com retorno à fila e histórico.
- [x] Mostrar avisos de atendimentos na Home conforme o perfil.
- [x] Reduzir duplicidade e excesso de novos protocolos; cinco envios por dez minutos por conta.
- [x] Remover progresso e registros individuais de leitura durante a anonimização da conta.

## Médio

- [x] Manter categorias com explicações e atalhos, destaques panorâmicos, Canto recreativo e matérias recentes.
- [x] Acrescentar Em alta baseado em leituras reais de estudantes nos últimos sete dias.
- [x] Criar Espaço de conhecimento com uma trilha de glossário, categorias, curiosidades e prática.
- [ ] Publicar mais matérias reais, revisadas e com créditos de imagens. O layout não cria conteúdo editorial nem contagens fictícias.
- [ ] Validar a experiência com colegas e registrar os resultados no relatório do PFC.

## Suave

- [ ] Revisar microtextos, imagens, contrastes e navegação com usuários.
- [ ] Ampliar e revisar pedagogicamente o banco de questões além dos termos atuais do glossário.
- [x] Persistir créditos individuais, legendas e posições das imagens internas; resumir links longos e torná-los clicáveis.
- [x] Dividir a criação de matéria em quatro etapas com editor de formatação e revisão antes do envio.

## Passo lento

- [ ] Expandir a trilha de conhecimento conforme orientação do professor.
- [ ] Definir retenção do histórico do jogo e das leituras; avaliar agregação e paginação conforme o uso crescer.
- [ ] Planejar convites de administrador e troca obrigatória da senha inicial, se exigidos pelo escopo do curso.

## Como demonstrar

1. Entrar como principal, abrir Tabelas / Notícias e criar uma conta administrativa de teste. Confirmar que suporte e leitores não podem cadastrar administradores.
2. Na sessão de administrador, abrir `/home_usuario` e conferir o 404. Como leitor, abrir `/home_admin` e conferir o mesmo 404.
3. Como leitor, abrir `/perfil`, alterar instituição e área, enviar uma foto e recarregar a página.
4. Abrir Juridle e jogar uma rodada. Testar resposta errada, explicação, retomada após recarga e rodada perfeita. O gabarito das próximas perguntas não é enviado.
5. Enviar um feedback e responder pela administração. Ver o aviso na Home do leitor e complementar o mesmo protocolo.
6. Ler uma matéria como estudante e conferir sua entrada em Em alta. Recarregar no mesmo dia não soma outra leitura; acessos de administrador não contam.
7. Explorar `/conhecimento`, categorias e curiosidades no computador e celular.

## Verificação técnica

A suíte inclui testes de permissões, cadastro administrativo, privacidade entre jogadores e atendimentos, respostas repetidas, duas abas concorrentes, expiração de rodada, dias consecutivos e contagem de leituras. A verificação no navegador usa dados fictícios e cobre rodada completa, erro recuperável, perfil com foto, complementação de atendimento, cadastro de administrador, temas e celular.

As novas tabelas são criadas de forma aditiva na inicialização da aplicação. Reiniciar o servidor e atualizar o navegador carrega as alterações. Não é necessário apagar o banco existente.
