// Usa a mesma preferência de tema das demais páginas do JurisHome.
(() => {
    let tema = "escuro";
    try {
        tema = localStorage.getItem("tema_juris") === "claro" ? "claro" : "escuro";
    } catch (_) {
        // A consulta continua funcionando quando o navegador bloqueia o armazenamento.
    }
    document.documentElement.dataset.tema = tema;

    document.addEventListener("DOMContentLoaded", () => {
        const botao = document.getElementById("alternar-tema");
        const atualizarBotao = () => {
            botao.textContent = tema === "claro" ? "Modo escuro" : "Modo claro";
            botao.setAttribute("aria-label", `Ativar ${botao.textContent.toLowerCase()}`);
        };
        atualizarBotao();
        botao.hidden = false;
        botao.addEventListener("click", () => {
            tema = tema === "claro" ? "escuro" : "claro";
            document.documentElement.dataset.tema = tema;
            try {
                localStorage.setItem("tema_juris", tema);
            } catch (_) {
                // A alternância nesta página independe da persistência.
            }
            atualizarBotao();
        });
    });
})();
