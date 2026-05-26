/* =============================================================================
   UTILITATS
   ============================================================================= */
function debounce(fn, delay) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
}

const MESOS_CA = ['gener','febrer','març','abril','maig','juny','juliol','agost','setembre','octubre','novembre','desembre'];
function formatarData(dateStr) {
    if (!dateStr) return '?';
    const s = String(dateStr).substring(0, 10);
    const parts = s.split('-').map(Number);
    if (parts.length < 3 || !parts[0]) return dateStr;
    const [y, m, d] = parts;
    return `${d} de ${MESOS_CA[m - 1]} de ${y}`;
}

function capitalitzar(str) {
    if (!str) return str;
    const s = str.trim().toLowerCase();
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function capitalitzarTitol(str) {
    if (!str) return str;
    const skip = new Set(['de','del','dels',"d'",'la','el','els','les','i','o','a','en','al','als','per','amb','un','una','uns','unes',"l'"]);
    return str.toLowerCase().trim().split(/\s+/).map((w, i) =>
        i === 0 || !skip.has(w) ? w.charAt(0).toUpperCase() + w.slice(1) : w
    ).join(' ');
}

function crearDescExpandible(text, limit = 120) {
    if (!text) return '';
    const clean = text.trim();
    if (clean.length <= limit) return `<p class="popup-desc">${clean}</p>`;
    const truncat = clean.substring(0, limit).trim() + '…';
    return `<p class="popup-desc"><span class="desc-short">${truncat}</span><span class="desc-full" style="display:none">${clean}</span><button class="btn-desc-toggle" onclick="toggleDesc(this)">Llegir més</button></p>`;
}

window.toggleDesc = function(btn) {
    const p       = btn.parentElement;
    const shortEl = p.querySelector('.desc-short');
    const fullEl  = p.querySelector('.desc-full');
    const isShort = fullEl.style.display === 'none';
    shortEl.style.display = isShort ? 'none' : '';
    fullEl.style.display  = isShort ? ''     : 'none';
    btn.textContent       = isShort ? 'Menys' : 'Llegir més';
};

/* =============================================================================
   ESTAT GLOBAL
   ============================================================================= */
const API_BASE       = "http://127.0.0.1:8000";
const MAX_PATRIMONI  = 30000;
const MAX_AGENDA     = 1000;
const MIN_ZOOM_DADES = 9;

const state = {
    patrimoniGeoJSON: null,
    agendaGeoJSON:    null,
    patrimoniMarkers: [],
    agendaMarkers:    [],
    featuresGlobals:  [],
    ubicacioUsuari:   null,
    markerUsuari:     null,
    isLoading:        false,
    currentBasemap:   'satellite',
};

let rutaLayer = null; // Capa de la ruta cultural activa

/* =============================================================================
   MAPA
   ============================================================================= */
const map = L.map('map', {
    center: [41.8204, 1.5671],
    zoom: 7,
    preferCanvas: true,
    zoomControl: false,
    scrollWheelZoom: false,
    dragging: false,
    doubleClickZoom: false,
    touchZoom: false,
});

L.control.zoom({ position: 'bottomleft' }).addTo(map);

const BASEMAPS = {
    dark: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap, © CARTO', maxZoom: 19,
    }),
    satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: '© Esri, Maxar, Earthstar Geographics', maxZoom: 19,
    }),
    topo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenTopoMap contributors', maxZoom: 17,
    }),
    light: L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap, © CARTO', maxZoom: 19,
    }),
};
BASEMAPS.satellite.addTo(map);

const clusterPatrimoni = L.markerClusterGroup({
    chunkedLoading: true, maxClusterRadius: 50,
    iconCreateFunction: (c) => L.divIcon({
        html: `<div class="custom-cluster cluster-patrimoni"><span>${c.getChildCount()}</span></div>`,
        className: '', iconSize: [40, 40],
    }),
});
const clusterAgenda = L.markerClusterGroup({
    chunkedLoading: true, maxClusterRadius: 50,
    iconCreateFunction: (c) => L.divIcon({
        html: `<div class="custom-cluster cluster-agenda"><span>${c.getChildCount()}</span></div>`,
        className: '', iconSize: [40, 40],
    }),
});

/* =============================================================================
   SIMBOLOGIA: EMOJIS PER CATEGORIA
   ============================================================================= */
const EMOJI_PATRIMONI = {
    "església": "⛪", "ermita": "⛪", "capella": "⛪", "oratori": "⛪",
    "monestir": "🛕", "convent": "🛕",
    "castell": "🏰", "torre": "🗼", "muralla": "🏯", "palau": "🏯",
    "pont": "🌉",
    "museu": "🏛️", "biblioteca": "📚", "teatre": "🎭",
    "arbre singular": "🌳", "jardí": "🌿",
    "font": "⛲", "pou": "⛲",
    "jaciment arqueològic": "🏺", "dolmen": "🪨", "cova": "🪨",
    "masia": "🏡", "mas": "🏡",
    "far": "💡",
    "cementiri": "🪦", "creu": "✝️",
};

const EMOJI_AGENDA_KEYS = [
    ["música",    "🎵"], ["concert",   "🎵"],
    ["teatre",    "🎭"], ["dansa",     "💃"], ["circ",     "🎪"],
    ["exposici",  "🖼️"], ["art",       "🎨"],
    ["festa maj", "🎉"], ["festa",     "🎉"],
    ["fira",      "🛍️"], ["mercat",    "🛍️"],
    ["cinema",    "🎬"], ["audiovis",  "🎬"],
    ["esport",    "⚽"],
    ["gastro",    "🍽️"], ["cuina",    "🍽️"],
    ["infantil",  "🎠"], ["familiar",  "🎠"],
    ["natura",    "🌿"], ["medi",      "🌿"],
    ["ciència",   "🔬"], ["tecnolog",  "🔬"],
    ["conferèn",  "🎤"], ["xerrada",   "🎤"],
    ["cultura",   "📖"], ["patrimon",  "🏛️"],
];

function emojiPatrimoni(categoria) {
    if (!categoria) return '🏛️';
    const c = categoria.toLowerCase().trim();
    return EMOJI_PATRIMONI[c] ||
        Object.entries(EMOJI_PATRIMONI).find(([k]) => c.includes(k))?.[1] ||
        '🏛️';
}

function emojiAgenda(categoria) {
    if (!categoria) return '📅';
    const c = categoria.toLowerCase();
    return EMOJI_AGENDA_KEYS.find(([k]) => c.includes(k))?.[1] || '📅';
}

/* =============================================================================
   SCROLLYTELLING
   ============================================================================= */
const capitols = {
    'cap-intro':      { center: [41.8204, 1.5671], zoom: 7  },
    'cap-context':    { center: [41.8204, 1.5671], zoom: 8  },
    'cap-patrimoni':  { center: [41.5932, 1.8362], zoom: 12 },
    'cap-festes':     { center: [42.1011, 1.8463], zoom: 13 },
    'cap-agenda':     { center: [41.3874, 2.1686], zoom: 13 },
    'cap-explorador': { center: [41.8204, 1.5671], zoom: 9  },
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        document.querySelectorAll('.step').forEach(el => el.classList.remove('active'));
        entry.target.classList.add('active');
        const id = entry.target.id;
        if (capitols[id]) map.flyTo(capitols[id].center, capitols[id].zoom, { duration: 1.5, easeLinearity: 0.25 });
        if (id === 'cap-explorador') enterExplorerMode();
    });
}, { threshold: 0.5 });

document.querySelectorAll('.step').forEach(step => observer.observe(step));

window.addEventListener('scroll', () => {
    const scrollActual = document.documentElement.scrollTop || document.body.scrollTop;
    const scrollTotal  = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    if (scrollTotal > 0) {
        document.getElementById('progress-bar').style.width = (scrollActual / scrollTotal * 100) + '%';
    }
});

/* =============================================================================
   TRANSICIONS ENTRE MODES
   ============================================================================= */
function enterExplorerMode() {
    observer.disconnect();
    document.querySelectorAll('.step').forEach(el => el.classList.remove('active'));
    document.getElementById('btn-saltar-intro').classList.add('hidden');

    document.body.style.overflow = 'hidden';

    const story = document.getElementById('story');
    story.style.opacity       = '0';
    story.style.pointerEvents = 'none';

    document.getElementById('ui-explorer').classList.remove('hidden');

    map.dragging.enable();
    map.scrollWheelZoom.enable();
    map.doubleClickZoom.enable();
    map.touchZoom.enable();

    if (!map.hasLayer(clusterPatrimoni)) map.addLayer(clusterPatrimoni);
    if (!map.hasLayer(clusterAgenda))    map.addLayer(clusterAgenda);

    const dataInput = document.getElementById('dataFiltre');
    if (!dataInput.value) {
        dataInput.value = new Date().toISOString().split('T')[0];
    }

    map.on('moveend', onMapMoveEnd);

    if (map.getZoom() < MIN_ZOOM_DADES) {
        document.getElementById('zoom-overlay').classList.remove('hidden');
        clusterPatrimoni.clearLayers();
        clusterAgenda.clearLayers();
        map.flyTo(capitols['cap-explorador'].center, MIN_ZOOM_DADES, { duration: 1.2 });
    } else {
        document.getElementById('zoom-overlay').classList.add('hidden');
        carregarDadesViewport();
    }

    if (!localStorage.getItem('atlas-welcome-seen')) {
        setTimeout(mostrarWelcome, 800);
    }
}

function exitExplorerMode() {
    document.body.style.overflow = '';

    const story = document.getElementById('story');
    story.style.opacity = '1';
    story.style.removeProperty('pointer-events');

    document.getElementById('ui-explorer').classList.add('hidden');
    document.getElementById('zoom-overlay').classList.add('hidden');
    document.getElementById('btn-saltar-intro').classList.remove('hidden');

    map.dragging.disable();
    map.scrollWheelZoom.disable();
    map.doubleClickZoom.disable();
    map.touchZoom.disable();

    if (map.hasLayer(clusterPatrimoni)) map.removeLayer(clusterPatrimoni);
    if (map.hasLayer(clusterAgenda))    map.removeLayer(clusterAgenda);
    map.off('moveend', onMapMoveEnd);

    document.querySelectorAll('.step').forEach(el => el.classList.remove('active'));
    document.getElementById('cap-agenda').classList.add('active');
    map.flyTo(capitols['cap-agenda'].center, capitols['cap-agenda'].zoom, { duration: 1.0 });
    document.getElementById('cap-agenda').scrollIntoView({ behavior: 'smooth' });

    setTimeout(() => {
        document.querySelectorAll('.step').forEach(step => observer.observe(step));
    }, 1400);
}

/* =============================================================================
   WELCOME MODAL
   ============================================================================= */
function mostrarWelcome() {
    document.getElementById('welcome-modal').classList.remove('hidden');
}

/* =============================================================================
   BASEMAP SWITCHER
   ============================================================================= */
const BM_LABELS = { satellite: 'Satèl·lit', dark: 'Fosc', light: 'Clar', topo: 'Topogràfic' };

function toggleBasemapWidget() {
    document.getElementById('basemap-panel').classList.toggle('hidden');
}

function switchBasemap(name) {
    if (state.currentBasemap !== name) {
        map.removeLayer(BASEMAPS[state.currentBasemap]);
        BASEMAPS[name].addTo(map);
        BASEMAPS[name].bringToBack();
        state.currentBasemap = name;
    }
    document.querySelectorAll('.bm-opt').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.bm === name);
    });
    const btn = document.getElementById('btn-basemap-toggle');
    if (btn) btn.innerHTML = `<div class="bm-thumb swatch-${name}"></div>${BM_LABELS[name] || name}`;
    document.getElementById('basemap-panel').classList.add('hidden');
}

/* =============================================================================
   CÀRREGA DE DADES (Bbox per viewport)
   ============================================================================= */
function getBboxParams() {
    const b = map.getBounds();
    return `minx=${b.getWest()}&miny=${b.getSouth()}&maxx=${b.getEast()}&maxy=${b.getNorth()}`;
}

function setLoading(on) {
    state.isLoading = on;
    document.getElementById('loading-indicator').classList.toggle('hidden', !on);
}

async function carregarDadesViewport() {
    if (state.isLoading) return;
    setLoading(true);
    try {
        const bbox = getBboxParams();
        const [resP, resA] = await Promise.all([
            fetch(`${API_BASE}/api/patrimonio?${bbox}&limit=${MAX_PATRIMONI}`),
            fetch(`${API_BASE}/api/agenda?${bbox}&limit=${MAX_AGENDA}`),
        ]);
        if (!resP.ok || !resA.ok) throw new Error('Error de xarxa');
        state.patrimoniGeoJSON = await resP.json();
        state.agendaGeoJSON    = await resA.json();
        precrearMarkers();
        aplicarFiltres();
    } catch (e) {
        console.error('Error carregant dades:', e);
        const el = document.getElementById('resultat-text');
        el.innerText   = "⚠️ Error connectant amb l'API.";
        el.style.color = '#ef4444';
    } finally {
        setLoading(false);
    }
}

const onMapMoveEnd = debounce(() => {
    const zoom    = map.getZoom();
    const overlay = document.getElementById('zoom-overlay');
    if (zoom < MIN_ZOOM_DADES) {
        overlay.classList.remove('hidden');
        clusterPatrimoni.clearLayers();
        clusterAgenda.clearLayers();
        document.getElementById('count-agenda').textContent  = '—';
        document.getElementById('resultat-text').innerText   = "Apropa't per veure detalls";
        document.getElementById('resultat-text').style.color = 'var(--text-muted)';
    } else {
        overlay.classList.add('hidden');
        carregarDadesViewport();
    }
}, 700);

/* =============================================================================
   ICONS EMOJI I POPUPS
   ============================================================================= */
function crearIconaEmoji(emoji, isAgenda) {
    return L.divIcon({
        className: isAgenda ? 'emoji-agenda' : '',
        html: `<div class="emoji-pin">${emoji}</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
    });
}

function crearPopupPatrimoni(p) {
    const nom   = capitalitzarTitol(p.nom || 'Sense nom');
    const cat   = capitalitzar(p.categoria || '');
    const estil = capitalitzar(p.estil || '');
    const prot  = capitalitzar(p.proteccio || '');
    const img   = p.imatge_url
        ? `<img src="${p.imatge_url}" alt="${nom}" loading="lazy" class="popup-img" onerror="this.style.display='none'">`
        : '';
    const ruta  = p.google_maps_url
        ? `<a href="${p.google_maps_url}" target="_blank" rel="noopener" class="btn-popup"><i class="fa-solid fa-route"></i> Com arribar</a>`
        : '';
    const wiki  = p.wikipedia_url
        ? `<a href="${p.wikipedia_url}" target="_blank" rel="noopener" class="btn-popup btn-popup-secondary"><i class="fa-brands fa-wikipedia-w"></i> Wikipedia</a>`
        : '';
    const desc  = crearDescExpandible(p.descripcio);
    return `
        <div class="custom-popup">
            ${img}
            <h3>${nom}</h3>
            <div class="popup-info">
                <p><strong>${cat}</strong>${estil ? ` · ${estil}` : ''}</p>
                ${prot ? `<p class="popup-tag">${prot}</p>` : ''}
                ${desc}
            </div>
            <div class="popup-actions">${ruta}${wiki}</div>
        </div>`;
}

function crearPopupAgenda(p, coords) {
    const emoji   = emojiAgenda(p.categoria);
    const nom     = capitalitzarTitol(p.denominacio || 'Sense nom');
    const img     = p.imatge
        ? `<img src="${p.imatge}" alt="${nom}" loading="lazy" class="popup-img" onerror="this.parentElement.querySelector('.popup-img-placeholder').style.display='flex'; this.style.display='none'"><div class="popup-img-placeholder" style="display:none"><span class="placeholder-emoji">${emoji}</span><span class="placeholder-cat">${capitalitzar(p.categoria || 'Cultura')}</span></div>`
        : `<div class="popup-img-placeholder"><span class="placeholder-emoji">${emoji}</span><span class="placeholder-cat">${capitalitzar(p.categoria || 'Cultura')}</span></div>`;
    const inici   = formatarData(p.data_inici);
    const fi      = formatarData(p.data_fi);
    const dataStr = (p.data_fi && inici !== fi) ? `${inici} → ${fi}` : inici;
    const gratuit = p.gratuita ? '<span class="badge-gratuit">Gratuït</span>' : '';
    const lloc    = capitalitzar(p.espai || p.municipi || '');
    const adreca  = capitalitzar(p.adrecca || '');
    const desc    = crearDescExpandible(p.descripcio);
    const mapsUrl = coords ? `https://www.google.com/maps/dir/?api=1&destination=${coords[1]},${coords[0]}` : '';
    const arribar = mapsUrl
        ? `<a href="${mapsUrl}" target="_blank" rel="noopener" class="btn-popup"><i class="fa-solid fa-route"></i> Com arribar</a>`
        : '';
    const entrades = p.enllac
        ? `<a href="${p.enllac}" target="_blank" rel="noopener" class="btn-popup btn-popup-secondary"><i class="fa-solid fa-ticket"></i> Entrades</a>`
        : '';
    return `
        <div class="custom-popup">
            ${img}
            <h3>${nom} ${gratuit}</h3>
            <div class="popup-info">
                <p>🗓️ ${dataStr}</p>
                ${lloc      ? `<p>📍 ${lloc}</p>`       : ''}
                ${adreca    ? `<p>🏠 ${adreca}</p>`     : ''}
                ${p.horari  ? `<p>🕐 ${p.horari}</p>`   : ''}
                ${desc}
            </div>
            <div class="popup-actions">${arribar}${entrades}</div>
        </div>`;
}

function precrearMarkers() {
    state.patrimoniMarkers = [];
    state.agendaMarkers    = [];

    (state.patrimoniGeoJSON?.features || []).forEach(feat => {
        if (!feat.geometry?.coordinates) return;
        const [lng, lat] = feat.geometry.coordinates;
        const p     = feat.properties;
        const emoji = emojiPatrimoni(p.categoria);
        const m     = L.marker([lat, lng], { icon: crearIconaEmoji(emoji, false) });
        m.bindPopup(crearPopupPatrimoni(p), { maxWidth: 320 });
        m.feature = feat;
        state.patrimoniMarkers.push(m);
    });

    (state.agendaGeoJSON?.features || []).forEach(feat => {
        if (!feat.geometry?.coordinates) return;
        const [lng, lat] = feat.geometry.coordinates;
        const p     = feat.properties;
        const emoji = emojiAgenda(p.categoria);
        const m     = L.marker([lat, lng], { icon: crearIconaEmoji(emoji, true) });
        m.bindPopup(crearPopupAgenda(p, feat.geometry.coordinates), { maxWidth: 320 });
        m.feature = feat;
        state.agendaMarkers.push(m);
    });

    actualitzarSelectCategories();
    actualitzarSelectCategoriesAgenda();
}

/* =============================================================================
   MOTOR DE FILTRAT (sense recrear markers)
   ============================================================================= */
function passaFiltrPatrimoni(feat) {
    const p    = feat.properties;
    const text = document.getElementById('inputCerca').value.toLowerCase();
    const cat  = document.getElementById('selectorCategoria').value.toLowerCase();
    if (text) {
        const nom  = (p.nom        || '').toLowerCase();
        const desc = (p.descripcio || '').toLowerCase();
        if (!nom.includes(text) && !desc.includes(text)) return false;
    }
    if (cat && !(p.categoria || '').toLowerCase().includes(cat)) return false;
    return true;
}

function passaFiltrAgenda(feat) {
    const p         = feat.properties;
    const text      = document.getElementById('inputCerca').value.toLowerCase();
    const data      = document.getElementById('dataFiltre').value;
    const catAgenda = document.getElementById('selectorCategoriaAgenda').value.toLowerCase();
    if (text) {
        const nom  = (p.denominacio || '').toLowerCase();
        const desc = (p.descripcio  || '').toLowerCase();
        if (!nom.includes(text) && !desc.includes(text)) return false;
    }
    if (data) {
        const inici = p.data_inici ? String(p.data_inici).substring(0, 10) : null;
        const fi    = p.data_fi    ? String(p.data_fi).substring(0, 10)    : null;
        if (inici && fi)  { if (data < inici || data > fi) return false; }
        else if (inici)   { if (data !== inici) return false; }
    }
    if (catAgenda && !(p.categoria || '').toLowerCase().includes(catAgenda)) return false;
    return true;
}

function aplicarFiltres() {
    clusterPatrimoni.clearLayers();
    clusterAgenda.clearLayers();

    const mostrarP = document.getElementById('check-patrimoni').checked;
    const mostrarA = document.getElementById('check-agenda').checked;
    const visP = [], visA = [];

    if (mostrarP) {
        state.patrimoniMarkers.forEach(m => { if (passaFiltrPatrimoni(m.feature)) visP.push(m); });
        clusterPatrimoni.addLayers(visP);
    }
    if (mostrarA) {
        state.agendaMarkers.forEach(m => { if (passaFiltrAgenda(m.feature)) visA.push(m); });
        clusterAgenda.addLayers(visA);
    }

    document.getElementById('count-agenda').textContent = visA.length;

    const total = visP.length + visA.length;
    const el    = document.getElementById('resultat-text');
    el.innerText   = total > 0 ? `${total} elements al viewport` : 'Cap resultat amb aquests filtres';
    el.style.color = total > 0 ? 'var(--success)' : 'var(--festa-color)';

    state.featuresGlobals = [
        ...visP.map(m => m.feature),
        ...visA.map(m => m.feature),
    ];
    if (state.ubicacioUsuari) actualitzarRadarProximitat();
}

/* =============================================================================
   SELECTORS DE CATEGORIA (des de dades reals)
   ============================================================================= */
function actualitzarSelectCategories() {
    const select      = document.getElementById('selectorCategoria');
    const valorActual = select.value;
    select.innerHTML  = '<option value="">— Totes les categories —</option>';

    const comptes = {};
    state.patrimoniMarkers.forEach(m => {
        const cat = (m.feature.properties.categoria || '').toLowerCase().trim();
        if (cat) comptes[cat] = (comptes[cat] || 0) + 1;
    });

    Object.entries(comptes).sort((a, b) => b[1] - a[1]).forEach(([cat, count]) => {
        const opt = document.createElement('option');
        opt.value       = cat;
        opt.textContent = `${emojiPatrimoni(cat)} ${capitalitzar(cat)} (${count})`;
        select.appendChild(opt);
    });

    select.value = valorActual;
}

function actualitzarSelectCategoriesAgenda() {
    const select      = document.getElementById('selectorCategoriaAgenda');
    const valorActual = select.value;
    select.innerHTML  = '<option value="">— Totes les categories —</option>';

    const comptes = {};
    state.agendaMarkers.forEach(m => {
        const cat = (m.feature.properties.categoria || '').toLowerCase().trim();
        if (cat) comptes[cat] = (comptes[cat] || 0) + 1;
    });

    Object.entries(comptes).sort((a, b) => b[1] - a[1]).forEach(([cat, count]) => {
        const opt = document.createElement('option');
        opt.value       = cat;
        opt.textContent = `${emojiAgenda(cat)} ${capitalitzar(cat)} (${count})`;
        select.appendChild(opt);
    });

    select.value = valorActual;
}

/* =============================================================================
   SIDEBAR: CONFIGURACIÓ DE FILTRES
   ============================================================================= */
function prepararInterficieFiltres() {
    const debouncedFiltres = debounce(aplicarFiltres, 300);
    document.getElementById('inputCerca').addEventListener('input', debouncedFiltres);
    document.getElementById('selectorCategoria').addEventListener('change', aplicarFiltres);
    document.getElementById('selectorCategoriaAgenda').addEventListener('change', aplicarFiltres);
    document.getElementById('dataFiltre').addEventListener('change', aplicarFiltres);
    document.getElementById('check-patrimoni').addEventListener('change', aplicarFiltres);
    document.getElementById('check-agenda').addEventListener('change', aplicarFiltres);
    document.getElementById('btn-filtrar').addEventListener('click', aplicarFiltres);

    document.getElementById('btn-reset').addEventListener('click', () => {
        document.getElementById('inputCerca').value              = '';
        document.getElementById('selectorCategoria').value       = '';
        document.getElementById('selectorCategoriaAgenda').value = '';
        document.getElementById('dataFiltre').value              = '';
        document.getElementById('check-patrimoni').checked       = true;
        document.getElementById('check-agenda').checked          = true;
        aplicarFiltres();
    });

    document.getElementById('btn-avui').addEventListener('click', () => {
        document.getElementById('dataFiltre').value = new Date().toISOString().split('T')[0];
        aplicarFiltres();
    });

    document.getElementById('btn-back-story').addEventListener('click', exitExplorerMode);

    document.getElementById('toggle-right-panel').addEventListener('click', () => {
        document.getElementById('sidebar-right').classList.toggle('collapsed');
    });

    document.getElementById('btn-basemap-toggle').addEventListener('click', toggleBasemapWidget);
    document.querySelectorAll('.bm-opt').forEach(opt => {
        opt.addEventListener('click', () => switchBasemap(opt.dataset.bm));
    });

    map.on('click', () => {
        const panel = document.getElementById('basemap-panel');
        if (panel && !panel.classList.contains('hidden')) panel.classList.add('hidden');
    });

    document.getElementById('btn-saltar-intro').addEventListener('click', enterExplorerMode);
    document.getElementById('btn-sorpren').addEventListener('click', sortirAlatzar);
    document.getElementById('btn-genera-ruta').addEventListener('click', generaRuta);

    document.getElementById('btn-welcome-close').addEventListener('click', () => {
        document.getElementById('welcome-modal').classList.add('hidden');
        if (document.getElementById('no-show-again').checked) {
            localStorage.setItem('atlas-welcome-seen', '1');
        }
    });
}

/* =============================================================================
   DESCOBERTA ALEATÒRIA — "Sorprèn-me"
   ============================================================================= */
function sortirAlatzar() {
    // Prioritza el pool filtrat; si és buit, usa tots els markers carregats
    let pool = [
        ...state.patrimoniMarkers.filter(m => passaFiltrPatrimoni(m.feature)),
        ...state.agendaMarkers.filter(m => passaFiltrAgenda(m.feature)),
    ].filter(m => m.feature?.geometry?.coordinates);

    if (pool.length === 0) {
        pool = [...state.patrimoniMarkers, ...state.agendaMarkers]
            .filter(m => m.feature?.geometry?.coordinates);
    }
    if (pool.length === 0) {
        const el = document.getElementById('resultat-text');
        el.innerText   = '⚠️ Carrega dades primer acostant el mapa.';
        el.style.color = 'var(--accent)';
        return;
    }

    map.closePopup();
    const m         = pool[Math.floor(Math.random() * pool.length)];
    const [lng, lat] = m.feature.geometry.coordinates;
    map.flyTo([lat, lng], 16, { duration: 1.8, easeLinearity: 0.2 });
    map.once('moveend', () => setTimeout(() => m.openPopup(), 300));
}

/* =============================================================================
   RUTA CULTURAL — Generador automàtic (nearest-neighbor TSP, Turf.js)
   ============================================================================= */
function generaRuta() {
    const llista = document.getElementById('llista-propers');

    // Si no hi ha GPS, obrim el radar i demanem la geolocalització
    if (!state.ubicacioUsuari) {
        document.getElementById('sidebar-right').classList.remove('collapsed');
        llista.innerHTML = '<div class="empty-state"><i class="fa-solid fa-location-crosshairs fa-bounce"></i><p>Primer necessito el teu GPS. Clica "Què tinc a prop?"</p></div>';
        return;
    }

    // Neteja la ruta anterior
    if (rutaLayer) { map.removeLayer(rutaLayer); rutaLayer = null; }

    const tots = state.featuresGlobals.filter(f => f.geometry?.coordinates);
    if (tots.length === 0) {
        llista.innerHTML = '<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><p>No hi ha elements a la vista. Apropa el mapa i aplica filtres primer.</p></div>';
        return;
    }

    // Calcula distàncies des de la ubicació de l'usuari i agafa els 6 més propers (màx. 15 km)
    const ambDist = tots
        .map(f => ({
            feature: f,
            km: turf.distance(state.ubicacioUsuari, turf.point(f.geometry.coordinates), { units: 'kilometers' }),
        }))
        .sort((a, b) => a.km - b.km);

    const selects = ambDist.slice(0, 6).filter(x => x.km <= 15);

    if (selects.length < 2) {
        llista.innerHTML = '<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><p>Pocs elements a prop (radi 15 km). Prova en una zona amb més densitat cultural!</p></div>';
        return;
    }

    // Algorisme greedy nearest-neighbor: construeix la ruta en ordre òptim
    let currentPt  = state.ubicacioUsuari;
    let remaining  = [...selects];
    const ordered  = [];
    while (remaining.length > 0) {
        let nearestIdx = 0, nearestDist = Infinity;
        remaining.forEach((item, i) => {
            const d = turf.distance(currentPt, turf.point(item.feature.geometry.coordinates), { units: 'kilometers' });
            if (d < nearestDist) { nearestDist = d; nearestIdx = i; }
        });
        ordered.push(remaining[nearestIdx]);
        currentPt = turf.point(remaining[nearestIdx].feature.geometry.coordinates);
        remaining.splice(nearestIdx, 1);
    }

    // Dibuixa la ruta com a polilínia discontinua sobre el mapa
    const userC   = state.ubicacioUsuari.geometry.coordinates;
    const latlngs = [
        [userC[1], userC[0]],
        ...ordered.map(o => { const [lng, lat] = o.feature.geometry.coordinates; return [lat, lng]; }),
    ];
    rutaLayer = L.polyline(latlngs, {
        color: '#5B2DAB', weight: 3.5, opacity: 0.88,
        dashArray: '10 5', lineCap: 'round', lineJoin: 'round',
    }).addTo(map);
    map.fitBounds(rutaLayer.getBounds(), { padding: [60, 60] });

    // Mostra la llista de parades al panel
    llista.innerHTML = `<p style="color:var(--festa-color);font-weight:700;font-size:0.85rem;margin-bottom:8px;display:flex;align-items:center;gap:6px;"><i class="fa-solid fa-route"></i> Ruta generada · ${ordered.length} parades</p>`;

    let rutaDist = 0;
    let prevPt   = state.ubicacioUsuari;
    ordered.forEach(({ feature: f }, i) => {
        const p       = f.properties;
        const isP     = p.id_wikidata !== undefined;
        const segDist = turf.distance(prevPt, turf.point(f.geometry.coordinates), { units: 'kilometers' });
        rutaDist     += segDist;
        prevPt        = turf.point(f.geometry.coordinates);

        const emoji = isP ? emojiPatrimoni(p.categoria) : emojiAgenda(p.categoria);
        const titol = capitalitzarTitol((isP ? p.nom : p.denominacio) || 'Sense nom');
        const div   = document.createElement('div');
        div.className = 'ruta-stop';
        div.innerHTML = `
            <div class="ruta-stop-num">${i + 1}</div>
            <div>
                <div class="ruta-stop-title">${emoji} ${titol}</div>
                <div class="ruta-stop-km">+${segDist.toFixed(1)} km del punt anterior</div>
            </div>`;
        div.addEventListener('click', () => {
            const [lng, lat] = f.geometry.coordinates;
            map.flyTo([lat, lng], 16, { duration: 1.0 });
        });
        llista.appendChild(div);
    });

    const totalDiv = document.createElement('div');
    totalDiv.className = 'ruta-total';
    totalDiv.innerHTML = `<i class="fa-solid fa-flag-checkered"></i> ~${rutaDist.toFixed(1)} km totals`;
    llista.appendChild(totalDiv);

    const clearBtn = document.createElement('button');
    clearBtn.className = 'ruta-btn clear';
    clearBtn.innerHTML = '<i class="fa-solid fa-xmark"></i> Eliminar ruta';
    clearBtn.addEventListener('click', () => {
        if (rutaLayer) { map.removeLayer(rutaLayer); rutaLayer = null; }
        actualitzarRadarProximitat();
    });
    llista.appendChild(clearBtn);
}

/* =============================================================================
   RADAR DE GEOLOCALITZACIÓ (Turf.js)
   ============================================================================= */
document.getElementById('btn-geo-float').addEventListener('click', () => {
    if (!('geolocation' in navigator)) return alert('GPS no compatible amb aquest navegador.');
    document.getElementById('sidebar-right').classList.remove('collapsed');
    document.getElementById('llista-propers').innerHTML =
        '<div class="empty-state"><i class="fa-solid fa-satellite fa-spin"></i><p>Triangulant GPS...</p></div>';

    navigator.geolocation.getCurrentPosition(pos => {
        const { latitude: lat, longitude: lon } = pos.coords;
        state.ubicacioUsuari = turf.point([lon, lat]);
        if (state.markerUsuari) map.removeLayer(state.markerUsuari);
        state.markerUsuari = L.circleMarker([lat, lon], {
            radius: 8, fillColor: '#22c55e', color: '#fff', weight: 2, fillOpacity: 1,
        }).addTo(map);
        map.flyTo([lat, lon], 13, { duration: 1.5 });
        actualitzarRadarProximitat();
    }, () => {
        document.getElementById('llista-propers').innerHTML =
            '<div class="empty-state"><i class="fa-solid fa-location-crosshairs"></i><p>GPS denegat pel navegador.</p></div>';
    });
});

function actualitzarRadarProximitat() {
    if (!state.ubicacioUsuari || state.featuresGlobals.length === 0) return;
    const llista = document.getElementById('llista-propers');
    llista.innerHTML = '';

    const propers = state.featuresGlobals
        .filter(f => f.geometry?.coordinates)
        .map(f => ({
            props:  f.properties,
            coords: f.geometry.coordinates,
            km:     turf.distance(state.ubicacioUsuari, f, { units: 'kilometers' }),
        }))
        .sort((a, b) => a.km - b.km)
        .slice(0, 10);

    if (propers.length === 0) {
        llista.innerHTML = '<div class="empty-state"><i class="fa-solid fa-ban"></i><p>Cap element a prop amb els filtres actius.</p></div>';
        return;
    }

    propers.forEach(({ props: p, coords, km }) => {
        const isP   = p.id_wikidata !== undefined;
        const emoji = isP ? emojiPatrimoni(p.categoria) : emojiAgenda(p.categoria);
        const titol = isP ? p.nom : p.denominacio;
        const div   = document.createElement('div');
        div.className = 'radar-item';
        div.innerHTML = `
            <div class="radar-item-title"><span class="radar-emoji">${emoji}</span>${capitalitzarTitol(titol || 'Sense nom')}</div>
            <div class="radar-item-meta">
                <span class="radar-dist"><i class="fa-solid fa-location-arrow"></i> ${km.toFixed(1)} km</span>
                <span class="radar-type">${isP ? 'Patrimoni' : 'Agenda'}</span>
            </div>`;
        div.addEventListener('click', () => map.flyTo([coords[1], coords[0]], 16));
        llista.appendChild(div);
    });
}

/* =============================================================================
   INICIALITZACIÓ
   ============================================================================= */
window.onload = async () => {
    prepararInterficieFiltres();
    document.getElementById('llista-propers').innerHTML =
        '<div class="empty-state"><i class="fa-solid fa-cloud-arrow-down fa-bounce"></i><p>Sincronitzant PostGIS...</p></div>';
    await carregarDadesViewport();
    document.getElementById('llista-propers').innerHTML =
        '<div class="empty-state"><i class="fa-solid fa-location-dot"></i><p>Pendents de senyal GPS...</p></div>';
};
