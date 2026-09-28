# Matriz de finalidade, base e retenção

| Tratamento | Finalidade | Base adotada | Acesso | Retenção/destino |
|---|---|---|---|---|
| Conta e autenticação | entregar acesso solicitado | art. 7º, V | titular e backend; admin somente conforme função | vida da conta; anonimização imediata a pedido |
| Pesquisa no acervo | localizar matérias conforme o termo e os filtros enviados | art. 7º, V | pessoa que consulta e serviço de hospedagem, conforme seus próprios logs | a aplicação não mantém histórico de pesquisa; logs de infraestrutura dependem do provedor |
| Feedback e suporte | atender solicitação | art. 7º, V | pessoa que envia e administradores | resolução/arquivo + 180 dias; depois anonimiza conteúdo |
| Segurança e auditoria | prevenir abuso e investigar falhas | art. 7º, IX, com minimização | administradores | 12 meses; depois elimina vínculos e detalhes |
| Prova de aceite | demonstrar versão e momento | art. 7º, VI | administradores responsáveis | 5 anos após anonimização; depois descarta |
| Registro de incidente | resposta e investigação, quando houver registro | art. 7º, VI | responsáveis pelo sistema | a rotina minimiza eventos de auditoria `incidente_*` após 5 anos; não há formulário próprio para incidentes |
| Conteúdo jurídico | disponibilizar o acervo aprovado | art. 7º, V | público para leitura; não há interface administrativa de edição | enquanto publicado; revisão na retirada do conteúdo |

Os prazos de feedback, auditoria e aceite correspondem aos valores implementados em `services/retencao.py`. A rotina precisa ser executada manualmente e não há agendamento automático. As bases legais e os prazos desta matriz são uma proposta técnica do projeto e precisam ser confirmados pelos responsáveis antes do uso com dados reais.
