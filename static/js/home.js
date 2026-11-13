(() => {
    'use strict';
    const $=id=>document.getElementById(id);
    const criar=(tag,texto,classe)=>{
        const e=document.createElement(tag);
        if(texto!==undefined)e.textContent=texto;
        if(classe)e.className=classe;
        return e;
    };
    const normalizar=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
    const areas=[
        ['Direito Constitucional','scale-balanced','#38a3ff'],
        ['Direito Civil','file-lines','#4bbe75'],
        ['Direito Penal','gavel','#f87171'],
        ['Direito Trabalhista','briefcase','#f5b32c'],
        ['Direito do Consumidor','cart-shopping','#e879f9'],
        ['Direito Tributário','receipt','#f97316'],
        ['Direito Administrativo','landmark','#bd70ff'],
        ['Direito Previdenciário','shield-halved','#22c55e'],
        ['Direito Empresarial','chart-line','#21c9cd'],
        ['Direito Ambiental','leaf','#84cc16']
    ];
    const sinonimosAreas={
        'Direito Trabalhista':['Direito do Trabalho','Trabalhista','Direito Trabalista','Trabalista'],
        'Direito do Consumidor':['Direito Consumidor','Consumidor'],
        'Direito Penal':['Direito Penal (Criminal)','Direito Criminal','Criminal','Penal'],
        'Direito Constitucional':['Constitucional'],
        'Direito Civil':['Civil'],
        'Direito Tributário':['Tributário'],
        'Direito Administrativo':['Administrativo'],
        'Direito Previdenciário':['Previdenciário'],
        'Direito Empresarial':['Empresarial'],
        'Direito Ambiental':['Ambiental']
    };
    let materias=[],posicao=0;
    function imagemSegura(v){
        if(typeof v!=='string')return null;
        if(/^data:image\/(jpeg|png|webp);base64,[a-zA-Z0-9+/=]+$/.test(v))return v;
        try{
            const u=new URL(v,location.origin);
            return ['http:','https:'].includes(u.protocol)?u.href:null;
        }catch(_){
            return null;
        }
    }
    function definirImagem(img,url){
        const segura=imagemSegura(url);
        if(!segura){
            img.hidden=true;
            return;
        }
        img.onerror=()=>{
            img.hidden=true;
        };
        img.src=segura;
        img.hidden=false;
    }
    function destaque(){
        const m=materias[posicao],link=$('home-destaque');
        const resumo = $('home-resumo');
        resumo.textContent = m?.resumo_home?.trim() || m?.sub_titulo?.trim() || '';
        resumo.hidden = !resumo.textContent;
        if(!m){
            link.removeAttribute('href');
            $('home-area').textContent='ACERVO JURISHOME';
            $('home-titulo').textContent='Novas leituras estão a caminho.';
            $('home-ler').textContent='Explore as categorias e o glossário enquanto isso.';
            $('home-capa').hidden=true;
            $('home-carousel').hidden=true;
            return;
        }
        link.href='/materia/'+encodeURIComponent(m.uuid);
        $('home-area').textContent=m.categoria||'Direito';
        $('home-titulo').textContent=m.titulo;
        $('home-ler').textContent='Ler matéria completa →';
        definirImagem($('home-capa'),m.imagem_miniatura);
        $('home-carousel').hidden=materias.length<2;
        $('home-posicao').textContent=`${posicao+1} de ${materias.length}`;
    }
    function criarCartaoMateria(materia) {
        const cartao = criar('a', undefined, 'home-article');
        cartao.href = '/materia/' + encodeURIComponent(materia.uuid);

        const placeholder = criar('span', undefined, 'home-thumb home-thumb-placeholder');
        placeholder.setAttribute('aria-hidden', 'true');
        placeholder.append(criar('i', undefined, 'fa-regular fa-file-lines'));
        const src = imagemSegura(materia.imagem_miniatura);
        if (src) {
            const imagem = criar('img', undefined, 'home-thumb');
            imagem.alt = '';
            imagem.loading = 'lazy';
            imagem.addEventListener('error', () => imagem.replaceWith(placeholder), {once: true});
            imagem.src = src;
            cartao.append(imagem);
        } else {
            cartao.append(placeholder);
        }

        const info = criar('div', undefined, 'home-article-info');
        const data = materia.criado_em ? `Publicado em ${materia.criado_em}` : 'Ler matéria →';
        info.append(criar('span', materia.categoria || 'Direito'), criar('h3', materia.titulo), criar('small', data));
        cartao.append(info);
        return cartao;
    }

    function cartoes(){
        const grade=$('home-materias');
        grade.replaceChildren();
        if(!materias.length){
            grade.append(criar('p','Ainda não há matérias publicadas. Explore o glossário para começar.','home-empty'));
            return;
        }
        for(const m of materias.slice(0,8)){
            grade.append(criarCartaoMateria(m));
        }
    }
    async function ler(url){
        const r=await fetch(url,{credentials:'same-origin'});
        if(!r.ok)throw new Error();
        const d=await r.json();
        if(!Array.isArray(d))throw new Error();
        return d;
    }
    async function carregarMaterias(){
        const grade=$('home-materias');
        grade.setAttribute('aria-busy','true');
        try{
            materias=await ler('/api/conteudos');
            posicao=0;
            destaque();
            cartoes();
        }catch(_){
            materias=[];
            destaque();
            $('home-titulo').textContent='Não foi possível carregar as matérias.';
            grade.replaceChildren();
            const box=criar('div','Confira sua conexão e tente novamente.','home-empty'),b=criar('button','Tentar novamente');
            b.type='button';
            b.addEventListener('click',carregarMaterias);
            box.append(b);
            grade.append(box);
        }finally{
            grade.setAttribute('aria-busy','false');
        }
    }
    async function carregarCategorias(){
        const grade=$('home-categorias');
        try{
            const lista=await ler('/api/categorias');
            grade.replaceChildren();
            for(const [nome,icone,cor] of areas){
                const equivalentes=[nome,...(sinonimosAreas[nome]||[])].map(normalizar);
                const c=lista.find(item=>normalizar(item.nome)===normalizar(nome))||lista.find(item=>equivalentes.includes(normalizar(item.nome)));
                if(!c)continue;
                const a=criar('a',undefined,'home-category');
                a.style.setProperty('--tile',cor);
                a.href='/categorias?categoria='+encodeURIComponent(c.nome);
                const i=criar('i',undefined,'fa-solid fa-'+icone);
                i.setAttribute('aria-hidden','true');
                a.append(i,criar('strong',c.nome));
                grade.append(a);
            }
            const outras=criar('a',undefined,'home-category');
            outras.style.setProperty('--tile','#939aaa');
            outras.href='/categorias';
            const i=criar('i',undefined,'fa-solid fa-ellipsis');
            i.setAttribute('aria-hidden','true');
            outras.append(i,criar('strong','Todas as áreas'));
            grade.append(outras);
        }catch(_){
            grade.replaceChildren();
            const link=criar('a','Explorar as categorias →','home-empty');
            link.href='/categorias';
            grade.append(link);
        }finally{
            grade.setAttribute('aria-busy','false');
        }
    }
    $('home-anterior').addEventListener('click',()=>{
        posicao=(posicao-1+materias.length)%materias.length;
        destaque();
    });
    $('home-proximo').addEventListener('click',()=>{
        posicao=(posicao+1)%materias.length;
        destaque();
    });
    const data=$('data-atual');
    if(data)data.textContent=new Intl.DateTimeFormat('pt-BR').format(new Date());
    document.body.classList.toggle('modo-claro',document.documentElement.dataset.theme==='light');
    async function emAlta() {
        const grade=$('home-em-alta');
        try{
            const lista=await ler('/api/conteudos/em-alta');
            grade.replaceChildren();
            if(!lista.length){
                grade.append(criar('p','As matérias em alta aparecerão aqui conforme o acervo receber leituras.','home-empty'));
                return;
            }
            for(const m of lista){
                const a=criar('a',undefined,'home-article');
                a.href='/materia/'+encodeURIComponent(m.uuid);
                const info=criar('div',undefined,'home-article-info');
                info.append(criar('span',m.categoria||'Direito'),criar('h3',m.titulo),criar('small',`${m.leituras} leitura(s) nesta semana`));
                a.append(info);
                grade.append(a);
            }
        }
 catch(_){
            grade.replaceChildren(criar('p','Não foi possível consultar as leituras agora.','home-empty'));
        }finally{
            grade.setAttribute('aria-busy','false');
        }
    }
    (async()=>{
        try{
            const r=await fetch('/api/feedbacks/resumo',{credentials:'same-origin'});
            if(!r.ok)return;
            const d=await r.json();
            const aviso=$('home-feedback-notice');
            if(d.quantidade){
                aviso.textContent=d.mensagem+' →';
                aviso.href=d.destino;
                aviso.hidden=false;
            }
        }catch(_){}
    })();
    async function carregarInteresse(){
        const grade=$('home-interesse');
        if(!grade)return;
        try{
            const r=await fetch('/api/conteudos/interesse',{credentials:'same-origin'});
            if(!r.ok)throw new Error();
            const d=await r.json();
            grade.replaceChildren();
            $('home-interesse-titulo').textContent=d.area||'Escolha sua área de interesse';
            $('home-interesse-descricao').textContent=d.area?'Publicações recentes sobre a área que você escolheu.':'Defina uma área no perfil para encontrar suas leituras aqui.';
            for(const m of d.itens){
                grade.append(criarCartaoMateria(m));
            }
            if(!d.itens.length){
                const a=criar('a',d.area?'Novas matérias desta área aparecerão aqui. Explorar categoria →':'Escolher área de interesse →','home-empty');
                a.href=d.area?'/categorias?categoria='+encodeURIComponent(d.area):'/perfil';
                grade.append(a);
            }
        }catch(_){
            grade.replaceChildren(criar('p','Não foi possível carregar suas leituras agora.','home-empty'));
        }finally{
            grade.setAttribute('aria-busy','false');
        }
    }
    carregarMaterias();
    carregarCategorias();
    emAlta();
    carregarInteresse();
})();
