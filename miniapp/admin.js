const tg = window.Telegram.WebApp;
const API_URL = window.location.origin + '/api';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    tg.ready();
    tg.expand(); // Full screen

    // Theme handling
    document.documentElement.className = tg.colorScheme;

    loadStats();
    loadUsers();
});

let allUsers = [];

async function loadStats() {
    try {
        const response = await fetch(`${API_URL}/admin/stats`, {
            headers: { 'X-Telegram-Init-Data': tg.initData }
        });
        const data = await response.json();

        if (data.total_users !== undefined) {
            document.getElementById('totalUsers').textContent = data.total_users;
            document.getElementById('activeUsers').textContent = data.verified_users;
        }
    } catch (error) {
        console.error('Stats error:', error);
    }
}

async function loadUsers() {
    const tbody = document.getElementById('userTableBody');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">Loading...</td></tr>';

    try {
        const response = await fetch(`${API_URL}/admin/users`, {
            headers: { 'X-Telegram-Init-Data': tg.initData }
        });

        if (!response.ok) {
            let errorMessage = 'Upload failed';
            try {
                const errData = await response.json();
                errorMessage = errData.detail || errorMessage;
            } catch (e) { }

            if (response.status === 403) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: red;">🚫 ${errorMessage}</td></tr>`;
                return;
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();
        allUsers = data.users || [];
        renderUsers(allUsers);

    } catch (error) {
        console.error('Users error:', error);
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: red;">Error: ${error.message}</td></tr>`;
    }
}

function renderUsers(users) {
    const tbody = document.getElementById('userTableBody');
    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">No users found</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(u => {
        const joinedDate = u.signup_date || 'N/A';
        const expiryDate = u.expiry || 'N/A';
        const isBanned = u.banned;

        return `
        <tr style="background: ${isBanned ? 'rgba(239, 68, 68, 0.05)' : 'transparent'}">
            <td>
                <div style="font-weight: 500;">${u.name || 'Unknown'} ${u.admin ? '👑' : ''}</div>
                <div style="font-size: 0.75rem; color: var(--text-secondary);">ID: ${u.id}</div>
                <div style="font-size: 0.75rem; color: var(--text-secondary);">Joined: ${joinedDate}</div>
            </td>
            <td>
                <div style="font-weight: 500;">${u.plan}</div>
                <div style="font-size: 0.75rem; color: var(--text-secondary);">Exp: ${expiryDate}</div>
            </td>
             <td>
                <div style="font-size: 0.8rem;">${u.email}</div>
                <div style="font-size: 0.8rem;">${u.phone}</div>
                <div style="font-size: 0.8rem;">${u.country}</div>
            </td>
            <td>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    <span class="status-badge ${u.verified ? 'status-verified' : 'status-unverified'}">
                        ${u.verified ? 'Verified' : 'Unverified'}
                    </span>
                    ${isBanned ? '<span class="status-badge status-unverified">BANNED</span>' : ''}
                </div>
            </td>
            <td>
                <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                    ${!u.verified ? `<button class="action-btn-sm btn-verify" onclick="verifyUser(${u.id})">✅</button>` : ''}
                    <button class="action-btn-sm" style="background:var(--secondary-color); color:var(--text-primary)" onclick="promoteUser(${u.id})" title="Upgrade">⬆️</button>
                    ${isBanned
                ? `<button class="action-btn-sm" style="background: #22c55e; color: white;" onclick="unbanUser(${u.id})" title="Unban">😇</button>`
                : `<button class="action-btn-sm" style="background: #ef4444; color: white;" onclick="banUser(${u.id})" title="Ban">🚫</button>`
            }
                    <button class="action-btn-sm" style="background: #ef4444; color: white;" onclick="deleteUser(${u.id})" title="Delete">🗑️</button>
                </div>
            </td>
        </tr>
    `}).join('');
}

function filterUsers() {
    const term = document.getElementById('userSearch').value.toLowerCase();
    const filtered = allUsers.filter(u =>
        (u.name && u.name.toLowerCase().includes(term)) ||
        String(u.id).includes(term) ||
        (u.email && u.email.toLowerCase().includes(term))
    );
    renderUsers(filtered);
}

async function verifyUser(userId) {
    if (!confirm(`Verify user ${userId}?`)) return;
    try {
        const res = await fetch(`${API_URL}/admin/verify/${userId}`, { method: 'POST', headers: { 'X-Telegram-Init-Data': tg.initData } });
        if (res.ok) { loadUsers(); loadStats(); } else alert("Failed");
    } catch (e) { console.error(e); }
}

async function promoteUser(userId) {
    const plan = prompt("Enter Plan Name (Free, Student, Researcher, Institution, Limitless):", "Limitless");
    if (!plan) return;
    try {
        const res = await fetch(`${API_URL}/admin/promote/${userId}?plan=${plan}`, { method: 'POST', headers: { 'X-Telegram-Init-Data': tg.initData } });
        if (res.ok) { loadUsers(); } else alert("Failed");
    } catch (e) { console.error(e); }
}

async function banUser(userId) {
    if (!confirm(`Ban user ${userId}?`)) return;
    try {
        const res = await fetch(`${API_URL}/admin/ban/${userId}`, { method: 'POST', headers: { 'X-Telegram-Init-Data': tg.initData } });
        if (res.ok) { loadUsers(); } else alert("Failed");
    } catch (e) { console.error(e); }
}

async function unbanUser(userId) {
    if (!confirm(`Unban user ${userId}?`)) return;
    try {
        const res = await fetch(`${API_URL}/admin/unban/${userId}`, { method: 'POST', headers: { 'X-Telegram-Init-Data': tg.initData } });
        if (res.ok) { loadUsers(); } else alert("Failed");
    } catch (e) { console.error(e); }
}

async function deleteUser(userId) {
    if (!confirm(`DELETE user ${userId}? This cannot be undone!`)) return;
    try {
        const res = await fetch(`${API_URL}/admin/users/${userId}`, { method: 'DELETE', headers: { 'X-Telegram-Init-Data': tg.initData } });
        if (res.ok) { loadUsers(); loadStats(); } else alert("Failed");
    } catch (e) { console.error(e); }
}
