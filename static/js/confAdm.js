document.addEventListener("DOMContentLoaded", () => {
    const btnVoltar = document.getElementById("btn-voltar");
    const formSenha = document.getElementById("form-troca-senha");
    const alertSucesso = document.getElementById("alert-sucesso");
    const btnTema = document.querySelector(".btn-theme");
    const iconeTema = btnTema ? btnTema.querySelector("i") : null;

    // Aplica a preferência salva na memória do navegador
    function aplicarTemaSalvo() {
        const temaSalvo = localStorage.getItem("tema_juris");
        if (temaSalvo === "claro") {
            document.body.classList.add("modo-claro");
            if (iconeTema) {
                iconeTema.classList.replace("fa-moon", "fa-sun");
            }
        }
    }

    // Clique no botão para alternar o visual
    if (btnTema) {
        btnTema.addEventListener("click", () => {
            document.body.classList.toggle("modo-claro");
            const estaNoModoClaro = document.body.classList.contains("modo-claro");

            // Salva a escolha
            localStorage.setItem("tema_juris", estaNoModoClaro ? "claro" : "escuro");

            // Troca o ícone de lua para sol
            if (iconeTema) {
                if (estaNoModoClaro) {
                    iconeTema.classList.replace("fa-moon", "fa-sun");
                } else {
                    iconeTema.classList.replace("fa-sun", "fa-moon");
                }
            }
        });
    }

    aplicarTemaSalvo();

    // Botão Voltar
    if (btnVoltar) {
        btnVoltar.addEventListener("click", () => {
            window.location.href = "/home_admin";
        });
    }

    // Envio do formulário
    if (formSenha) {
        formSenha.addEventListener("submit", (e) => {
            e.preventDefault();

            const novaSenha = document.getElementById("nova-senha").value;
            const confirmaSenha = document.getElementById("confirma-senha").value;

            if (novaSenha !== confirmaSenha) {
                alert("A nova senha e a confirmação não conferem!");
                return;
            }

            alertSucesso.classList.add("exibir");
            formSenha.reset();

            setTimeout(() => {
                alertSucesso.classList.remove("exibir");
            }, 4000);
        });
    }
});