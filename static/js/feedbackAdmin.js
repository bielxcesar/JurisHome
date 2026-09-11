(function () {
    "use strict";

    const service = window.FeedbackMockService;
    if (!service) {
        console.error("Serviço de feedback indisponível.");
        return;
    }

    const dateFormatter = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
    const dateTimeFormatter = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    let feedbackSelecionadoId = null;
    let ultimoAcionadorDoDialogo = null;
    let toastTimer = null;

    document.addEventListener("DOMContentLoaded", iniciar);

    function iniciar() {
        aplicarTemaSalvo();
        preencherDataAtual();
        configurarMenuPerfil();
        preencherOpcoes();
        configurarFiltros();
        configurarDialogo();
        renderizarTudo();
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

        function fecharMenu() {
            menu.classList.remove("ativo");
            botao.setAttribute("aria-expanded", "false");
        }
    }

    function preencherOpcoes() {
        preencherSelect("admin-type-filter", service.TIPOS, false);
        preencherSelect("admin-status-filter", service.STATUS, false);
        preencherSelect("admin-priority-filter", service.PRIORIDADES, false);
        preencherSelect("feedback-admin-status", service.STATUS, true);
        preencherSelect("feedback-admin-priority", service.PRIORIDADES, true);
    }

    function preencherSelect(id, opcoes, limparPrimeiro) {
        const select = document.getElementById(id);
        if (limparPrimeiro) select.replaceChildren();
        opcoes.forEach((valor) => {
            const option = document.createElement("option");
            option.value = valor;
            option.textContent = valor;
            select.append(option);
        });
    }

    function configurarFiltros() {
        const ids = ["admin-search", "admin-type-filter", "admin-status-filter", "admin-priority-filter", "admin-order"];
        ids.forEach((id) => {
            const campo = document.getElementById(id);
            campo.addEventListener(id === "admin-search" ? "input" : "change", renderizarLista);
        });
        document.getElementById("admin-clear-filters").addEventListener("click", limparFiltros);
        document.getElementById("admin-empty-clear").addEventListener("click", limparFiltros);
        document.getElementById("feedback-filter-form").addEventListener("submit", (evento) => evento.preventDefault());
    }

    function limparFiltros() {
        document.getElementById("admin-search").value = "";
        document.getElementById("admin-type-filter").value = "";
        document.getElementById("admin-status-filter").value = "";
        document.getElementById("admin-priority-filter").value = "";
        document.getElementById("admin-order").value = "desc";
        renderizarLista();
        document.getElementById("admin-search").focus();
    }

    function renderizarTudo() {
        renderizarResumo();
        renderizarLista();
    }

    function renderizarResumo() {
        const registros = service.listar();
        definirTexto("summary-total", registros.length);
        definirTexto("summary-recebido", contarStatus(registros, "Recebido"));
        definirTexto("summary-em-analise", contarStatus(registros, "Em análise"));
        definirTexto("summary-respondido", contarStatus(registros, "Respondido"));
        definirTexto("summary-resolvido", contarStatus(registros, "Resolvido"));
    }

    function contarStatus(registros, status) {
        return registros.filter((item) => item.status === status).length;
    }

    function obterFiltrados() {
        const termo = normalizarTexto(document.getElementById("admin-search").value.trim());
        const tipo = document.getElementById("admin-type-filter").value;
        const status = document.getElementById("admin-status-filter").value;
        const prioridade = document.getElementById("admin-priority-filter").value;
        const ordem = document.getElementById("admin-order").value;

        return service.listar()
            .filter((item) => {
                const alvo = normalizarTexto([item.protocolo, item.usuario.nome, item.usuario.email, item.assunto].join(" "));
                return (!termo || alvo.includes(termo))
                    && (!tipo || item.tipo === tipo)
                    && (!status || item.status === status)
                    && (!prioridade || item.prioridade === prioridade);
            })
            .sort((a, b) => ordem === "asc"
                ? new Date(a.criadoEm) - new Date(b.criadoEm)
                : new Date(b.criadoEm) - new Date(a.criadoEm));
    }

    function renderizarLista() {
        const registros = obterFiltrados();
        const corpoTabela = document.getElementById("admin-feedback-table-body");
        const listaMobile = document.getElementById("admin-feedback-mobile-list");
        const vazio = document.getElementById("admin-feedback-empty");
        const contador = document.getElementById("admin-result-count");

        corpoTabela.replaceChildren();
        listaMobile.replaceChildren();
        registros.forEach((feedback) => {
            corpoTabela.append(criarLinhaTabela(feedback));
            listaMobile.append(criarCardMobile(feedback));
        });

        contador.textContent = `${registros.length} ${registros.length === 1 ? "registro encontrado" : "registros encontrados"}`;
        vazio.hidden = registros.length !== 0;
        document.querySelector(".feedback-table-wrap").classList.toggle("is-empty", registros.length === 0);
        listaMobile.classList.toggle("is-empty", registros.length === 0);
    }

    function criarLinhaTabela(feedback) {
        const linha = document.createElement("tr");

        const protocoloCell = document.createElement("td");
        const protocoloWrap = criarElemento("div", "feedback-table-protocol-cell");
        protocoloWrap.append(criarElemento("span", "feedback-protocol", feedback.protocolo));
        if (feedback.novo) protocoloWrap.append(criarElemento("span", "feedback-new-badge", "Novo"));
        protocoloCell.append(protocoloWrap);

        const usuarioCell = document.createElement("td");
        const usuario = criarElemento("div", "feedback-table-user");
        usuario.append(criarElemento("strong", "", feedback.usuario.nome));
        usuario.append(criarElemento("small", "", feedback.usuario.email));
        usuarioCell.append(usuario);

        const assuntoCell = document.createElement("td");
        const assunto = criarElemento("div", "feedback-table-subject");
        assunto.append(criarElemento("small", "", feedback.tipo));
        assunto.append(criarElemento("strong", "", feedback.assunto));
        assuntoCell.append(assunto);

        const statusCell = document.createElement("td");
        statusCell.append(criarBadgeStatus(feedback.status));
        const prioridadeCell = document.createElement("td");
        prioridadeCell.append(criarBadgePrioridade(feedback.prioridade));
        const dataCell = criarElemento("td", "", formatarData(feedback.criadoEm));
        const acaoCell = document.createElement("td");
        acaoCell.append(criarBotaoDetalhes(feedback));

        linha.append(protocoloCell, usuarioCell, assuntoCell, statusCell, prioridadeCell, dataCell, acaoCell);
        return linha;
    }

    function criarCardMobile(feedback) {
        const card = criarElemento("article", "feedback-mobile-admin-card");
        const cabecalho = criarElemento("div", "feedback-mobile-admin-card-header");
        cabecalho.append(criarElemento("span", "feedback-protocol", feedback.protocolo));
        if (feedback.novo) cabecalho.append(criarElemento("span", "feedback-new-badge", "Novo"));

        card.append(cabecalho);
        card.append(criarElemento("h3", "", feedback.assunto));
        card.append(criarElemento("p", "", `${feedback.usuario.nome} · ${feedback.usuario.email}`));

        const rodape = criarElemento("div", "feedback-mobile-admin-card-footer");
        const badges = criarElemento("div", "feedback-mobile-admin-card-badges");
        badges.append(criarBadgeStatus(feedback.status), criarBadgePrioridade(feedback.prioridade));
        rodape.append(badges, criarBotaoDetalhes(feedback));
        card.append(rodape);
        return card;
    }

    function criarBotaoDetalhes(feedback) {
        const botao = criarElemento("button", "feedback-table-action", "Ver detalhes");
        botao.type = "button";
        botao.setAttribute("aria-label", `Ver detalhes de ${feedback.protocolo}: ${feedback.assunto}`);
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
            ocultarConfirmacaoArquivo();
            if (ultimoAcionadorDoDialogo) ultimoAcionadorDoDialogo.focus();
        });

        document.getElementById("feedback-admin-status").addEventListener("change", alterarStatus);
        document.getElementById("feedback-admin-priority").addEventListener("change", alterarPrioridade);
        document.getElementById("feedback-admin-send-response").addEventListener("click", enviarResposta);
        document.getElementById("feedback-admin-add-note").addEventListener("click", adicionarObservacao);
        document.getElementById("feedback-admin-archive").addEventListener("click", exibirConfirmacaoArquivo);
        document.getElementById("feedback-archive-cancel").addEventListener("click", ocultarConfirmacaoArquivo);
        document.getElementById("feedback-archive-confirm-button").addEventListener("click", confirmarArquivo);
    }

    function abrirDetalhes(id, acionador) {
        feedbackSelecionadoId = id;
        ultimoAcionadorDoDialogo = acionador;
        const atual = service.buscarPorId(id);
        if (!atual) return;
        if (atual.novo) service.marcarComoVisto(id);
        preencherDetalhes(service.buscarPorId(id));
        renderizarLista();
        document.getElementById("feedback-admin-dialog").showModal();
    }

    function preencherDetalhes(feedback) {
        if (!feedback) return;
        definirTexto("feedback-admin-dialog-protocol", feedback.protocolo);
        definirTexto("feedback-admin-dialog-title", feedback.assunto);
        document.getElementById("feedback-admin-dialog-new").hidden = !feedback.novo;
        definirTexto("feedback-admin-user-name", feedback.usuario.nome);
        const email = document.getElementById("feedback-admin-user-email");
        email.textContent = feedback.usuario.email;
        email.href = `mailto:${feedback.usuario.email}`;
        definirTexto("feedback-admin-avatar", obterIniciais(feedback.usuario.nome));
        definirTexto("feedback-admin-created-date", `Enviado em ${formatarDataHora(feedback.criadoEm)}`);
        definirTexto("feedback-admin-type", feedback.tipo);
        definirTexto("feedback-admin-rating", formatarAvaliacao(feedback.avaliacao));
        definirTexto("feedback-admin-subject", feedback.assunto);
        definirTexto("feedback-admin-message", feedback.mensagem);
        definirTexto("feedback-admin-updated-date", formatarDataHora(feedback.atualizadoEm));
        document.getElementById("feedback-admin-status").value = feedback.status;
        document.getElementById("feedback-admin-priority").value = feedback.prioridade;

        const botaoArquivar = document.getElementById("feedback-admin-archive");
        botaoArquivar.disabled = feedback.arquivado;
        botaoArquivar.textContent = feedback.arquivado ? "Registro arquivado" : "Arquivar registro";
        if (!feedback.arquivado) {
            const icone = criarIcone("fa-regular fa-folder-closed");
            botaoArquivar.prepend(icone);
        }

        renderizarTimelineAdministrativa(feedback);
    }

    function alterarStatus(evento) {
        if (!feedbackSelecionadoId) return;
        try {
            const atualizado = service.alterarStatus(feedbackSelecionadoId, evento.target.value);
            preencherDetalhes(atualizado);
            renderizarTudo();
            mostrarToast(`Status: ${atualizado.status}.`);
        } catch (erro) {
            mostrarToast(erro.message, true);
        }
    }

    function alterarPrioridade(evento) {
        if (!feedbackSelecionadoId) return;
        try {
            const atualizado = service.alterarPrioridade(feedbackSelecionadoId, evento.target.value);
            preencherDetalhes(atualizado);
            renderizarTudo();
            mostrarToast(`Prioridade: ${atualizado.prioridade}.`);
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
            await service.aguardar(700);
            const atualizado = service.responder(feedbackSelecionadoId, texto);
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

    function adicionarObservacao() {
        const campo = document.getElementById("feedback-admin-note");
        const erroAlvo = document.getElementById("feedback-admin-note-error");
        const texto = campo.value.trim();
        if (!texto) {
            campo.setAttribute("aria-invalid", "true");
            erroAlvo.textContent = "Digite uma observação interna.";
            campo.focus();
            return;
        }

        try {
            campo.removeAttribute("aria-invalid");
            erroAlvo.textContent = "";
            const atualizado = service.adicionarObservacao(feedbackSelecionadoId, texto);
            campo.value = "";
            preencherDetalhes(atualizado);
            renderizarLista();
            mostrarToast("Observação salva.");
        } catch (erro) {
            mostrarToast(erro.message, true);
        }
    }

    function exibirConfirmacaoArquivo() {
        const confirmacao = document.getElementById("feedback-archive-confirm");
        confirmacao.hidden = false;
        document.getElementById("feedback-archive-cancel").focus();
    }

    function ocultarConfirmacaoArquivo() {
        document.getElementById("feedback-archive-confirm").hidden = true;
    }

    function confirmarArquivo() {
        if (!feedbackSelecionadoId) return;
        try {
            const atualizado = service.arquivar(feedbackSelecionadoId);
            ocultarConfirmacaoArquivo();
            preencherDetalhes(atualizado);
            renderizarTudo();
            mostrarToast(`Feedback ${atualizado.protocolo} arquivado.`);
        } catch (erro) {
            mostrarToast(erro.message, true);
        }
    }

    function renderizarTimelineAdministrativa(feedback) {
        const alvo = document.getElementById("feedback-admin-timeline");
        const eventos = feedback.historico.map((item) => ({ ...item, conteudo: item.descricao }));
        feedback.respostas.forEach((resposta) => eventos.push({
            id: resposta.id,
            autor: resposta.autor,
            conteudo: resposta.mensagem,
            criadoEm: resposta.criadoEm,
            visibilidade: "publica",
            rotulo: "Resposta enviada"
        }));
        feedback.observacoesInternas.forEach((observacao) => eventos.push({
            id: observacao.id,
            autor: observacao.autor,
            conteudo: observacao.mensagem,
            criadoEm: observacao.criadoEm,
            visibilidade: "interna",
            rotulo: "Observação interna"
        }));
        eventos.sort((a, b) => new Date(a.criadoEm) - new Date(b.criadoEm));

        alvo.replaceChildren();
        eventos.forEach((evento) => {
            const item = criarElemento("li", `feedback-timeline-item${evento.visibilidade === "interna" ? " is-internal" : ""}`);
            item.append(criarElemento("strong", "", evento.rotulo || evento.autor));
            item.append(criarElemento("p", "", evento.conteudo));
            item.append(criarElemento("time", "", `${evento.autor} · ${formatarDataHora(evento.criadoEm)}`));
            alvo.append(item);
        });
    }

    function mostrarToast(mensagem, erro = false) {
        const toast = document.getElementById("feedback-admin-toast");
        window.clearTimeout(toastTimer);
        toast.textContent = mensagem;
        toast.hidden = false;
        toast.setAttribute("role", erro ? "alert" : "status");
        toast.classList.toggle("is-error", erro);
        toastTimer = window.setTimeout(() => {
            toast.hidden = true;
        }, 3600);
    }

    function criarBadgeStatus(status) {
        return criarElemento("span", `feedback-status-badge feedback-status-${normalizarClasse(status)}`, status);
    }

    function criarBadgePrioridade(prioridade) {
        return criarElemento("span", `feedback-priority-badge feedback-priority-${normalizarClasse(prioridade)}`, prioridade);
    }

    function normalizarClasse(texto) {
        return normalizarTexto(texto).replace(/\s+/g, "-");
    }

    function normalizarTexto(texto) {
        return String(texto).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    }

    function obterIniciais(nome) {
        return nome.split(/\s+/).slice(0, 2).map((parte) => parte.charAt(0)).join("").toUpperCase();
    }

    function formatarData(valor) {
        return dateFormatter.format(new Date(valor));
    }

    function formatarDataHora(valor) {
        return dateTimeFormatter.format(new Date(valor));
    }

    function formatarAvaliacao(valor) {
        return valor ? `${"★".repeat(valor)}${"☆".repeat(5 - valor)} (${valor}/5)` : "Não informada";
    }

    function criarIcone(classes) {
        const icone = document.createElement("i");
        icone.className = classes;
        icone.setAttribute("aria-hidden", "true");
        return icone;
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
