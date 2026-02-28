// ══════════════════════════════════════════════════════════
// Info de Máquinas (MAC Address etc)
// ══════════════════════════════════════════════════════════

async function showMachinesInfo() {
    try {
        const res = await fetch(`${API}/api/machines`);
        if (!res.ok) {
            const txt = await res.text().catch(() => '');
            toast('Erro ao buscar máquinas: ' + (txt || `HTTP ${res.status}`), 'error');
            return;
        }
        const data = await res.json();
        const arr = Array.isArray(data) ? data : (Array.isArray(data?.machines) ? data.machines : null);
        if (!arr) {
            toast('Erro ao buscar máquinas', 'error');
            return;
        }
        let html = '<h3>Máquinas Detectadas</h3>';
        html += '<table class="fm-machines-table"><tr><th>MAC</th><th>Nome</th><th>Interface</th><th>Vendor</th><th>Random?</th></tr>';
        for (const m of data) {
            html += `<tr>
                <td>${m.address}</td>
                <td>${m.name || ''}</td>
                <td>${m.interface || ''}</td>
                <td>${m.vendor || ''}</td>
                <td>${m.is_randomized ? 'Sim' : 'Não'}</td>
            </tr>`;
        }
        html += '</table>';
        showModalContent('modal-machines', html);
    } catch (e) {
        toast('Erro ao buscar máquinas: ' + e.message, 'error');
    }
}

function showModalContent(id, html) {
    let modal = document.getElementById(id);
    if (!modal) {
        // Cria modal se não existir
        modal = document.createElement('div');
        modal.className = 'fm-modal-overlay';
        modal.id = id;
        modal.style.display = 'flex';
        modal.innerHTML = `<div class="fm-modal fm-modal-lg"><div class="fm-modal-header"><h3>Info</h3><button class="fm-modal-close" onclick="closeModal('${id}')">✕</button></div><div class="fm-modal-body" id="${id}-body"></div></div>`;
        document.body.appendChild(modal);
    } else {
        modal.style.display = 'flex';
    }
    document.getElementById(`${id}-body`).innerHTML = html;
}
const API = window.location.origin;

/* ══════════════════════════════════════════════════════════
   Estado Global
   ══════════════════════════════════════════════════════════ */

let currentBase = '';       // base selecionada (vazio = modo path direto)
let currentPath = '';       // subpath dentro da base
let directPath = '';        // caminho absoluto no OS (modo direto)
let browseMode = 'base';   // 'base' | 'direct'
let pathHistory = [];
let currentView = 'list';
let pendingUploadFiles = [];
let actionTarget = null;    // { path, type, name }

/* ══════════════════════════════════════════════════════════
   Inicialização
   ══════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const health = await fetch(`${API}/api/health`);
        if (health.ok) {
            setOnline(true);
        } else {
            setOnline(false);
            return;
        }
    } catch {
        setOnline(false);
        return;
    }

    await Promise.all([
        loadBases(),
        loadFilesystem()
    ]);
});

function setOnline(ok) {
    const dot  = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    if (ok) { dot.classList.remove('offline'); text.textContent = 'Online'; }
    else    { dot.classList.add('offline');    text.textContent = 'Offline'; }
}

/* ══════════════════════════════════════════════════════════
   Sidebar - Bases
   ══════════════════════════════════════════════════════════ */

async function loadBases() {
    try {
        const res = await fetch(`${API}/api/global_paths`);
            if (!res.ok) {
                const txt = await res.text().catch(() => '');
                toast('Erro ao carregar GLOBAL PATHS: ' + (txt || `HTTP ${res.status}`), 'error');
            return;
        }
        let data = null;
        try {
              data = await res.json();
        } catch (err) {
              toast('Erro ao interpretar resposta das GLOBAL PATHS: ' + err.message, 'error');
            return;
        }
        const container = document.getElementById('fm-bases');
        container.innerHTML = '';

        for (const [name, info] of Object.entries(data)) {
            // info.path pode ser uma lista (nova estrutura)
            let pathStr = '';
            if (Array.isArray(info.path)) {
                pathStr = info.path.map(p => typeof p === 'string' ? p : JSON.stringify(p)).join(', ');
            } else {
                pathStr = info.path;
            }
            const ok = info.exists && info.readable;
            container.innerHTML += `
                <div class="fm-base-item ${currentBase === name ? 'active' : ''} ${!ok ? 'disabled' : ''}" 
                     onclick="${ok ? `selectBase('${name}')` : ''}">
                    <span class="fm-base-icon">${ok ? '📂' : '⚠'}</span>
                    <div class="fm-base-info">
                        <span class="fm-base-name">${name}</span>
                        <span class="fm-base-path">${pathStr}</span>
                    </div>
                </div>
            `;
        }
    } catch (e) {
        toast(`Erro ao carregar bases: ${e.message}`, 'error');
    }
}

async function selectBase(name) {
    browseMode = 'base';
    currentBase = name;
    currentPath = '';
    directPath = '';
    pathHistory = [];
    
    document.getElementById('fm-path-input').value = '';
    document.querySelectorAll('.fm-base-item').forEach(el => el.classList.remove('active'));
    event.currentTarget?.classList.add('active');
    document.getElementById('btn-back').disabled = true;
    
    await Promise.all([
        browseBase(''),
        loadBaseStats()
    ]);
}

async function loadBaseStats() {
    if (!currentBase) return;
    try {
        const res = await fetch(`${API}/files/stats/${currentBase}`);
        const data = await res.json();
        const el = document.getElementById('fm-stats');
        
        if (data.error) {
            el.innerHTML = `<span class="fm-hint">${data.error}</span>`;
            return;
        }
        
        el.innerHTML = `
            <div class="fm-stat-row"><span>Arquivos</span><span>${data.total_files}</span></div>
            <div class="fm-stat-row"><span>Diretórios</span><span>${data.total_dirs}</span></div>
            <div class="fm-stat-row"><span>Markdown</span><span>${data.md_files}</span></div>
            <div class="fm-stat-row"><span>Python</span><span>${data.py_files}</span></div>
            <div class="fm-stat-row"><span>Tamanho</span><span>${data.total_size_mb} MB</span></div>
        `;
    } catch (e) {
        toast(`Erro stats: ${e.message}`, 'error');
    }
}

/* ══════════════════════════════════════════════════════════
   Sidebar - Filesystem Info
   ══════════════════════════════════════════════════════════ */

async function loadFilesystem() {
    try {
        const res = await fetch(`${API}/files/filesystem`);
        const data = await res.json();

        const fsEl = document.getElementById('fm-filesystem');
        fsEl.innerHTML = (data.partitions || []).map(p => {
            const warn = p.percent_used > 80;
            return `
                <div class="fm-partition">
                    <div class="fm-partition-header">
                        <span>${p.mountpoint}</span>
                        <span class="${warn ? 'fm-warn' : ''}">${p.percent_used}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${warn ? 'warning' : ''}" style="width:${p.percent_used}%"></div>
                    </div>
                    <div class="fm-partition-detail">
                        <span>${p.fstype}</span>
                        <span>${p.used_human} / ${p.total_human}</span>
                    </div>
                </div>
            `;
        }).join('');

        if (data.memory) {
            const m = data.memory;
            const mWarn = m.percent_used > 80;
            document.getElementById('fm-memory').innerHTML = `
                <div class="fm-partition">
                    <div class="fm-partition-header">
                        <span>RAM</span>
                        <span class="${mWarn ? 'fm-warn' : ''}">${m.percent_used}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${mWarn ? 'warning' : ''}" style="width:${m.percent_used}%"></div>
                    </div>
                    <div class="fm-partition-detail">
                        <span>${m.used_gb} GB / ${m.total_gb} GB</span>
                    </div>
                </div>
            `;
        }

        if (data.disk_io) {
            const io = data.disk_io;
            document.getElementById('fm-diskio').innerHTML = `
                <div class="fm-stat-row"><span>Read</span><span>${io.read_mb} MB (${io.read_count} ops)</span></div>
                <div class="fm-stat-row"><span>Write</span><span>${io.write_mb} MB (${io.write_count} ops)</span></div>
            `;
        }
    } catch (e) {
        toast(`Erro filesystem: ${e.message}`, 'error');
    }
}

// Obtém o home do usuário autenticado e navega até ele
async function getMyHome() {
    try {
        const res = await fetch(`${API}/api/files/get_home_user`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!res.ok) {
              const err = await res.json().catch(() => ({}));
              toast(err.detail || 'Erro ao obter home do usuário', 'error');
            return;
        }

        const data = await res.json();
        if (data && data.path) {
            browseDirect(data.path);
            toast('Abrindo seu diretório home', 'success');
        } else {
            toast('Caminho do home não retornado', 'error');
        }
    } catch (e) {
        console.error('getMyHome error', e);
        toast('Erro ao conectar com o servidor', 'error');
    }
}

/* ══════════════════════════════════════════════════════════
   Navegação por Path Direto (sem base)
   ══════════════════════════════════════════════════════════ */

function goToPath() {
    const input = document.getElementById('fm-path-input').value.trim();
    if (!input) { toast('Digite um caminho', 'error'); return; }
    
    browseMode = 'direct';
    currentBase = '';
    currentPath = '';
    pathHistory = [];
    
    document.querySelectorAll('.fm-base-item').forEach(el => el.classList.remove('active'));
    document.getElementById('btn-back').disabled = true;
    document.getElementById('fm-stats').innerHTML = '<span class="fm-hint">Modo path direto</span>';
    
    browseDirect(input);
}

async function browseDirect(absPath) {
    if (directPath && directPath !== absPath) {
        pathHistory.push(directPath);
        document.getElementById('btn-back').disabled = false;
    }
    directPath = absPath;
    
    document.getElementById('fm-path-input').value = absPath;
    
    try {
        const params = new URLSearchParams({ path: absPath });
        const res = await fetch(`${API}/files/browse-path?${params}`);
        const data = await res.json();
        
        if (data.detail) {
            toast(`Erro: ${data.detail}`, 'error');
            return;
        }
        
        renderBreadcrumbDirect(absPath);
        renderBrowser(data.items);
        renderSummary(data.summary);
    } catch (e) {
        toast(`Erro ao navegar: ${e.message}`, 'error');
    }
}

async function browseDirectRefresh(absPath) {
    directPath = absPath;
    document.getElementById('fm-path-input').value = absPath;
    
    try {
        const params = new URLSearchParams({ path: absPath });
        const res = await fetch(`${API}/files/browse-path?${params}`);
        const data = await res.json();
        if (data.detail) return;
        
        renderBreadcrumbDirect(absPath);
        renderBrowser(data.items);
        renderSummary(data.summary);
    } catch {}
}

/* ══════════════════════════════════════════════════════════
   Navegação por Base
   ══════════════════════════════════════════════════════════ */

async function browseBase(path = '') {
    if (!currentBase) { toast('Selecione uma base', 'error'); return; }
        if (!currentBase) { toast('Selecione um GLOBAL PATH', 'error'); return; }
        if (!currentBase) { toast('Selecione um GLOBAL PATH', 'error'); return; }
    
    if (currentPath !== path) {
        pathHistory.push(currentPath);
        document.getElementById('btn-back').disabled = false;
    }
    currentPath = path;
    
    try {
        const params = new URLSearchParams();
        if (path) params.append('path', path);
        
        const res = await fetch(`${API}/files/browse/${currentBase}?${params}`);
        const data = await res.json();
        
        if (data.error) {
            toast(`Erro: ${data.error}`, 'error');
            return;
        }
        
        renderBreadcrumbBase(data.current_path);
        renderBrowser(data.items);
        renderSummary(data.summary);
    } catch (e) {
        toast(`Erro ao navegar: ${e.message}`, 'error');
    }
}

async function browseBaseRefresh(path) {
    if (!currentBase) return;
    currentPath = path;
    
    try {
        const params = new URLSearchParams();
        if (path) params.append('path', path);
        
        const res = await fetch(`${API}/files/browse/${currentBase}?${params}`);
        const data = await res.json();
        if (data.error) return;
        
        renderBreadcrumbBase(data.current_path);
        renderBrowser(data.items);
        renderSummary(data.summary);
    } catch {}
}

/* ══════════════════════════════════════════════════════════
   Navegação Unificada (dispatch por modo)
   ══════════════════════════════════════════════════════════ */

function goBack() {
    if (pathHistory.length === 0) return;
    const prev = pathHistory.pop();
    
    if (pathHistory.length === 0) {
        document.getElementById('btn-back').disabled = true;
    }
    
    if (browseMode === 'direct') {
        browseDirectRefresh(prev);
    } else {
        currentPath = prev;
        browseBaseRefresh(prev);
    }
}

function goHome() {
    if (browseMode === 'direct') {
        browseDirect('/');
    } else if (currentBase) {
        browseBase('');
    }
}

function refreshCurrent() {
    if (browseMode === 'direct' && directPath) {
        browseDirectRefresh(directPath);
    } else if (currentBase) {
        browseBaseRefresh(currentPath);
    }
    loadFilesystem();
    if (currentBase) loadBaseStats();
    toast('Atualizado', 'success');
}

function handleDblClick(path, type, name) {
    if (type === 'dir') {
        if (browseMode === 'direct') {
            browseDirect(path);
        } else {
            browseBase(path);
        }
    } else {
        previewFile(path, name);
    }
}

/* ══════════════════════════════════════════════════════════
   Breadcrumb
   ══════════════════════════════════════════════════════════ */

function renderBreadcrumbBase(current) {
    const el = document.getElementById('fm-breadcrumb');
    const parts = current.split('/').filter(p => p && p !== '/');
    
    let html = `<span class="fm-crumb clickable" onclick="browseBase('')">${currentBase}</span>`;
    
    let accumulated = '';
    for (const part of parts) {
        accumulated += (accumulated ? '/' : '') + part;
        const pathVal = accumulated;
        html += `<span class="fm-crumb-sep">/</span>
                 <span class="fm-crumb clickable" onclick="browseBase('${pathVal}')">${part}</span>`;
    }
    
    el.innerHTML = html;
}

function renderBreadcrumbDirect(absPath) {
    const el = document.getElementById('fm-breadcrumb');
    const parts = absPath.split('/').filter(p => p);
    
    let html = `<span class="fm-crumb clickable" onclick="browseDirect('/')">/</span>`;
    
    let accumulated = '';
    for (const part of parts) {
        accumulated += '/' + part;
        const pathVal = accumulated;
        html += `<span class="fm-crumb-sep">/</span>
                 <span class="fm-crumb clickable" onclick="browseDirect('${escapeAttr(pathVal)}')">${part}</span>`;
    }
    
    el.innerHTML = html;
}

function renderSummary(summary) {
    if (!summary) return;
    document.getElementById('fm-dir-summary').textContent = 
        `${summary.dirs} pasta${summary.dirs !== 1 ? 's' : ''}, ${summary.files} arquivo${summary.files !== 1 ? 's' : ''} — ${summary.total_size_human}`;
}

/* ══════════════════════════════════════════════════════════
   Renderizar Arquivos
   ══════════════════════════════════════════════════════════ */

const ICONS = {
    dir: '📁', code: '💻', web: '🌐', doc: '📝', data: '📊',
    img: '🖼', audio: '🎵', video: '🎬', archive: '📦', config: '⚙', other: '📄'
};

function renderBrowser(items) {
    const browser = document.getElementById('fm-browser');
    
    if (!items || items.length === 0) {
        browser.innerHTML = '<div class="fm-empty">Diretório vazio</div>';
        browser.className = 'fm-browser';
        return;
    }
    
    const dirs = items.filter(i => i.type === 'dir');
    const files = items.filter(i => i.type === 'file');
    const all = [...dirs, ...files];
    
    browser.className = `fm-browser fm-view-${currentView}`;
    
    if (currentView === 'grid') {
        browser.innerHTML = all.map(item => renderGridItem(item)).join('');
    } else {
        browser.innerHTML = all.map(item => renderListItem(item)).join('');
    }
}

function renderListItem(item) {
    const icon = item.type === 'dir' ? ICONS.dir : (ICONS[item.category] || ICONS.other);
    const escapedPath = escapeAttr(item.path);
    const escapedName = escapeAttr(item.name);
    
    return `
        <div class="fm-list-item" ondblclick="handleDblClick('${escapedPath}', '${item.type}', '${escapedName}')">
            <span class="fm-item-icon">${icon}</span>
            <span class="fm-item-name" title="${item.path}">${item.name}</span>
            <span class="fm-item-ext">${item.ext || ''}</span>
            <span class="fm-item-size">${item.size_human || '—'}</span>
            <span class="fm-item-date">${item.modified}</span>
            <span class="fm-item-perms">${item.permissions || ''}</span>
            <div class="fm-item-actions">
                ${item.type === 'file' ? `<button class="fm-action-btn" onclick="downloadFile('${escapedPath}')" title="Download">⬇</button>` : ''}
                <button class="fm-action-btn" onclick="showRenameModal('${escapedPath}', '${escapedName}')" title="Renomear">✏</button>
                <button class="fm-action-btn danger" onclick="showDeleteModal('${escapedPath}', '${item.type}', '${escapedName}')" title="Deletar">🗑</button>
            </div>
        </div>
    `;
}

function renderGridItem(item) {
    const icon = item.type === 'dir' ? ICONS.dir : (ICONS[item.category] || ICONS.other);
    const escapedPath = escapeAttr(item.path);
    const escapedName = escapeAttr(item.name);
    
    return `
        <div class="fm-grid-item" ondblclick="handleDblClick('${escapedPath}', '${item.type}', '${escapedName}')">
            <span class="fm-grid-icon">${icon}</span>
            <span class="fm-grid-name" title="${item.path}">${item.name}</span>
            <span class="fm-grid-meta">${item.size_human || ''}</span>
            <div class="fm-grid-actions">
                ${item.type === 'file' ? `<button class="fm-action-btn" onclick="event.stopPropagation(); downloadFile('${escapedPath}')">⬇</button>` : ''}
                <button class="fm-action-btn danger" onclick="event.stopPropagation(); showDeleteModal('${escapedPath}', '${item.type}', '${escapedName}')">🗑</button>
            </div>
        </div>
    `;
}

function setView(view) {
    currentView = view;
    document.getElementById('btn-view-list').classList.toggle('active', view === 'list');
    document.getElementById('btn-view-grid').classList.toggle('active', view === 'grid');
    refreshCurrent();
}

/* ══════════════════════════════════════════════════════════
   Busca Avançada (funciona em ambos os modos)
   ══════════════════════════════════════════════════════════ */

async function executeSearch() {
    const query   = document.getElementById('fm-search-input').value.trim();
    const ext     = document.getElementById('fm-search-ext').value;
    const cat     = document.getElementById('fm-search-cat').value;
    const sort    = document.getElementById('fm-search-sort').value;
    const content = document.getElementById('fm-search-content-check').checked;
    
    if (!query && !ext && !cat) {
        toast('Digite algo para buscar ou selecione um filtro', 'error');
        return;
    }
    
    let url;
    
    if (browseMode === 'direct' && directPath) {
        const params = new URLSearchParams({ path: directPath });
        if (query) params.append('query', query);
        if (ext)   params.append('ext', ext);
        if (cat)   params.append('category', cat);
        if (sort)  params.append('sort', sort);
        if (content && query) params.append('content', query);
        params.append('limit', '100');
        url = `${API}/files/search-path?${params}`;
    } else if (currentBase) {
        const params = new URLSearchParams();
        if (query) params.append('query', query);
        if (ext)   params.append('ext', ext);
        if (cat)   params.append('category', cat);
        if (sort)  params.append('sort', sort);
        if (content && query) params.append('content', query);
        params.append('limit', '100');
        url = `${API}/files/search/${currentBase}?${params}`;
    } else {
        toast('Selecione uma base ou digite um path', 'error');
        return;
    }
    
    try {
        const res = await fetch(url);
        const data = await res.json();
        
        if (data.error || data.detail) {
            toast(data.error || data.detail, 'error');
            return;
        }
        
        renderSearchResults(data);
        toast(`${data.count} resultado(s) encontrado(s)`, 'success');
    } catch (e) {
        toast(`Erro na busca: ${e.message}`, 'error');
    }
}

function renderSearchResults(data) {
    const browser = document.getElementById('fm-browser');
    browser.className = `fm-browser fm-view-${currentView}`;
    
    if (!data.matches || data.matches.length === 0) {
        browser.innerHTML = '<div class="fm-empty">Nenhum resultado encontrado</div>';
        document.getElementById('fm-dir-summary').textContent = '0 resultados';
        return;
    }
    
    document.getElementById('fm-dir-summary').textContent = `${data.count} resultado(s) encontrado(s)`;
    
    const items = data.matches.map(m => ({
        name: m.name,
        path: m.path,
        type: 'file',
        ext: m.ext,
        category: m.category,
        size_human: m.size_human,
        size_bytes: m.size_bytes,
        modified: m.modified,
        permissions: ''
    }));
    
    if (currentView === 'grid') {
        browser.innerHTML = items.map(item => renderGridItem(item)).join('');
    } else {
        browser.innerHTML = items.map(item => renderListItem(item)).join('');
    }
}

function clearSearch() {
    document.getElementById('fm-search-input').value = '';
    document.getElementById('fm-search-ext').value = '';
    document.getElementById('fm-search-cat').value = '';
    document.getElementById('fm-search-sort').value = 'name';
    document.getElementById('fm-search-content-check').checked = false;
    refreshCurrent();
}

/* ══════════════════════════════════════════════════════════
   File Preview (ambos os modos)
   ══════════════════════════════════════════════════════════ */

async function previewFile(path, name) {
    let url;
    if (browseMode === 'direct') {
        url = `${API}/files/read-path?path=${encodeURIComponent(path)}`;
    } else {
        url = `${API}/files/read/${currentBase}?path=${encodeURIComponent(path)}`;
    }
    
    try {
        const res = await fetch(url);
        const data = await res.json();
        
        if (data.error || data.detail) {
            toast(`Erro: ${data.error || data.detail}`, 'error');
            return;
        }
        
        document.getElementById('preview-title').textContent = name;
        document.getElementById('preview-info').innerHTML = `
            <span>Caminho: ${data.path}</span>
            <span>Tamanho: ${data.size_human || data.size_bytes + ' bytes'}</span>
        `;
        
        const content = data.content || '';
        document.getElementById('preview-content').textContent = 
            content.length > 5000 ? content.substring(0, 5000) + '\n\n... (truncado — 5KB máx)' : content;
        
        actionTarget = { path, type: 'file', name };
        showModal('modal-preview');
    } catch (e) {
        toast(`Erro ao ler: ${e.message}`, 'error');
    }
}

function downloadCurrent() {
    if (actionTarget && actionTarget.type === 'file') {
        downloadFile(actionTarget.path);
    }
}

/* ══════════════════════════════════════════════════════════
   Download (ambos os modos)
   ══════════════════════════════════════════════════════════ */

function downloadFile(path) {
    let url;
    if (browseMode === 'direct') {
        url = `${API}/files/download-path?path=${encodeURIComponent(path)}`;
    } else {
        url = `${API}/files/download/${currentBase}?path=${encodeURIComponent(path)}`;
    }
    window.open(url, '_blank');
    toast(`Download: ${path.split('/').pop()}`, 'success');
}

/* ══════════════════════════════════════════════════════════
   Upload (ambos os modos)
   ══════════════════════════════════════════════════════════ */

function showUploadModal() {
    if (!currentBase && browseMode !== 'direct') { toast('Selecione uma base ou digite um path', 'error'); return; }
    pendingUploadFiles = [];
    document.getElementById('upload-file-list').innerHTML = '';
    document.getElementById('upload-progress').innerHTML = '';
    document.getElementById('upload-input').value = '';
    document.getElementById('btn-upload-confirm').disabled = true;
    showModal('modal-upload');
}

function handleDragOver(e)  { e.preventDefault(); e.currentTarget.classList.add('dragover'); }
function handleDragLeave(e) { e.currentTarget.classList.remove('dragover'); }

function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    addPendingFiles(Array.from(e.dataTransfer.files));
}

function handleFileSelect(e) { addPendingFiles(Array.from(e.target.files)); }

function addPendingFiles(files) {
    pendingUploadFiles = [...pendingUploadFiles, ...files];
    renderPendingFiles();
}

function removePendingFile(index) {
    pendingUploadFiles.splice(index, 1);
    renderPendingFiles();
}

function renderPendingFiles() {
    const list = document.getElementById('upload-file-list');
    document.getElementById('btn-upload-confirm').disabled = pendingUploadFiles.length === 0;
    
    list.innerHTML = pendingUploadFiles.map((f, i) => `
        <div class="fm-upload-file-item">
            <span class="fm-upload-file-name">${f.name}</span>
            <span class="fm-upload-file-size">${formatBytes(f.size)}</span>
            <button class="fm-action-btn danger" onclick="removePendingFile(${i})">✕</button>
        </div>
    `).join('');
}

async function confirmUpload() {
    if (pendingUploadFiles.length === 0) return;
    
    const progress = document.getElementById('upload-progress');
    const btn = document.getElementById('btn-upload-confirm');
    btn.disabled = true;
    btn.textContent = 'Enviando...';
    
    let success = 0, fail = 0;
    
    for (let i = 0; i < pendingUploadFiles.length; i++) {
        const file = pendingUploadFiles[i];
        progress.innerHTML = `Enviando ${i + 1}/${pendingUploadFiles.length}: ${file.name}...`;
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            let url;
            if (browseMode === 'direct') {
                const params = new URLSearchParams({ path: directPath });
                url = `${API}/files/upload-path?${params}`;
            } else {
                const params = new URLSearchParams();
                if (currentPath) params.append('path', currentPath);
                url = `${API}/files/upload/${currentBase}?${params}`;
            }
            
            const res = await fetch(url, { method: 'POST', body: formData });
            
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${res.status}`);
            }
            
            success++;
        } catch (e) {
            fail++;
            progress.innerHTML += `<br><span class="fm-warn">✗ ${file.name}: ${e.message}</span>`;
        }
    }
    
    progress.innerHTML = `<br>✓ ${success} enviado(s)${fail > 0 ? `, ✗ ${fail} falhou` : ''}`;
    toast(`Upload: ${success} sucesso, ${fail} falha(s)`, fail > 0 ? 'error' : 'success');
    
    btn.textContent = 'Enviar';
    btn.disabled = false;
    
    setTimeout(() => {
        closeModal('modal-upload');
        refreshCurrent();
    }, 1500);
}

/* ══════════════════════════════════════════════════════════
   New Folder (ambos os modos)
   ══════════════════════════════════════════════════════════ */

function showNewFolderModal() {
    if (!currentBase && browseMode !== 'direct') { toast('Selecione uma base ou digite um path', 'error'); return; }
    document.getElementById('newfolder-name').value = '';
    showModal('modal-newfolder');
    setTimeout(() => document.getElementById('newfolder-name').focus(), 100);
}

async function confirmNewFolder() {
    const name = document.getElementById('newfolder-name').value.trim();
    if (!name) { toast('Nome obrigatório', 'error'); return; }
    
    try {
        let url;
        if (browseMode === 'direct') {
            const params = new URLSearchParams({ path: directPath, name });
            url = `${API}/files/create-folder-path?${params}`;
        } else {
            const params = new URLSearchParams({ path: currentPath, name });
            url = `${API}/files/create-folder/${currentBase}?${params}`;
        }
        
        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || 'Erro');
        
        toast(`Pasta "${name}" criada`, 'success');
        closeModal('modal-newfolder');
        refreshCurrent();
    } catch (e) {
        toast(`Erro: ${e.message}`, 'error');
    }
}

/* ══════════════════════════════════════════════════════════
   Rename (ambos os modos)
   ══════════════════════════════════════════════════════════ */

function showRenameModal(path, name) {
    actionTarget = { path, name };
    document.getElementById('rename-input').value = name;
    showModal('modal-rename');
    setTimeout(() => {
        const input = document.getElementById('rename-input');
        input.focus();
        input.select();
    }, 100);
}

async function confirmRename() {
    const newName = document.getElementById('rename-input').value.trim();
    if (!newName || !actionTarget) return;
    
    try {
        let url;
        if (browseMode === 'direct') {
            const params = new URLSearchParams({ path: actionTarget.path, new_name: newName });
            url = `${API}/files/rename-path?${params}`;
        } else {
            const params = new URLSearchParams({ path: actionTarget.path, new_name: newName });
            url = `${API}/files/rename/${currentBase}?${params}`;
        }
        
        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || 'Erro');
        
        toast(`Renomeado: ${actionTarget.name} → ${newName}`, 'success');
        closeModal('modal-rename');
        refreshCurrent();
    } catch (e) {
        toast(`Erro: ${e.message}`, 'error');
    }
}

/* ══════════════════════════════════════════════════════════
   Delete (ambos os modos)
   ══════════════════════════════════════════════════════════ */

function showDeleteModal(path, type, name) {
    actionTarget = { path, type, name };
    document.getElementById('delete-msg').innerHTML = `
        Deletar <strong>${type === 'dir' ? 'pasta' : 'arquivo'}</strong>: <code>${name}</code>?
    `;
    showModal('modal-delete');
}

async function confirmDelete() {
    if (!actionTarget) return;
    
    try {
        let url;
        if (browseMode === 'direct') {
            url = `${API}/files/delete-path?path=${encodeURIComponent(actionTarget.path)}`;
        } else {
            url = `${API}/files/delete/${currentBase}?path=${encodeURIComponent(actionTarget.path)}`;
        }
        
        const res = await fetch(url, { method: 'DELETE' });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || 'Erro');
        
        toast(`Deletado: ${actionTarget.name}`, 'success');
        closeModal('modal-delete');
        refreshCurrent();
    } catch (e) {
        toast(`Erro: ${e.message}`, 'error');
    }
}

/* ══════════════════════════════════════════════════════════
   Modals
   ══════════════════════════════════════════════════════════ */

function showModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('fm-modal-overlay')) {
        e.target.style.display = 'none';
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.fm-modal-overlay').forEach(m => m.style.display = 'none');
    }
});

/* ══════════════════════════════════════════════════════════
   Toast Notifications
   ══════════════════════════════════════════════════════════ */

function toast(msg, type = 'info') {
    const container = document.getElementById('fm-toasts');
    const el = document.createElement('div');
    el.className = `fm-toast fm-toast-${type}`;
    el.textContent = msg;
    container.appendChild(el);
    
    setTimeout(() => el.classList.add('show'), 10);
    setTimeout(() => {
        el.classList.remove('show');
        setTimeout(() => el.remove(), 300);
    }, 3000);
}

/* ══════════════════════════════════════════════════════════
   Helpers
   ══════════════════════════════════════════════════════════ */

function escapeAttr(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024**2) return `${(bytes/1024).toFixed(1)} KB`;
    if (bytes < 1024**3) return `${(bytes/(1024**2)).toFixed(2)} MB`;
    return `${(bytes/(1024**3)).toFixed(2)} GB`;
}
