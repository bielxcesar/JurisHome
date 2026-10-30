(() => {
'use strict';
const botao = document.getElementById('error-retry');
if (botao) { botao.hidden = false; botao.addEventListener('click', () => window.location.reload()); }
})();
