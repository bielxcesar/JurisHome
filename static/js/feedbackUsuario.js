(function () {
    "use strict";

    const service = window.FeedbackMockService;
    if (!service) {
        console.error("Serviço de feedback indisponível.");
        return;
    }

    document.addEventListener("DOMContentLoaded", iniciar);

    function iniciar() {
        aplicarTemaSalvo();
        preencherDataAtual();
        configurarMenuPerfil();
        configurarFormulario();
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

    function configurarFormulario() {
        const form = document.getElementById("feedback-form");
        const assunto = document.getElementById("feedback-assunto");
        const mensagem = document.getElementById("feedback-mensagem");
        const tipo = document.getElementById("feedback-tipo");
        const radios = Array.from(document.querySelectorAll('input[name="avaliacao"]'));

        assunto.addEventListener("input", () => {
            atualizarContador(assunto, "contador-assunto", 120);
            if (assunto.value.trim().length >= 5) limparErro(assunto, "erro-assunto");
        });

        mensagem.addEventListener("input", () => {
            atualizarContador(mensagem, "contador-mensagem", 2000);
            if (mensagem.value.trim().length >= 10) limparErro(mensagem, "erro-mensagem");
        });

        tipo.addEventListener("change", () => {
            if (tipo.value) limparErro(tipo, "erro-tipo");
        });

        radios.forEach((radio) => radio.addEventListener("change", atualizarEstrelas));
        form.addEventListener("submit", enviarFeedback);
    }

    function atualizarContador(campo, contadorId, limite) {
        document.getElementById(contadorId).textContent = `${campo.value.length}/${limite}`;
    }

    function atualizarEstrelas() {
        const selecionado = Number(document.querySelector('input[name="avaliacao"]:checked')?.value || 0);
        document.querySelectorAll(".feedback-stars label").forEach((rotulo, indice) => {
            rotulo.classList.toggle("is-selected", indice < selecionado);
        });
    }

    function validarFormulario() {
        const tipo = document.getElementById("feedback-tipo");
        const assunto = document.getElementById("feedback-assunto");
        const mensagem = document.getElementById("feedback-mensagem");
        const invalidos = [];

        validarCampo(tipo, "erro-tipo", Boolean(tipo.value), "Escolha o motivo do contato.", invalidos);

        const tamanhoAssunto = assunto.value.trim().length;
        validarCampo(
            assunto,
            "erro-assunto",
            tamanhoAssunto >= 5 && tamanhoAssunto <= 120,
            "O assunto deve ter entre 5 e 120 caracteres.",
            invalidos
        );

        const tamanhoMensagem = mensagem.value.trim().length;
        validarCampo(
            mensagem,
            "erro-mensagem",
            tamanhoMensagem >= 10 && tamanhoMensagem <= 2000,
            "A mensagem deve ter entre 10 e 2.000 caracteres.",
            invalidos
        );

        if (invalidos.length) invalidos[0].focus();
        return invalidos.length === 0;
    }

    function validarCampo(campo, erroId, valido, mensagem, invalidos) {
        if (valido) {
            limparErro(campo, erroId);
            return;
        }
        definirErro(campo, erroId, mensagem);
        invalidos.push(campo);
    }

    function definirErro(campo, erroId, mensagem) {
        campo.setAttribute("aria-invalid", "true");
        document.getElementById(erroId).textContent = mensagem;
    }

    function limparErro(campo, erroId) {
        campo.removeAttribute("aria-invalid");
        document.getElementById(erroId).textContent = "";
    }

    async function enviarFeedback(evento) {
        evento.preventDefault();
        const sucesso = document.getElementById("feedback-sucesso");
        const erroGeral = document.getElementById("feedback-erro-geral");
        sucesso.hidden = true;
        erroGeral.hidden = true;
        if (!validarFormulario()) return;

        const form = evento.currentTarget;
        const botao = document.getElementById("feedback-enviar");
        const textoBotao = botao.querySelector(".feedback-button-text");
        botao.disabled = true;
        botao.classList.add("is-loading");
        textoBotao.textContent = "Enviando...";

        try {
            await service.aguardar(750);
            const criado = await service.criar({
                tipo: document.getElementById("feedback-tipo").value,
                assunto: document.getElementById("feedback-assunto").value,
                mensagem: document.getElementById("feedback-mensagem").value,
                avaliacao: Number(document.querySelector('input[name="avaliacao"]:checked')?.value || 0) || null
            });

            form.reset();
            atualizarContador(document.getElementById("feedback-assunto"), "contador-assunto", 120);
            atualizarContador(document.getElementById("feedback-mensagem"), "contador-mensagem", 2000);
            atualizarEstrelas();
            sucesso.textContent = `Feedback enviado! Protocolo: ${criado.protocolo}.`;
            sucesso.hidden = false;
            sucesso.scrollIntoView({ behavior: "smooth", block: "nearest" });
        } catch (erro) {
            erroGeral.textContent = erro.message || "Não foi possível enviar agora. Tente de novo.";
            erroGeral.hidden = false;
        } finally {
            botao.disabled = false;
            botao.classList.remove("is-loading");
            textoBotao.textContent = "Enviar feedback";
        }
    }
})();
