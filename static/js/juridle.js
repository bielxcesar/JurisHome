(() => {
'use strict';
const $ = id => document.getElementById(id);
let rodada = null, ocupada = false, enviando = false;
function aviso(texto) { $('home-aviso').hidden=false; $('home-aviso').textContent=texto; }
async function api(caminho, dados) {
 const r = await fetch('/api/juridle/'+caminho,{credentials:'same-origin',...(dados===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dados)})});
 const d=await r.json().catch(()=>({})); if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Não foi possível concluir. Tente novamente.'); return d;
}
function progresso(p) {
 $('j-nivel').textContent='Nível '+p.nivel; $('j-frequencia').textContent=p.frequencia+' dia'+(p.frequencia===1?'':'s');
 $('j-sequencia').textContent=p.sequencia;$('j-recorde').textContent=p.melhorSequencia;$('j-coroas').textContent=p.coroas;
 const lista=$('j-historico');lista.replaceChildren();
 if(!p.historico.length){const li=document.createElement('li');li.textContent='Sua primeira rodada começa aqui.';lista.append(li);}
 for(const h of p.historico){const li=document.createElement('li');li.textContent=`${new Date(h.data).toLocaleDateString('pt-BR')} · ${h.acertos}/${h.total} acertos${h.coroa?' · Coroa conquistada!':''}`;lista.append(li);}
}
function mostrarPergunta() {
 $('j-final').hidden=true; $('j-jogo').hidden=false; $('j-retorno').hidden=true; $('j-proxima').hidden=true;
 $('j-andamento').textContent=`Pergunta ${rodada.respondidas+1} de ${rodada.total}`;
 $('j-pergunta-titulo').textContent=rodada.pergunta.enunciado;$('j-definicao').textContent=rodada.pergunta.definicao;
 const box=$('j-opcoes');box.replaceChildren();
 rodada.pergunta.opcoes.forEach((texto,i)=>{const b=document.createElement('button');b.type='button';b.className='juridle-option';const letra=document.createElement('b');letra.textContent='ABCD'[i];const span=document.createElement('span');span.textContent=texto;b.append(letra,span);b.addEventListener('click',()=>responder(i));box.append(b);});
 $('j-jogo').focus();
}
function final() {
 $('j-jogo').hidden=true;$('j-final').hidden=false;
 $('j-final-titulo').textContent=rodada.coroa?'Coroa conquistada!':'Rodada concluída';
 $('j-final-texto').textContent=`Você acertou ${rodada.acertos} de ${rodada.total} perguntas. ${rodada.coroa?'Uma rodada perfeita!':'Continue praticando e consulte o glossário para revisar.'}`;
 $('j-final').focus();$('j-play').textContent='Jogar novamente';
}
async function iniciar() {if(ocupada)return;ocupada=true;$('j-play').disabled=true;$('j-nova').disabled=true;
 try{const d=await api('rodadas',{});rodada=d.rodada;progresso(d.progresso);$('home-aviso').hidden=true;mostrarPergunta();}
 catch(e){aviso(e.message);}finally{ocupada=false;$('j-play').disabled=false;$('j-nova').disabled=false;}}
async function responder(opcao) {
 if(enviando||ocupada)return;enviando=true;const atual=rodada;const botoes=[...$('j-opcoes').children];botoes.forEach(b=>b.disabled=true);$('j-play').disabled=true;
 try{const d=await api(`rodadas/${encodeURIComponent(atual.uuid)}/respostas`,{pergunta:atual.respondidas,opcao});
 rodada=d.rodada;progresso(d.progresso);$('home-aviso').hidden=true;$('j-retorno').hidden=false;$('j-resultado').textContent=d.resultado.acertou?'Você acertou!':'Vamos aprender com essa resposta';
 $('j-explicacao').textContent=`Resposta: ${atual.pergunta.opcoes[d.resultado.correta]}. ${d.resultado.explicacao}`;
 $('j-exemplo').textContent=d.resultado.exemplo;const fonte=$('j-fonte');try{const u=new URL(d.resultado.fonte.url);fonte.hidden=!['http:','https:'].includes(u.protocol);if(!fonte.hidden)fonte.href=u.href;}catch(_){fonte.hidden=true;}
 botoes[d.resultado.correta].classList.add('j-correta');if(!d.resultado.acertou)botoes[opcao].classList.add('j-incorreta');
 $('j-proxima').hidden=false;$('j-proxima').textContent=rodada.concluida?'Ver resultado da rodada':'Próxima pergunta →';
 }catch(e){aviso(e.message);botoes.forEach(b=>b.disabled=false);}finally{enviando=false;$('j-play').disabled=false;}
}
$('j-proxima').addEventListener('click',()=>{if(rodada.concluida)final();else mostrarPergunta();});$('j-play').addEventListener('click',iniciar);$('j-nova').addEventListener('click',iniciar);
(async()=>{try{const d=await api('estado');rodada=d.rodada;progresso(d.progresso);$('j-play').textContent=rodada?'Continuar rodada':'Play · iniciar rodada';}
 catch(e){aviso(e.message);$('j-play').textContent='Tentar iniciar rodada';}finally{$('j-play').disabled=false;}})();
})();
