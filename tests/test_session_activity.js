// Executar: node --test tests/test_session_activity.js
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const codigo = fs.readFileSync(path.join(__dirname, '../static/js/session.js'), 'utf8');
const aguardar = () => new Promise(setImmediate);

function navegador() {
    const eventos = {}, eventosJanela = {}, chamadas = [];
    let relogio = 0, intervalo, status = 204, destino, interrompido = false;
    const document = {hidden: false, addEventListener: (tipo, fn) => {eventos[tipo] = fn;}};
    const location = {pathname: '/perfil', origin: 'https://jurishome.test', reload() {},
        assign(url) {destino = url;}, replace(url) {destino = url;}};
    const window = {addEventListener(tipo, fn) {eventosJanela[tipo] = fn;}, fetch: async (_, opcoes) => {
        chamadas.push(JSON.parse(opcoes.body));
        return {status, ok: status < 400, headers: new Headers()};
    }};
    vm.runInNewContext(codigo, {window, document, location, navigator: {}, Request, URL,
        Date: {now: () => relogio}, setInterval(fn) {intervalo = fn; return 1;},
        clearInterval() {interrompido = true;}});
    return {eventos, eventosJanela, chamadas, document,
        tempo(valor) {relogio = valor;}, responder(valor) {status = valor;}, tick() {intervalo();},
        destino: () => destino, interrompido: () => interrompido};
}

test('presença automática não simula atividade após a abertura', async () => {
    const n = navegador(); await aguardar();
    assert.equal(n.chamadas[0].atividade, true);
    n.tempo(15000); n.tick(); await aguardar();
    assert.equal(n.chamadas.at(-1).atividade, false);
    n.tempo(30000); n.tick(); await aguardar();
    assert.equal(n.chamadas.at(-1).atividade, false);
});

test('mouse, teclado, clique, toque e rolagem renovam sem enviar por movimento', async () => {
    for (const tipo of ['mousemove', 'keydown', 'pointerdown', 'touchstart', 'scroll']) {
        const n = navegador(); await aguardar(); n.tempo(16000);
        for(let i=0;i<100;i++) n.eventos[tipo]({isTrusted: true});
        await aguardar();
        assert.equal(n.chamadas.length, 2, tipo);
        assert.equal(n.chamadas[1].atividade, true, tipo);
    }
});

test('retorno a uma aba sinaliza atividade; aba oculta não gera atividade', async () => {
    const n = navegador(); await aguardar(); n.tempo(16000);
    n.document.hidden = true;
    n.eventos.mousemove({isTrusted: true}); n.tick(); await aguardar();
    assert.equal(n.chamadas.at(-1).atividade, false);
    n.document.hidden = false; n.eventos.visibilitychange(); await aguardar();
    assert.equal(n.chamadas.at(-1).atividade, true);
    n.tempo(32000); n.eventosJanela.focus({isTrusted: true}); await aguardar();
    assert.equal(n.chamadas.at(-1).atividade, true);
});

test('eventos sintéticos não renovam; resposta 401 encerra a página', async () => {
    const n = navegador(); await aguardar(); n.tempo(16000);
    n.eventos.mousemove({isTrusted: false}); n.tick(); await aguardar();
    assert.equal(n.chamadas.at(-1).atividade, false);
    n.responder(401); n.tick(); await aguardar();
    assert.equal(n.destino(), '/?sessao=expirada');
    assert.equal(n.interrompido(), true);
});
