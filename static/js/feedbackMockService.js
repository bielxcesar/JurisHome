(function () {
    "use strict";

    const STORAGE_KEY = "jurishome_feedback_v6";
    const LEGACY_STORAGE_KEY = "jurishome_feedback_v5";
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

    let memoria = lerCache();

    function copiar(valor) {
        return JSON.parse(JSON.stringify(valor));
    }

    function lerCache() {
        try {
            const atual = window.localStorage.getItem(STORAGE_KEY);
            if (atual) return JSON.parse(atual);

            const legado = window.localStorage.getItem(LEGACY_STORAGE_KEY)
                || window.sessionStorage.getItem(LEGACY_STORAGE_KEY);
            if (legado) {
                const registros = JSON.parse(legado);
                window.localStorage.setItem(STORAGE_KEY, JSON.stringify(registros));
                return registros;
            }
        } catch (erro) {
            console.warn("Não foi possível ler o cache de feedbacks.", erro);
        }
        return [];
    }

    function salvarCache() {
        try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(memoria));
        } catch (erro) {
            console.warn("Não foi possível atualizar o cache de feedbacks.", erro);
        }
    }

    function gerarId(prefixo) {
        const identificador = window.crypto?.randomUUID
            ? window.crypto.randomUUID()
            : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        return `${prefixo}-${identificador}`;
    }

    function gerarProtocolo() {
        const agora = new Date();
        const data = [
            agora.getFullYear(),
            String(agora.getMonth() + 1).padStart(2, "0"),
            String(agora.getDate()).padStart(2, "0")
        ].join("");
        return `JH-${data}-${String(Math.floor(1000 + Math.random() * 9000))}`;
    }

    async function requisitar(url, opcoes = {}) {
        let resposta;
        try {
            resposta = await window.fetch(url, {
                ...opcoes,
                headers: {
                    "Content-Type": "application/json",
                    ...(opcoes.headers || {})
                }
            });
        } catch (erro) {
            erro.apiIndisponivel = true;
            throw erro;
        }

        if (!resposta.ok) {
            let mensagem = "Não foi possível concluir a operação.";
            try {
                const corpo = await resposta.json();
                mensagem = typeof corpo.detail === "string" ? corpo.detail : mensagem;
            } catch (erro) {
                // Mantém a mensagem padrão quando a resposta não é JSON.
            }
            const erro = new Error(mensagem);
            erro.apiRespondeu = true;
            throw erro;
        }
        return resposta.json();
    }

    function atualizarMemoria(feedback) {
        const indice = memoria.findIndex((item) => item.id === feedback.id);
        if (indice >= 0) memoria[indice] = copiar(feedback);
        else memoria.unshift(copiar(feedback));
        salvarCache();
        return copiar(feedback);
    }

    async function inicializar() {
        try {
            const registros = await requisitar("/api/admin/feedbacks");
            memoria = Array.isArray(registros) ? registros : [];
            salvarCache();
            return listar();
        } catch (erro) {
            if (!erro.apiIndisponivel) throw erro;
            memoria = lerCache();
            return listar();
        }
    }

    function listar() {
        return copiar(memoria);
    }

    function buscarPorId(id) {
        const feedback = memoria.find((item) => item.id === id);
        return feedback ? copiar(feedback) : null;
    }

    function criarLocal(dados) {
        const agora = new Date().toISOString();
        return atualizarMemoria({
            id: gerarId("fb"),
            protocolo: gerarProtocolo(),
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
            historico: [{
                id: gerarId("hist"),
                tipo: "criacao",
                autor: CURRENT_USER.nome,
                descricao: "Feedback enviado.",
                criadoEm: agora,
                visibilidade: "publica"
            }],
            novo: true,
            arquivado: false
        });
    }

    async function criar(dados) {
        try {
            const feedback = await requisitar("/api/feedbacks", {
                method: "POST",
                body: JSON.stringify(dados)
            });
            return atualizarMemoria(feedback);
        } catch (erro) {
            if (!erro.apiIndisponivel) throw erro;
            return criarLocal(dados);
        }
    }

    function alterarLocal(id, acao) {
        const indice = memoria.findIndex((item) => item.id === id);
        if (indice < 0) throw new Error("Feedback não encontrado.");
        acao(memoria[indice]);
        memoria[indice].atualizadoEm = new Date().toISOString();
        salvarCache();
        return copiar(memoria[indice]);
    }

    async function alterarNoServidor(id, caminho, metodo, dados, alternativaLocal) {
        try {
            const feedback = await requisitar(`/api/admin/feedbacks/${encodeURIComponent(id)}/${caminho}`, {
                method: metodo,
                body: dados === undefined ? undefined : JSON.stringify(dados)
            });
            return atualizarMemoria(feedback);
        } catch (erro) {
            if (!erro.apiIndisponivel) throw erro;
            return alterarLocal(id, alternativaLocal);
        }
    }

    function adicionarHistoricoLocal(feedback, tipo, descricao, visibilidade) {
        feedback.historico.push({
            id: gerarId("hist"),
            tipo,
            autor: "Administrador JurisHome",
            descricao,
            criadoEm: new Date().toISOString(),
            visibilidade
        });
    }

    async function alterarStatus(id, novoStatus) {
        if (!STATUS.includes(novoStatus)) throw new Error("Status inválido.");
        return alterarNoServidor(id, "status", "PATCH", { status: novoStatus }, (feedback) => {
            feedback.status = novoStatus;
            feedback.arquivado = novoStatus === "Arquivado";
            adicionarHistoricoLocal(feedback, "status", `Status: ${novoStatus}.`, "publica");
        });
    }

    async function alterarPrioridade(id, novaPrioridade) {
        if (!PRIORIDADES.includes(novaPrioridade)) throw new Error("Prioridade inválida.");
        return alterarNoServidor(id, "prioridade", "PATCH", { prioridade: novaPrioridade }, (feedback) => {
            feedback.prioridade = novaPrioridade;
            adicionarHistoricoLocal(feedback, "prioridade", `Prioridade: ${novaPrioridade}.`, "interna");
        });
    }

    async function responder(id, mensagem) {
        const texto = String(mensagem || "").trim();
        if (!texto) throw new Error("Digite uma resposta antes de enviar.");
        return alterarNoServidor(id, "respostas", "POST", { mensagem: texto }, (feedback) => {
            feedback.respostas.push({
                id: gerarId("resp"),
                autor: "Equipe JurisHome",
                papel: "administrador",
                mensagem: texto,
                criadoEm: new Date().toISOString()
            });
            feedback.status = "Respondido";
            feedback.arquivado = false;
            feedback.novo = false;
            adicionarHistoricoLocal(feedback, "resposta", "Resposta enviada.", "publica");
        });
    }

    async function adicionarObservacao(id, mensagem) {
        const texto = String(mensagem || "").trim();
        if (!texto) throw new Error("Digite uma observação interna antes de adicionar.");
        return alterarNoServidor(id, "observacoes", "POST", { mensagem: texto }, (feedback) => {
            feedback.observacoesInternas.push({
                id: gerarId("obs"),
                autor: "Administrador JurisHome",
                mensagem: texto,
                criadoEm: new Date().toISOString()
            });
            adicionarHistoricoLocal(feedback, "observacao", "Observação adicionada.", "interna");
        });
    }

    async function arquivar(id) {
        return alterarNoServidor(id, "arquivar", "PATCH", undefined, (feedback) => {
            feedback.status = "Arquivado";
            feedback.arquivado = true;
            adicionarHistoricoLocal(feedback, "status", "Status: Arquivado.", "publica");
        });
    }

    async function marcarComoVisto(id) {
        return alterarNoServidor(id, "visto", "PATCH", undefined, (feedback) => {
            feedback.novo = false;
        });
    }

    function aguardar(tempo = 350) {
        return new Promise((resolve) => window.setTimeout(resolve, tempo));
    }

    window.FeedbackMockService = Object.freeze({
        STORAGE_KEY,
        TIPOS,
        STATUS,
        PRIORIDADES,
        inicializar,
        listar,
        buscarPorId,
        criar,
        alterarStatus,
        alterarPrioridade,
        responder,
        adicionarObservacao,
        arquivar,
        marcarComoVisto,
        aguardar
    });
})();
