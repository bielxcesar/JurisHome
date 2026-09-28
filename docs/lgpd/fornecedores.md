# Serviços externos e operadores

| Serviço | Uso atual | Dados enviados |
|---|---|---|
| Railway | hospedagem da versão publicada e do PostgreSQL | requisições técnicas e dados armazenados nas tabelas do JurisHome |
| Google Fonts e cdnjs / Cloudflare | fontes e ícones da interface | metadados técnicos normais da requisição |
| e-MEC / API pública CAU/BR | consulta opcional de IES por código | apenas o código numérico consultado |
| WhatsApp | compartilhamento iniciado pelo usuário | título e endereço público da matéria |
| Origem de imagem informada na matéria | carregamento de imagem externa, quando houver URL | requisição do navegador à origem indicada; não há upload automático para Cloudinary |

O login utiliza e-mail, senha e TOTP. A instalação local usa SQLite por padrão e não envia dados à Railway. O código não configura a região de processamento nem a retenção de logs e backups do provedor; confira esses pontos na conta usada para a implantação.

Contratos, regiões de processamento, suboperadores, política de backup, suporte a incidentes e regras de transferência internacional não são definidos por este repositório. A equipe responsável deve conferi-los nos serviços contratados e atualizar esta lista quando houver mudança.
