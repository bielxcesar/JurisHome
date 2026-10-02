# Perfis e permissões

| Operação | Anônimo | Estudante | Administrador |
|---|---:|---:|---:|
| Ler documentos legais e conteúdos aprovados | sim | sim | sim |
| Criar conta e autenticar | sim | sim | sim |
| Consultar/editar o próprio perfil | não | sim | sim |
| Enviar feedback | não | sim | não |
| Consultar e gerenciar feedbacks recebidos | não | não | sim |
| Anonimizar a própria conta | não | sim | não para a conta raiz |
| Criar ou editar matérias pela interface | não | não | não |
| Consultar logs | não | não | sim, rota protegida no backend |
| Alterar ou apagar logs pela interface | não | não | não |

Todo ambiente que contenha dados pessoais deve manter `REQUIRE_ADMIN_AUTH=true`. A proteção das rotas administrativas não deve ser desativada durante a operação do sistema.
