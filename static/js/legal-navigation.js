(function () {
    "use strict";

    const RETURN_KEY = "jurishome_legal_return";
    const LEGAL_PATHS = new Set(["/termos-de-aceite", "/politica-de-privacidade"]);

    function isLegalPath(path) {
        return LEGAL_PATHS.has(path);
    }

    function saveInternalDestination(url) {
        if (url.origin !== window.location.origin || isLegalPath(url.pathname)) return;
        sessionStorage.setItem(RETURN_KEY, `${url.pathname}${url.search}${url.hash}`);
    }

    document.addEventListener("click", (event) => {
        const link = event.target.closest("a[href]");
        if (!link || isLegalPath(window.location.pathname)) return;

        const destination = new URL(link.href, window.location.href);
        if (isLegalPath(destination.pathname)) {
            saveInternalDestination(new URL(window.location.href));
        }
    });

    if (!isLegalPath(window.location.pathname)) return;

    if (!sessionStorage.getItem(RETURN_KEY) && document.referrer) {
        try {
            saveInternalDestination(new URL(document.referrer));
        } catch (_) {
            sessionStorage.removeItem(RETURN_KEY);
        }
    }

    const returnTo = sessionStorage.getItem(RETURN_KEY) || "/";
    document.querySelectorAll("[data-legal-return]").forEach((link) => {
        link.href = returnTo;
    });
})();
