# Autenticação e revisão de segurança

O backend valida credenciais, 2FA, bloqueio da conta e permissões em cada rota protegida. `static/js/auth.js` cuida dos formulários e da navegação; validações no navegador ajudam a experiência, mas não concedem acesso.

## Alterações desta revisão

- Os endpoints de autenticação e troca de senha retornam `autenticado: true`, sem expor o JWT no JSON. A sessão é enviada por cookie HttpOnly, SameSite=Lax.
- A autorização administrativa é obrigatória, independentemente de `REQUIRE_ADMIN_AUTH`.
- Escritas verificam Origin/Referer e Fetch Metadata. Operações com cookie exigem evidência de mesma origem. Clientes HTTP sem cookie podem continuar usando Bearer.
- Logout atualiza a revogação da conta no banco, invalidando também cópias de tokens anteriores. Isso encerra as outras sessões da conta.
- Uploads de perfil limitam leitura a 2 MB, verificam formato e dimensões, reencodam a imagem em JPEG sem metadados originais e usam nome aleatório. O código anterior utilizava `usuario.id`, mas a chave do modelo é `uuid`.
- A página de matéria recusa conteúdos não aprovados para estudantes.
- Textos da matéria são escapados antes de compor HTML. O preview usa elementos DOM e textContent para fontes, links e imagens; URLs aceitam apenas HTTP/HTTPS.

## Execução e implantação

Execute `venv\Scripts\python.exe -m unittest discover -s tests -v` na raiz do projeto.

Em produção, configure HTTPS, `COOKIE_SECURE=true`, uma chave `JurisHome_senha` aleatória e `PUBLIC_ORIGIN` com esquema e domínio exatos, sem caminho. Atrás de proxy, configure corretamente os hosts permitidos e os cabeçalhos encaminhados. Não versione `.env`, bancos, backups ou uploads pessoais.

## Limites e próximos trabalhos

Esta revisão não é uma certificação nem uma refatoração completa de todos os módulos. Ainda devem ser avaliados: limitação de requisições compartilhada entre processos, recuperação de 2FA pelo suporte, demais usos de HTML dinâmico, dependências e configuração de produção. Os desafios temporários continuam no sessionStorage, mas seu consumo e a revogação são verificados no banco. Uploads pessoais precisam de política de limpeza dos arquivos substituídos e anonimizados.

Referência para proteção de origem: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

## Revisão de auth/security.py

A decodificação agora é centralizada e exige `sub`, `tipo`, `iat` e `exp`. Datas precisam ser números finitos, representáveis pelo servidor, com expiração posterior à emissão. O algoritmo continua fixo em HS256; o tipo específico continua sendo conferido por cada consumidor. Ausência de expiração passa a invalidar tokens em todos os fluxos. Essa é uma defesa contra emissão incorreta de tokens assinados; não significa que um atacante sem a chave possa alterar um JWT válido.

A inicialização recusa chaves menores que 32 bytes e o marcador do arquivo de exemplo. Comprimento não comprova aleatoriedade: gere a chave com uma fonte criptográfica. A verificação de senha também retorna falso para hash ausente em vez de provocar AttributeError.

A chave Fernet agora vem de `TOTP_ENCRYPTION_KEY`, independente de `JurisHome_senha`. A migração local recifrou duas configurações existentes e verificou que ambas são legíveis apenas com a nova chave. Trocar a chave JWT passa a invalidar os JWTs sem impedir a leitura dos segredos TOTP.

Os desafios possuem identificador aleatório e expiram. Seu consumo é registrado uma única vez no banco, com unicidade e transação. O intervalo TOTP usado também fica registrado por usuário e segredo, impedindo o reaproveitamento do código em outro desafio. Logout, troca de senha, anonimização e reset de 2FA pelo suporte invalidam os desafios anteriores pelo instante de revogação. Códigos incorretos continuam sujeitos ao bloqueio por tentativas. Depois de usar um código, aguarde o próximo código do autenticador para entrar novamente.

O access token dura 30 minutos mesmo com “manter conectado”. A opção cria uma sessão de no máximo 14 dias, com refresh token aleatório em cookie HttpOnly, SameSite=Strict e Secure em produção. Apenas o hash do refresh fica no banco. Cada renovação marca o token anterior como usado e emite outro, sem estender o prazo absoluto. Reutilizar um token anterior revoga a sessão inteira, incluindo access tokens ainda não expirados. Sessões anteriores à mudança de senha ou logout também são recusadas. Tokens antigos, sem identificação de sessão, exigem novo login após esta atualização.

O navegador renova a sessão ao receber 401 da API; páginas protegidas podem passar por `/renovar-sessao`. O script usa Web Locks para serializar renovações entre abas nos navegadores que oferecem esse recurso. Sem Web Locks, requisições simultâneas entre abas podem provocar a revogação conservadora da sessão. Clientes de API devem coordenar as renovações e enviar Origin nas escritas com cookies. Credenciais de login e erros de 2FA não acionam renovação automática.

## Migração e rotação de chaves

Em outra instalação existente, pare o servidor, mantenha as chaves antigas e faça backup do banco e do `.env`. Execute `venv\Scripts\python.exe migrar_seguranca.py` para verificar, e `venv\Scripts\python.exe migrar_seguranca.py --apply` para migrar. O script gera uma chave independente, valida todos os registros antes de alterá-los, recifra em transação e cria as novas tabelas sem alterar colunas existentes. Durante a transição preserva explicitamente a chave legada; só a remove da configuração ativa após verificar todos os registros com a chave nova. Reinicie o servidor depois.

Para futuras rotações TOTP, use `venv\Scripts\python.exe migrar_seguranca.py --apply --rotate`. `TOTP_PREVIOUS_KEYS` permite leitura com chaves Fernet anteriores. Guarde essas chaves enquanto houver backups que dependam delas. A migração preserva um `.env.auth-backup-*`, ignorado pelo Git: proteja esse arquivo como segredo e não o restaure isoladamente sobre um banco já migrado. Se houver interrupção entre a gravação da configuração e o commit do banco, preserve as chaves de transição e execute novamente a migração com o servidor parado. Não execute migrações concorrentes. O utilitário altera o `.env` local; em hospedagem com gerenciador de segredos, adapte a publicação das chaves antes de migrar.

Mantenha registros de refresh usados até expirar a sessão para preservar a detecção de reutilização. Registros de desafios só podem ser eliminados após sua expiração; intervalos TOTP só após saírem da janela aceita. A manutenção dessas tabelas deve respeitar a política de retenção e não remover tombstones de sessões ainda válidas. As garantias de concorrência foram testadas com SQLite; valide também no banco escolhido para produção.

Referências: https://www.rfc-editor.org/rfc/rfc9700.html e https://cryptography.io/en/stable/fernet/

Referência de claims obrigatórios: https://pyjwt.readthedocs.io/en/latest/usage.html
