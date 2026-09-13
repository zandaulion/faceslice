/**
 * Faceslice — fluxul: fotografie, reglaje, export.
 *
 * Reglajele nu retrimit fotografia. Reconstrucţia a rulat o dată şi harta de
 * adâncime a rămas pe server; mişcarea unui cursor cere doar o feliere nouă.
 * De aceea cererile se şi anulează între ele: la tras de cursor pleacă zeci,
 * şi contează numai ultima.
 */
import { installUpdates } from '/pwa-update.js';

const $ = (s, r = document) => r.querySelector(s);
const cheieJeton = 'faceslice-jeton';
let jeton = localStorage.getItem(cheieJeton) || '';
let lucrare = null;
let inZbor = null;
let asteapta = null;

async function api(cale, opt = {}) {
  const r = await fetch(cale, {
    ...opt,
    headers: { ...(opt.headers || {}), ...(jeton ? { 'X-Device-Token': jeton } : {}) },
  });
  if (r.status === 401) { jeton = ''; localStorage.removeItem(cheieJeton); poarta(); throw new Error('acces'); }
  if (!r.ok) {
    let m = `Eroare ${r.status}`;
    try { m = (await r.json()).detail || m; } catch { /* răspuns fără corp */ }
    throw new Error(m);
  }
  return r.headers.get('content-type')?.includes('json') ? r.json() : r;
}

/* Ce trebuie desfăcut când se schimbă ecranul.

   Ascultătorii puşi pe `document` -- lipirea din clipboard, de pildă -- nu
   dispar odată cu marcajul care i-a cerut, aşa că ar rămâne agăţaţi şi ar
   căuta câmpuri care nu mai există. */
const curatenii = [];

function pune(sablon) {
  while (curatenii.length) curatenii.pop()();
  const c = $('#continut');
  c.innerHTML = '';
  c.appendChild($(sablon).content.cloneNode(true));
  return c;
}

/* ---------------------------------------------------------------- poarta */

function poarta() {
  pune('#sablon-poarta');
  $('#insigna').textContent = '🔒 fără acces';
  const cod = $('#cod');
  const din = new URLSearchParams(location.search).get('code');
  if (din) cod.value = din;
  $('#btn-revendica').onclick = async () => {
    try {
      const r = await fetch('/api/invites/redeem', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: cod.value.trim() }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || 'Cod respins.');
      const d = await r.json();
      jeton = d.token;
      localStorage.setItem(cheieJeton, jeton);
      history.replaceState({}, '', location.pathname);
      ecranFoto();
    } catch (e) { $('#eroare-poarta').textContent = e.message; }
  };
}

/* ------------------------------------------------------------ fotografia */

function ecranFoto() {
  pune('#sablon-foto');
  $('#insigna').textContent = '🟢 conectat';
  const fisier = $('#fisier');
  const zona = $('#zona');
  const trimite = $('#btn-trimite');
  let ales = null;

  const arata = (f) => {
    ales = f;
    trimite.disabled = !f;
    const u = URL.createObjectURL(f);
    zona.querySelector('.zona-int').innerHTML =
      `<img src="${u}" alt="" /><div class="mut mic" style="margin-top:8px">${f.name}</div>`;
  };
  fisier.onchange = () => fisier.files[0] && arata(fisier.files[0]);

  // Pe laptop, o poză ajunge de multe ori în clipboard înainte să ajungă în
  // vreun fişier -- decupată dintr-un mesaj, trasă dintr-un album. Lipirea o
  // duce direct în prima zonă liberă, ca să nu treacă prin Salvare ca…
  const peLipire = (e) => {
    const item = [...(e.clipboardData?.items || [])]
      .find((x) => x.type.startsWith('image/'));
    if (!item) return;
    const f = item.getAsFile();
    if (!f) return;
    e.preventDefault();
    if (!ales) arata(f); else arataProfil(f);
  };
  document.addEventListener('paste', peLipire);
  curatenii.push(() => document.removeEventListener('paste', peLipire));

  // A doua poză: acelaşi tipar, dar fără ea se merge mai departe.
  const fisierProfil = $('#fisier-profil');
  const zonaProfil = $('#zona-profil');
  let alesProfil = null;
  const arataProfil = (f) => {
    alesProfil = f;
    const u = URL.createObjectURL(f);
    zonaProfil.querySelector('.zona-int').innerHTML =
      `<img src="${u}" alt="" /><div class="mut mic" style="margin-top:8px">${f.name}</div>`;
  };
  fisierProfil.onchange = () => fisierProfil.files[0] && arataProfil(fisierProfil.files[0]);
  zonaProfil.ondragover = (e) => { e.preventDefault(); zonaProfil.classList.add('activ'); };
  zonaProfil.ondragleave = () => zonaProfil.classList.remove('activ');
  zonaProfil.ondrop = (e) => {
    e.preventDefault(); zonaProfil.classList.remove('activ');
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('image/')) arataProfil(f);
  };
  zona.ondragover = (e) => { e.preventDefault(); zona.classList.add('activ'); };
  zona.ondragleave = () => zona.classList.remove('activ');
  zona.ondrop = (e) => {
    e.preventDefault(); zona.classList.remove('activ');
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('image/')) arata(f);
  };

  trimite.onclick = async () => {
    if (!ales) return;
    const fd = new FormData();
    fd.append('foto', ales);
    if (alesProfil) fd.append('profil_foto', alesProfil);
    fd.append('dip_mm', $('#dip').value);
    fd.append('oglindit', $('#oglindit').checked);
    fd.append('cu_gat', $('#cu-gat').checked);
    trimite.disabled = true;
    $('#eroare-foto').textContent = '';
    zona.querySelector('.zona-int').innerHTML =
      `<div class="lucreaza">Caut faţa, silueta şi adâncimea${
        alesProfil ? ', apoi măsor nasul din profil' : ''}…</div>`;
    try {
      lucrare = await api('/api/jobs', { method: 'POST', body: fd });
      ecranReglaje();
    } catch (e) {
      $('#eroare-foto').textContent = e.message;
      trimite.disabled = false;
      arata(ales);
    }
  };

  api('/api/jobs').then(listaLucrari).catch(() => {});
}

function listaLucrari(l) {
  if (!l.length || !$('#lucrari')) return;
  const d = document.createElement('div');
  d.className = 'lista';
  d.innerHTML = '<h3>Lucrări salvate</h3>' + l.map((j) =>
    `<div class="lista-el" data-id="${j.id}"><span>${j.nume || 'portret'}</span>` +
    `<span class="mut mic">${(j.rezumat.latime_cap_mm || 0).toFixed(0)} mm lat</span></div>`
  ).join('');
  d.querySelectorAll('.lista-el').forEach((el) => {
    el.onclick = () => { lucrare = { id: el.dataset.id }; ecranReglaje(); };
  });
  $('#lucrari').appendChild(d);
}

/* --------------------------------------------------------------- reglaje */

const CURSOARE = {
  grosime: ['grosime_mm', (v) => `${(+v).toFixed(1)} mm`],
  adancime: ['adancime_mm', (v) => `${v} mm`],
  kerf: ['kerf_mm', (v) => `${(+v).toFixed(2)} mm`],
  detaliu: ['detaliu', (v) => `${(+v).toFixed(2).replace(/0$/, '')}×`],
  curba: ['curba', (v) => `${(+v).toFixed(2).replace(/0$/, '')}×`],
  inclinare: ['inclinare', (v) => `${v}°`],
  rotire: ['rotire', (v) => `${v}°`],
  sari: ['sari', (v) => (v === '1' ? '1 (toate)' : `1 din ${v}`)],
  margine: ['margine_mm', (v) => `${v} mm`],
};

function citesteReglaje() {
  const r = { goleste: $('#goleste').checked };
  for (const [id, [cheie]] of Object.entries(CURSOARE)) r[cheie] = parseFloat($(`#${id}`).value);
  return r;
}

/**
 * Măreşte o previzualizare.
 *
 * Pe laptop se judecă dacă un detaliu mic supravieţuieşte tăierii, iar asta nu
 * se vede într-o imagine cât un card. Escape şi clicul pe fundal închid --
 * ambele, fiindcă pe laptop mâna e când pe tastatură, când pe maus.
 */
function porneseLupa() {
  const strat = $('#lupa-strat');
  const mare = $('#lupa-img');
  if (!strat) return;

  const inchide = () => {
    strat.hidden = true;
    mare.removeAttribute('src');
    document.removeEventListener('keydown', peTasta);
  };
  const peTasta = (e) => { if (e.key === 'Escape') inchide(); };

  for (const b of document.querySelectorAll('.lupa')) {
    b.onclick = () => {
      const sursa = document.getElementById(b.dataset.mare);
      if (!sursa?.src) return;
      mare.src = sursa.src;
      mare.alt = sursa.alt;
      strat.hidden = false;
      document.addEventListener('keydown', peTasta);
      $('#lupa-inchide').focus();
    };
  }
  strat.onclick = (e) => { if (e.target === strat) inchide(); };
  $('#lupa-inchide').onclick = inchide;
}

function ecranReglaje() {
  pune('#sablon-reglaje');
  $('#btn-inapoi').onclick = ecranFoto;
  porneseLupa();

  // Cursorul de relief porneşte de la ce s-a măsurat pentru omul acesta, dacă
  // s-a măsurat. Altfel rămâne pe media care nu ştie ce obiectiv a fost.
  const rez = lucrare?.rezumat || {};
  if (rez.detaliu) $('#detaliu').value = rez.detaliu;
  const nota = $('#calibrare');
  if (rez.calibrat && rez.calibrare) {
    const c = rez.calibrare;
    nota.innerHTML =
      `<strong>Calibrat după poza din profil.</strong> Nasul tău iese ` +
      `${c.nas_masurat_mm.toFixed(1)} mm; din poza frontală ieşeau ` +
      `${c.nas_dedus_mm.toFixed(1)} mm, deci relieful se ridică de ` +
      `${c.factor.toFixed(2)} ori. Valoarea e a ta şi a aparatului cu care ai pozat.`;
    nota.hidden = false;
  } else {
    nota.innerHTML =
      `<strong>Fără poză din profil.</strong> Adâncimea feţei foloseşte o ` +
      `valoare medie (${(rez.detaliu || 1.5).toFixed(2)}×), fiindcă dintr-o ` +
      `singură poză nu se poate şti dacă nasul e mare sau obiectivul a fost ` +
      `aproape. Reîncarcă adăugând o poză din profil dacă vrei exactitate.`;
    nota.hidden = false;
  }

  for (const [id, [, fmt]] of Object.entries(CURSOARE)) {
    const el = $(`#${id}`);
    const et = $(`#v-${id}`);
    const scrie = () => { et.textContent = fmt(el.value); };
    scrie();
    el.oninput = () => { scrie(); cerePrevizualizare(); };
  }
  $('#goleste').onchange = cerePrevizualizare;

  $('#btn-dxf').onclick = () => {
    const p = new URLSearchParams({ coala_w: $('#coala-w').value, coala_h: $('#coala-h').value });
    // Link obişnuit: jetonul călătoreşte prin cookie, aşa că descărcarea nu
    // are nevoie de cod care să pună antete.
    location.href = `/api/jobs/${lucrare.id}/dxf?${p}`;
  };

  cerePrevizualizare();
}

function cerePrevizualizare() {
  clearTimeout(asteapta);
  asteapta = setTimeout(previzualizeaza, 180);
}

async function previzualizeaza() {
  if (inZbor) inZbor.abort();
  const ctl = new AbortController();
  inZbor = ctl;
  const sumar = $('#sumar');
  if (sumar) sumar.style.opacity = '0.45';
  try {
    const d = await api(`/api/jobs/${lucrare.id}/previzualizare`, {
      method: 'POST', signal: ctl.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(citesteReglaje()),
    });
    $('#img-asamblat').src = `data:image/png;base64,${d.asamblat}`;
    $('#img-plane').src = `data:image/png;base64,${d.plane}`;
    const i = d.info;
    // Fiecare material îşi primeşte căsuţa lui, ca toate celelalte cifre.
    // Înşirate într-un bloc pe toată lăţimea, se rupeau pe patru rânduri şi
    // împingeau sumarul sub marginea de jos -- pe laptop, unde stă lipit lângă
    // imagine, asta însemna că nu se mai vedea deloc.
    sumar.innerHTML = [
      ['plăci', i.placi],
      ['contururi', i.contururi],
      ['tablă', `${i.arie_dm2} dm²`],
      ['teanc', `${i.inaltime_teanc_mm} mm`],
      ...Object.entries(i.greutate_kg).map(([n, v]) => [n, `${v} kg`]),
    ].map(([e, v]) => `<div><div class="et">${e}</div><div class="va">${v}</div></div>`).join('');
    sumar.style.opacity = '1';
  } catch (e) {
    if (e.name !== 'AbortError' && sumar) {
      sumar.innerHTML = `<div style="grid-column:1/-1" class="eroare">${e.message}</div>`;
      sumar.style.opacity = '1';
    }
  } finally {
    if (inZbor === ctl) inZbor = null;
  }
}

/* ---------------------------------------------------------------- pornire */

async function porneste() {
  installUpdates({ appName: 'Faceslice', message: 'Faceslice s-a actualizat.' });
  if (!jeton) return poarta();
  try { await api('/api/me'); ecranFoto(); } catch { /* poarta a preluat */ }
}
porneste();
