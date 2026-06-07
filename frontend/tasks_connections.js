/**
 * Scapyfy - Tasks & Connections UI Logic
 */

// ============================================================================
// API Extensions
// ============================================================================
Object.assign(Api, {
    // Connections API
    async listConnections() {
        return await this.request('/connections/');
    },
    async createConnection(data) {
        return await this.request('/connections/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    async updateConnection(id, data) {
        return await this.request(`/connections/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    async deleteConnection(id) {
        return await this.request(`/connections/${id}`, { method: 'DELETE' });
    },
    async testConnection(id) {
        return await this.request(`/connections/${id}/test`, { method: 'POST' });
    },
    async generateBotHash(id) {
        return await this.request(`/connections/${id}/generate-hash`, { method: 'POST' });
    },
    async getBotAuths(id) {
        return await this.request(`/connections/bot-auths/${id}`);
    },
    async revokeBotAuth(authId) {
        return await this.request(`/connections/bot-auths/${authId}`, { method: 'DELETE' });
    },
    async exportData(connectionId, content, source) {
        return await this.request('/connections/export', {
            method: 'POST',
            body: JSON.stringify({
                connection_id: connectionId,
                content: content,
                source: source
            })
        });
    },

    // Tasks API
    async listTasks() {
        return await this.request('/tasks/');
    },
    async getAvailableTools() {
        return await this.request('/tasks/available-tools');
    },
    async createTask(data) {
        return await this.request('/tasks/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    async updateTask(id, data) {
        return await this.request(`/tasks/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    async deleteTask(id) {
        return await this.request(`/tasks/${id}`, { method: 'DELETE' });
    },
    async runTaskNow(id) {
        return await this.request(`/tasks/${id}/run-now`, { method: 'POST' });
    },
    async getTaskRuns(id) {
        return await this.request(`/tasks/${id}/runs`);
    }
});

// ============================================================================
// Connections UI
// ============================================================================
const ConnectionsUI = {
    connections: [],
    
    async init() {
        await this.loadConnections();
        this.renderConnections();
        this.setupEventListeners();
    },

    async loadConnections() {
        try {
            this.connections = await Api.listConnections();
        } catch (error) {
            UI.showToast('error', 'Error', 'Failed to load connections: ' + error.message);
        }
    },

    renderConnections() {
        const container = document.getElementById('connections-list');
        if (!container) return;

        if (this.connections.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M2 12h3M19 12h3M12 2v3M12 19v3"></path>
                        <circle cx="12" cy="12" r="7"></circle>
                    </svg>
                    <h3>No Connections Yet</h3>
                    <p>Create a connection to export your data and reports.</p>
                </div>
            `;
            return;
        }

        const icons = {
            'mongodb': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: #10b981;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
            'elasticsearch': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: #06b6d4;"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>',
            'telegram': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: #3b82f6;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>'
        };

        container.innerHTML = this.connections.map(conn => `
            <div class="connection-card glass-card" style="display: flex; flex-direction: column; height: 100%; overflow: hidden; transition: transform var(--transition-normal); border-top: 3px solid var(--accent-primary);">
                <div class="conn-header" style="padding: 1.5rem; display: flex; align-items: flex-start; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <div class="conn-title" style="display: flex; align-items: center; gap: 1rem;">
                        <div class="conn-icon" style="width: 48px; height: 48px; border-radius: var(--radius-md); background: rgba(255,255,255,0.05); display: flex; align-items: center; justify-content: center;">
                            ${icons[conn.conn_type] || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 16V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9m16 0H4m16 0 1.28 2.55a1 1 0 0 1-.9 1.45H3.62a1 1 0 0 1-.9-1.45L4 16"></path></svg>'}
                        </div>
                        <div>
                            <h4 style="margin-bottom: 0.2rem; font-size: 1.1rem; font-weight: 600;">${UI.escapeHtml(conn.name)}</h4>
                            <div style="display: flex; gap: 0.5rem; align-items: center;">
                                <span class="badge ${conn.is_active ? 'success' : 'danger'}">${conn.is_active ? 'Active' : 'Inactive'}</span>
                                <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: capitalize;">${conn.conn_type}</span>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="conn-details" style="padding: 1.5rem; flex: 1; display: flex; flex-direction: column; background: rgba(0,0,0,0.1);">
                    <span style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">Configuration</span>
                    <pre class="config-preview" style="background: var(--bg-tertiary); padding: 1rem; border-radius: var(--radius-md); font-size: 0.85rem; color: var(--text-secondary); overflow-x: auto; border: 1px solid rgba(255,255,255,0.05); margin: 0; flex: 1; box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);">${UI.escapeHtml(JSON.stringify(conn.config, null, 2))}</pre>
                </div>
                <div class="conn-footer" style="padding: 1rem 1.5rem; display: flex; justify-content: flex-end; gap: 0.5rem; border-top: 1px solid rgba(255,255,255,0.05); background: var(--surface-glass);">
                    <button class="btn btn-sm btn-ghost test-conn-btn" data-id="${conn.id}" title="Test Connection">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="12" y1="18" x2="12" y2="12"></line><line x1="9" y1="15" x2="15" y2="15"></line></svg> Test
                    </button>
                    ${['telegram'].includes(conn.conn_type) ? 
                      `<button class="btn btn-sm btn-primary auth-hash-btn" data-id="${conn.id}" title="Bot Auth"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"></path></svg> Auth</button>` : ''}
                    <button class="btn btn-sm btn-ghost edit-conn-btn" data-id="${conn.id}" title="Edit" style="padding: 0.4rem;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                    </button>
                    <button class="btn btn-sm btn-danger delete-conn-btn" data-id="${conn.id}" title="Delete" style="padding: 0.4rem;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </div>
            </div>
        `).join('');
    },

    setupEventListeners() {
        const view = document.getElementById('connections-view');
        if (!view || view.dataset.eventsBound) return;
        view.dataset.eventsBound = "true";

        document.getElementById('new-conn-btn')?.addEventListener('click', () => this.showModal());
        document.getElementById('conn-type-select')?.addEventListener('change', (e) => this.updateConfigFields(e.target.value));
        document.getElementById('save-conn-btn')?.addEventListener('click', () => this.saveConnection());
        document.getElementById('close-conn-modal')?.addEventListener('click', () => UI.closeModal('connection-modal'));
        document.getElementById('close-auth-modal')?.addEventListener('click', () => UI.closeModal('auth-hash-modal'));
        document.getElementById('generate-hash-btn')?.addEventListener('click', () => this.generateHash());

        document.getElementById('connections-list')?.addEventListener('click', async (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;

            const id = parseInt(btn.dataset.id);
            if (btn.classList.contains('delete-conn-btn')) {
                if (await UI.confirm('Delete Connection', 'Are you sure you want to delete this connection?')) {
                    try {
                        await Api.deleteConnection(id);
                        UI.showToast('success', 'Deleted', 'Connection deleted successfully');
                        await this.init();
                    } catch (err) {
                        UI.showToast('error', 'Error', err.message);
                    }
                }
            } else if (btn.classList.contains('test-conn-btn')) {
                const originalText = btn.innerHTML;
                btn.innerHTML = '⏳';
                try {
                    const res = await Api.testConnection(id);
                    UI.showToast(res.success ? 'success' : 'error', 'Test Result', res.message);
                } catch (err) {
                    UI.showToast('error', 'Test Failed', err.message);
                } finally {
                    btn.innerHTML = originalText;
                }
            } else if (btn.classList.contains('auth-hash-btn')) {
                this.showAuthModal(id);
            } else if (btn.classList.contains('edit-conn-btn')) {
                this.showModal(this.connections.find(c => c.id === id));
            }
        });
    },

    selectType(type) {
        document.querySelectorAll('.conn-type-card').forEach(c => {
            c.classList.toggle('active', c.dataset.type === type);
        });
        document.getElementById('conn-type-select').value = type;
        this.updateConfigFields(type);
    },

    showModal(conn = null) {
        const modal = document.getElementById('connection-modal');
        const title = document.getElementById('conn-modal-title');
        const form = document.getElementById('connection-form');
        
        form.reset();
        document.getElementById('conn-id').value = conn ? conn.id : '';
        title.textContent = conn ? 'Edit Connection' : 'New Connection';
        
        if (conn) {
            document.getElementById('conn-name').value = conn.name;
            this.selectType(conn.conn_type);
            document.getElementById('conn-active').checked = conn.is_active;
            this.updateConfigFields(conn.conn_type, conn.config);
        } else {
            this.selectType('mongodb');
        }
        
        modal.classList.add('active');
    },

    updateConfigFields(type, config = {}) {
        const container = document.getElementById('conn-config-fields');
        let html = '';

        if (type === 'mongodb') {
            html = `
                <div class="form-group">
                    <label>MongoDB URI</label>
                    <input type="text" id="cfg-uri" class="input-wrapper" value="${config.uri || 'mongodb://localhost:27017'}" required>
                </div>
                <div class="form-group">
                    <label>Database</label>
                    <input type="text" id="cfg-db" class="input-wrapper" value="${config.database || 'scapyfy'}" required>
                </div>
                <div class="form-group">
                    <label>Collection</label>
                    <input type="text" id="cfg-coll" class="input-wrapper" value="${config.collection || 'outputs'}" required>
                </div>
            `;
        } else if (type === 'elasticsearch') {
            html = `
                <div class="form-group">
                    <label>Elasticsearch URL</label>
                    <input type="url" id="cfg-url" class="input-wrapper" value="${config.url || 'http://localhost:9200'}" required>
                </div>
                <div class="form-group">
                    <label>Index Name</label>
                    <input type="text" id="cfg-index" class="input-wrapper" value="${config.index || 'scapyfy-outputs'}" required>
                </div>
                <div class="form-group">
                    <label>Username (Optional)</label>
                    <input type="text" id="cfg-user" class="input-wrapper" value="${config.username || ''}">
                </div>
                <div class="form-group">
                    <label>Password (Optional)</label>
                    <input type="password" id="cfg-pass" class="input-wrapper" value="">
                    <small>Leave blank to keep existing password</small>
                </div>
            `;
        } else if (type === 'telegram') {
            html = `
                <div class="form-group">
                    <label>Bot Token</label>
                    <input type="password" id="cfg-token" class="input-wrapper" value="" ${config.bot_token ? '' : 'required'}>
                    <small>Leave blank to keep existing token</small>
                </div>
                <div class="form-group">
                    <label>Chat IDs (Comma separated)</label>
                    <input type="text" id="cfg-chats" class="input-wrapper" value="${(config.chat_ids || []).join(', ')}">
                    <small>Will auto-populate when users authenticate via bot</small>
                </div>
            `;
        }

        container.innerHTML = html;
    },

    async saveConnection() {
        const id = document.getElementById('conn-id').value;
        const name = document.getElementById('conn-name').value;
        const type = document.getElementById('conn-type-select').value;
        const isActive = document.getElementById('conn-active').checked;
        
        if (!name) return UI.showToast('error', 'Validation Error', 'Name is required');

        let config = {};
        if (type === 'mongodb') {
            config = {
                uri: document.getElementById('cfg-uri').value,
                database: document.getElementById('cfg-db').value,
                collection: document.getElementById('cfg-coll').value
            };
        } else if (type === 'elasticsearch') {
            config = {
                url: document.getElementById('cfg-url').value,
                index: document.getElementById('cfg-index').value,
                username: document.getElementById('cfg-user').value
            };
            const p = document.getElementById('cfg-pass').value;
            if (p) config.password = p;
        } else if (type === 'telegram') {
            const t = document.getElementById('cfg-token').value;
            if (t) config.bot_token = t;
            const chats = document.getElementById('cfg-chats').value;
            config.chat_ids = chats ? chats.split(',').map(s => s.trim()) : [];
        }

        try {
            if (id) {
                await Api.updateConnection(id, { name, config, is_active: isActive });
                UI.showToast('success', 'Updated', 'Connection updated');
            } else {
                await Api.createConnection({ name, conn_type: type, config });
                UI.showToast('success', 'Created', 'Connection created');
            }
            UI.closeModal('connection-modal');
            await this.init();
        } catch (error) {
            UI.showToast('error', 'Error', error.message);
        }
    },

    authPollInterval: null,

    async showAuthModal(connectionId) {
        document.getElementById('auth-conn-id').value = connectionId;
        const modal = document.getElementById('auth-hash-modal');
        await this.loadHashes(connectionId);
        modal.classList.add('active');
        
        if (this.authPollInterval) clearInterval(this.authPollInterval);
        this.authPollInterval = setInterval(() => {
            if (modal.classList.contains('active')) {
                this.loadHashes(connectionId);
            } else {
                clearInterval(this.authPollInterval);
                this.authPollInterval = null;
            }
        }, 3000);
    },

    async loadHashes(connId) {
        try {
            const auths = await Api.getBotAuths(connId);
            const list = document.getElementById('auth-hash-list');
            
            if (auths.length === 0) {
                list.innerHTML = '<p class="text-muted">No auth hashes generated yet.</p>';
                return;
            }

            list.innerHTML = auths.map(a => `
                <div class="hash-item">
                    <div>
                        <code>${a.auth_hash.substring(0, 16)}...</code>
                        <span class="badge ${a.is_bound ? 'success' : 'warning'}">${a.is_bound ? 'Bound' : 'Pending'}</span>
                        ${a.external_user_id ? `<small>(${a.external_user_id})</small>` : ''}
                    </div>
                    <button class="btn btn-sm btn-danger" onclick="ConnectionsUI.revokeHash(${a.id}, ${connId})">Revoke</button>
                </div>
            `).join('');
        } catch (error) {
            UI.showToast('error', 'Error', 'Failed to load auths');
        }
    },

    async generateHash() {
        const connId = document.getElementById('auth-conn-id').value;
        try {
            const auth = await Api.generateBotHash(connId);
            document.getElementById('new-hash-display').innerHTML = `
                <div class="success-box">
                    <p>Send this hash to your bot to bind your account:</p>
                    <code style="user-select: all; display: block; padding: 10px; background: #000; word-break: break-all;">${auth.auth_hash}</code>
                </div>
            `;
            await this.loadHashes(connId);
        } catch (error) {
            UI.showToast('error', 'Error', error.message);
        }
    },

    async revokeHash(authId, connId) {
        if (await UI.confirm('Revoke Hash', 'Revoke this auth hash?')) {
            try {
                await Api.revokeBotAuth(authId);
                await this.loadHashes(connId);
            } catch (error) {
                UI.showToast('error', 'Error', error.message);
            }
        }
    }
};

// ============================================================================
// Tasks UI
// ============================================================================
const TasksUI = {
    tasks: [],
    availableTools: [],   // [{name, parameters, description}, ...]

    async init() {
        try {
            // Fix: use Api.listTools() which already exists, then enrich with getToolInfo
            const toolList = await Api.listTools();
            // toolList is [{name, description, ...}] - store lightweight list first
            this.availableTools = toolList;
            await this.loadTasks();
            this.renderTasks();
            this.setupEventListeners();

            if (!ConnectionsUI.connections.length) {
                await ConnectionsUI.loadConnections();
            }
            this._populateOutputSelect();
        } catch (error) {
            UI.showToast('error', 'Error', 'Failed to initialize Tasks UI: ' + error.message);
        }
    },

    _populateOutputSelect() {
        const container = document.getElementById('task-outputs');
        if (container) {
            if (ConnectionsUI.connections.length === 0) {
                container.innerHTML = '<span style="font-size: 0.85rem; color: var(--text-muted); font-style: italic;">No connections available</span>';
                return;
            }
            container.innerHTML = ConnectionsUI.connections.map(c =>
                `<div class="conn-chip" data-id="${c.id}" onclick="this.classList.toggle('active')">
                    ${UI.escapeHtml(c.name)} <span class="conn-type-badge">${c.conn_type}</span>
                </div>`
            ).join('');
        }
    },

    async loadTasks() {
        this.tasks = await Api.listTasks();
    },

    renderTasks() {
        const container = document.getElementById('tasks-list');
        if (!container) return;

        if (this.tasks.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <polyline points="9 11 12 14 22 4"></polyline>
                        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
                    </svg>
                    <h3>No Scheduled Tasks</h3>
                    <p>Create a task to automate your network operations.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.tasks.map(t => `
            <div class="task-card glass-card" style="display: flex; flex-direction: column; height: 100%; border-top: 3px solid var(--accent-secondary);">
                <div class="task-header" style="padding: 1.5rem; border-bottom: 1px solid rgba(255, 255, 255, 0.05); display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <h4 style="margin-bottom: 0.25rem; font-size: 1.1rem;">${UI.escapeHtml(t.name)}</h4>
                        <span class="badge ${t.is_active ? 'success' : 'danger'}">${t.is_active ? 'Active' : 'Paused'}</span>
                    </div>
                    <div class="task-actions" style="display: flex; gap: 0.25rem;">
                        <button class="btn btn-sm btn-primary run-now-btn" data-id="${t.id}" title="Run Now" style="padding: 0.4rem;">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        </button>
                        <button class="btn btn-sm toggle-active-btn ${t.is_active ? 'btn-warning' : 'btn-success'}" data-id="${t.id}" data-active="${t.is_active}" title="${t.is_active ? 'Pause Task' : 'Enable Task'}" style="padding: 0.4rem;">
                            ${t.is_active
                                ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>'
                                : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="10 8 16 12 10 16 10 8"></polyline></svg>'
                            }
                        </button>
                        <button class="btn btn-sm btn-ghost edit-task-btn" data-id="${t.id}" title="Edit" style="padding: 0.4rem;">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                        </button>
                        <button class="btn btn-sm btn-danger delete-task-btn" data-id="${t.id}" title="Delete" style="padding: 0.4rem;">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                </div>
                <div class="task-body" style="padding: 1.5rem; flex: 1; display: flex; flex-direction: column; gap: 1rem;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                        <div class="info-group">
                            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Schedule</span>
                            <div style="font-weight: 500; text-transform: capitalize; margin-top: 0.2rem;">${t.schedule_type}</div>
                        </div>
                        <div class="info-group">
                            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Runs</span>
                            <div style="font-weight: 500; margin-top: 0.2rem;">${t.run_count} ${t.max_runs ? '/ ' + t.max_runs : ''}</div>
                        </div>
                    </div>
                    <div class="info-group">
                        <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Last Run</span>
                        <div style="font-size: 0.9rem; margin-top: 0.2rem; color: var(--text-secondary);">${t.last_run_at ? new Date(t.last_run_at).toLocaleString() : 'Never'}</div>
                    </div>
                </div>
                <div class="task-footer" style="padding: 1rem 1.5rem; border-top: 1px solid rgba(255, 255, 255, 0.05); background: rgba(0,0,0,0.2);">
                    <button class="btn btn-sm btn-ghost btn-full view-runs-btn" data-id="${t.id}" title="View Logs">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 0.5rem;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
                        View Execution Logs
                    </button>
                </div>
            </div>
        `).join('');
    },

    setupEventListeners() {
        const view = document.getElementById('tasks-view');
        if (!view || view.dataset.eventsBound) return;
        view.dataset.eventsBound = "true";

        document.getElementById('new-task-btn')?.addEventListener('click', () => this.showTaskBuilder());
        document.getElementById('add-step-btn')?.addEventListener('click', () => this.addStepToBuilder());
        document.getElementById('task-schedule-type')?.addEventListener('change', (e) => {
            document.getElementById('sched-once').style.display = e.target.value === 'once' ? 'block' : 'none';
            document.getElementById('sched-interval').style.display = e.target.value === 'interval' ? 'block' : 'none';
            document.getElementById('sched-cron').style.display = e.target.value === 'cron' ? 'block' : 'none';
        });

        document.getElementById('save-task-btn')?.addEventListener('click', () => this.saveTask());
        document.getElementById('close-task-modal')?.addEventListener('click', () => UI.closeModal('task-modal'));
        document.getElementById('close-task-modal-footer')?.addEventListener('click', () => UI.closeModal('task-modal'));
        document.getElementById('close-runs-modal')?.addEventListener('click', () => UI.closeModal('task-runs-modal'));

        // Tab switching
        document.querySelectorAll('.task-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => this._switchTab(btn.dataset.tab));
        });

        // JSON editor helpers
        document.getElementById('task-json-format-btn')?.addEventListener('click', () => {
            const ta = document.getElementById('task-json-editor');
            const errEl = document.getElementById('task-json-error');
            try {
                ta.value = JSON.stringify(JSON.parse(ta.value), null, 2);
                errEl.style.display = 'none';
            } catch(e) {
                errEl.textContent = 'Invalid JSON: ' + e.message;
                errEl.style.display = 'block';
            }
        });
        document.getElementById('task-json-from-form-btn')?.addEventListener('click', () => {
            const payload = this._collectFormPayload();
            if (payload) {
                document.getElementById('task-json-editor').value = JSON.stringify(payload, null, 2);
                document.getElementById('task-json-error').style.display = 'none';
            }
        });

        document.getElementById('task-test-run-btn')?.addEventListener('click', () => this.testRun());

        document.getElementById('tasks-list')?.addEventListener('click', async (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;
            const id = parseInt(btn.dataset.id);
            if (btn.classList.contains('delete-task-btn')) {
                if (await UI.confirm('Delete Task', 'Delete this task forever?')) {
                    await Api.deleteTask(id);
                    await this.init();
                }
            } else if (btn.classList.contains('run-now-btn')) {
                try {
                    await Api.runTaskNow(id);
                    UI.showToast('success', 'Triggered', 'Task triggered in background');
                } catch (err) {
                    UI.showToast('error', 'Error', err.message);
                }
            } else if (btn.classList.contains('toggle-active-btn')) {
                const currentlyActive = btn.dataset.active === 'true';
                btn.disabled = true;
                try {
                    await Api.updateTask(id, { is_active: !currentlyActive });
                    UI.showToast('success', currentlyActive ? 'Paused' : 'Enabled',
                        `Task ${currentlyActive ? 'paused' : 'enabled'} successfully`);
                    await this.loadTasks();
                    this.renderTasks();
                } catch (err) {
                    UI.showToast('error', 'Error', err.message);
                    btn.disabled = false;
                }
            } else if (btn.classList.contains('view-runs-btn')) {
                this.showRunsModal(id);
            } else if (btn.classList.contains('edit-task-btn')) {
                this.showTaskBuilder(this.tasks.find(t => t.id === id));
            }
        });
    },

    _switchTab(tab) {
        document.querySelectorAll('.task-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
        document.getElementById('task-tab-form').style.display = tab === 'form' ? 'block' : 'none';
        const jsonTab = document.getElementById('task-tab-json');
        jsonTab.style.display = tab === 'json' ? 'flex' : 'none';
        // When switching to JSON, auto-sync from form
        if (tab === 'json') {
            const payload = this._collectFormPayload(true);
            if (payload) {
                document.getElementById('task-json-editor').value = JSON.stringify(payload, null, 2);
            }
        }
    },

    showTaskBuilder(task = null) {
        document.getElementById('task-modal-title').textContent = task ? 'Edit Task' : 'New Task';
        document.getElementById('task-id').value = task ? task.id : '';
        document.getElementById('task-name').value = task ? task.name : '';
        document.getElementById('task-desc').value = task ? (task.description || '') : '';
        document.getElementById('task-active').checked = task ? task.is_active : true;

        this._populateOutputSelect();
        const sel = document.getElementById('task-outputs');
        if (sel) {
            sel.querySelectorAll('.conn-chip').forEach(chip => chip.classList.remove('active'));
            if (task && task.output_connections) {
                task.output_connections.forEach(id => {
                    const chip = sel.querySelector(`.conn-chip[data-id="${id}"]`);
                    if (chip) chip.classList.add('active');
                });
            }
        }

        const stype = task ? task.schedule_type : 'once';
        document.getElementById('task-schedule-type').value = stype;
        document.getElementById('task-schedule-type').dispatchEvent(new Event('change'));
        document.getElementById('max-runs').value = task && task.max_runs ? task.max_runs : '';
        const conf = task ? (task.schedule_config || {}) : {};
        document.getElementById('run-at').value = conf.run_at ? conf.run_at.slice(0,16) : '';
        document.getElementById('interval-sec').value = conf.interval_seconds || 3600;
        document.getElementById('cron-expr').value = conf.cron_expression || '0 * * * *';

        const stepsContainer = document.getElementById('task-steps-container');
        stepsContainer.innerHTML = '';
        if (task && task.steps && task.steps.length > 0) {
            task.steps.forEach(s => this.addStepToBuilder(s));
        } else {
            this.addStepToBuilder();
        }

        // Reset to form tab
        this._switchTab('form');
        document.getElementById('task-json-error').style.display = 'none';
        document.getElementById('task-modal').classList.add('active');
    },

    async addStepToBuilder(stepData = null) {
        const container = document.getElementById('task-steps-container');
        const index = container.children.length;
        const type = stepData ? stepData.type : 'prompt';
        const div = document.createElement('div');
        div.className = 'task-step';

        // Build tool options
        const toolOpts = this.availableTools.map(t =>
            `<option value="${t.name}">${t.name}</option>`
        ).join('');

        div.innerHTML = `
            <div class="task-step-header">
                <span class="task-step-number">Step ${index + 1}</span>
                <select class="step-type input-wrapper" style="flex:1; margin: 0 0.75rem;">
                    <option value="prompt" ${type === 'prompt' ? 'selected' : ''}>🤖 LLM Prompt</option>
                    <option value="tool" ${type === 'tool' ? 'selected' : ''}>🔧 Specific Tool</option>
                </select>
                <button type="button" class="modal-close" style="flex-shrink:0;" onclick="this.closest('.task-step').remove()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            </div>
            <div class="step-prompt-ui" style="display: ${type === 'prompt' ? 'block' : 'none'}; margin-top: 0.75rem;">
                <label style="font-size:0.8rem; color: var(--text-muted); margin-bottom:0.3rem; display:block;">Instructions for the AI Agent</label>
                <textarea class="input-wrapper step-prompt" rows="3" placeholder="e.g. Scan target host for open ports and summarize findings...">${type === 'prompt' && stepData ? UI.escapeHtml(stepData.prompt_text || '') : ''}</textarea>
            </div>
            <div class="step-tool-ui" style="display: ${type === 'tool' ? 'block' : 'none'}; margin-top: 0.75rem;">
                <label style="font-size:0.8rem; color: var(--text-muted); margin-bottom:0.3rem; display:block;">Select Tool</label>
                <select class="step-tool-name input-wrapper" style="margin-bottom: 0.75rem;">${toolOpts}</select>
                <div class="step-tool-params-form"></div>
            </div>
        `;

        // Wire up type switcher
        const typeSelect = div.querySelector('.step-type');
        typeSelect.addEventListener('change', () => {
            div.querySelector('.step-prompt-ui').style.display = typeSelect.value === 'prompt' ? 'block' : 'none';
            div.querySelector('.step-tool-ui').style.display = typeSelect.value === 'tool' ? 'block' : 'none';
        });

        // Wire up tool-name switcher to load param form
        const toolSelect = div.querySelector('.step-tool-name');
        toolSelect.addEventListener('change', () => this._buildStepParamForm(div, toolSelect.value));

        container.appendChild(div);

        // Pre-select tool and load its params
        if (type === 'tool' && stepData) {
            toolSelect.value = stepData.tool_name;
            await this._buildStepParamForm(div, stepData.tool_name, stepData.parameters || {});
        } else if (type === 'tool' && toolSelect.value) {
            await this._buildStepParamForm(div, toolSelect.value);
        }
    },

    async _buildStepParamForm(stepDiv, toolName, existingValues = {}) {
        const formContainer = stepDiv.querySelector('.step-tool-params-form');
        if (!formContainer) return;
        formContainer.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">Loading parameters...</div>';
        try {
            const toolInfo = await Api.getToolInfo(toolName);
            if (!toolInfo.parameters || toolInfo.parameters.length === 0) {
                formContainer.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;font-style:italic;">This tool has no parameters.</div>';
                return;
            }
            formContainer.innerHTML = '';
            toolInfo.parameters.forEach(param => {
                const group = document.createElement('div');
                group.className = 'form-group';
                group.style.marginBottom = '0.6rem';
                const label = document.createElement('label');
                const displayLabel = param.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                label.innerHTML = `${displayLabel} ${param.required ? '<span class="required">*</span>' : '<span class="optional">(optional)</span>'}`;
                label.style.fontSize = '0.8rem';

                let input;
                const existingVal = existingValues[param.name];

                if (param.type === 'boolean') {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'checkbox-wrapper';
                    input = document.createElement('input');
                    input.type = 'checkbox';
                    input.dataset.paramName = param.name;
                    input.dataset.paramType = 'boolean';
                    input.checked = existingVal !== undefined ? existingVal : (param.default === true);
                    wrapper.appendChild(input);
                    const lbl = document.createElement('span');
                    lbl.textContent = input.checked ? 'Enabled' : 'Disabled';
                    input.addEventListener('change', () => lbl.textContent = input.checked ? 'Enabled' : 'Disabled');
                    wrapper.appendChild(lbl);
                    group.appendChild(label);
                    group.appendChild(wrapper);
                } else if (param.enum) {
                    input = document.createElement('select');
                    input.className = 'input-wrapper';
                    input.dataset.paramName = param.name;
                    param.enum.forEach(val => {
                        const opt = document.createElement('option');
                        opt.value = val; opt.textContent = val;
                        if ((existingVal !== undefined ? existingVal : param.default) === val) opt.selected = true;
                        input.appendChild(opt);
                    });
                    group.appendChild(label); group.appendChild(input);
                } else {
                    input = document.createElement('input');
                    input.type = (param.type === 'integer' || param.type === 'number') ? 'number' : 'text';
                    input.className = 'input-wrapper';
                    input.dataset.paramName = param.name;
                    input.dataset.paramType = param.type || 'string';
                    input.placeholder = param.description || `Enter ${param.name}`;
                    input.value = existingVal !== undefined ? existingVal : (param.default !== null && param.default !== undefined ? param.default : '');
                    if (param.required) input.required = true;
                    group.appendChild(label); group.appendChild(input);
                }

                if (param.description) {
                    const hint = document.createElement('span');
                    hint.className = 'param-hint';
                    hint.textContent = param.description;
                    group.appendChild(hint);
                }
                formContainer.appendChild(group);
            });
        } catch(e) {
            formContainer.innerHTML = `<div style="color:#ff6b6b;font-size:0.8rem;">Failed to load parameters: ${e.message}</div>`;
        }
    },

    _collectStepParams(stepDiv) {
        const params = {};
        stepDiv.querySelectorAll('.step-tool-params-form [data-param-name]').forEach(input => {
            const name = input.dataset.paramName;
            const ptype = input.dataset.paramType;
            if (input.type === 'checkbox') {
                params[name] = input.checked;
            } else if (ptype === 'integer') {
                if (input.value !== '') params[name] = parseInt(input.value, 10);
            } else if (ptype === 'number') {
                if (input.value !== '') params[name] = parseFloat(input.value);
            } else {
                if (input.value !== '') params[name] = input.value;
            }
        });
        return params;
    },

    _collectFormPayload(silent = false) {
        const name = document.getElementById('task-name').value;
        if (!name && !silent) { UI.showToast('error', 'Error', 'Task name required'); return null; }
        const sel = document.getElementById('task-outputs');
        const output_connections = Array.from(sel.querySelectorAll('.conn-chip.active')).map(chip => parseInt(chip.dataset.id));
        const schedType = document.getElementById('task-schedule-type').value;
        let schedule = { schedule_type: schedType };
        const mr = document.getElementById('max-runs').value;
        if (mr) schedule.max_runs = parseInt(mr);
        if (schedType === 'once') {
            const d = document.getElementById('run-at').value;
            if (!d && !silent) { UI.showToast('error', 'Error', 'Run At required for one-time task'); return null; }
            if (d) schedule.run_at = new Date(d).toISOString();
        } else if (schedType === 'interval') {
            schedule.interval_seconds = parseInt(document.getElementById('interval-sec').value) || 3600;
        } else if (schedType === 'cron') {
            schedule.cron_expression = document.getElementById('cron-expr').value;
        }
        const steps = [];
        let hasError = false;
        document.querySelectorAll('#task-steps-container .task-step').forEach(div => {
            const type = div.querySelector('.step-type').value;
            if (type === 'prompt') {
                const txt = div.querySelector('.step-prompt').value;
                if (!txt) hasError = true;
                steps.push({ type: 'prompt', prompt_text: txt });
            } else {
                const tn = div.querySelector('.step-tool-name').value;
                const params = this._collectStepParams(div);
                steps.push({ type: 'tool', tool_name: tn, parameters: params });
            }
        });
        if (hasError && !silent) { UI.showToast('error', 'Error', 'All prompt steps must have text'); return null; }
        return {
            name,
            description: document.getElementById('task-desc').value,
            is_active: document.getElementById('task-active').checked,
            steps,
            schedule,
            output_connections,
        };
    },

    async saveTask() {
        const activeTab = document.querySelector('.task-tab-btn.active')?.dataset.tab;
        let payload;
        const id = document.getElementById('task-id').value;

        if (activeTab === 'json') {
            const errEl = document.getElementById('task-json-error');
            try {
                payload = JSON.parse(document.getElementById('task-json-editor').value);
                errEl.style.display = 'none';
            } catch(e) {
                errEl.textContent = 'Invalid JSON: ' + e.message;
                errEl.style.display = 'block';
                return;
            }
        } else {
            payload = this._collectFormPayload();
            if (!payload) return;
        }

        try {
            let savedId = id;
            if (id) {
                await Api.updateTask(id, payload);
                UI.showToast('success', 'Updated', 'Task updated successfully');
            } else {
                const created = await Api.createTask(payload);
                savedId = created.id;
                UI.showToast('success', 'Created', 'Task created successfully');
            }
            UI.closeModal('task-modal');
            await this.init();
            return savedId;
        } catch (error) {
            UI.showToast('error', 'Error', error.message);
            return null;
        }
    },

    async testRun() {
        const btn = document.getElementById('task-test-run-btn');
        const id = document.getElementById('task-id').value;
        btn.disabled = true;
        const original = btn.innerHTML;
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Running...';
        try {
            UI.showToast('info', 'Saving...', 'Saving task before test run');
            const savedId = await this.saveTask();
            if (!savedId) { 
                btn.disabled = false; 
                btn.innerHTML = original; 
                return; 
            }
            
            await Api.runTaskNow(savedId);
            UI.showToast('success', 'Test Run Triggered', 'Task is running in the background. Check Execution Logs for results.');
            // Note: saveTask already closes the modal and calls this.init()
        } catch (err) {
            UI.showToast('error', 'Test Run Failed', err.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = original;
        }
    },

    async showRunsModal(taskId) {
        try {
            const runs = await Api.getTaskRuns(taskId);
            const container = document.getElementById('task-runs-list');
            if (runs.length === 0) {
                container.innerHTML = '<p class="text-muted">No runs executed yet.</p>';
            } else {
                container.innerHTML = runs.map(r => `
                    <div class="glass-card" style="margin-bottom: 1rem; padding: 1rem;">
                        <div style="display: flex; justify-content: space-between;">
                            <strong>Run #${r.id}</strong>
                            <span class="badge ${r.status === 'completed' ? 'success' : (r.status === 'running' ? 'info' : 'danger')}">${r.status}</span>
                        </div>
                        <p><small>${new Date(r.created_at).toLocaleString()}</small></p>
                        ${r.error_message ? `<p class="text-danger" style="margin-top:0.5rem;">${UI.escapeHtml(r.error_message)}</p>` : ''}
                        <details style="margin-top: 0.5rem; cursor: pointer;">
                            <summary>View Log JSON</summary>
                            <pre style="font-size: 11px; background: rgba(0,0,0,0.5); padding: 0.5rem; border-radius: 4px; max-height: 200px; overflow: auto; margin-top: 0.5rem;">${UI.escapeHtml(JSON.stringify(r.steps_log, null, 2))}</pre>
                        </details>
                    </div>
                `).join('');
            }
            document.getElementById('task-runs-modal').classList.add('active');
        } catch(e) {
            UI.showToast('error', 'Error', 'Failed to load runs: ' + e.message);
        }
    }
};

// ============================================================================
// Global Export Injector
// ============================================================================

window.openExportModal = async function(contentDataStr, source) {
    if (!ConnectionsUI.connections.length) {
        await ConnectionsUI.loadConnections();
    }
    
    if (ConnectionsUI.connections.length === 0) {
        UI.showToast('warning', 'No Connections', 'Please create a connection first.');
        Router.navigate('connections');
        return;
    }
    
    // Remove any existing export modal to prevent duplicate IDs and dead buttons
    const existingModal = document.getElementById('export-modal');
    if (existingModal) existingModal.remove();

    const modalHtml = `
        <div class="modal-overlay active" id="export-modal" style="z-index: 10000;">
            <div class="modal glass-card">
                <div class="modal-header">
                    <h2>Export Data</h2>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>Select Target Connection</label>
                        <select id="export-target" class="input-wrapper">
                            ${ConnectionsUI.connections.filter(c => c.is_active).map(c => 
                                `<option value="${c.id}">${UI.escapeHtml(c.name)} (${c.conn_type})</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-primary" id="confirm-export-btn">Send Export</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    document.getElementById('confirm-export-btn').onclick = async (e) => {
        const btn = e.target;
        const connId = parseInt(document.getElementById('export-target').value);
        if (!connId) return;
        
        btn.disabled = true;
        btn.textContent = 'Sending...';
        
        try {
            const parsedData = JSON.parse(decodeURIComponent(contentDataStr));
            await Api.exportData(connId, parsedData, source);
            UI.showToast('success', 'Exported', 'Data successfully sent to connection.');
            document.getElementById('export-modal').remove();
        } catch (error) {
            UI.showToast('error', 'Export Failed', error.message);
            btn.disabled = false;
            btn.textContent = 'Send Export';
        }
    };
};
