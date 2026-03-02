// ── Auth Check ──
async function checkAuthOrRedirect() {
    try {
        const res = await fetch(`${API_BASE}/api/auth/check`, { credentials: 'include' });
        const data = await res.json();
        if (!data.authenticated) {
            log('Usuário não autenticado. Redirecionando para login...', 'error');
                // Redireciona para página de login (ajuste o caminho conforme necessário)
                window.location.href = '/pages/login.html';
        }
    } catch (e) {
        log('Erro ao verificar autenticação: ' + e.message, 'error');
        window.location.href = '/pages/login.html';
    }
}
const API_BASE = window.location.origin;
const logContainer = document.getElementById('log-container');

// Populate header/mini panel with authenticated user's name (lightweight endpoint)
async function populateUserName() {
    try {
        const r = await fetch(`${API_BASE}/api/auth/user/name`, { credentials: 'include' });
        console.debug('populateUserName: response status', r.status);
        if (!r.ok) {
            console.debug('populateUserName: non-ok response');
            return false;
        }
        const d = await r.json().catch(err => { console.debug('populateUserName: json parse failed', err); return null; });
        console.debug('populateUserName: response body', d);
        const name = (d && d.name) ? d.name : null;
        if (!name) return false;
        showUserName(name);
        return true;
    } catch (e) {
        console.debug('populateUserName: error', e);
        return false;
    }
}

function showUserName(name){
    const displayName = toTitleCase(name || 'Usuário');
    const nameEl = document.getElementById('mini-name');
    const avatar = document.getElementById('mini-avatar');
    const header = document.getElementById('header-username');
    if (nameEl) nameEl.textContent = displayName;
    if (avatar) avatar.textContent = (displayName[0]||'U').toUpperCase();
    if (header) header.textContent = displayName;
}

// Utility: convert a name to Title Case
function toTitleCase(s){
    if(!s) return s;
    return s.split(/\s+/).map(w => w ? (w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()) : '').join(' ');
}

/* ── Helpers ── */

function log(msg, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function setStatus(online) {
    const dot  = document.getElementById('status-dot');
    const text = document.getElementById('status-text');

    if (online) {
        dot.classList.remove('offline');
        text.textContent = 'Online';
    } else {
        dot.classList.add('offline');
        text.textContent = 'Offline';
    }
}

function renderInfoRows(container, data, mapping) {
    container.innerHTML = '';
    for (const [label, key] of Object.entries(mapping)) {
        const value = data[key] ?? 'N/A';
        container.innerHTML += `
            <div class="info-row">
                <span class="label">${label}</span>
                <span class="value" title="${value}">${value}</span>
            </div>
        `;
    }
}

/* ── Fetchers ── */

async function fetchData(endpoint, containerId, mapping) {
    try {
        const res  = await fetch(`${API_BASE}${endpoint}`, { credentials: 'include' });
        let data = null;
        try {
            data = await res.json();
        } catch (err) {
            log(`Erro ao interpretar resposta de ${endpoint}: ${err.message}`, 'error');
            renderInfoRows(document.getElementById(containerId), {}, mapping);
            return null;
        }
        renderInfoRows(document.getElementById(containerId), data, mapping);
        return data;
    } catch (e) {
        log(`Erro ao buscar ${endpoint}: ${e.message}`, 'error');
        renderInfoRows(document.getElementById(containerId), {}, mapping);
        return null;
    }
}

async function fetchDiskInfo() {
    try {
        const res  = await fetch(`${API_BASE}/api/info/disk`, { credentials: 'include' });
        let data = null;
        try {
            data = await res.json();
        } catch (err) {
            log(`Erro ao interpretar resposta dos discos: ${err.message}`, 'error');
            document.getElementById('disk-info').innerHTML = '<div class="info-row">Erro ao carregar discos</div>';
            return;
        }
        const container = document.getElementById('disk-info');
        container.innerHTML = '';

        for (const disk of data.disks || []) {
            const isWarning = disk.percent_used > 80;
            container.innerHTML += `
                <div style="margin-bottom: 1rem;">
                    <div class="info-row">
                        <span class="label">${disk.mount}</span>
                        <span class="value ${isWarning ? 'warning' : ''}">${disk.used_gb}GB / ${disk.total_gb}GB</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${isWarning ? 'warning' : ''}" style="width: ${disk.percent_used}%"></div>
                    </div>
                </div>
            `;
        }
    } catch (e) {
        log(`Erro ao buscar discos: ${e.message}`, 'error');
        document.getElementById('disk-info').innerHTML = '<div class="info-row">Erro ao carregar discos</div>';
    }
}

async function fetchBases() {
    try {
        const res  = await fetch(`${API_BASE}/api/global_paths`, { credentials: 'include' });
        if (!res.ok) {
            const text = await res.text().catch(() => '');
            log(`Erro ao buscar GLOBAL PATHS: HTTP ${res.status} - ${text.split('\n')[0]}`, 'error');
                document.getElementById('bases-list').innerHTML = '<div class="base-item base-status error">Erro ao carregar GLOBAL PATHS</div>';
            return;
        }
        let data = null;
        try {
            data = await res.json();
        } catch (err) {
            log(`Erro ao interpretar resposta das GLOBAL PATHS: ${err.message}`, 'error');
            document.getElementById('bases-list').innerHTML = '<div class="base-item base-status error">Erro ao carregar GLOBAL PATHS</div>';
            return;
        }
        const container = document.getElementById('bases-list');
        container.innerHTML = '';

        // Support both legacy mapping and new `entries` array returned by the
        // backend. New format: { legacy: {...}, entries: [{base, path, machine}, ...] }
        let map = {};
        if (data && Array.isArray(data.entries)) {
            for (const e of data.entries) {
                const name = e.base || '(unknown)';
                if (!map[name]) map[name] = { paths: [], machines: [] };
                if (e.path) map[name].paths.push(e.path);
                if (e.machine) map[name].machines.push(e.machine);
            }
        } else {
            // legacy response: { BASE: { path: [...], exists: bool, readable: bool }, ... }
            for (const [name, info] of Object.entries(data)) {
                map[name] = { paths: Array.isArray(info.path) ? info.path.slice() : [info.path], machines: [] };
                // keep legacy flags
                map[name].exists = info.exists;
                map[name].readable = info.readable;
            }
        }

        for (const [name, info] of Object.entries(map)) {
            const pathStr = (info.paths || []).map(p => typeof p === 'string' ? p : JSON.stringify(p)).join(', ');
            // determine simple status: if legacy flags exist use them, otherwise remote if machines present
            let status = 'unknown';
            if (info.exists === true && info.readable === true) status = 'ok';
            else if (info.exists === false || info.readable === false) status = 'error';
            else if ((info.machines || []).length > 0) status = 'remote';
            const statusText = status === 'ok' ? 'OK' : (status === 'remote' ? 'REMOTE' : 'N/A');
            container.innerHTML += `
                <div class="base-item">
                    <span>${name}</span>
                    <span class="base-path">${pathStr}</span>
                    <span class="base-status ${status}">${statusText}</span>
                </div>
            `;
        }
    } catch (e) {
        log(`Erro ao buscar GLOBAL PATHS: ${e.message}`, 'error');
        document.getElementById('bases-list').innerHTML = '<div class="base-item base-status error">Erro ao carregar GLOBAL PATHS</div>';
    }
}

/* ── Main Fetch ── */

async function fetchAllData() {
    log('Iniciando fetch de dados...', 'info');
    const start = Date.now();

    try {
        const health = await fetch(`${API_BASE}/api/health`, { credentials: 'include' });
        if (health.ok) {
            setStatus(true);
            log('Servidor respondendo OK', 'success');
        } else {
            setStatus(false);
            log('Servidor offline', 'error');
            return;
        }
    } catch {
        setStatus(false);
        log('Falha ao conectar com servidor', 'error');
        return;
    }

    // Fetch em paralelo
    await Promise.all([
        fetchData('/api/info/system', 'system-info', {
            'OS': 'os',
            'Release': 'os_release',
            'Hostname': 'hostname',
            'Arch': 'architecture',
            'Processor': 'processor'
        }),
        fetchData('/api/info/python', 'python-info', {
            'Version': 'version',
            'Implementation': 'implementation',
            'Platform': 'platform',
            'Compiler': 'compiler'
        }),
        fetchData('/api/info/network', 'network-info', {
            'Hostname': 'hostname',
            'IP Local': 'local_ip',
            'FQDN': 'fqdn'
        }),
        fetchData('/api/info/datetime', 'datetime-info', {
            'Local': 'local',
            'UTC': 'utc',
            'Timezone': 'timezone',
            'Timestamp': 'timestamp'
        }),
        fetchData('/api/info/process', 'process-info', {
            'PID': 'pid',
            'PPID': 'ppid',
            'CWD': 'cwd',
            'UID': 'uid'
        }),
        fetchDiskInfo(),
        fetchBases(),
        fetchCalender()
    ]);

    const elapsed = Date.now() - start;
    log(`Dados carregados em ${elapsed}ms`, 'success');
}

/* ── Auto-refresh datetime a cada 1s (DESATIVADO - muitas requests) ── */

// setInterval(async () => {
//     try {
//         const res  = await fetch(`${API_BASE}/api/info/datetime`);
//         const data = await res.json();
//         renderInfoRows(document.getElementById('datetime-info'), data, {
//             'Local': 'local',
//             'UTC': 'utc',
//             'Timezone': 'timezone',
//             'Timestamp': 'timestamp'
//         });
//     } catch { /* silencioso */ }
// }, 1000);

/* ── Calender ── */

function getWeekDays() {
    const days = [];
    const now = new Date();
    const monday = new Date(now);
    monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
    
    const dayNames = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
    
    for (let i = 0; i < 7; i++) {
        const d = new Date(monday);
        d.setDate(monday.getDate() + i);
        days.push({
            name: dayNames[i],
            date: d.toISOString().split('T')[0],
            day: d.getDate(),
            isToday: d.toDateString() === now.toDateString()
        });
    }
    return days;
}

function renderWeekHeader(container) {
    const days = getWeekDays();
    container.innerHTML = days.map(d => `
        <div class="calender-day ${d.isToday ? 'today' : ''}">
            <span class="day-name">${d.name}</span>
            <span class="day-number">${d.day}</span>
        </div>
    `).join('');
}

function renderEvents(container, events) {
    if (!events || events.length === 0) {
        container.innerHTML = '<div class="calender-empty">Nenhum evento esta semana</div>';
        return;
    }

    container.innerHTML = events.map(ev => {
        const title = ev.title || ev.subject || 'Sem título';
        const date  = ev.date || ev.start || '';
        const time  = ev.time || ev.start_time || '';

        return `
            <div class="calender-event">
                <div class="event-time">${time || '─'}</div>
                <div class="event-info">
                    <span class="event-title">${title}</span>
                    <span class="event-date">${date}</span>
                </div>
            </div>
        `;
    }).join('');
}

async function fetchCalender() {
    const weekContainer = document.getElementById('calender-week');
    const eventsContainer = document.getElementById('calender-events');
    
    renderWeekHeader(weekContainer);
    
    try {
        const res = await fetch(`${API_BASE}/calender/events`, { credentials: 'include' });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            eventsContainer.innerHTML = `<div class="calender-empty calender-error">${err.detail || 'Erro ao buscar eventos'}</div>`;
            log(`Calender: ${err.detail || res.status}`, 'error');
            return;
        }
        const data = await res.json();
        renderEvents(eventsContainer, data.events || []);
        log(`Calender: ${data.count || 0} eventos carregados`, 'success');
    } catch (e) {
        eventsContainer.innerHTML = '<div class="calender-empty calender-error">Falha ao conectar com OutlookFusion</div>';
        log(`Calender erro: ${e.message}`, 'error');
    }
}

/* ── Create Project ── */

document.getElementById('create-project-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const name = document.getElementById('proj-name').value.trim();
    const lang = document.getElementById('proj-lang').value;
    const path = document.getElementById('proj-path').value.trim();
    const btn  = document.getElementById('create-btn');
    const result = document.getElementById('project-result');

    if (!name) return;

    btn.disabled = true;
    btn.textContent = 'Criando...';
    result.style.display = 'block';
    result.className = 'project-result loading';
    result.textContent = `Criando projeto "${name}" (${lang})...`;
    log(`Criando projeto: ${name} [${lang}]`, 'info');

    try {
        const params = new URLSearchParams({ name, language: lang });
        if (path) params.append('path', path);

        const res  = await fetch(`${API_BASE}/create_project?${params}`);
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || `HTTP ${res.status}`);
        }

        if (data.returncode === 0) {
            result.className = 'project-result success';
            result.textContent = data.stdout || 'Projeto criado com sucesso!';
            log(`Projeto "${name}" criado com sucesso`, 'success');
        } else {
            result.className = 'project-result error';
            result.textContent = data.stderr || data.stdout || 'Erro ao criar projeto';
            log(`Erro ao criar "${name}": returncode=${data.returncode}`, 'error');
        }
    } catch (err) {
        result.className = 'project-result error';
        result.textContent = `Erro: ${err.message}`;
        log(`Falha ao criar projeto: ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Criar';
    }
});

/* ── Endpoints Dynamic Render ── */
async function renderEndpoints() {
    const container = document.getElementById('endpoints-list');
    if (!container) return;
    container.innerHTML = '<span>Carregando endpoints...</span>';
    try {
        const res = await fetch('/info');
        const data = await res.json();
        if (!data.routes) {
            container.innerHTML = '<span>Nenhum endpoint encontrado.</span>';
            return;
        }
        // Agrupa endpoints por grupo, cada grupo em um bloco
        let html = '';
        for (const [group, routes] of Object.entries(data.routes)) {
            html += `<div style="width:100%;margin-top:0.5em;"><b style="color:var(--accent-blue);text-transform:uppercase;font-size:0.8em;">${group}</b></div>`;
            html += '<div class="endpoints-list" style="margin-bottom:0.7em">';
            for (const r of routes) {
                html += `<span class="endpoint-tag">${r}</span>`;
            }
            html += '</div>';
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<span>Falha ao carregar endpoints.</span>';
    }
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
    checkAuthOrRedirect().then(async () => {
        log('MCP Dashboard iniciado', 'info');

        // Tenta popular o nome do usuário imediatamente para o header/global
        try {
            const ok = await populateUserName();
            if (!ok) {
                // fallback: checa sessão mais pesada e define um nome genérico se necessário
                try {
                    const r = await fetch(`${API_BASE}/api/auth/check`, { credentials: 'include' });
                    const d = await r.json().catch(() => ({}));
                    if (d && d.authenticated) {
                        const name = d.name || 'Usuário';
                        showUserName(name);
                    } else {
                        showUserName('Convidado');
                    }
                } catch {
                    showUserName('Convidado');
                }
            }
        } catch (e) {
            showUserName('Convidado');
        }

        fetchAllData();
        renderEndpoints();
        initMiniPanel();
    });
});

/* ── Mini panel init ── */
function initMiniPanel(){
    const panel = document.getElementById('mini-panel');
    const toggle = document.getElementById('mini-toggle');
    const autohide = document.getElementById('mini-autohide');
    const nameEl = document.getElementById('mini-name');
    const avatar = document.getElementById('mini-avatar');

    // Load saved autohide preference
    const saved = localStorage.getItem('miniPanelAutoHide');
    if(saved === 'false'){
        panel.classList.remove('auto-hide');
        autohide.checked = false;
    } else {
        panel.classList.add('auto-hide');
        autohide.checked = true;
    }

    if(toggle){
        toggle.addEventListener('click', ()=>{
            panel.classList.toggle('open');
        });
    }

    autohide.addEventListener('change', (e)=>{
        const want = e.target.checked;
        if(want){ panel.classList.add('auto-hide'); localStorage.setItem('miniPanelAutoHide','true'); }
        else { panel.classList.remove('auto-hide'); localStorage.setItem('miniPanelAutoHide','false'); }
    });

    // populate account name if available (prefer lightweight username endpoint)
    populateUserName().then(ok => {
        if (!ok) {
            // fallback: try heavier auth check and use any name present, otherwise set guest
            fetch(`${API_BASE}/api/auth/check`, { credentials: 'include' })
                .then(r => r.json().catch(()=>({})))
                .then(d => {
                    if(d && d.authenticated){
                        const name = d.name || 'Usuário';
                        const displayName = toTitleCase(name);
                        nameEl.textContent = displayName;
                        avatar.textContent = (displayName[0]||'U').toUpperCase();
                        const header = document.getElementById('header-username'); if(header) header.textContent = displayName;
                    } else {
                        nameEl.textContent = 'Convidado';
                        avatar.textContent = 'G';
                        const header = document.getElementById('header-username'); if(header) header.textContent = 'Convidado';
                    }
                }).catch(()=>{ nameEl.textContent='Convidado'; avatar.textContent='G'; });
        }
    });
}
