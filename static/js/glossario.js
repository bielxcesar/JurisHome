(() => {
    'use strict';
    function iniciar() {
        document.body.classList.toggle('modo-claro', document.documentElement.dataset.theme === 'light');
        const data = document.getElementById('data-atual');
        if (data) data.textContent = new Intl.DateTimeFormat('pt-BR').format(new Date());
        const botao = document.getElementById('btn-perfil');
        const menu = document.getElementById('dropdown-perfil');
        function fechar() {
            menu.classList.add('hidden');
            botao.setAttribute('aria-expanded', 'false');
        }
        if (botao && menu) {
            botao.addEventListener('click', () => {
                const aberto = menu.classList.toggle('hidden') === false;
                botao.setAttribute('aria-expanded', String(aberto));
            });
            document.addEventListener('click', evento => {
                if (!menu.contains(evento.target) && !botao.contains(evento.target)) fechar();
            });
            document.addEventListener('keydown', evento => {
                if (evento.key === 'Escape' && !menu.classList.contains('hidden')) {
                    fechar(); botao.focus();
                }
            });
        }
        let saindo = false;
        document.querySelectorAll('.btn-desconectar').forEach(link => link.addEventListener('click', async evento => {
            evento.preventDefault();
            if (saindo) return;
            saindo = true;
            try {
                const resposta = await fetch('/api/auth/logout', {method: 'POST', credentials: 'same-origin'});
                if (!resposta.ok) throw new Error();
                location.assign('/');
            } catch (_) {
                const aviso = document.getElementById('glossario-alerta');
                aviso.textContent = 'Não foi possível encerrar a sessão. Tente novamente.';
                aviso.hidden = false;
                aviso.scrollIntoView({block: 'center'});
            } finally { saindo = false; }
        }));
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar, {once: true});
    else iniciar();
})();
