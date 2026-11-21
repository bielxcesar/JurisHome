(() => {
    "use strict";
    const form = document.getElementById("form-curadoria");
    if (!form) return;
    const pagina = document.getElementById("curadoria");
    const retorno = document.getElementById("retorno-curadoria");
    let enviando = false;
    form.addEventListener("submit", async evento => {
        evento.preventDefault();
        if (enviando) return;
        const decisao = evento.submitter.value;
        const orientacoes = document.getElementById("orientacoes").value.trim();
        if (decisao === "devolver" && orientacoes.length < 10) {
            retorno.textContent = "Explique as correções necessárias com pelo menos dez caracteres.";
            return;
        }
        enviando = true;
        form.querySelectorAll("button").forEach(botao => botao.disabled = true);
        try {
            const resposta = await fetch("/api/admin/materias/" + encodeURIComponent(pagina.dataset.id) + "/curadoria", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({decisao, orientacoes, versao: Number(pagina.dataset.versao)}),
            });
            const dados = await resposta.json();
            if (!resposta.ok) throw new Error(typeof dados.detail === "string" ? dados.detail : "Confira os dados da revisão.");
            location.reload();
        } catch (erro) {
            retorno.textContent = erro.message;
            enviando = false;
            form.querySelectorAll("button").forEach(botao => botao.disabled = false);
        }
    });
})();
