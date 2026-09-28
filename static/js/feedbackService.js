(function () {
    "use strict";

    const STATUS = Object.freeze(["Recebido", "Em análise", "Respondido", "Resolvido", "Arquivado"]);
    const PRIORIDADES = Object.freeze(["Baixa", "Normal", "Alta", "Urgente"]);
    let registros = [];

    function copiar(valor) {
        return JSON.parse(JSON.stringify(valor));
    }

    async function requisitar(url, opcoes = {}) {
        const headers = { ...(opcoes.headers || {}) };
        if (opcoes.body !== undefined) headers["Content-Type"] = "application/json";

        let resposta;
        try {
            resposta = await window.fetch(url, {
                credentials: "same-origin",
                ...opcoes,
                headers,
            });
        } catch (_) {
            throw new Error("Nao foi possivel conectar ao JurisHome. Verifique se o servidor esta em execucao.");
        }

        if (resposta.status === 204) {
            if (!resposta.ok) throw new Error("Nao foi possivel concluir a operacao.");
            return null;
        }

        const corpo = await resposta.json().catch(() => ({}));
        if (!resposta.ok) {
            const detalhe = typeof corpo.detail === "string" ? corpo.detail : "Nao foi possivel concluir a operacao.";
            throw new Error(detalhe);
        }
        return corpo;
    }

    function atualizarCache(feedback) {
        const indice = registros.findIndex((item) => item.id === feedback.id);
        if (indice >= 0) registros[indice] = copiar(feedback);
        else registros.unshift(copiar(feedback));
        return copiar(feedback);
    }

    async function inicializar() {
        const resposta = await requisitar("/api/admin/feedbacks");
        registros = Array.isArray(resposta) ? resposta : [];
        return listar();
    }

    function listar() {
        return copiar(registros);
    }

    function buscarPorId(id) {
        const feedback = registros.find((item) => item.id === id);
        return feedback ? copiar(feedback) : null;
    }

    async function criar(dados) {
        const feedback = await requisitar("/api/feedbacks", {
            method: "POST",
            body: JSON.stringify(dados),
        });
        return atualizarCache(feedback);
    }

    async function alterarStatus(id, status) {
        const feedback = await requisitar(`/api/admin/feedbacks/${encodeURIComponent(id)}/status`, {
            method: "PATCH",
            body: JSON.stringify({ status }),
        });
        return atualizarCache(feedback);
    }

    async function alterarPrioridade(id, prioridade) {
        const feedback = await requisitar(`/api/admin/feedbacks/${encodeURIComponent(id)}/prioridade`, {
            method: "PATCH",
            body: JSON.stringify({ prioridade }),
        });
        return atualizarCache(feedback);
    }

    async function responder(id, mensagem) {
        const feedback = await requisitar(`/api/admin/feedbacks/${encodeURIComponent(id)}/respostas`, {
            method: "POST",
            body: JSON.stringify({ mensagem }),
        });
        return atualizarCache(feedback);
    }

    async function adicionarObservacao(id, mensagem) {
        const feedback = await requisitar(`/api/admin/feedbacks/${encodeURIComponent(id)}/observacoes`, {
            method: "POST",
            body: JSON.stringify({ mensagem }),
        });
        return atualizarCache(feedback);
    }

    async function arquivar(id) {
        const feedback = await requisitar(`/api/admin/feedbacks/${encodeURIComponent(id)}/arquivar`, {
            method: "PATCH",
        });
        return atualizarCache(feedback);
    }

    async function marcarComoVisto(id) {
        const feedback = await requisitar(`/api/admin/feedbacks/${encodeURIComponent(id)}/visto`, {
            method: "PATCH",
        });
        return atualizarCache(feedback);
    }

    window.FeedbackService = Object.freeze({
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
    });
})();
