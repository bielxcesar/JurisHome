(function () {
    "use strict";

    const elementos = {};

    document.addEventListener("DOMContentLoaded", () => {
        aplicarTemaSalvo();
        preencherDataAtual();
        configurarMenuPerfil();
        configurarSaida();
        elementos.form = document.getElementById("audit-filters");
        elementos.busca = document.getElementById("audit-search");
        elementos.acao = document.getElementById("audit-action");
        elementos.resultado = document.getElementById("audit-result");
        elementos.loading = document.getElementById("audit-loading");
        elementos.alerta = document.getElementById("audit-alert");
        elementos.vazio = document.getElementById("audit-empty");
        elementos.tabela = document.getElementById("audit-table-wrap");
        elementos.corpo = document.getElementById("audit-table-body");
        elementos.cards = document.getElementById("audit-cards");

        elementos.form.addEventListener("submit", (evento) => {
            evento.preventDefault();
            carregar();
        });
        document.getElementById("audit-refresh").addEventListener("click", carregar);
        document.getElementById("audit-clear").addEventListener("click", () => {
            elementos.form.reset();
            carregar();
        });
        carregar();
    });

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

        const fechar = () => {
            menu.classList.remove("ativo");
            botao.setAttribute("aria-expanded", "false");
        };
        botao.addEventListener("click", (evento) => {
            evento.stopPropagation();
            const aberto = menu.classList.toggle("ativo");
            botao.setAttribute("aria-expanded", String(aberto));
        });
        document.addEventListener("click", (evento) => {
            if (!menu.contains(evento.target) && !botao.contains(evento.target)) fechar();
        });
        document.addEventListener("keydown", (evento) => {
            if (evento.key === "Escape") fechar();
        });
    }

    function configurarSaida() {
        document.querySelectorAll(".btn-desconectar").forEach((link) => {
            link.addEventListener("click", (evento) => {
                evento.preventDefault();
                window.localStorage.removeItem("jurishome_access_token");
                window.sessionStorage.removeItem("jurishome_desafio_2fa");
                window.fetch("/api/auth/logout", { method: "POST" })
                    .finally(() => { window.location.href = "/"; });
            });
        });
    }

    async function carregar() {
        alternarEstado("carregando");
        const parametros = new URLSearchParams({ limite: "100" });
        if (elementos.busca.value.trim()) parametros.set("busca", elementos.busca.value.trim());
        if (elementos.acao.value) parametros.set("acao", elementos.acao.value);
        if (elementos.resultado.value) parametros.set("resultado", elementos.resultado.value);

        try {
            const resposta = await fetch(`/api/admin/auditoria?${parametros.toString()}`);
            const dados = await resposta.json().catch(() => ({}));
            if (!resposta.ok) throw new Error(dados.detail || "Não foi possível carregar os logs.");
            preencherAcoes(dados.acoesDisponiveis || []);
            renderizar(dados.itens || []);
            document.getElementById("audit-total").textContent = String(dados.totalExibido ?? 0);
            document.getElementById("audit-updated").textContent = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(new Date());
        } catch (erro) {
            elementos.alerta.textContent = erro.message || "Não foi possível carregar os logs.";
            alternarEstado("erro");
        }
    }

    function preencherAcoes(acoes) {
        const atual = elementos.acao.value;
        const existentes = new Set(Array.from(elementos.acao.options).map((opcao) => opcao.value));
        acoes.forEach((acao) => {
            if (existentes.has(acao)) return;
            const opcao = document.createElement("option");
            opcao.value = acao;
            opcao.textContent = rotulo(acao);
            elementos.acao.append(opcao);
        });
        elementos.acao.value = atual;
    }

    function renderizar(itens) {
        elementos.corpo.replaceChildren();
        elementos.cards.replaceChildren();
        if (!itens.length) {
            alternarEstado("vazio");
            return;
        }
        itens.forEach((item) => {
            elementos.corpo.append(criarLinha(item));
            elementos.cards.append(criarCard(item));
        });
        alternarEstado("lista");
    }

    function criarLinha(item) {
        const linha = document.createElement("tr");
        linha.append(celula(formatarData(item.criadoEm)));
        linha.append(celulaUsuario(item));
        linha.append(celulaComDetalhes(item));
        linha.append(celulaRecurso(item));
        linha.append(celulaResultado(item.resultado));
        const correlacao = celula("");
        correlacao.append(codigo(item.correlacaoId));
        linha.append(correlacao);
        return linha;
    }

    function criarCard(item) {
        const card = document.createElement("article");
        card.className = "audit-card";
        const topo = document.createElement("div");
        topo.append(document.createTextNode(rotulo(item.acao) + " "));
        topo.append(criarPill(item.resultado));
        card.append(topo);
        const lista = document.createElement("dl");
        adicionarDefinicao(lista, "Data", formatarData(item.criadoEm));
        adicionarDefinicao(lista, "Usuário", item.usuarioId || "Não identificado");
        adicionarDefinicao(lista, "Perfil", item.usuarioTipo || "anonimo");
        adicionarDefinicao(lista, "Recurso", `${item.recursoTipo}${item.recursoId ? ` · ${item.recursoId}` : ""}`);
        adicionarDefinicao(lista, "Correlação", item.correlacaoId);
        card.append(lista);
        return card;
    }

    function celula(texto) {
        const elemento = document.createElement("td");
        elemento.textContent = texto;
        return elemento;
    }

    function celulaUsuario(item) {
        const elemento = celula(item.usuarioTipo || "anonimo");
        if (item.usuarioId) elemento.append(codigo(item.usuarioId));
        return elemento;
    }

    function celulaComDetalhes(item) {
        const elemento = celula(rotulo(item.acao));
        const detalhes = formatarDetalhes(item.detalhes);
        if (detalhes) {
            const pequeno = document.createElement("div");
            pequeno.className = "audit-details";
            pequeno.textContent = detalhes;
            elemento.append(pequeno);
        }
        return elemento;
    }

    function celulaRecurso(item) {
        const elemento = celula(item.recursoTipo || "–");
        if (item.recursoId) elemento.append(codigo(item.recursoId));
        return elemento;
    }

    function celulaResultado(resultado) {
        const elemento = celula("");
        elemento.append(criarPill(resultado));
        return elemento;
    }

    function criarPill(resultado) {
        const pill = document.createElement("span");
        pill.className = `audit-pill ${resultado || ""}`;
        pill.textContent = resultado || "–";
        return pill;
    }

    function codigo(texto) {
        const elemento = document.createElement("code");
        elemento.className = "audit-code";
        elemento.textContent = texto || "–";
        elemento.title = texto || "";
        return elemento;
    }

    function adicionarDefinicao(lista, termo, valor) {
        const dt = document.createElement("dt");
        dt.textContent = termo;
        const dd = document.createElement("dd");
        dd.textContent = valor || "–";
        lista.append(dt, dd);
    }

    function formatarDetalhes(detalhes) {
        return Object.entries(detalhes || {}).map(([chave, valor]) => `${rotulo(chave)}: ${Array.isArray(valor) ? valor.join(", ") : valor}`).join(" · ");
    }

    function rotulo(valor) {
        return String(valor || "").replaceAll("_", " ").replace(/^./, (letra) => letra.toUpperCase());
    }

    function formatarData(valor) {
        const data = new Date(valor);
        if (Number.isNaN(data.getTime())) return "–";
        return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" }).format(data);
    }

    function alternarEstado(estado) {
        elementos.loading.hidden = estado !== "carregando";
        elementos.alerta.hidden = estado !== "erro";
        elementos.vazio.hidden = estado !== "vazio";
        elementos.tabela.hidden = estado !== "lista";
        elementos.cards.hidden = estado !== "lista";
    }
})();
