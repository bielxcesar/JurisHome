(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", iniciar);

    function iniciar() {
        aplicarTema();
        mostrarData();
        configurarPerfil();
        configurarMenuJuris();
        carregarMaterias();
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

    async function carregarMaterias() {
        try {
            const resposta = await window.fetch("/api/conteudos");
            if (!resposta.ok) throw new Error("Não foi possível carregar as matérias.");
            const materias = await resposta.json();
            if (!Array.isArray(materias) || materias.length === 0) {
                mostrarEstadoVazio();
                return;
            }

            preencherDestaque("card-destaque-principal", "hero-cat-1", "hero-titulo-1", materias[0]);
            preencherDestaque("card-destaque-2", "hero-cat-2", "hero-titulo-2", materias[1] || materias[0]);
            preencherDestaque("card-destaque-3", "hero-cat-3", "hero-titulo-3", materias[2] || materias[0]);
            preencherRecomendados(materias.slice(3));
        } catch (erro) {
            mostrarEstadoVazio("Não foi possível carregar as matérias agora.");
            console.error(erro);
        }
    }

    function preencherDestaque(cardId, categoriaId, tituloId, materia) {
        const card = document.getElementById(cardId);
        document.getElementById(categoriaId).textContent = materia.categoria || "Direito";
        document.getElementById(tituloId).textContent = materia.titulo;
        card.style.backgroundImage = `linear-gradient(180deg, rgba(0,0,0,.2), rgba(0,0,0,.88)), url('${materia.imagem_miniatura || ""}')`;
        tornarClicavel(card, materia.uuid);
    }

    function preencherRecomendados(materias) {
        const grade = document.getElementById("grid-voce-pode-gostar");
        grade.replaceChildren();

        if (materias.length === 0) {
            const aviso = document.createElement("p");
            aviso.textContent = "Novas matérias aparecerão aqui.";
            grade.append(aviso);
            return;
        }

        materias.forEach((materia) => {
            const card = document.createElement("article");
            card.className = "card-recomendado";
            card.tabIndex = 0;
            card.style.backgroundImage = `linear-gradient(180deg, rgba(0,0,0,.2), rgba(0,0,0,.88)), url('${materia.imagem_miniatura || ""}')`;

            const categoria = document.createElement("span");
            categoria.className = "categoria-tag";
            categoria.textContent = materia.categoria || "Direito";
            const titulo = document.createElement("h3");
            titulo.textContent = materia.titulo;
            card.append(categoria, titulo);
            tornarClicavel(card, materia.uuid);
            grade.append(card);
        });
    }

    function tornarClicavel(elemento, uuid) {
        if (!uuid) return;
        const abrir = () => { window.location.href = `/materia/${uuid}`; };
        elemento.addEventListener("click", abrir);
        elemento.addEventListener("keydown", (evento) => {
            if (evento.key === "Enter" || evento.key === " ") {
                evento.preventDefault();
                abrir();
            }
        });
    }

    function mostrarEstadoVazio(mensagem = "Nenhuma matéria disponível.") {
        document.getElementById("hero-titulo-1").textContent = mensagem;
        document.getElementById("hero-titulo-2").textContent = "Tente novamente mais tarde.";
        document.getElementById("hero-titulo-3").textContent = "";
    }
})();
