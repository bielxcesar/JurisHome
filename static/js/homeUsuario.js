(function () {
    "use strict";

    let materias = [];
    let categoriaAtiva = "";

    document.addEventListener("DOMContentLoaded", iniciar);

    function iniciar() {
        aplicarTema();
        mostrarData();
        configurarPerfil();
        configurarMenuJuris();
        configurarFiltros();
        configurarNavegacaoMaterias();
        carregarMaterias();
        configurarSaida();
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

    function aplicarTema() {
        document.body.classList.toggle("modo-claro", window.localStorage.getItem("tema_juris") === "claro");
    }

    function mostrarData() {
        document.getElementById("data-atual").textContent = new Intl.DateTimeFormat("pt-BR").format(new Date());
    }

    function configurarPerfil() {
        const botao = document.getElementById("btn-perfil");
        const menu = document.getElementById("dropdown-perfil");

        botao.addEventListener("click", (evento) => {
            evento.stopPropagation();
            const aberto = menu.classList.toggle("ativo");
            botao.setAttribute("aria-expanded", String(aberto));
            if (aberto) fecharMenuFeedback();
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

        function fecharMenuFeedback() {
            const containerFeedback = document.getElementById("juris-fab");
            const menuFeedback = document.getElementById("juris-fab-menu");
            const botaoFeedback = document.getElementById("juris-fab-toggle");
            if (!containerFeedback || !menuFeedback || !botaoFeedback) return;

            menuFeedback.hidden = true;
            containerFeedback.classList.remove("aberto");
            botaoFeedback.setAttribute("aria-expanded", "false");
            botaoFeedback.setAttribute("aria-label", "Abrir acesso ao feedback");
        }
    }

    function configurarMenuJuris() {
        const container = document.getElementById("juris-fab");
        const botao = document.getElementById("juris-fab-toggle");
        const menu = document.getElementById("juris-fab-menu");
        if (!container || !botao || !menu) return;

        function definirAberto(aberto, devolverFoco = false) {
            menu.hidden = !aberto;
            container.classList.toggle("aberto", aberto);
            botao.setAttribute("aria-expanded", String(aberto));
            botao.setAttribute("aria-label", aberto ? "Fechar acesso ao feedback" : "Abrir acesso ao feedback");

            if (aberto) {
                menu.querySelector("a, button")?.focus();
            } else if (devolverFoco) {
                botao.focus();
            }
        }

        botao.addEventListener("click", (evento) => {
            evento.stopPropagation();
            const abrir = menu.hidden;
            if (abrir) {
                document.getElementById("dropdown-perfil")?.classList.remove("ativo");
                document.getElementById("btn-perfil")?.setAttribute("aria-expanded", "false");
            }
            definirAberto(abrir);
        });

        menu.addEventListener("click", (evento) => {
            if (evento.target.closest("a")) definirAberto(false);
        });

        document.addEventListener("click", (evento) => {
            if (!menu.hidden && !container.contains(evento.target)) definirAberto(false);
        });

        document.addEventListener("keydown", (evento) => {
            if (evento.key === "Escape" && !menu.hidden) definirAberto(false, true);
        });
    }

    function configurarFiltros() {
        const lista = document.getElementById("lista-categorias");
        if (!lista) return;

        lista.addEventListener("click", (evento) => {
            const botao = evento.target.closest("button[data-categoria]");
            if (!botao) return;

            categoriaAtiva = botao.dataset.categoria || "";
            lista.querySelectorAll("button[data-categoria]").forEach((item) => {
                const ativo = item === botao;
                item.classList.toggle("ativa", ativo);
                item.setAttribute("aria-pressed", String(ativo));
            });
            aplicarFiltros();
        });
    }

    function configurarNavegacaoMaterias() {
        const conteudo = document.getElementById("conteudo-principal");
        if (!conteudo) return;

        conteudo.addEventListener("click", (evento) => {
            const card = evento.target.closest("[data-conteudo-id]");
            if (card) abrirMateria(card.dataset.conteudoId);
        });

        conteudo.addEventListener("keydown", (evento) => {
            if (evento.key !== "Enter" && evento.key !== " ") return;
            const card = evento.target.closest("[data-conteudo-id]");
            if (!card) return;
            evento.preventDefault();
            abrirMateria(card.dataset.conteudoId);
        });
    }

    async function carregarMaterias() {
        try {
            const resposta = await window.fetch("/api/conteudos");
            if (!resposta.ok) throw new Error("Não foi possível carregar as matérias.");
            const dados = await resposta.json();
            materias = Array.isArray(dados) ? dados : [];
            renderizarCategorias();
            aplicarFiltros();
        } catch (erro) {
            materias = [];
            renderizarCategorias();
            renderizarDestaques([]);
            atualizarStatus("Não foi possível carregar as matérias agora.");
            console.error(erro);
        }
    }

    function renderizarCategorias() {
        const lista = document.getElementById("lista-categorias");
        const vazio = document.getElementById("categorias-vazio");
        if (!lista) return;

        const categorias = [...new Set(
            materias.map((materia) => materia.categoria || "Direito")
        )].sort((a, b) => a.localeCompare(b, "pt-BR"));

        lista.replaceChildren(criarBotaoCategoria("Todas", "", !categoriaAtiva));
        categorias.forEach((categoria) => {
            lista.append(criarBotaoCategoria(categoria, categoria, categoriaAtiva === categoria));
        });
        if (vazio) vazio.hidden = categorias.length > 0;
    }

    function criarBotaoCategoria(rotulo, valor, ativo) {
        const botao = document.createElement("button");
        botao.type = "button";
        botao.className = `categoria-filtro${ativo ? " ativa" : ""}`;
        botao.dataset.categoria = valor;
        botao.setAttribute("aria-pressed", String(ativo));
        botao.textContent = rotulo;
        return botao;
    }

    function aplicarFiltros() {
        const categoria = normalizar(categoriaAtiva);
        const resultados = materias.filter((materia) =>
            !categoria || normalizar(materia.categoria || "Direito") === categoria
        );

        renderizarDestaques(resultados);
        const quantidade = resultados.length;
        atualizarStatus(`${quantidade} ${quantidade === 1 ? "matéria encontrada" : "matérias encontradas"}${categoriaAtiva ? ` em ${categoriaAtiva}` : ""}.`);
    }

    function renderizarDestaques(resultados) {
        const principal = document.getElementById("card-destaque-principal");
        const segundo = document.getElementById("card-destaque-2");
        const terceiro = document.getElementById("card-destaque-3");
        const coluna = document.getElementById("coluna-destaques-secundarios");
        const grade = document.getElementById("destaques-home");

        if (resultados.length === 0) {
            preencherEstadoVazio(principal);
            segundo.hidden = true;
            terceiro.hidden = true;
            coluna.hidden = true;
            grade.classList.add("um-resultado");
            preencherRecomendados([]);
            return;
        }

        preencherDestaque(principal, "hero-cat-1", "hero-titulo-1", resultados[0]);
        preencherDestaque(segundo, "hero-cat-2", "hero-titulo-2", resultados[1]);
        preencherDestaque(terceiro, "hero-cat-3", "hero-titulo-3", resultados[2]);
        coluna.hidden = resultados.length < 2;
        grade.classList.toggle("um-resultado", resultados.length < 2);
        preencherRecomendados(resultados.slice(3));
    }

    function preencherDestaque(card, categoriaId, tituloId, materia) {
        card.hidden = !materia;
        if (!materia) return;
        card.dataset.conteudoId = materia.uuid;
        card.setAttribute("role", "link");
        card.classList.remove("card-sem-conteudo");
        document.getElementById(categoriaId).textContent = materia.categoria || "Direito";
        document.getElementById(tituloId).textContent = materia.titulo;
    }

    function preencherRecomendados(recomendadas) {
        const grade = document.getElementById("grid-voce-pode-gostar");
        grade.replaceChildren();

        if (recomendadas.length === 0) {
            const aviso = document.createElement("p");
            aviso.className = "mensagem-recomendados";
            aviso.textContent = !materias.length
                ? "O acervo ainda não possui matérias cadastradas."
                : categoriaAtiva
                    ? `Todas as matérias de ${categoriaAtiva} estão nos destaques.`
                    : "Todas as matérias aprovadas estão nos destaques.";
            const link = document.createElement("a");
            link.className = "link-acervo";
            link.href = "/pesquisa";
            link.textContent = "Pesquisar no acervo";
            grade.append(aviso, link);
            return;
        }

        recomendadas.forEach((materia) => {
            const card = document.createElement("article");
            card.className = "card-recomendado";
            card.tabIndex = 0;
            card.setAttribute("role", "link");
            card.dataset.conteudoId = materia.uuid;

            const categoria = document.createElement("span");
            categoria.className = "categoria-tag";
            categoria.textContent = materia.categoria || "Direito";
            const titulo = document.createElement("h3");
            titulo.textContent = materia.titulo;
            card.append(categoria, titulo);
            grade.append(card);
        });
    }

    function preencherEstadoVazio(card) {
        delete card.dataset.conteudoId;
        card.setAttribute("role", "status");
        card.classList.add("card-sem-conteudo");
        document.getElementById("hero-cat-1").textContent = "Acervo JurisHome";
        document.getElementById("hero-titulo-1").textContent = materias.length
            ? "Nenhuma matéria corresponde a esta categoria."
            : "Nenhuma matéria cadastrada no momento.";
    }

    function abrirMateria(uuid) {
        if (uuid) window.location.href = `/materia/${encodeURIComponent(uuid)}`;
    }

    function atualizarStatus(mensagem) {
        const elemento = document.getElementById("status-conteudos");
        if (elemento) elemento.textContent = mensagem;
    }

    function normalizar(valor) {
        return String(valor || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\s+/g, " ")
            .trim()
            .toLocaleLowerCase("pt-BR");
    }

})();
