# Inventário de dados

| Origem | Dados | Armazenamento | Uso | Saída/terceiro |
|---|---|---|---|---|
| Cadastro | nome, e-mail, hash da senha, tipo, aceite, versão e data | `usuarios` | conta, autenticação e prova do aceite | nenhum |
| 2FA | segredo TOTP cifrado, estado de ativação, tentativas e bloqueio | `usuarios`; desafio temporário no `sessionStorage` | segurança da conta | aplicativo autenticador lê o QR; o servidor não envia o segredo a serviço externo |
| Campos adicionais do perfil | `universidade` e `especialidade_juridica` existem no modelo de dados, mas as telas e rotas atuais não os preenchem | colunas opcionais de `usuarios` | sem uso ativo nesta versão | nenhum |
| Preferência de tema | escolha do tema claro ou escuro | `localStorage` do navegador | manter a aparência escolhida no dispositivo | nenhum |
| Pesquisa | termo e filtros enviados à consulta do acervo | usados na requisição; a aplicação não grava histórico de pesquisa em suas tabelas | localizar matérias | o provedor de hospedagem pode registrar requisições técnicas conforme sua configuração |
| Consulta e-MEC | código numérico informado no campo opcional | não é salvo pelo JurisHome | consultar uma instituição | o código é enviado ao serviço e-MEC ou à API pública de IES do CAU/BR |
| Conteúdo | UUID do autor, textos, fontes, categorias, tags e URLs de imagens | `conteudos` e tabelas relacionadas | exibir matérias aprovadas | o navegador pode carregar imagens da origem informada na URL; não há upload automático para Cloudinary nem tela de edição nesta versão |
| Feedback | usuário, nome, e-mail, tipo, assunto, mensagem, nota, estado, prioridade, respostas, observações e histórico | `feedback_atendimentos` | atendimento e acompanhamento | nenhum |
| Auditoria | UUID, perfil, ação, recurso, resultado, correlação, data e detalhes mínimos | `logs_auditoria` | segurança e rastreabilidade | somente administradores |
| Navegador | cookie HTTP-only de sessão, desafio 2FA temporário e preferência de tema | cookie, `sessionStorage` e `localStorage` | sessão, 2FA e aparência | Google Fonts e cdnjs/Cloudflare recebem metadados normais da requisição |

O cadastro inclui uma declaração de que a pessoa tem pelo menos 18 anos, mas o sistema não solicita data de nascimento nem verifica a idade de forma independente.

O sistema não solicita CPF, RG, endereço, telefone, data de nascimento ou dados bancários.
