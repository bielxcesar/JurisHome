(() => {
'use strict';
const $=id=>document.getElementById(id);
const data=$('data-atual');if(data)data.textContent=new Intl.DateTimeFormat('pt-BR').format(new Date());
document.body.classList.toggle('modo-claro',document.documentElement.dataset.theme==='light');
const perfil=$('btn-perfil'),menu=$('dropdown-perfil');function fechar(){menu.classList.add('hidden');perfil.setAttribute('aria-expanded','false');}
perfil.addEventListener('click',()=>{menu.classList.toggle('hidden');perfil.setAttribute('aria-expanded',String(!menu.classList.contains('hidden')));});document.addEventListener('click',e=>{if(!menu.contains(e.target)&&!perfil.contains(e.target))fechar();});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!menu.classList.contains('hidden')){fechar();perfil.focus();}});
let saindo=false;document.querySelectorAll('.btn-desconectar').forEach(link=>link.addEventListener('click',async e=>{e.preventDefault();if(saindo)return;saindo=true;try{const r=await fetch('/api/auth/logout',{method:'POST',credentials:'same-origin'});if(!r.ok)throw new Error();location.assign('/');}catch(_){$('home-aviso').textContent='Não foi possível encerrar a sessão. Tente novamente.';$('home-aviso').hidden=false;}finally{saindo=false;}}));
})();
