(() => {
'use strict';
const $=id=>document.getElementById(id);
const data=$('data-atual');if(data)data.textContent=new Intl.DateTimeFormat('pt-BR').format(new Date());
document.body.classList.toggle('modo-claro',document.documentElement.dataset.theme==='light');
})();
