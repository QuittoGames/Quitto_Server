document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('login-form');
    const errorDiv = document.getElementById('login-error');
    // Quick pre-check: if the session is already authenticated on the server,
    // redirect to avoid asking the user to log in twice.
    (async function checkAuth() {
        try {
            const res = await fetch('/api/auth/check', { credentials: 'include' });
            if (res.ok) {
                const data = await res.json();
                if (data && (data.ok === true || data.authenticated === true)) {
                    window.location.href = '/server';
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
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ name: username, password })
            });
            const data = await res.json();
            if (res.ok && data.ok) {
                window.location.href = '/server';
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
