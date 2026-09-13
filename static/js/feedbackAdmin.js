(function () {
    "use strict";

    const service = window.FeedbackMockService;
    if (!service) {
        console.error("Serviço de feedback indisponível.");
        return;
    }

    const formatadorData = new Intl.DateTimeFormat("pt-BR", {
        day: "2-digit",
        month: "short",
        year: "numeric"
    });
    const formatadorDataHora = new Intl.DateTimeFormat("pt-BR", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });

    let feedbackSelecionadoId = null;
    let ultimoAcionadorDoDialogo = null;
    let temporizadorToast = null;

    document.addEventListener("DOMContentLoaded", iniciar);

    async function iniciar() {
        aplicarTemaSalvo();
        preencherDataAtual();
        configurarMenuPerfil();
        preencherStatus();
        configurarFiltros();
        configurarDialogo();
        configurarSincronizacao();
        await atualizarDoServidor();
    }

    function aplicarTemaSalvo() {
        document.body.classList.toggle("modo-claro", window.localStorage.getItem("tema_juris") === "claro");
    }

    function preencherDataAtual() {
        const alvo = document.getElementById("data-atual");
        if (alvo) alvo.textContent = new Intl.DateTimeFormat("pt-BR").format(new Date());
    }

    function configurarMenuPerfil() {
        const botao = document.getElementById("btn-perfil");
        const menu = document.getElementById("dropdown-perfil");
        if (!botao || !menu) return;

        const fecharMenu = () => {
            menu.classList.remove("ativo");
            botao.setAttribute("aria-expanded", "false");
        };

        botao.addEventListener("click", (evento) => {
            evento.stopPropagation();
            const aberto = menu.classList.toggle("ativo");
            botao.setAttribute("aria-expanded", String(aberto));
        });
        document.addEventListener("click", (evento) => {
            if (!menu.contains(evento.target) && !botao.contains(evento.target)) fecharMenu();
        });
        document.addEventListener("keydown", (evento) => {
            if (evento.key === "Escape") fecharMenu();
        });
    }

    function preencherStatus() {
        ["admin-status-filter", "feedback-admin-status"].forEach((id) => {
            const select = document.getElementById(id);
            service.STATUS.forEach((status) => {
                const opcao = document.createElement("option");
                opcao.value = status;
                opcao.textContent = status;
                select.append(opcao);
            });
        });
    }

    function configurarFiltros() {
        document.getElementById("admin-search").addEventListener("input", renderizarLista);
        document.getElementById("admin-status-filter").addEventListener("change", renderizarLista);
        document.getElementById("admin-clear-filters").addEventListener("click", limparFiltros);
        document.getElementById("admin-empty-clear").addEventListener("click", limparFiltros);
        document.getElementById("feedback-filter-form").addEventListener("submit", (evento) => evento.preventDefault());
    }

    function limparFiltros() {
        document.getElementById("admin-search").value = "";
        document.getElementById("admin-status-filter").value = "";
        renderizarLista();
        document.getElementById("admin-search").focus();
    }

    function configurarSincronizacao() {
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) atualizarDoServidor();
        });
        window.addEventListener("focus", atualizarDoServidor);
    }

    async function atualizarDoServidor() {
        try {
            await service.inicializar();
            renderizarTudo();

            const dialogo = document.getElementById("feedback-admin-dialog");
            if (dialogo.open && feedbackSelecionadoId) {
                preencherDetalhes(service.buscarPorId(feedbackSelecionadoId));
            }
        } catch (erro) {
            renderizarTudo();
            mostrarToast(erro.message || "Não foi possível atualizar os feedbacks.", true);
        }
    }

    function renderizarTudo() {
        const registros = service.listar();
        definirTexto("summary-total", registros.length);
        definirTexto("summary-pendente", registros.filter((item) => ["Recebido", "Em análise"].includes(item.status)).length);
        definirTexto("summary-respondido", registros.filter((item) => ["Respondido", "Resolvido"].includes(item.status)).length);
        renderizarLista();
    }

    function obterFiltrados() {
        const termo = normalizarTexto(document.getElementById("admin-search").value.trim());
        const status = document.getElementById("admin-status-filter").value;

        return service.listar()
            .filter((item) => {
                const alvo = normalizarTexto([
                    item.protocolo,
                    item.usuario.email,
                    item.tipo,
                    item.assunto
                ].join(" "));
                return (!termo || alvo.includes(termo)) && (!status || item.status === status);
            })
            .sort((a, b) => new Date(b.criadoEm) - new Date(a.criadoEm));
    }

    function renderizarLista() {
        const registros = obterFiltrados();
        const corpoTabela = document.getElementById("admin-feedback-table-body");
        const listaMobile = document.getElementById("admin-feedback-mobile-list");
        const vazio = document.getElementById("admin-feedback-empty");

        corpoTabela.replaceChildren();
        listaMobile.replaceChildren();
        registros.forEach((feedback) => {
            corpoTabela.append(criarLinhaTabela(feedback));
            listaMobile.append(criarCardMobile(feedback));
        });

        definirTexto(
            "admin-result-count",
            `${registros.length} ${registros.length === 1 ? "registro encontrado" : "registros encontrados"}`
        );
        vazio.hidden = registros.length !== 0;
        document.querySelector(".feedback-table-wrap").classList.toggle("is-empty", registros.length === 0);
        listaMobile.classList.toggle("is-empty", registros.length === 0);
    }

    function criarLinhaTabela(feedback) {
        const linha = document.createElement("tr");

        const protocoloCelula = document.createElement("td");
        const protocolo = criarElemento("div", "feedback-table-protocol-cell");
        protocolo.append(criarElemento("span", "feedback-protocol", feedback.protocolo));
        if (feedback.novo) protocolo.append(criarElemento("span", "feedback-new-badge", "Novo"));
        protocoloCelula.append(protocolo);

        const usuarioCelula = document.createElement("td");
        const usuario = criarElemento("div", "feedback-table-user");
        usuario.append(criarElemento("strong", "", feedback.usuario.email));
        usuarioCelula.append(usuario);

        const assuntoCelula = document.createElement("td");
        const assunto = criarElemento("div", "feedback-table-subject");
        assunto.append(criarElemento("small", "", feedback.tipo));
        assunto.append(criarElemento("strong", "", feedback.assunto));
        assuntoCelula.append(assunto);

        const statusCelula = document.createElement("td");
        statusCelula.append(criarBadgeStatus(feedback.status));
        const dataCelula = criarElemento("td", "", formatarData(feedback.criadoEm));
        const acaoCelula = document.createElement("td");
        acaoCelula.append(criarBotaoDetalhes(feedback));

        linha.append(protocoloCelula, usuarioCelula, assuntoCelula, statusCelula, dataCelula, acaoCelula);
        return linha;
    }

    function criarCardMobile(feedback) {
        const card = criarElemento("article", "feedback-mobile-admin-card");
        const cabecalho = criarElemento("div", "feedback-mobile-admin-card-header");
        cabecalho.append(criarElemento("span", "feedback-protocol", feedback.protocolo));
        if (feedback.novo) cabecalho.append(criarElemento("span", "feedback-new-badge", "Novo"));

        card.append(cabecalho);
        card.append(criarElemento("h3", "", feedback.assunto));
        card.append(criarElemento("p", "", `${feedback.usuario.email} · ${feedback.tipo}`));

        const rodape = criarElemento("div", "feedback-mobile-admin-card-footer");
        rodape.append(criarBadgeStatus(feedback.status), criarBotaoDetalhes(feedback));
        card.append(rodape);
        return card;
    }

    function criarBotaoDetalhes(feedback) {
        const botao = criarElemento("button", "feedback-table-action", "Abrir");
        botao.type = "button";
        botao.setAttribute("aria-label", `Abrir ${feedback.protocolo}: ${feedback.assunto}`);
        botao.addEventListener("click", () => abrirDetalhes(feedback.id, botao));
        return botao;
    }

    function configurarDialogo() {
        const dialogo = document.getElementById("feedback-admin-dialog");
        document.getElementById("feedback-admin-dialog-close").addEventListener("click", () => dialogo.close());
        dialogo.addEventListener("click", (evento) => {
            if (evento.target === dialogo) dialogo.close();
        });
        dialogo.addEventListener("close", () => {
            if (ultimoAcionadorDoDialogo) ultimoAcionadorDoDialogo.focus();
        });
        document.getElementById("feedback-admin-status").addEventListener("change", alterarStatus);
        document.getElementById("feedback-admin-send-response").addEventListener("click", enviarResposta);
    }

    async function abrirDetalhes(id, acionador) {
        feedbackSelecionadoId = id;
        ultimoAcionadorDoDialogo = acionador;
        const atual = service.buscarPorId(id);
        if (!atual) return;
        if (atual.novo) await service.marcarComoVisto(id);
        preencherDetalhes(service.buscarPorId(id));
        renderizarLista();
        document.getElementById("feedback-admin-dialog").showModal();
    }

    function preencherDetalhes(feedback) {
        if (!feedback) return;
        definirTexto("feedback-admin-dialog-protocol", feedback.protocolo);
        definirTexto("feedback-admin-dialog-title", feedback.assunto);
        document.getElementById("feedback-admin-dialog-new").hidden = !feedback.novo;
        const email = document.getElementById("feedback-admin-user-email");
        email.textContent = feedback.usuario.email;
        email.href = `mailto:${feedback.usuario.email}`;
        definirTexto("feedback-admin-avatar", "@");
        definirTexto("feedback-admin-created-date", `Enviado em ${formatarDataHora(feedback.criadoEm)}`);
        definirTexto("feedback-admin-type", feedback.tipo);
        definirTexto("feedback-admin-rating", formatarAvaliacao(feedback.avaliacao));
        definirTexto("feedback-admin-subject", feedback.assunto);
        definirTexto("feedback-admin-message", feedback.mensagem);
        definirTexto("feedback-admin-updated-date", formatarDataHora(feedback.atualizadoEm));
        document.getElementById("feedback-admin-status").value = feedback.status;
        renderizarRespostas(feedback.respostas);
    }

    function renderizarRespostas(respostas) {
        const alvo = document.getElementById("feedback-admin-responses");
        alvo.replaceChildren();

        if (!respostas.length) {
            alvo.append(criarElemento("p", "feedback-no-responses", "Nenhuma resposta enviada ainda."));
            return;
        }

        respostas.forEach((resposta) => {
            const item = criarElemento("article", "feedback-simple-response-item");
            item.append(criarElemento("p", "", resposta.mensagem));
            item.append(criarElemento("small", "", `${resposta.autor} · ${formatarDataHora(resposta.criadoEm)}`));
            alvo.append(item);
        });
    }

    async function alterarStatus(evento) {
        if (!feedbackSelecionadoId) return;
        try {
            const atualizado = await service.alterarStatus(feedbackSelecionadoId, evento.target.value);
            preencherDetalhes(atualizado);
            renderizarTudo();
            mostrarToast(`Status alterado para ${atualizado.status}.`);
        } catch (erro) {
            mostrarToast(erro.message, true);
        }
    }

    async function enviarResposta() {
        const campo = document.getElementById("feedback-admin-response");
        const erroAlvo = document.getElementById("feedback-admin-response-error");
        const texto = campo.value.trim();
        if (!texto) {
            campo.setAttribute("aria-invalid", "true");
            erroAlvo.textContent = "Digite uma resposta antes de enviar.";
            campo.focus();
            return;
        }

        campo.removeAttribute("aria-invalid");
        erroAlvo.textContent = "";
        const botao = document.getElementById("feedback-admin-send-response");
        const textoBotao = botao.querySelector(".feedback-button-text");
        botao.disabled = true;
        campo.disabled = true;
        botao.classList.add("is-loading");
        textoBotao.textContent = "Enviando...";

        try {
            await service.aguardar(500);
            const atualizado = await service.responder(feedbackSelecionadoId, texto);
            campo.value = "";
            preencherDetalhes(atualizado);
            renderizarTudo();
            mostrarToast("Resposta enviada.");
        } catch (erro) {
            mostrarToast(erro.message, true);
        } finally {
            botao.disabled = false;
            campo.disabled = false;
            botao.classList.remove("is-loading");
            textoBotao.textContent = "Enviar resposta";
        }
    }

    function mostrarToast(mensagem, erro = false) {
        const toast = document.getElementById("feedback-admin-toast");
        window.clearTimeout(temporizadorToast);
        toast.textContent = mensagem;
        toast.hidden = false;
        toast.setAttribute("role", erro ? "alert" : "status");
        toast.classList.toggle("is-error", erro);
        temporizadorToast = window.setTimeout(() => {
            toast.hidden = true;
        }, 3600);
    }

    function criarBadgeStatus(status) {
        return criarElemento("span", `feedback-status-badge feedback-status-${normalizarClasse(status)}`, status);
    }

    function normalizarClasse(texto) {
        return normalizarTexto(texto).replace(/\s+/g, "-");
    }

    function normalizarTexto(texto) {
        return String(texto).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    }

    function formatarData(valor) {
        return formatadorData.format(new Date(valor));
    }

    function formatarDataHora(valor) {
        return formatadorDataHora.format(new Date(valor));
    }

    function formatarAvaliacao(valor) {
        return valor ? `${"★".repeat(valor)}${"☆".repeat(5 - valor)} (${valor}/5)` : "Não informada";
    }

    function criarElemento(tag, classe, texto) {
        const elemento = document.createElement(tag);
        if (classe) elemento.className = classe;
        if (texto !== undefined) elemento.textContent = texto;
        return elemento;
    }

    function definirTexto(id, texto) {
        document.getElementById(id).textContent = texto;
    }
})();
