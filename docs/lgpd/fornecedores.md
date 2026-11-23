# Responsabilidades e serviços externos

Atualização: 20/11/2026. Responsável operacional: administrador root, inclusive publicação dos termos e da política. Substituto: administrador de suporte designado pelo root. Confirmação de recebimento e triagem dos pedidos: até 2 dias úteis, sem ampliar prazos legais.

## Papéis no projeto acadêmico

O controlador é quem efetivamente decide as finalidades e os meios do tratamento. O operador trata dados em nome do controlador e conforme suas instruções. O perfil root é uma autorização técnica, não define sozinho o agente jurídico. A equipe do JurisHome deve registrar quem assume as decisões e a relação institucional aplicável. O acompanhamento pelo orientador ou pela instituição não os torna automaticamente controladores ou operadores.

O grupo limita a coleta ao necessário, usa contas fictícias nas apresentações e não inclui dados reais, segredos, dumps ou credenciais nas evidências acadêmicas. O root controla acessos, coordena solicitações e incidentes, verifica retenção e mantém o registro de decisões. Administradores de suporte executam apenas tarefas autorizadas; autores não recebem acesso aos dados pessoais dos leitores. Nomes da equipe constam da Política; a formalização institucional ainda precisa ser confirmada. O root deve registrar qual administrador de suporte assume a substituição em cada período ou atendimento.

| Serviço | Uso e dados | Papel a conferir e providência |
|---|---|---|
| Railway | Hospedagem, banco, requisições técnicas e dados armazenados | Confirmar contrato, papel de operador para hospedagem, suboperadores, região, transferências internacionais, logs, backups e descarte. A aplicação não controla as cópias do provedor. |
| Google Fonts e cdnjs/Cloudflare | Fontes/ícones; IP e metadados de requisição | Não presumir operador contratado; conferir políticas próprias e necessidade de carregar recursos externos. |
| API de Dados Abertos do Senado | Tipo, número e ano de norma e, quando houver, o identificador retornado pela própria API | Serviço externo consultado pelo backend; sem envio intencional de conta/e-mail. Pode receber IP técnico do servidor. |
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
| Logs do provedor | A documentação oficial de logs consultada em 21/11/2026 indica 7 dias de retenção visível para Hobby. Essa janela não comprova a eliminação de toda cópia interna do fornecedor; não afirmar descarte total após 7 dias sem confirmação. |

### Backups e recuperação

Na consulta de painel registrada acima, feita em 20/11/2026, não havia backup de volume listado nem agenda configurada para `postgres-volume` no ambiente production. A equipe adiou a proposta de backup a cada 72 horas antes da implantação. Nenhuma cópia foi criada ou apagada e nenhum plano ou agendamento foi alterado. Essa constatação é histórica e não foi confirmada novamente durante a revisão de 21/11/2026.

Na [documentação oficial de backups](https://docs.railway.com/volumes/backups), consultada em 21/11/2026, a Railway descreve cópias de volume manuais ou agendadas diariamente, semanalmente ou mensalmente, com retenção publicada de 6, 27 e 89 dias, respectivamente. O armazenamento incremental pode gerar cobrança. A documentação atual não confirma, por si só, a disponibilidade do recurso no plano usado pelo projeto; verificar no painel antes de planejar sua ativação.

O código do JurisHome não cria cópias, exportações `pg_dump` ou agendamentos. A documentação da Railway descreve que uma restauração de volume prepara outro volume para revisão, mantendo o anterior desanexado até a conclusão da implantação. A documentação de [Point-in-Time Recovery para PostgreSQL](https://docs.railway.com/volumes/point-in-time-recovery) também descreve restauração para um novo serviço. Não há evidência de que backups ou PITR estejam habilitados para este projeto.

Nenhuma restauração foi testada, e o projeto ainda não definiu RPO ou RTO. Antes de ativar backups, os responsáveis precisam definir frequência, retenção, destino, responsável e custos. Antes de liberar um ambiente restaurado, validar a cópia isoladamente e reaplicar solicitações de remoção e prazos de retenção. Backups externos não são atualizados automaticamente pelas rotinas da aplicação.

### Confirmações que ainda dependem da equipe ou do fornecedor

- Substituto e triagem definidos pela equipe: administrador de suporte designado pelo root; confirmação e triagem em até 2 dias úteis. Registrar a designação nominal operacionalmente.
- Confirmar no painel o plano, a existência de cópias/agendas, a disponibilidade do backup de volume e o estado de PITR. A aplicação e o repositório não fornecem essas informações.
- Definir responsável, frequência, retenção, destino protegido, custos, RPO/RTO e teste de restauração antes de tratar backup como procedimento operacional implantado.
- Identificação formal do controlador e mecanismo aplicável a transferências internacionais: validar com os responsáveis pelo projeto; não inferir conformidade LGPD apenas do DPA europeu.
- Lista completa de suboperadores, localização física/replicação, retenção efetiva de logs e cópias internas: obter evidência contratual ou resposta do fornecedor.
