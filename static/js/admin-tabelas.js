(() => {
'use strict';
const $ = id => document.getElementById(id);
const root = document.body.dataset.root === 'true';
const normalizar = v => String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const estado = {usuarios: [], filtroUsuario:'', filtroMateria:'', paginaUsuario:1, paginaMateria:1};
const linhas = [...$('lista-materias').rows];
const limite = 8;
function aviso(texto) { $('painel-aviso').textContent = texto; $('painel-aviso').hidden = false; }
function criar(tag, texto, classe) { const e=document.createElement(tag); if(texto !== undefined)e.textContent=texto; if(classe)e.className=classe; return e; }
function paginar(id, total, pagina, mudar) {
 const box=$(id); box.replaceChildren();
 box.append(criar('span', total ? `Exibindo ${(pagina-1)*limite+1}–${Math.min(pagina*limite,total)} de ${total} registros` : 'Nenhum registro encontrado'));
 const nav=criar('nav'); nav.setAttribute('aria-label', id==='paginacao-usuarios'?'Páginas de usuários':'Páginas de matérias');
 const paginas=Math.max(1,Math.ceil(total/limite));
 function botao(texto, destino, disabled=false) { const b=criar('button',texto); b.type='button'; b.disabled=disabled; b.addEventListener('click',()=>mudar(destino)); nav.append(b); return b; }
 botao('Anterior',pagina-1,pagina===1);
 for(let n=Math.max(1,pagina-2); n<=Math.min(paginas,pagina+2); n++) { const b=botao(String(n),n); if(n===pagina)b.setAttribute('aria-current','page'); }
 botao('Próxima',pagina+1,pagina===paginas); box.append(nav);
}
function materias() {
 const busca=normalizar($('busca-materias').value);
 const filtradas=linhas.filter(r=>(!estado.filtroMateria || (estado.filtroMateria==='revisao'?r.dataset.status!=='aprovado':r.dataset.status==='aprovado')) && normalizar(r.cells[0].textContent+' '+r.cells[1].textContent).includes(busca));
 linhas.forEach(r=>r.hidden=true);
 filtradas.slice((estado.paginaMateria-1)*limite,estado.paginaMateria*limite).forEach(r=>r.hidden=false);
 $('materias-vazio').hidden=filtradas.length>0;
 paginar('paginacao-materias',filtradas.length,estado.paginaMateria,n=>{estado.paginaMateria=n;materias();});
}
function usuarios() {
 const busca=normalizar($('busca-usuarios').value);
 const filtrados=estado.usuarios.filter(u=>(!estado.filtroUsuario || (estado.filtroUsuario==='administrador'?u.tipo==='administrador':u.tipo!=='administrador')) && normalizar(u.nome+' '+u.email).includes(busca));
 const body=$('lista-usuarios'); body.replaceChildren();
 for(const u of filtrados.slice((estado.paginaUsuario-1)*limite,estado.paginaUsuario*limite)) {
  const tr=criar('tr'); const td=criar('td'); const identity=criar('div',undefined,'identity');
  identity.append(criar('span',String(u.nome||'?').split(/\s+/).filter(Boolean).slice(0,2).map(s=>s[0]).join('').toUpperCase(),'avatar'));
  const nome=criar('div'); nome.append(criar('strong',u.nome),criar('small',u.email)); identity.append(nome);td.append(identity);tr.append(td);
  tr.append(criar('td',u.e_root_admin?'Administrador principal':u.tipo==='administrador'?'Administrador':'Leitor'));
  const status=criar('td');status.append(criar('span',u.is_2fa_enabled?'Ativa':'Inativa','badge '+(u.is_2fa_enabled?'success':'neutral')));tr.append(status);
  tr.append(criar('td',u.solicitou_ajuda?'Recuperação 2FA solicitada':'Sem solicitação'));
  const acoes=criar('td');
  if(u.e_root_admin)acoes.textContent='Conta protegida';
  else if(root && u.tipo === 'administrador') {
   const grupo=criar('div',undefined,'actions');
   const editar=criar('a','Editar','button');editar.href='/admin/administradores/'+encodeURIComponent(u.uuid);editar.setAttribute('aria-label','Editar administrador '+u.nome);
   const excluir=criar('button','Excluir','danger');excluir.type='button';excluir.setAttribute('aria-label','Excluir administrador '+u.nome);excluir.addEventListener('click',()=>abrirExclusaoAdmin(u));
   grupo.append(editar,excluir);acoes.append(grupo);
  }
  else if(!root && (u.is_2fa_enabled || u.solicitou_ajuda)) { const b=criar('button','Resetar 2FA','danger');b.addEventListener('click',()=>executar(b,async()=>{if(!confirm('O autenticador atual será revogado. Continuar?'))return;await requisitar('/api/admin/resetar-2fa/'+encodeURIComponent(u.uuid),'POST');aviso('Autenticador revogado. O usuário deverá configurar o 2FA novamente.');await carregar();}));acoes.append(b); }
  else acoes.textContent='Somente leitura';
  tr.append(acoes);body.append(tr);
 }
 if(!filtrados.length) { const r=criar('tr'); const td=criar('td','Nenhum usuário encontrado.');td.colSpan=5;r.append(td);body.append(r); }
 paginar('paginacao-usuarios',filtrados.length,estado.paginaUsuario,n=>{estado.paginaUsuario=n;usuarios();});
}
async function requisitar(url,method='GET',dados) {
 const resposta=await fetch(url,{method,credentials:'same-origin',...(dados?{headers:{'Content-Type':'application/json'},body:JSON.stringify(dados)}:{})});
 const data=await resposta.json().catch(()=>({}));
 if(!resposta.ok)throw new Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(item=>item.msg.replace(/^Value error, /,'')).join(' '):resposta.status===401?'Sua sessão expirou. Entre novamente.':'Não foi possível concluir a operação.');
 return data;
}
async function executar(botao,acao) { if(botao.disabled)return;botao.disabled=true;try{await acao();}catch(e){aviso(e.message);if(modal)alert(e.message);}finally{botao.disabled=false;} }
async function carregar() {
 const b=$('atualizar-usuarios');b.disabled=true;$('lista-usuarios').setAttribute('aria-busy','true');
 try { const dados=await requisitar('/api/admin/usuarios'); if(!Array.isArray(dados))throw new Error('Resposta inválida ao carregar usuários.');estado.usuarios=dados;estado.paginaUsuario=1;$('total-usuarios').textContent=dados.length;$('total-admins').textContent=dados.filter(u=>u.tipo==='administrador').length;usuarios(); }
 catch(e){aviso(e.message);if(!estado.usuarios.length){$('lista-usuarios').replaceChildren();const tr=criar('tr'),td=criar('td','Falha ao carregar usuários. Use Atualizar para tentar novamente.');td.colSpan=5;tr.append(td);$('lista-usuarios').append(tr);}}
 finally{b.disabled=false;$('lista-usuarios').removeAttribute('aria-busy');}
}
let modal=null, foco=null;
function abrir(id) { foco=document.activeElement;modal=$(id);modal.hidden=false;modal.querySelector('input:not([type="hidden"])').focus(); }
function fechar() { if(!modal)return;modal.hidden=true;modal=null;foco?.focus(); }
window.fecharEdicao=fechar;window.fecharModalNovoAdmin=fechar;
window.salvarEdicao=()=>executar($('modalEdicao').querySelector('button:last-child'),async()=>{
 const titulo=$('editTitulo').value.trim();if(!titulo)throw new Error('Informe o título da matéria.');
 await requisitar('/editar-materia/'+encodeURIComponent($('editUuid').value),'PUT',{titulo});
 const linha=linhas.find(r=>r.dataset.id===$('editUuid').value);linha.cells[0].querySelector('a').textContent=titulo;fechar();materias();aviso('Título atualizado.');
});
window.salvarNovoAdmin=()=>executar($('modalNovoAdmin').querySelector('button:last-child'),async()=>{
 const nome=$('novoAdminNome').value.trim(),email=$('novoAdminEmail').value.trim(),senha=$('novoAdminSenha').value;
 if(!nome||!email||!senha||!$('novoAdminEmail').checkValidity())throw new Error('Preencha nome, e-mail válido e senha.');
 await requisitar('/api/admin/criar-admin','POST',{nome,email,senha});$('novoAdminSenha').value='';fechar();aviso('Administrador cadastrado.');await carregar();
});
$('novo-admin')?.addEventListener('click',()=>{['novoAdminNome','novoAdminEmail','novoAdminSenha'].forEach(id=>$(id).value='');abrir('modalNovoAdmin');});
$('lista-materias').addEventListener('click',e=>{const b=e.target.closest('button[data-action]');if(!b)return;const r=b.closest('tr');
 if(b.dataset.action==='editar'){$('editUuid').value=r.dataset.id;$('editTitulo').value=r.cells[0].textContent;abrir('modalEdicao');return;}
 executar(b,async()=>{const aprovar=b.dataset.action==='aprovar';if(!confirm(aprovar?'Publicar esta matéria para os leitores?':'Excluir permanentemente esta matéria?'))return;
 await requisitar((aprovar?'/aprovar-materia/':'/deletar-materia/')+encodeURIComponent(r.dataset.id),aprovar?'PUT':'DELETE');location.reload();});
});
document.addEventListener('keydown',e=>{if(!modal)return;if(e.key==='Escape'){fechar();return;}if(e.key==='Tab'){const itens=[...modal.querySelectorAll('input:not([type="hidden"]),button')].filter(e=>!e.disabled);const primeiro=itens[0],ultimo=itens.at(-1);if(e.shiftKey&&document.activeElement===primeiro){e.preventDefault();ultimo.focus();}else if(!e.shiftKey&&document.activeElement===ultimo){e.preventDefault();primeiro.focus();}}});
for(const tipo of ['user','materia'])document.querySelectorAll(`[data-${tipo}-filter]`).forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll(`[data-${tipo}-filter]`).forEach(el=>el.setAttribute('aria-pressed',String(el===b)));if(tipo==='user'){estado.filtroUsuario=b.dataset.userFilter;estado.paginaUsuario=1;usuarios();}else{estado.filtroMateria=b.dataset.materiaFilter;estado.paginaMateria=1;materias();}}));
$('busca-usuarios').addEventListener('input',()=>{estado.paginaUsuario=1;usuarios();});$('busca-materias').addEventListener('input',()=>{estado.paginaMateria=1;materias();});$('atualizar-usuarios').addEventListener('click',carregar);
$('painel-data').textContent=new Intl.DateTimeFormat('pt-BR',{dateStyle:'long'}).format(new Date());
// Labels are connected to the existing modal inputs for keyboard and screen reader use.
document.querySelectorAll('[role="dialog"] label').forEach(label=>{const input=label.parentElement.querySelector('input');if(input)label.htmlFor=input.id;});
let alvoExclusao=null, excluindo=false;
const dialogExclusao=$('excluir-admin-dialog');
function abrirExclusaoAdmin(usuario) {
 if(!root || usuario.e_root_admin || usuario.tipo!=='administrador')return;
 alvoExclusao=usuario;
 $('excluir-admin-pergunta').textContent='Você deseja excluir o administrador '+usuario.nome+'?';
 $('excluir-admin-esperado').textContent=usuario.nome;
 $('excluir-admin-nome').value='';$('excluir-admin-confirmar').disabled=true;$('excluir-admin-erro').hidden=true;
 dialogExclusao.showModal();$('excluir-admin-nome').focus();
}
$('excluir-admin-nome').addEventListener('input',()=>{$('excluir-admin-confirmar').disabled=excluindo || $('excluir-admin-nome').value.trim()!==alvoExclusao?.nome;});
$('excluir-admin-cancelar').addEventListener('click',()=>{if(!excluindo)dialogExclusao.close();});
dialogExclusao.addEventListener('cancel',evento=>{if(excluindo)evento.preventDefault();});
$('excluir-admin-form').addEventListener('submit',async evento=>{
 evento.preventDefault();if(excluindo||!alvoExclusao||$('excluir-admin-nome').value.trim()!==alvoExclusao.nome)return;
 excluindo=true;$('excluir-admin-confirmar').disabled=true;$('excluir-admin-cancelar').disabled=true;$('excluir-admin-erro').hidden=true;
 try{const resposta=await requisitar('/api/admin/administradores/'+encodeURIComponent(alvoExclusao.uuid),'DELETE',{nome_confirmacao:$('excluir-admin-nome').value.trim()});dialogExclusao.close();aviso(resposta.mensagem);await carregar();$('atualizar-usuarios').focus();}
 catch(erro){$('excluir-admin-erro').textContent=erro.message;$('excluir-admin-erro').hidden=false;}
 finally{excluindo=false;$('excluir-admin-cancelar').disabled=false;$('excluir-admin-confirmar').disabled=$('excluir-admin-nome').value.trim()!==alvoExclusao?.nome;}
});
materias();carregar();
})();
