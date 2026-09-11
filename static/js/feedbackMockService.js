(function () {
    "use strict";

    // Substituir os dados locais pela API quando o backend estiver disponível.
    const STORAGE_KEY = "jurishome_feedback_v5";
    const CURRENT_USER = Object.freeze({
        id: "usr-sessao",
        nome: "Usuário",
        email: "usuario@jurishome.local"
    });

    const TIPOS = Object.freeze([
        "Reclamação",
        "Dificuldade de acesso",
        "Problema técnico",
        "Sugestão",
        "Dúvida",
        "Elogio",
        "Outro"
    ]);
    const STATUS = Object.freeze(["Recebido", "Em análise", "Respondido", "Resolvido", "Arquivado"]);
    const PRIORIDADES = Object.freeze(["Baixa", "Normal", "Alta", "Urgente"]);

    const DADOS_INICIAIS = [
        {
            id: "fb-001",
            protocolo: "JH-20260911-1042",
            usuario: {
                id: "usr-erick",
                nome: "Erick Santos",
                email: "erick.santos@aluno.umc.br"
            },
            tipo: "Sugestão",
            assunto: "Filtro por tribunal na pesquisa",
            mensagem: "Podiam colocar filtros por tribunal e período na pesquisa? Isso ajudaria bastante.",
            avaliacao: 5,
            status: "Recebido",
            prioridade: "Normal",
            criadoEm: "2026-09-11T09:14:00-03:00",
            atualizadoEm: "2026-09-11T09:14:00-03:00",
            respostas: [],
            observacoesInternas: [],
            historico: [
                {
                    id: "hist-001",
                    tipo: "criacao",
                    autor: "Erick Santos",
                    descricao: "Feedback enviado.",
                    criadoEm: "2026-09-11T09:14:00-03:00",
                    visibilidade: "publica"
                }
            ],
            novo: true,
            arquivado: false
        },
        {
            id: "fb-002",
            protocolo: "JH-20260909-0837",
            usuario: {
                id: "usr-pedro",
                nome: "Pedro Henrique",
                email: "pedro.henrique@aluno.umc.br"
            },
            tipo: "Dificuldade de acesso",
            assunto: "Não consigo acessar pelo celular",
            mensagem: "No celular, depois que digito o código de verificação, o sistema volta para a tela de login.",
            avaliacao: null,
            status: "Em análise",
            prioridade: "Alta",
            criadoEm: "2026-09-09T18:22:00-03:00",
            atualizadoEm: "2026-09-10T08:37:00-03:00",
            respostas: [],
            observacoesInternas: [],
            historico: [
                {
                    id: "hist-002-a",
                    tipo: "criacao",
                    autor: "Pedro Henrique",
                    descricao: "Feedback enviado.",
                    criadoEm: "2026-09-09T18:22:00-03:00",
                    visibilidade: "publica"
                },
                {
                    id: "hist-002-b",
                    tipo: "status",
                    autor: "Equipe JurisHome",
                    descricao: "Estamos verificando o problema de acesso.",
                    criadoEm: "2026-09-10T08:37:00-03:00",
                    visibilidade: "publica"
                }
            ],
            novo: false,
            arquivado: false
        }
    ];

    let memoria = copiar(DADOS_INICIAIS);

    function copiar(valor) {
        return JSON.parse(JSON.stringify(valor));
    }

    function ler() {
        try {
            const salvo = window.sessionStorage.getItem(STORAGE_KEY);
            if (salvo) return JSON.parse(salvo);
            window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(memoria));
        } catch (erro) {
            return copiar(memoria);
        }
        return copiar(memoria);
    }

    function salvar(registros) {
        memoria = copiar(registros);
        try {
            window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(registros));
        } catch (erro) {
            return;
        }
    }

    function gerarId(prefixo) {
        const identificador = window.crypto && window.crypto.randomUUID
            ? window.crypto.randomUUID()
            : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        return `${prefixo}-${identificador}`;
    }

    function gerarProtocolo(registros) {
        const agora = new Date();
        const data = [
            agora.getFullYear(),
            String(agora.getMonth() + 1).padStart(2, "0"),
            String(agora.getDate()).padStart(2, "0")
        ].join("");
        let protocolo;

        do {
            protocolo = `JH-${data}-${String(Math.floor(1000 + Math.random() * 9000))}`;
        } while (registros.some((item) => item.protocolo === protocolo));

        return protocolo;
    }

    function prepararParaUsuario(feedback) {
        const registro = copiar(feedback);
        delete registro.observacoesInternas;
        registro.historico = registro.historico.filter((evento) => evento.visibilidade !== "interna");
        return registro;
    }

    function listar() {
        return copiar(ler());
    }

    function buscarPorId(id) {
        const feedback = ler().find((item) => item.id === id);
        return feedback ? copiar(feedback) : null;
    }

    function criar(dados) {
        const registros = ler();
        const agora = new Date().toISOString();
        const feedback = {
            id: gerarId("fb"),
            protocolo: gerarProtocolo(registros),
            usuario: copiar(CURRENT_USER),
            tipo: dados.tipo,
            assunto: dados.assunto.trim(),
            mensagem: dados.mensagem.trim(),
            avaliacao: dados.avaliacao || null,
            status: "Recebido",
            prioridade: "Normal",
            criadoEm: agora,
            atualizadoEm: agora,
            respostas: [],
            observacoesInternas: [],
            historico: [
                {
                    id: gerarId("hist"),
                    tipo: "criacao",
                    autor: CURRENT_USER.nome,
                    descricao: "Feedback enviado.",
                    criadoEm: agora,
                    visibilidade: "publica"
                }
            ],
            novo: true,
            arquivado: false
        };

        registros.unshift(feedback);
        salvar(registros);
        return prepararParaUsuario(feedback);
    }

    function alterar(id, acao) {
        const registros = ler();
        const indice = registros.findIndex((item) => item.id === id);
        if (indice < 0) throw new Error("Feedback não encontrado.");

        acao(registros[indice]);
        registros[indice].atualizadoEm = new Date().toISOString();
        salvar(registros);
        return copiar(registros[indice]);
    }

    function adicionarHistorico(feedback, tipo, descricao, visibilidade) {
        feedback.historico.push({
            id: gerarId("hist"),
            tipo,
            autor: "Administrador JurisHome",
            descricao,
            criadoEm: new Date().toISOString(),
            visibilidade
        });
    }

    function alterarStatus(id, novoStatus) {
        if (!STATUS.includes(novoStatus)) throw new Error("Status inválido.");
        return alterar(id, (feedback) => {
            feedback.status = novoStatus;
            feedback.arquivado = novoStatus === "Arquivado";
            adicionarHistorico(feedback, "status", `Status: ${novoStatus}.`, "publica");
        });
    }

    function alterarPrioridade(id, novaPrioridade) {
        if (!PRIORIDADES.includes(novaPrioridade)) throw new Error("Prioridade inválida.");
        return alterar(id, (feedback) => {
            feedback.prioridade = novaPrioridade;
            adicionarHistorico(feedback, "prioridade", `Prioridade: ${novaPrioridade}.`, "interna");
        });
    }

    function responder(id, mensagem) {
        const texto = String(mensagem || "").trim();
        if (!texto) throw new Error("Digite uma resposta antes de enviar.");

        return alterar(id, (feedback) => {
            const agora = new Date().toISOString();
            feedback.respostas.push({
                id: gerarId("resp"),
                autor: "Equipe JurisHome",
                papel: "administrador",
                mensagem: texto,
                criadoEm: agora
            });
            feedback.status = "Respondido";
            feedback.arquivado = false;
            feedback.novo = false;
            adicionarHistorico(feedback, "resposta", "Resposta enviada.", "publica");
        });
    }

    function adicionarObservacao(id, mensagem) {
        const texto = String(mensagem || "").trim();
        if (!texto) throw new Error("Digite uma observação interna antes de adicionar.");

        return alterar(id, (feedback) => {
            feedback.observacoesInternas.push({
                id: gerarId("obs"),
                autor: "Administrador JurisHome",
                mensagem: texto,
                criadoEm: new Date().toISOString()
            });
            adicionarHistorico(feedback, "observacao", "Observação adicionada.", "interna");
        });
    }

    function arquivar(id) {
        return alterarStatus(id, "Arquivado");
    }

    function marcarComoVisto(id) {
        return alterar(id, (feedback) => {
            feedback.novo = false;
        });
    }

    function aguardar(tempo = 650) {
        return new Promise((resolve) => window.setTimeout(resolve, tempo));
    }

    function restaurarDadosIniciais() {
        salvar(copiar(DADOS_INICIAIS));
    }

    window.FeedbackMockService = Object.freeze({
        TIPOS,
        STATUS,
        PRIORIDADES,
        listar,
        buscarPorId,
        criar,
        alterarStatus,
        alterarPrioridade,
        responder,
        adicionarObservacao,
        arquivar,
        marcarComoVisto,
        aguardar,
        restaurarDadosIniciais
    });
})();
