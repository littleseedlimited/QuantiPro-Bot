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
            if (response.status === 403) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: red;">🚫 Access Denied</td></tr>';
                return;
            }
            throw new Error('Upload failed');
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
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No users found</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(u => `
        <tr>
            <td>
                <div style="font-weight: 500;">${u.full_name || 'Unknown'}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">${u.telegram_id}</div>
            </td>
            <td>${u.plan_id === 1 ? 'Free' : 'Pro'}</td>
            <td>
                <span class="status-badge ${u.verified ? 'status-verified' : 'status-unverified'}">
                    ${u.verified ? 'Verified' : 'Unverified'}
                </span>
            </td>
            <td>
                <button class="action-btn-sm btn-verify" onclick="verifyUser(${u.telegram_id})">✅</button>
            </td>
        </tr>
    `).join('');
}

function filterUsers() {
    const term = document.getElementById('userSearch').value.toLowerCase();
    const filtered = allUsers.filter(u =>
        (u.full_name && u.full_name.toLowerCase().includes(term)) ||
        String(u.telegram_id).includes(term)
    );
    renderUsers(filtered);
}

function verifyUser(userId) {
    // Placeholder for actual verification API
    tg.showPopup({
        title: 'Verify User',
        message: `Verify user ${userId}?`,
        buttons: [
            { id: 'yes', type: 'ok', text: 'Yes' },
            { id: 'no', type: 'cancel' }
        ]
    });
}
