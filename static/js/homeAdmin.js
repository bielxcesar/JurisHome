document.addEventListener("DOMContentLoaded", () => {
    carregarTemaSalvo();
    exibirDataAtual();
    carregarConteudosHome();
    configurarMenuPerfil();
});

function carregarTemaSalvo() {
    const temaSalvo = localStorage.getItem("tema_juris");
    if (temaSalvo === "claro") {
        document.body.classList.add("modo-claro");
    } else {
        document.body.classList.remove("modo-claro");
    }
}

function exibirDataAtual() {
    const hoje = new Date();
    const dia = String(hoje.getDate()).padStart(2, '0');
    const mes = String(hoje.getMonth() + 1).padStart(2, '0');
    const ano = hoje.getFullYear();
    document.getElementById("data-atual").innerText = `${dia}/${mes}/${ano}`;
}

async function carregarConteudosHome() {
    try {
        const resposta = await fetch("/api/conteudos");
        const conteudos = await resposta.json();

        if (!conteudos || conteudos.length === 0) return;

        if (conteudos[0]) {
            document.getElementById("hero-titulo-1").innerText = conteudos[0].titulo;
            document.getElementById("hero-cat-1").innerText = "Direito Trabalhista";
        }

        if (conteudos[1]) {
            document.getElementById("hero-titulo-2").innerText = conteudos[1].titulo;
            document.getElementById("hero-cat-2").innerText = "Direito Trabalhista";
        } else if (conteudos[0]) {
            document.getElementById("hero-titulo-2").innerText = "Justiça reverte justa causa de funcionária após discussão no refeitório;";
            document.getElementById("hero-cat-2").innerText = "Direito Trabalhista";
        }

        if (conteudos[2]) {
            document.getElementById("hero-titulo-3").innerText = conteudos[2].titulo;
            document.getElementById("hero-cat-3").innerText = "Direito Trabalhista";
        } else {
            document.getElementById("hero-titulo-3").innerText = "Empresa é condenada a pagar indenização após chefe cobrar metas pelo WhatsApp";
            document.getElementById("hero-cat-3").innerText = "Direito Trabalhista";
        }

        const gridRecomendados = document.getElementById("grid-voce-pode-gostar");
        const itensRecomendados = conteudos.slice(3);
        
        if (itensRecomendados.length > 0) {
            gridRecomendados.innerHTML = itensRecomendados.map(item => `
                <article class="card-item">
                    <span class="categoria-tag">Direito Trabalhista</span>
                    <h4>${item.titulo}</h4>
                </article>
            `).join('');
        } else {
            gridRecomendados.innerHTML = `
                <article class="card-item"></article>
                <article class="card-item"></article>
                <article class="card-item"></article>
            `;
        }

    } catch (erro) {
        console.error("Erro ao carregar os dados:", erro);
    }
}

function configurarMenuPerfil() {
    const btnPerfil = document.getElementById("btn-perfil");
    const dropdown = document.getElementById("dropdown-perfil");

    if (!btnPerfil || !dropdown) return;

    btnPerfil.addEventListener("click", (e) => {
        e.stopPropagation();
        dropdown.classList.toggle("ativo");
    });

    document.addEventListener("click", (e) => {
        if (!dropdown.contains(e.target) && !btnPerfil.contains(e.target)) {
            dropdown.classList.remove("ativo");
        }
    });
}
document.addEventListener("DOMContentLoaded", () => {
    // Atualiza a data atual no cabeçalho
    const dataElemento = document.getElementById("data-atual");
    if (dataElemento) {
        const hoje = new Date();
        dataElemento.textContent = hoje.toLocaleDateString("pt-BR");
    }

    const btnPerfil = document.getElementById("btn-perfil");
    const dropdownPerfil = document.getElementById("dropdown-perfil");

    if (btnPerfil && dropdownPerfil) {
        btnPerfil.addEventListener("click", (e) => {
            e.stopPropagation();
            dropdownPerfil.classList.toggle("active");
        });

        document.addEventListener("click", () => {
            dropdownPerfil.classList.remove("active");
        });
    }

    carregarConteudos();
});

async function carregarConteudos() {
    try {
        const response = await fetch("/api/conteudos");
        if (!response.ok) throw new Error("Erro ao carregar matérias");

        const materias = await response.json();
        if (!materias || materias.length === 0) return;

        // 1. Notícia Destaque Principal (Card Grande Esquerda)
        if (materias[0]) {
            const card1 = document.getElementById("card-destaque-principal");
            const cat1 = document.getElementById("hero-cat-1");
            const titulo1 = document.getElementById("hero-titulo-1");

            cat1.textContent = materias[0].categoria;
            titulo1.textContent = materias[0].titulo;
            
            // Define a imagem de fundo e redirecionamento
            card1.style.backgroundImage = `linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.85) 100%), url('${materias[0].imagem_miniatura}')`;
            card1.style.backgroundSize = "cover";
            card1.style.backgroundPosition = "center";
            card1.style.cursor = "pointer";
            card1.onclick = () => window.location.href = `/materia/${materias[0].uuid}`;
        }

        if (materias[1]) {
            const card2 = document.getElementById("card-destaque-2");
            const cat2 = document.getElementById("hero-cat-2");
            const titulo2 = document.getElementById("hero-titulo-2");

            cat2.textContent = materias[1].categoria;
            titulo2.textContent = materias[1].titulo;

            card2.style.backgroundImage = `linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.85) 100%), url('${materias[1].imagem_miniatura}')`;
            card2.style.backgroundSize = "cover";
            card2.style.backgroundPosition = "center";
            card2.style.cursor = "pointer";
            card2.onclick = () => window.location.href = `/materia/${materias[1].uuid}`;
        }

        if (materias[2]) {
            const card3 = document.getElementById("card-destaque-3");
            const cat3 = document.getElementById("hero-cat-3");
            const titulo3 = document.getElementById("hero-titulo-3");

            cat3.textContent = materias[2].categoria;
            titulo3.textContent = materias[2].titulo;

            card3.style.backgroundImage = `linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.85) 100%), url('${materias[2].imagem_miniatura}')`;
            card3.style.backgroundSize = "cover";
            card3.style.backgroundPosition = "center";
            card3.style.cursor = "pointer";
            card3.onclick = () => window.location.href = `/materia/${materias[2].uuid}`;
        }

        const gridGostar = document.getElementById("grid-voce-pode-gostar");
        if (gridGostar) {
            gridGostar.innerHTML = "";

            const recomendados = materias.slice(3);
            recomendados.forEach(item => {
                const card = document.createElement("article");
                card.className = "card-recomendado";
                card.style.backgroundImage = `linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.85) 100%), url('${item.imagem_miniatura}')`;
                card.style.backgroundSize = "cover";
                card.style.backgroundPosition = "center";
                card.style.cursor = "pointer";
                card.onclick = () => window.location.href = `/materia/${item.uuid}`;

                card.innerHTML = `
                    <span class="categoria-tag">${item.categoria}</span>
                    <h4>${item.titulo}</h4>
                `;
                gridGostar.appendChild(card);
            });
        }

    } catch (err) {
        console.error("Falha ao buscar dados das notícias:", err);
    }
}