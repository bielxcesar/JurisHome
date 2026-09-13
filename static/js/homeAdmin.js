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
        configurarNavegacaoDasMaterias();
        carregarMaterias();
    }

    function aplicarTema() {
        const temaClaro = window.localStorage.getItem("tema_juris") === "claro";
        document.body.classList.toggle("modo-claro", temaClaro);
    }

    function mostrarData() {
        const elemento = document.getElementById("data-atual");
        if (elemento) {
            elemento.textContent = new Intl.DateTimeFormat("pt-BR").format(new Date());
        }
    }

    function configurarPerfil() {
        const botao = document.getElementById("btn-perfil");
        const menu = document.getElementById("dropdown-perfil");
        if (!botao || !menu) return;

        botao.addEventListener("click", (evento) => {
            evento.stopPropagation();
            const aberto = menu.classList.toggle("ativo");
            botao.setAttribute("aria-expanded", String(aberto));
            if (aberto) fecharMenuFeedback();
        });

        document.addEventListener("click", (evento) => {
            if (!menu.contains(evento.target) && !botao.contains(evento.target)) {
                fecharMenu();
            }
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
            botaoFeedback.setAttribute("aria-label", "Abrir feedbacks recebidos");
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
            botao.setAttribute("aria-label", aberto ? "Fechar feedbacks recebidos" : "Abrir feedbacks recebidos");

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
        const formulario = document.getElementById("form-pesquisa-home");
        const campo = document.getElementById("pesquisa-home");
        const lista = document.getElementById("lista-categorias");

        formulario?.addEventListener("submit", (evento) => {
            evento.preventDefault();
            aplicarFiltros();
        });

        campo?.addEventListener("input", aplicarFiltros);

        lista?.addEventListener("click", (evento) => {
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

    function configurarNavegacaoDasMaterias() {
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
        atualizarStatus("Carregando matérias...");

        try {
            const resposta = await window.fetch("/api/conteudos");
            if (!resposta.ok) throw new Error("Não foi possível carregar as matérias.");

            const dados = await resposta.json();
            materias = Array.isArray(dados) ? dados : [];
            renderizarCategorias();
            aplicarFiltros();
        } catch (erro) {
            materias = [];
            renderizarMaterias([]);
            atualizarStatus("Não foi possível carregar as matérias agora.");
            console.error(erro);
        }
    }

    function renderizarCategorias() {
        const lista = document.getElementById("lista-categorias");
        if (!lista) return;

        const categorias = [...new Set(
            materias.map((materia) => materia.categoria || "Direito")
        )].sort((a, b) => a.localeCompare(b, "pt-BR"));

        lista.replaceChildren(criarBotaoCategoria("Todas", "", true));
        categorias.forEach((categoria) => {
            lista.append(criarBotaoCategoria(categoria, categoria, false));
        });
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
        const busca = normalizar(document.getElementById("pesquisa-home")?.value || "");
        const categoria = normalizar(categoriaAtiva);

        const resultados = materias.filter((materia) => {
            const correspondeCategoria = !categoria
                || normalizar(materia.categoria || "Direito") === categoria;
            const texto = normalizar([
                materia.titulo,
                materia.sub_titulo,
                materia.resumo_home,
                materia.categoria,
            ].filter(Boolean).join(" "));
            return correspondeCategoria && (!busca || texto.includes(busca));
        });

        renderizarMaterias(resultados);

        const quantidade = resultados.length;
        const complemento = categoriaAtiva ? ` em ${categoriaAtiva}` : "";
        atualizarStatus(`${quantidade} ${quantidade === 1 ? "matéria encontrada" : "matérias encontradas"}${complemento}.`);
    }

    function renderizarMaterias(resultados) {
        const grade = document.getElementById("destaques-home");
        const coluna = document.getElementById("coluna-destaques-secundarios");
        const principal = document.getElementById("card-destaque-principal");
        const segundo = document.getElementById("card-destaque-2");
        const terceiro = document.getElementById("card-destaque-3");

        if (resultados.length === 0) {
            preencherEstadoVazio(principal);
            segundo.hidden = true;
            terceiro.hidden = true;
            coluna.hidden = true;
            grade.classList.add("um-resultado");
            preencherRecomendados([]);
            return;
        }

        preencherCard(principal, "hero-cat-1", "hero-titulo-1", resultados[0]);
        preencherCardOpcional(segundo, "hero-cat-2", "hero-titulo-2", resultados[1]);
        preencherCardOpcional(terceiro, "hero-cat-3", "hero-titulo-3", resultados[2]);

        coluna.hidden = resultados.length < 2;
        grade.classList.toggle("um-resultado", resultados.length < 2);
        preencherRecomendados(resultados.slice(3));
    }

    function preencherCardOpcional(card, categoriaId, tituloId, materia) {
        card.hidden = !materia;
        if (materia) preencherCard(card, categoriaId, tituloId, materia);
    }

    function preencherCard(card, categoriaId, tituloId, materia) {
        card.hidden = false;
        card.dataset.conteudoId = materia.uuid;
        card.classList.remove("card-sem-conteudo");
        document.getElementById(categoriaId).textContent = materia.categoria || "Direito";
        document.getElementById(tituloId).textContent = materia.titulo;
        aplicarImagem(card, materia.imagem_miniatura);
    }

    function preencherEstadoVazio(card) {
        delete card.dataset.conteudoId;
        card.classList.add("card-sem-conteudo");
        card.style.backgroundImage = "none";
        document.getElementById("hero-cat-1").textContent = "Acervo JurisHome";
        document.getElementById("hero-titulo-1").textContent = materias.length
            ? "Nenhuma matéria corresponde aos filtros."
            : "Nenhuma matéria cadastrada. Execute o seed para carregar os conteúdos de demonstração.";
    }

    function preencherRecomendados(recomendadas) {
        const grade = document.getElementById("grid-voce-pode-gostar");
        if (!grade) return;
        grade.replaceChildren();

        if (recomendadas.length === 0) {
            const aviso = document.createElement("p");
            aviso.className = "mensagem-recomendados";
            aviso.textContent = materias.length
                ? "Outras matérias aparecerão aqui quando forem cadastradas."
                : "O acervo ainda não possui matérias.";
            grade.append(aviso);
            return;
        }

        recomendadas.forEach((materia) => {
            const card = document.createElement("article");
            card.className = "card-recomendado";
            card.tabIndex = 0;
            card.dataset.conteudoId = materia.uuid;
            aplicarImagem(card, materia.imagem_miniatura);

            const categoria = document.createElement("span");
            categoria.className = "categoria-tag";
            categoria.textContent = materia.categoria || "Direito";

            const titulo = document.createElement("h3");
            titulo.textContent = materia.titulo;
            card.append(categoria, titulo);
            grade.append(card);
        });
    }

    function aplicarImagem(card, url) {
        const imagem = String(url || "")
            .replace(/\\/g, "%5C")
            .replace(/"/g, "%22")
            .replace(/[\r\n]/g, "");
        const gradiente = "linear-gradient(180deg, rgba(0,0,0,.2), rgba(0,0,0,.88))";
        card.style.backgroundImage = imagem ? `${gradiente}, url("${imagem}")` : gradiente;
        card.style.backgroundSize = "cover";
        card.style.backgroundPosition = "center";
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
