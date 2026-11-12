(() => {
    "use strict";

    if (document.body.dataset.tipoUsuario === "administrador") return;

    function registrar(categoria) {
        const nome = String(categoria || "").trim();
        if (!nome) return Promise.resolve();

        return fetch("/api/perfil/categoria-acesso", {
            method: "POST",
            credentials: "same-origin",
            keepalive: true,
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ categoria: nome }),
        }).catch(() => undefined);
    }

    document.getElementById("home-categorias")?.addEventListener("click", evento => {
        if (evento.defaultPrevented || evento.button !== 0 || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
        const alvo = evento.target instanceof Element ? evento.target : evento.target?.parentElement;
        const link = alvo?.closest("a.home-category[href]");
        if (!link) return;

        const categoria = new URL(link.href, window.location.origin).searchParams.get("categoria");
        if (!categoria) return;

        evento.preventDefault();
        let navegou = false;
        const navegar = () => {
            if (navegou) return;
            navegou = true;
            window.location.assign(link.href);
        };
        const limite = window.setTimeout(navegar, 900);
        registrar(categoria).finally(() => {
            window.clearTimeout(limite);
            navegar();
        });
    });

    document.getElementById("categoria-materias")?.addEventListener("change", evento => {
        registrar(evento.target.value);
    });
})();
