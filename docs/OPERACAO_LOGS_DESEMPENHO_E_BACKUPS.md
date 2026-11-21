# Operação, logs, desempenho e recuperação

**Revisado em:** 21/11/2026  
**Escopo:** comportamento encontrado no código e configuração registrada para o JurisHome. Este documento não é um SLA nem confirma a execução de backup ou de teste de restauração.

## Evidência e limites desta revisão

O painel Railway não foi consultado durante esta atualização. A última conferência registrada em [`docs/lgpd/fornecedores.md`](lgpd/fornecedores.md) é de 20/11/2026: ela identificou o plano Hobby, o volume `postgres-volume` no ambiente `production` e nenhuma cópia ou agenda de backup listada. Esse registro é uma captura histórica; a configuração atual precisa ser confirmada no painel antes de uma decisão operacional.

## Logs operacionais

A aplicação envia para `stdout` eventos JSON de uma linha. Cada requisição registra horário UTC, nível, componente, método HTTP, modelo da rota, status, duração e identificador de correlação. As rotas são obtidas do registro FastAPI, sem caminho literal ou query string. O corpo, os cabeçalhos, cookies, e-mails, identificadores de usuário e parâmetros SQL não são incluídos.

Respostas 4xx são registradas como aviso; respostas 5xx como erro. Requisições acima de 2,5 segundos também geram aviso. Em falhas inesperadas, o log contém somente o tipo da exceção e os últimos quadros técnicos (arquivo, função e linha); não registra a mensagem da exceção nem variáveis locais. O `uvicorn.access` padrão é desligado porque pode registrar o caminho recebido; o evento seguro da aplicação ocupa esse lugar. `X-Correlation-ID` também é devolvido na resposta para localizar a ocorrência nos logs.

Avisos e erros são enviados também, de forma assíncrona, para a tabela `logs_operacionais`; requisições normais ficam somente no `stdout`. O evento no banco conserva nível, componente, tipo da ocorrência, método, rota-modelo, status, duração, correlação, identificador de implantação e quadros técnicos sanitizados. A gravação usa uma fila limitada a 1.000 eventos para não bloquear a resposta. Se o banco falhar, a fila lotar ou o processo encerrar antes de esvaziá-la, a cópia persistente pode faltar; o evento enviado ao `stdout` continua sendo a alternativa de consulta. O sistema não disponibiliza uma tela para esses registros: o acesso é feito por ferramenta administrativa autorizada ao banco.

Consulta de referência no banco (com acesso administrativo):

```sql
SELECT criado_em, nivel, componente, evento, operacao, metodo, rota,
       status_http, duracao_ms, correlacao_id, tipo_excecao, quadros_json
FROM logs_operacionais
ORDER BY criado_em DESC
LIMIT 100;
```

Falhas da consulta externa ao Senado registram componente, operação, tipo da exceção e quadros técnicos; o evento reutiliza a correlação da requisição quando disponível. A rotina de limpeza das métricas informa a operação e o erro técnico sem a mensagem SQL.

O SQLAlchemy está configurado com `hide_parameters=True`, evitando exibir valores de parâmetros SQL em mensagens do próprio SQLAlchemy. Isso não substitui a revisão dos demais logs.

Os logs operacionais são diferentes dos registros de auditoria. A auditoria persistida em `logs_auditoria` identifica o ator e a ação necessária à rastreabilidade, com acesso administrativo e regras próprias de minimização. Ela não é copiada para os logs técnicos de execução. A tabela `logs_operacionais` não contém identificador do usuário e não substitui a auditoria.

Railway captura a saída de `stdout` e `stderr`. A documentação consultada informa retenção visível de 7 dias no plano Hobby; isso descreve a janela do produto de logs e não comprova a eliminação de toda cópia interna do fornecedor. Os logs HTTP da borda Railway também são separados dos eventos JSON da aplicação e podem incluir método, caminho, status, duração, IP de origem e agente do navegador. Não envie dados pessoais ou credenciais em URLs. O projeto não contém integração com um serviço externo de armazenamento de logs.

## Metas de desempenho propostas

Não foram encontrados requisitos de carga nem resultados de teste de desempenho. Os números abaixo são **metas iniciais propostas**, não capacidade comprovada nem compromisso da Railway:

| Cenário | Meta inicial | Situação |
|---|---:|---|
| Usuários ativos ao mesmo tempo | 20 sessões durante uma avaliação de 5 minutos | Premissa de piloto pequeno; confirmar com os responsáveis. Não foi medida. |
| Páginas e consultas internas principais | p95 de até 2 segundos | Meta a medir com banco PostgreSQL isolado e conjunto de dados de teste. Não é limite imposto pelo código. |
| Operações internas de escrita | p95 de até 3 segundos e limite operacional desejado de 5 segundos | Meta a medir. O projeto não define prazo global de requisição nem `statement_timeout` do PostgreSQL. |
| Conexão ao PostgreSQL | até 5 segundos como objetivo de conexão | A configuração do SQLAlchemy não define `connect_timeout`; não está imposto pelo código. |
| Consulta externa ao Senado | 12 segundos por chamada HTTP externa | Limite implementado em `services/legislacao_senado.py`. A consulta pode fazer duas chamadas em sequência; portanto, o tempo total pode se aproximar de 24 segundos, além do processamento local. |
| Consulta completa ao Senado | até 25 segundos como objetivo de interface | Margem proposta sobre os dois limites de 12 segundos; ainda não medida como tempo total da rota. |

Uma validação reproduzível deve usar uma instância PostgreSQL isolada, dados fictícios e 20 sessões concorrentes por 5 minutos. Registrar percentis p50/p95/p99, erros e consumo de CPU/memória. Não usar o PostgreSQL Railway de `production` ou `staging` para esse ensaio. Nesta revisão, nenhum teste de carga foi executado; as metas permanecem preliminares.

## Railway: disponibilidade e monitoramento

No código não há rota dedicada `/health`, arquivo `railway.json`, `Procfile` ou comando de implantação declarado. O painel Railway não foi consultado nesta revisão; portanto, permanecem **a confirmar** o comando de inicialização efetivo, a rota de healthcheck, a política de reinício, o número de réplicas, as regiões, os limites selecionados e a existência de monitores.

A documentação atual da Railway informa que:

- o painel de métricas apresenta CPU, memória, disco e rede; essas métricas de serviço não representam, por si só, latência interna da aplicação ou tempo de consulta ao banco;
- logs de implantação são a saída do processo, e os logs HTTP da borda apresentam informações de cada requisição;
- um healthcheck configurado é consultado durante a implantação antes do tráfego ser direcionado à nova versão; ele não é uma verificação contínua depois que o deploy fica ativo;
- a política padrão de reinício é `On Failure`, mas o valor efetivo pode ser alterado por serviço.

Não foi definido um objetivo de disponibilidade mensal pelo projeto nem um RPO/RTO aprovado. Os recursos da plataforma não significam disponibilidade garantida do JurisHome. A equipe deve conferir a configuração atual no painel e registrar qualquer mudança.

## Backups e recuperação

O código não cria dumps, não agenda cópias e não implementa restauração do PostgreSQL. A conferência de painel registrada em 20/11/2026 não encontrou backups de volume nem agendamentos no ambiente `production`. Esta revisão não repetiu a consulta ao painel nem criou, apagou ou restaurou qualquer cópia. Assim, não há backup periódico ou recuperação testada que possa ser apresentada como prática ativa do projeto.

A documentação Railway consultada descreve backups de volume manuais ou agendados (diários, semanais ou mensais), com janelas publicadas de retenção de 6, 27 e 89 dias, respectivamente. A criação pode gerar custo de armazenamento incremental. A restauração prepara um novo volume para revisão; ao concluir, o serviço é implantado com esse volume e o volume anterior fica desanexado. A disponibilidade e o custo para o plano atualmente contratado precisam ser confirmados no painel.

A Railway também documenta recuperação pontual (PITR) para PostgreSQL, que restaura para um novo serviço. A documentação do provedor não comprova que PITR esteja habilitado para este projeto. A equipe não testou restauração, não definiu destino de cópias externas e não estabeleceu RPO ou RTO.

Se uma cópia vier a ser ativada, antes de chamar o processo de rotina devem ser definidos responsável, frequência, retenção, destino protegido, custo e teste de restauração. Depois de restaurar, validar a integridade em ambiente isolado e reaplicar solicitações de remoção e prazos de retenção antes de liberar acesso. Backups externos não são automaticamente alterados pelas rotinas de exclusão do JurisHome.

## Retenção implementada

Os prazos abaixo são os valores encontrados em `services/leituras.py`, `services/retencao.py` e `manutencao_lgpd.py`. Os prazos de governança também constam da [matriz de retenção](lgpd/matriz_bases_retencao.md).

| Registro | Critério encontrado | Execução |
|---|---|---|
| Leituras de matérias | Mantém hoje e os 89 dias anteriores (90 dias no total). | Limpeza ao iniciar a aplicação, depois a cada 24 horas enquanto ativa e durante consultas às métricas. Se a limpeza diária falha, tenta novamente em uma hora. |
| Acessos por categoria | Mantém 90 dias, uma linha por usuário/categoria/dia. | Limpeza na rotina diária, ao registrar um acesso e ao calcular a dashboard daquele usuário. |
| Feedback de suporte | Registros `Resolvido` ou `Arquivado` sem atualização há mais de 180 dias são anonimizados. | Rotina geral manual; a referência de data do código é `atualizado_em`. |
| Logs de auditoria | Eventos gerais com mais de 365 dias têm ator, recurso, detalhes e correlação minimizados. Ações `incidente_*` usam 1.825 dias desde o evento. | Rotina geral manual. O evento-base permanece, sem os vínculos e detalhes minimizados. |
| Logs operacionais | Avisos e erros permanecem por até 90 dias desde `criado_em`; níveis informativos não são gravados na tabela. | A tabela é criada pelo `Base.metadata.create_all` na inicialização. A exclusão dos vencidos é aplicada pela rotina manual de retenção, sem agendamento automático. O prazo de 90 dias é um parâmetro técnico inicial e deve ser confirmado pelos responsáveis. |
| Prova de aceite de conta encerrada | Após 1.825 dias desde a data de encerramento registrada, a linha de aceite e os campos de aceite remanescentes são eliminados. | Rotina geral manual. |

`python manutencao_lgpd.py` apenas simula e informa quantidades. `python manutencao_lgpd.py --executar` aplica alterações permanentes; precisa ser executado pelo responsável após conferir o resultado. Esse script não é agendado pelo código. A limpeza automática diária refere-se apenas às métricas de leituras e categorias, não aos demais prazos acima.

## Fontes Railway consultadas em 21/11/2026

- [Logs e retenção](https://docs.railway.com/observability/logs)
- [Métricas](https://docs.railway.com/observability/metrics)
- [Healthchecks](https://docs.railway.com/deployments/healthchecks)
- [Política de reinício](https://docs.railway.com/deployments/restart-policy)
- [Backups de volume](https://docs.railway.com/volumes/backups)
- [Recuperação pontual do PostgreSQL](https://docs.railway.com/volumes/point-in-time-recovery)
