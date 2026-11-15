(() => {
    "use strict";

    const chave = "jurishome_ultima_pagina";
    const paginaAtual = () => location.pathname + location.search;
    const paginaDeErro = document.body.classList.contains("error-page");

    if (!paginaDeErro) {
        function salvarPagina() {
            try {
                sessionStorage.setItem(chave, paginaAtual() + location.hash);
            } catch {
                // A navegação continua quando o navegador bloqueia o armazenamento.
            }
        }

        salvarPagina();
        window.addEventListener("pageshow", salvarPagina);
        window.addEventListener("pagehide", salvarPagina);
        return;
    }

    const voltar = document.querySelector(".error-actions .error-primary");
    try {
        const salvo = sessionStorage.getItem(chave);
        if (voltar && salvo?.startsWith("/") && !salvo.startsWith("//")) {
            const anterior = new URL(salvo, location.origin);
            if (anterior.origin === location.origin && anterior.pathname + anterior.search !== paginaAtual()) {
                voltar.href = anterior.href;
                voltar.querySelector("span").textContent = "Voltar à última página";
            }
        }
    } catch {
        // O link original leva à tela principal.
    }

    const tentar = document.getElementById("error-retry");
    if (tentar) {
        tentar.hidden = false;
        tentar.addEventListener("click", () => location.reload());
    }
})();
