document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('login-form');
    const errorDiv = document.getElementById('login-error');

    // Resolve API_BASE same as machines.js so all pages call the same endpoints
    const API_BASE = (function(){
        const fromWindow = (typeof window !== 'undefined' && window.API_BASE) ? window.API_BASE : null;
        const origin = window.location.origin;
        const fallback = origin.includes('3333') ? origin : `${window.location.protocol}//${window.location.hostname}:3333`;
        return fromWindow || fallback;
    })();

    // compute UI redirect root: if API_BASE already ends with /server, use it, otherwise append
    const UI_ROOT = API_BASE.endsWith('/server') ? API_BASE : `${API_BASE}/server`;

    // Quick pre-check: if the session is already authenticated on the server,
    // redirect to avoid asking the user to log in twice.
    (async function checkAuth() {
        try {
            const res = await fetch(`${API_BASE}/api/auth/check`, { credentials: 'include' });
            if (res.ok) {
                const data = await res.json();
                if (data && (data.ok === true || data.authenticated === true)) {
                    window.location.href = UI_ROOT;
                    return;
                }
            }
        } catch (e) {
            // ignore: endpoint might not exist in current backend
        }
    })();

    let submitting = false;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (submitting) return; // avoid duplicate submits
        submitting = true;
        errorDiv.textContent = '';
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;
        if (!username || !password) {
            errorDiv.textContent = 'Preencha todos os campos.';
            submitting = false;
            return;
        }
        try {
            const res = await fetch(`${API_BASE}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ name: username, password })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) {
                window.location.href = UI_ROOT;
            } else {
                errorDiv.textContent = data.detail || 'Usuário ou senha inválidos.';
            }
        } catch (err) {
            errorDiv.textContent = 'Erro ao conectar ao servidor.';
        } finally {
            submitting = false;
        }
    });
});
