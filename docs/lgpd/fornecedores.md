# Responsabilidades e serviços externos

Atualização: 20/11/2026. Responsável operacional: administrador root, inclusive publicação dos termos e da política. Substituto: administrador de suporte designado pelo root. Confirmação de recebimento e triagem dos pedidos: até 2 dias úteis, sem ampliar prazos legais.

## Papéis no projeto acadêmico

O controlador é quem efetivamente decide as finalidades e os meios do tratamento. O operador trata dados em nome do controlador e conforme suas instruções. O perfil root é uma autorização técnica, não define sozinho o agente jurídico. A equipe do JurisHome deve registrar quem assume as decisões e a relação institucional aplicável. O acompanhamento pelo orientador ou pela instituição não os torna automaticamente controladores ou operadores.

O grupo limita a coleta ao necessário, usa contas fictícias nas apresentações e não inclui dados reais, segredos, dumps ou credenciais nas evidências acadêmicas. O root controla acessos, coordena solicitações e incidentes, verifica retenção e mantém o registro de decisões. Administradores de suporte executam apenas tarefas autorizadas; autores não recebem acesso aos dados pessoais dos leitores. Nomes da equipe constam da Política; a formalização institucional ainda precisa ser confirmada. O root deve registrar qual administrador de suporte assume a substituição em cada período ou atendimento.

| Serviço | Uso e dados | Papel a conferir e providência |
|---|---|---|
| Railway | Hospedagem, banco, requisições técnicas e dados armazenados | Confirmar contrato, papel de operador para hospedagem, suboperadores, região, transferências internacionais, logs, backups e descarte. A aplicação não controla as cópias do provedor. |
| Google Fonts e cdnjs/Cloudflare | Fontes/ícones; IP e metadados de requisição | Não presumir operador contratado; conferir políticas próprias e necessidade de carregar recursos externos. |
| API de Dados Abertos do Senado | Tipo, número e ano de norma | Serviço externo consultado pelo backend; sem envio intencional de conta/e-mail. Pode receber IP técnico do servidor. |
| WhatsApp | Título e URL pública por iniciativa do usuário | Serviço escolhido pelo titular, sujeito às próprias condições; não recebe cadastro pelo JurisHome. |
| Origem de imagem legada | Metadados da requisição do navegador à URL | Conferir origem; imagens novas em Base64 ficam no banco. Não presumir contrato de operador. |

## Conferência antes de uso com dados reais

O root registra data, fornecedor, contrato/política consultada, região, suporte a incidentes, retenção e descarte/backup. Não declarar verificações não realizadas. A conferência técnica abaixo registra o plano, a região informada e a ausência de backups/agendamentos; as condições externas não comprovadas continuam identificadas como pendentes. Em restaurações, reaplicar pedidos de remoção e políticas de retenção antes de liberar o serviço. Não existe certificação de conformidade LGPD por este documento.

Referências: [LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm), [guia da ANPD sobre agentes de tratamento](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia_agentes_de_tratamento_e_encarregado___defeso_eleitoral.pdf).

## Conferência técnica do Railway — 20/11/2026

Consulta autenticada somente de leitura ao projeto JurisHome, ambiente production. Não houve alteração de plano, configuração, restauração ou acesso a registros pessoais do banco.

| Item | Evidência e conclusão |
|---|---|
| Plano da conta | A API retornou `HOBBY`. |
| Volume PostgreSQL | `postgres-volume`; consulta de backups retornou lista vazia. Não há backup de volume recuperável listado para a equipe no momento da conferência. Isso não comprova ausência de cópias internas de infraestrutura do fornecedor. |
| Agendamentos | Consulta de agendamentos retornou lista vazia. Backup automático do volume não está configurado. |
| Região | O volume e os manifestos de implantação de Postgres e JurisHome retornaram `sfo`. O campo simples de região do serviço veio nulo. Preservar esse identificador como evidência; confirmar a denominação/localização contratual da região legada com o fornecedor antes de declarar residência física completa. |
| Contrato de tratamento | O [DPA público](https://railway.com/legal/dpa) descreve tratamento sob instruções do cliente e condições de devolução/eliminação. A leitura do documento não comprova assinatura específica, adesão institucional ou atendimento automático aos mecanismos brasileiros de transferência internacional. |
| Suboperadores | O DPA remete ao [Trust Center](https://trust.railway.com/item/subprocessors). A página foi consultada, mas a lista detalhada não ficou acessível no conteúdo público retornado. O root deve obter a relação vigente no portal/suporte; não presumir lista completa. |
| Proteção da plataforma | A [documentação de segurança](https://docs.railway.com/enterprise/security) informa criptografia em repouso e em trânsito. É declaração do fornecedor, não auditoria técnica independente desta equipe. |
| Logs externos | A documentação de segurança indica 7 dias para Hobby, mas isso não é evidência da eliminação de todas as cópias internas. Há [respostas no canal do fornecedor](https://station.railway.com/questions/how-long-are-logs-actually-stored-on-the-c60999d6) distinguindo janela visível e armazenamento por 90 dias. Confirmar retenção efetiva, local e eventual exceção por escrito antes de prometer descarte em 7 dias. |

### Backup: decisão e execução ainda necessárias

A [documentação de backups](https://docs.railway.com/volumes/backups) descreve agendas diária/semanal/mensal, retenções de 6/27/89 dias e cobrança por armazenamento incremental. A disponibilidade para o plano contratado precisa ser conferida antes de ativar. A [orientação publicada no suporte](https://station.railway.com/questions/need-to-get-backup-from-database-44a3320b) informa exigência de Pro para backups nativos. Não houve upgrade nem criação de cópia nesta conferência.

Opções propostas, ainda sem compromisso operacional aprovado:

- Backup nativo diário, se a equipe aprovar as condições e o custo: acompanhar primeira execução bem-sucedida e expiração. Não confundir agendamento criado com cópia válida.
- Exportação lógica com `pg_dump`, sem mudança de plano: definir responsável, frequência, destino protegido e prazo de descarte antes de chamar o procedimento de política implantada. Não guardar dump no Git nem em evidências acadêmicas; ele contém dados pessoais e hashes.

Antes de qualquer restauração: validar em ambiente isolado; conferir integridade e acesso; reaplicar remoções de titulares e retenção; registrar data, executor, resultado e origem da cópia. O teste em produção e qualquer restauração dependem de uma ação específica autorizada; não foram executados.

### Confirmações que ainda dependem da equipe ou do fornecedor

- Substituto e triagem definidos pela equipe: administrador de suporte designado pelo root; confirmação e triagem em até 2 dias úteis. Registrar a designação nominal operacionalmente.
- Backup adiado por decisão da equipe em 20/11/2026. A proposta de intervalo de 72 horas foi cancelada antes da implantação. Nenhuma criação, exclusão de cópia, mudança de plano ou ativação de agenda foi realizada. A ausência de backup configurado continua registrada como pendência operacional.
- Identificação formal do controlador e mecanismo aplicável a transferências internacionais: validar com os responsáveis pelo projeto; não inferir conformidade LGPD apenas do DPA europeu.
- Lista completa de suboperadores, localização física/replicação, retenção efetiva de logs e cópias internas: obter evidência contratual ou resposta do fornecedor.

### Backup adiado pela equipe — 20/11/2026

A equipe cancelou a proposta de backup a cada 3 dias antes de qualquer implantação. Nenhum backup ou agendamento foi criado por este trabalho; nenhum backup existente foi apagado, e não houve mudança de plano ou cobrança ativada. A conta consultada permanece sem backup de volume ou agendamento confirmado na conferência anterior.

Não há compromisso de execução periódica nem tarefa de backup pendente de ativação. Se a equipe retomar o assunto, deverá definir novamente destino, frequência, retenção, responsável, teste de restauração e custos antes de implantar. A ausência de cópia recuperável configurada permanece uma pendência operacional documentada, sem declaração de conformidade integral.