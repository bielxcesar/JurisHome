(() => {
    'use strict';
    const botao = document.getElementById('juris-perfil');
    const menu = document.getElementById('juris-perfil-menu');
    if (!botao || !menu) return;

    const data = document.getElementById('data-atual');
    if (data) data.textContent = new Intl.DateTimeFormat('pt-BR').format(new Date());

    function abrirMenu(aberto) {
        menu.hidden = !aberto;
        botao.setAttribute('aria-expanded', String(aberto));
    }
    botao.addEventListener('click', () => abrirMenu(menu.hidden));
    document.addEventListener('click', evento => {
        if (!menu.contains(evento.target) && !botao.contains(evento.target)) abrirMenu(false);
    });
    document.addEventListener('keydown', evento => {
        if (evento.key === 'Escape' && !menu.hidden) {
            abrirMenu(false);
            botao.focus();
        }
    });

    const coroa = document.getElementById('juris-coroa');
    if (coroa) {
        let temporizador;
        let ultimoEstado = 0;

        function exibirCoroa(conquistada) {
            coroa.style.opacity = conquistada ? '1' : '.22';
            coroa.style.filter = conquistada ? 'none' : 'grayscale(1)';
            coroa.title = conquistada ? 'Coroa de hoje conquistada · 5 de 5' : 'Coroa diária ainda não conquistada';
            coroa.setAttribute('aria-label', coroa.title);
        }

        window.addEventListener('juridle:coroa', ({detail}) => {
            const servidorEm = Date.parse(detail.servidorEm);
            if (!Number.isFinite(servidorEm) || servidorEm < ultimoEstado) return;
            ultimoEstado = servidorEm;
            exibirCoroa(detail.coroaHoje);
            clearTimeout(temporizador);
            const espera = Date.parse(detail.proximaRodadaEm) - servidorEm;
            temporizador = setTimeout(() => {
                exibirCoroa(false);
                carregarCoroa();
            }, Math.max(1000, espera));
        });

        async function carregarCoroa() {
            try {
                const resposta = await fetch('/api/juridle/coroa', {cache: 'no-store'});
                if (!resposta.ok) return;
                const detail = await resposta.json();
                window.dispatchEvent(new CustomEvent('juridle:coroa', {detail}));
            } catch {
                // A próxima visita ou retorno à aba consulta novamente.
            }
        }

        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) carregarCoroa();
        });
        carregarCoroa();
    }

    const sair = menu.querySelector('.juris-desconectar');
    sair?.addEventListener('click', async evento => {
        evento.preventDefault();
        if (sair.getAttribute('aria-busy') === 'true') return;
        sair.setAttribute('aria-busy', 'true');
        try {
            const resposta = await fetch('/api/auth/logout', {method: 'POST', credentials: 'same-origin'});
            if (!resposta.ok) throw new Error();
            location.assign('/');
        } catch {
            const aviso = document.getElementById('juris-nav-aviso');
            aviso.textContent = 'Não foi possível desconectar. Tente novamente.';
            aviso.hidden = false;
            sair.removeAttribute('aria-busy');
        }
    });
})();
