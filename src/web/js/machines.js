// Determine API base (use window.API_BASE from page or fallback)
const API_BASE = (function(){
    const fromWindow = (typeof window !== 'undefined' && window.API_BASE) ? window.API_BASE : null;
    const origin = window.location.origin;
    const fallback = origin.includes('3333') ? origin : `${window.location.protocol}//${window.location.hostname}:3333`;
    const base = fromWindow || fallback;
    console.log('[DEBUG] API_BASE =', base);
    return base;
})();

async function fetchMachines() {
    try {
        const auth = await fetch(`${API_BASE}/api/auth/check`, { credentials: 'include' });
        const authJson = auth.ok ? await auth.json() : { authenticated: false };
        if (!authJson.authenticated) {
            window.location.href = '/pages/login.html';
            return;
        }

        // busca máquinas
        const res = await fetch(`${API_BASE}/machine/all`, { credentials: 'include' });
        console.log(res)
        if (!res.ok) throw new Error(`API returned ${res.status}`);
        const machines = await res.json();

        const tableBody = document.getElementById('machine-list');
        const wolSelect = document.getElementById('wol-machine');
        const machineCount = document.getElementById('machine-count');

        if (!tableBody) {
            console.error('Elemento #machine-list não encontrado.');
            return;
        }

        tableBody.innerHTML = '';
        if (wolSelect) wolSelect.innerHTML = '<option value="">-- Selecione --</option>';

        if (!machines || machines.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="fm-empty">Nenhuma máquina cadastrada</td></tr>';
            if (machineCount) machineCount.textContent = '0';
            if (typeof setStatus === 'function') setStatus(false);
            return;
        }

        machines.forEach(machine => {
            const row = document.createElement('tr');
            row.className = 'fm-list-item';
            row.innerHTML = `
                <td>${machine.id}</td>
                <td>${machine.address}</td>
                <td>${machine.name || ''}</td>
                <td>${machine.interface || ''}</td>
                <td>${machine.vendor || ''}</td>
                <td>${machine.is_randomized ? 'Sim' : 'Não'}</td>
                <td>${machine.url_connect ? `<a href="${machine.url_connect}" target="_blank" rel="noopener" class="fm-link">Conectar</a>` : ''}</td>
            `;
            tableBody.appendChild(row);

            if (wolSelect) {
                const option = document.createElement('option');
                option.value = machine.id;
                option.textContent = `${machine.name || machine.address}`;
                wolSelect.appendChild(option);
            }
        });

        if (machineCount) machineCount.textContent = machines.length;
        if (typeof setStatus === 'function') setStatus(true);
    } catch (err) {
        console.error('Erro fetchMachines:', err);
        const tableBody = document.getElementById('machine-list');
        const machineCount = document.getElementById('machine-count');
        if (tableBody) tableBody.innerHTML = '<tr><td colspan="7" class="fm-empty">Erro ao buscar máquinas</td></tr>';
        if (machineCount) machineCount.textContent = '0';
        if (typeof setStatus === 'function') setStatus(false);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const wolBtn = document.getElementById('wol-button');
    if (wolBtn) {
        wolBtn.addEventListener('click', async () => {
            const wolSelect = document.getElementById('wol-machine');
            const selected = wolSelect ? wolSelect.value : '';
            if (!selected) {
                alert('Por favor, selecione uma máquina.');
                return;
            }

            wolBtn.disabled = true;
            try {
                console.log('WOL click, sending to:', `${API_BASE}/machine/wake_on_lan?id_machine=${selected}`);
                // FastAPI handler expects id_machine as a query param for this endpoint
                const res = await fetch(`${API_BASE}/machine/wake_on_lan?id_machine=${encodeURIComponent(selected)}`, {
                    method: 'POST',
                    credentials: 'include'
                });

                if (!res.ok) {
                    const text = await res.text().catch(() => '');
                    throw new Error(`Server returned ${res.status}: ${text}`);
                }

                const data = await res.json().catch(() => ({}));
                if (data && data.ok) {
                    alert(`Wake-on-LAN sent to ${data.address || selected}`);
                } else {
                    alert(`Wake-on-LAN request completed: ${JSON.stringify(data)}`);
                }
            } catch (err) {
                console.error('WOL error', err);
                alert('Error sending Wake-on-LAN: ' + (err.message || err));
            } finally {
                wolBtn.disabled = false;
            }
        });
    }

    fetchMachines();
});