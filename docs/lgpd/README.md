# Dados e privacidade

Estes arquivos registram os dados tratados pelo código e os procedimentos previstos para o projeto. Revise-os quando as telas, integrações ou serviços de hospedagem mudarem. Eles não substituem a validação jurídica das bases legais, dos prazos ou da definição dos responsáveis pelo tratamento.

Equipe informada no projeto: Erick Santos Barbosa, Pedro Henrique Harada Pecegueiro e Gabriel Agustín Fernández Alves. Canal de contato: jurishome2026@gmail.com.

- `inventario_dados.md`: dados e fluxos encontrados no código.
- `matriz_bases_retencao.md`: finalidade, base adotada, acesso e descarte.
- `perfis_permissoes.md`: acessos por perfil.
- `direitos_titular.md`: procedimento operacional de atendimento.
- `resposta_incidentes.md`: procedimento de segurança.
- `fornecedores.md`: integrações e pontos que mudam na hospedagem.

Rotina de retenção (execução manual):

- `python manutencao_lgpd.py`: apresenta os registros alcançados pelos prazos de retenção, sem alterá-los.
- `python manutencao_lgpd.py --executar`: aplica os prazos configurados após a conferência do responsável.

O script não é executado automaticamente. A aplicação também não cria nem gerencia cópias de segurança; confira a configuração e a retenção de backups diretamente no provedor de hospedagem.

A versão do Termo é gravada quando a conta é criada. Esta versão da aplicação não solicita novo aceite a contas existentes quando o texto muda.
