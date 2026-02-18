// Padrão similar a files.js: usa API_BASE relativo e checa sessão
const API_BASE = window.location.origin;

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
            tableBody.innerHTML = '<tr><td colspan="6" class="fm-empty">Nenhuma máquina cadastrada</td></tr>';
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
        if (tableBody) tableBody.innerHTML = '<tr><td colspan="6" class="fm-empty">Erro ao buscar máquinas</td></tr>';
        if (machineCount) machineCount.textContent = '0';
        if (typeof setStatus === 'function') setStatus(false);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const wolBtn = document.getElementById('wol-button');
    if (wolBtn) {
        wolBtn.addEventListener('click', () => {
            const wolSelect = document.getElementById('wol-machine');
            const selected = wolSelect ? wolSelect.value : '';
            if (!selected) {
                alert('Por favor, selecione uma máquina.');
                return;
            }
            // placeholder: enviar WOL via API no futuro
            alert(`Wake-on-LAN enviado para ID: ${selected}`);
        });
    }

    fetchMachines();
});