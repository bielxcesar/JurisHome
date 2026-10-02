(function () {
    "use strict";

    const visao = document.body.dataset.visao;
    let materias = [];

    document.addEventListener("DOMContentLoaded", iniciar);

    function iniciar() {
        document.body.classList.toggle("modo-claro", window.localStorage.getItem("tema_juris") === "claro");
        const data = document.getElementById("data-atual");
        if (data) data.textContent = new Intl.DateTimeFormat("pt-BR").format(new Date());
        configurarPerfil();
        configurarSaida();
        configurarOrdenacao();
        carregarMaterias();
    }

    function configurarPerfil() {
        const botao = document.getElementById("btn-perfil");
        const menu = document.getElementById("dropdown-perfil");
        if (!botao || !menu) return;

        botao.addEventListener("click", (evento) => {
            evento.stopPropagation();
            const aberto = menu.classList.toggle("ativo");
            botao.setAttribute("aria-expanded", String(aberto));
        });
        document.addEventListener("click", (evento) => {
            if (!menu.contains(evento.target) && !botao.contains(evento.target)) {
                menu.classList.remove("ativo");
                botao.setAttribute("aria-expanded", "false");
            }
        });
        document.addEventListener("keydown", (evento) => {
            if (evento.key !== "Escape") return;
            menu.classList.remove("ativo");
            botao.setAttribute("aria-expanded", "false");
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

    function configurarOrdenacao() {
        document.getElementById("ordem-materias")?.addEventListener("change", renderizar);
        document.getElementById("categoria-materias")?.addEventListener("change", (evento) => {
            const url = new URL(window.location.href);
            if (evento.target.value) url.searchParams.set("categoria", evento.target.value);
            else url.searchParams.delete("categoria");
            window.history.replaceState({}, "", url);
            renderizar();
        });
    }

    async function carregarMaterias() {
        try {
            const resposta = await window.fetch("/api/conteudos");
            const dados = await resposta.json();
            if (!resposta.ok) throw new Error(dados.detail || "Não foi possível carregar as matérias.");
            materias = Array.isArray(dados) ? dados : [];
            prepararSeletorCategoria();
            renderizar();
        } catch (erro) {
            materias = [];
            prepararSeletorCategoria();
            mostrarEstado(erro.message || "Não foi possível carregar as matérias agora.");
            console.error(erro);
        }
    }

    function prepararSeletorCategoria() {
        const seletor = document.getElementById("categoria-materias");
        if (!seletor) return;

        const categorias = [...new Set(materias.map((materia) => materia.categoria || "Direito"))]
            .sort((a, b) => a.localeCompare(b, "pt-BR"));
        seletor.replaceChildren();

        if (categorias.length === 0) {
            const opcao = document.createElement("option");
            opcao.value = "";
            opcao.textContent = "Sem categorias";
            seletor.append(opcao);
            seletor.disabled = true;
            return;
        }

        seletor.disabled = false;
        categorias.forEach((categoria) => {
            const opcao = document.createElement("option");
            opcao.value = categoria;
            opcao.textContent = categoria;
            seletor.append(opcao);
        });

        const solicitada = new URLSearchParams(window.location.search).get("categoria");
        const categoriaPadraoFigma = categorias.find((categoria) =>
            categoria.toLocaleLowerCase("pt-BR") === "direito trabalhista"
        );
        seletor.value = categorias.includes(solicitada)
            ? solicitada
            : categoriaPadraoFigma || categorias[0];
    }

    function renderizar() {
        const lista = document.getElementById("lista-materias");
        if (!lista) return;

        const seletorCategoria = document.getElementById("categoria-materias");
        const categoria = seletorCategoria?.value || "";
        const resultados = materias.filter((materia) =>
            visao !== "categorias" || (materia.categoria || "Direito") === categoria
        );

        if (visao === "recentes") {
            const ordem = document.getElementById("ordem-materias")?.value || "recente";
            resultados.sort((a, b) => {
                const diferenca = converterData(a.criado_em) - converterData(b.criado_em);
                return ordem === "antiga" ? diferenca : -diferenca;
            });
        }

        lista.replaceChildren();
        if (resultados.length === 0) {
            mostrarEstado(materias.length
                ? "Nenhuma matéria disponível nesta categoria."
                : "Nenhuma matéria disponível.");
            return;
        }

        const estadoAnterior = document.querySelector(".estado-listagem");
        estadoAnterior?.remove();
        atualizarStatus(`${resultados.length} ${resultados.length === 1 ? "matéria encontrada" : "matérias encontradas"}.`);

        resultados.forEach((materia) => lista.append(criarLinhaMateria(materia)));
    }

    function criarLinhaMateria(materia) {
        const linha = document.createElement("a");
        linha.className = "materia-linha";
        linha.href = `/materia/${encodeURIComponent(materia.uuid)}`;

        const titulo = document.createElement("h2");
        titulo.className = "materia-titulo";
        titulo.textContent = materia.titulo || "Matéria sem título";
        linha.append(titulo);
        return linha;
    }

    function converterData(valor) {
        const partes = String(valor || "").split("/").map(Number);
        if (partes.length !== 3 || partes.some(Number.isNaN)) return 0;
        return Date.UTC(partes[2], partes[1] - 1, partes[0]);
    }

    function mostrarEstado(mensagem) {
        document.querySelector(".estado-listagem")?.remove();
        const estado = document.createElement("p");
        estado.className = "estado-listagem";
        estado.textContent = mensagem;
        document.getElementById("lista-materias")?.append(estado);
        atualizarStatus(mensagem);
    }

    function atualizarStatus(mensagem) {
        const status = document.getElementById("status-listagem");
        if (status) status.textContent = mensagem;
    }
})();
