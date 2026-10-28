(function () {
    "use strict";

    const service = window.FeedbackService;
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
    let atualizacaoEmCurso = false;
    let operacaoEmCurso = false;
    let paginaAtual = 1;
    const TAMANHO_PAGINA = 10;
    const rascunhos = new Map();

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
        document.querySelectorAll('.btn-desconectar').forEach(link => link.addEventListener('click', async evento => {
            evento.preventDefault();
            try {
                const resposta = await window.fetch('/api/auth/logout', {method: 'POST'});
                if (!resposta.ok) throw new Error();
                window.location.assign('/');
            } catch { mostrarToast('Não foi possível encerrar a sessão. Tente novamente.', true); }
        }));

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
        const filtrar = () => { paginaAtual = 1; renderizarLista(); };
        document.getElementById("admin-search").addEventListener("input", filtrar);
        document.getElementById("admin-status-filter").addEventListener("change", filtrar);
        document.getElementById('admin-refresh').addEventListener('click', atualizarDoServidor);
        document.getElementById('admin-previous').addEventListener('click', () => { paginaAtual--; renderizarLista(); });
        document.getElementById('admin-next').addEventListener('click', () => { paginaAtual++; renderizarLista(); });
        document.getElementById("admin-clear-filters").addEventListener("click", limparFiltros);
        document.getElementById("admin-empty-clear").addEventListener("click", limparFiltros);
        document.getElementById("feedback-filter-form").addEventListener("submit", (evento) => evento.preventDefault());
    }

    function limparFiltros() {
        paginaAtual = 1;
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
        if (atualizacaoEmCurso || operacaoEmCurso) return;
        atualizacaoEmCurso = true;
        const botao = document.getElementById('admin-refresh');
        botao.disabled = true;
        const estado = document.getElementById('admin-load-state');
        estado.textContent = 'Atualizando os atendimentos…';
        document.querySelector('.feedback-admin-list-panel').setAttribute('aria-busy', 'true');
        try {
            await service.inicializar();
            renderizarTudo();
            estado.textContent = 'Atendimentos atualizados.';

            const dialogo = document.getElementById("feedback-admin-dialog");
            if (dialogo.open && feedbackSelecionadoId) {
                preencherDetalhes(service.buscarPorId(feedbackSelecionadoId));
            }
        } catch (erro) {
            estado.textContent = 'Não foi possível atualizar. Os dados exibidos podem estar desatualizados. Use Atualizar para tentar novamente.';
            mostrarToast(erro.message || "Não foi possível atualizar os feedbacks.", true);
        } finally {
            botao.disabled = false;
            atualizacaoEmCurso = false;
            document.querySelector('.feedback-admin-list-panel').setAttribute('aria-busy', 'false');
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
                    item.usuario.nome,
                    item.tipo,
                    item.assunto
                ].join(" "));
                return (!termo || alvo.includes(termo)) && (!status || item.status === status);
            })
            .sort((a, b) => new Date(b.criadoEm) - new Date(a.criadoEm));
    }

    function renderizarLista() {
        const registros = obterFiltrados();
        const paginas = Math.max(1, Math.ceil(registros.length / TAMANHO_PAGINA));
        paginaAtual = Math.min(Math.max(1, paginaAtual), paginas);
        const visiveis = registros.slice((paginaAtual - 1) * TAMANHO_PAGINA, paginaAtual * TAMANHO_PAGINA);
        definirTexto('admin-page-label', `Página ${paginaAtual} de ${paginas}`);
        document.getElementById('admin-previous').disabled = paginaAtual === 1;
        document.getElementById('admin-next').disabled = paginaAtual === paginas;
        const corpoTabela = document.getElementById("admin-feedback-table-body");
        const listaMobile = document.getElementById("admin-feedback-mobile-list");
        const vazio = document.getElementById("admin-feedback-empty");

        corpoTabela.replaceChildren();
        listaMobile.replaceChildren();
        visiveis.forEach((feedback) => {
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
        usuario.append(criarElemento("strong", "", feedback.usuario.nome || 'Usuário'));
        usuario.append(criarElemento("small", "", feedback.usuario.email));
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
        botao.dataset.feedbackId = feedback.id;
        botao.setAttribute("aria-label", `Abrir ${feedback.protocolo}: ${feedback.assunto}`);
        botao.addEventListener("click", () => abrirDetalhes(feedback.id, botao));
        return botao;
    }

    function configurarDialogo() {
        const dialogo = document.getElementById("feedback-admin-dialog");
        document.getElementById("feedback-admin-dialog-close").addEventListener("click", () => { if (!operacaoEmCurso) dialogo.close(); });
        dialogo.addEventListener('cancel', evento => { if (operacaoEmCurso) evento.preventDefault(); });
        dialogo.addEventListener("click", (evento) => {
            if (evento.target === dialogo && !operacaoEmCurso) dialogo.close();
        });
        dialogo.addEventListener("close", () => {
            rascunhos.set(feedbackSelecionadoId, document.getElementById('feedback-admin-response').value);
            const acionador = Array.from(document.querySelectorAll(`[data-feedback-id="${CSS.escape(feedbackSelecionadoId || '')}"]`)).find(botao => botao.getClientRects().length);
            (acionador || document.getElementById('admin-search')).focus();
        });
        document.getElementById("feedback-admin-status").addEventListener("change", alterarStatus);
        document.getElementById("feedback-admin-send-response").addEventListener("click", enviarResposta);
    }

    async function abrirDetalhes(id, acionador) {
        if (operacaoEmCurso) return;
        feedbackSelecionadoId = id;
        ultimoAcionadorDoDialogo = acionador;
        const atual = service.buscarPorId(id);
        if (!atual) return;
        try {
            if (atual.novo) await service.marcarComoVisto(id);
        } catch (erro) { mostrarToast(erro.message, true); }
        document.getElementById('feedback-admin-response').value = rascunhos.get(id) || '';
        document.getElementById('feedback-admin-response-error').textContent = '';
        document.getElementById('feedback-admin-dialog-notice').hidden = true;
        document.getElementById('feedback-admin-response').removeAttribute('aria-invalid');
        preencherDetalhes(service.buscarPorId(id));
        renderizarLista();
        const dialogo = document.getElementById("feedback-admin-dialog");
        if (!dialogo.open) dialogo.showModal();
    }

    function preencherDetalhes(feedback) {
        if (!feedback) return;
        definirTexto("feedback-admin-dialog-protocol", feedback.protocolo);
        definirTexto("feedback-admin-dialog-title", feedback.assunto);
        document.getElementById("feedback-admin-dialog-new").hidden = !feedback.novo;
        const email = document.getElementById("feedback-admin-user-email");
        email.textContent = feedback.usuario.email;
        email.href = `mailto:${feedback.usuario.email}`;
        definirTexto('feedback-admin-user-name', feedback.usuario.nome || 'Usuário');
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
        if (!feedbackSelecionadoId || operacaoEmCurso) return;
        operacaoEmCurso = true;
        evento.target.disabled = true;
        document.getElementById('feedback-admin-send-response').disabled = true;
        try {
            const atualizado = await service.alterarStatus(feedbackSelecionadoId, evento.target.value);
            preencherDetalhes(atualizado);
            renderizarTudo();
            mostrarToast(`Status alterado para ${atualizado.status}.`);
        } catch (erro) {
            evento.target.value = service.buscarPorId(feedbackSelecionadoId).status;
            mostrarToast(erro.message, true);
        } finally {
            operacaoEmCurso = false;
            evento.target.disabled = false;
            document.getElementById('feedback-admin-send-response').disabled = false;
        }
    }

    async function enviarResposta() {
        if (operacaoEmCurso || !feedbackSelecionadoId) return;
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
        operacaoEmCurso = true;
        document.getElementById('feedback-admin-status').disabled = true;
        campo.disabled = true;
        botao.classList.add("is-loading");
        textoBotao.textContent = "Enviando...";

        try {
            const atualizado = await service.responder(feedbackSelecionadoId, texto);
            campo.value = "";
            preencherDetalhes(atualizado);
            renderizarTudo();
            mostrarToast("Resposta enviada.");
        } catch (erro) {
            mostrarToast(erro.message, true);
        } finally {
            botao.disabled = false;
            operacaoEmCurso = false;
            document.getElementById('feedback-admin-status').disabled = false;
            campo.disabled = false;
            botao.classList.remove("is-loading");
            textoBotao.textContent = "Enviar resposta";
        }
    }

    function mostrarToast(mensagem, erro = false) {
        const dialogo = document.getElementById('feedback-admin-dialog');
        if (dialogo.open) {
            const aviso = document.getElementById('feedback-admin-dialog-notice');
            aviso.textContent = mensagem;
            aviso.hidden = false;
            aviso.className = `feedback-alert ${erro ? 'feedback-alert-error' : 'feedback-alert-success'}`;
            aviso.setAttribute('role', erro ? 'alert' : 'status');
            return;
        }
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
        const data = new Date(valor);
        return Number.isNaN(data.getTime()) ? 'Data não informada' : formatadorData.format(data);
    }

    function formatarDataHora(valor) {
        const data = new Date(valor);
        return Number.isNaN(data.getTime()) ? 'Data não informada' : formatadorDataHora.format(data);
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
