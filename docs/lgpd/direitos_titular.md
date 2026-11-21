# Atendimento aos direitos do titular

Atualização: 20/11/2026. Responsável operacional: administrador root. O root também administra a publicação dos termos e da política. Substituto: administrador de suporte designado pelo root. Compromisso interno: confirmar recebimento e realizar triagem em até 2 dias úteis. A designação nominal deve ser registrada no atendimento e na passagem de responsabilidade. Não há envio automático de mensagens.

## Fluxo operacional

1. Receber na área autenticada ou em `jurishome2026@gmail.com`. O encerramento automático exige acesso à conta e senha atual. A conta root exige transferência controlada de responsabilidade, sem exclusão automática.
2. Registrar um atendimento restrito com protocolo, tipo de direito, data de recebimento, responsável designado e situação. Para e-mail externo, o administrador registra manualmente no canal de atendimento; não há importação automática de caixa postal. Registrar só o necessário, sem senha, tokens, segredo 2FA ou documento completo.
3. Verificar identidade proporcionalmente, preferindo o fluxo autenticado e o canal cadastrado. Não aceitar acesso a conta de terceiro nem solicitar cópia integral de documento por padrão.
4. Classificar: confirmação/acesso, correção, informação, anonimização/eliminação, portabilidade, oposição ou revisão. O root avalia fundamento, finalidade e exceções; encaminha execução apenas ao administrador autorizado. O suporte não deve receber permissões adicionais de edição por este procedimento.
5. Localizar cadastro, suporte (inclusive banco separado), logs, aceites, métricas, sessões e vínculos editoriais. Registrar escopo e decisão, com justificativa concreta para qualquer retenção ou impossibilidade. Não classificar a simples necessidade de auditoria como obrigação legal genérica.
6. Executar a medida; registrar resultado, conclusão e informação de eventual falha parcial. Com bancos separados não há transação distribuída: uma falha exige conferência dos dois bancos e conclusão controlada, sem presumir reversão global.
7. Responder pelo canal de origem após verificar identidade. Indicar dados eliminados, registros pseudonimizados retidos, fundamento/finalidade, prazo, limitações de backups e eventual impedimento. Registrar envio manual e data, sem copiar o conteúdo pessoal para a auditoria.
8. O root acompanha pendências e confirma o descarte; em restaurações, reaplica pedidos antes da reabertura. Evidências acadêmicas usam dados fictícios e e-mails mascarados.

## Prazos

Para confirmação/acesso, o art. 19 prevê forma simplificada imediatamente ou declaração clara e completa em até 15 dias da requisição. Não estender automaticamente esse prazo a todos os direitos. Para os demais, adotar providência imediata quando possível e informar razões de fato/direito quando não for possível, observando as normas aplicáveis. A equipe confirmou triagem e confirmação de recebimento em até 2 dias úteis, sob responsabilidade do root ou do administrador de suporte por ele designado. Esse compromisso não é prazo geral para concluir todos os pedidos e não amplia nenhum prazo legal. Registrar recebimento, prazo previsto, responsável, encaminhamentos e conclusão; priorizar pedidos sujeitos a atendimento imediato. A substituição operacional não cria permissões de root para o suporte.

## O que o sistema faz no encerramento

Remove dados diretos do cadastro, senha, TOTP e foto atual; elimina sessões/tokens/desafios, leituras, categorias e progresso individual. Feedback legado perde mensagem e vínculo; atendimento perde vínculo com conta e conteúdo pessoal. O e-mail residual usa um valor aleatório sem incorporar o UUID. Logs anteriores vinculados à conta perdem ator, recurso, detalhes e correlação original.

UUID residual, autoria editorial, prova de aceite e evento técnico de encerramento continuam pseudonimizados e protegidos. Protocolos/datas de atendimento também podem ser associados a informações externas; não são declarados anônimos. Máscara de e-mail é somente ocultação na interface e na resposta administrativa, sem eliminar o original do cadastro. Não há garantia de anonimização irreversível de todo o conjunto ou de backups externos.

## Retenção e operação

Leituras e categorias: 90 dias de calendário, limpeza diária com serviço ativo, na reinicialização e nos acessos às métricas. Em alta usa 7 dias; a retenção de 90 permite a dashboard pessoal. A rotina geral `aplicar_retencao` continua com simulação e execução operacional para feedbacks (encerramento +180 dias), logs (365 dias), incidentes (5 anos da data do evento) e aceites (5 anos após encerramento da conta). A prova de aceite fica na conta e em `aceites_documentos`; ao vencer, ambos são descartados. São prazos de governança propostos, sujeitos à validação dos responsáveis; não prazos universalmente impostos pela LGPD.

Backups e infraestrutura: verificar contrato e retenção com fornecedor; a aplicação não os apaga. Para retenção excepcional, registrar fundamento, dados mínimos, acesso, responsável, revisão e término.

Referências: [arts. 12, 16, 18 e 19 da LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm), [direitos dos titulares — ANPD](https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados/direito-dos-titulares).
