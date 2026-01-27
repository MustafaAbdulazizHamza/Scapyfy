const API_BASE_URL = window.location.origin;
const AppState = {
    token: localStorage.getItem('scapyfy_token'),
    user: JSON.parse(localStorage.getItem('scapyfy_user') || 'null'),
    currentView: 'chat',
    provider: 'auto',
    isLoading: false,
    chatHistory: [],
    sessionHistory: [],
};
function getUserHistoryKey(userId) {
    return `scapyfy_history_user_${userId}`;
}
function isRootUser(user) {
    return user && user.id === 0 && user.username === 'root';
}
function loadUserHistory() {
    if (AppState.user && AppState.user.id !== undefined) {
        const key = getUserHistoryKey(AppState.user.id);
        AppState.sessionHistory = JSON.parse(localStorage.getItem(key) || '[]');
    } else {
        AppState.sessionHistory = [];
    }
}
function saveUserHistory() {
    if (AppState.user && AppState.user.id !== undefined) {
        const key = getUserHistoryKey(AppState.user.id);
        localStorage.setItem(key, JSON.stringify(AppState.sessionHistory));
    }
}
const Router = {
    routes: ['chat', 'history', 'tools', 'admin'],
    init() {
        window.addEventListener('hashchange', () => this.handleRoute());
        this.handleRoute();
    },
    navigate(route) {
        if (this.routes.includes(route)) {
            window.location.hash = `#/${route}`;
        }
    },
    getCurrentRoute() {
        const hash = window.location.hash;
        if (hash && hash.startsWith('#/')) {
            const route = hash.slice(2); // Remove '#/'
            if (this.routes.includes(route)) {
                return route;
            }
        }
        return 'chat';
    },
    handleRoute() {
        if (!AppState.token || !AppState.user) {
            return;
        }
        const route = this.getCurrentRoute();
        if (route === 'admin' && !isRootUser(AppState.user)) {
            this.navigate('chat');
            UI.showToast('error', 'Access Denied', 'Only root user can access admin panel');
            return;
        }
        UI.switchViewInternal(route);
    },
    setRoute(route) {
        if (this.routes.includes(route)) {
            history.replaceState(null, '', `#/${route}`);
        }
    }
};
const Api = {
    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };
        if (AppState.token) {
            headers['Authorization'] = `Bearer ${AppState.token}`;
        }
        try {
            const response = await fetch(url, {
                ...options,
                headers,
            });
            if (response.status === 401) {
                this.handleUnauthorized();
                throw new Error('Unauthorized');
            }
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'Request failed');
            }
            return data;
        } catch (error) {
            if (error.message === 'Failed to fetch') {
                throw new Error('Cannot connect to server. Is the API running?');
            }
            throw error;
        }
    },
    handleUnauthorized() {
        AppState.token = null;
        AppState.user = null;
        localStorage.removeItem('scapyfy_token');
        localStorage.removeItem('scapyfy_user');
        UI.showLoginPage();
    },
    async login(username, password) {
        const data = await this.request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        return data;
    },
    async getCurrentUser() {
        return await this.request('/users/me');
    },
    async changePassword(currentPassword, newPassword) {
        return await this.request('/users/change-password', {
            method: 'PUT',
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword,
            }),
        });
    },
    async getProviders() {
        return await this.request('/providers');
    },
    async getStatus() {
        return await this.request('/status');
    },
    async craft(prompt, maxIterations = 10, provider = null) {
        return await this.request('/craft', {
            method: 'POST',
            body: JSON.stringify({
                prompt,
                max_iterations: maxIterations,
                provider: provider === 'auto' ? null : provider,
            }),
        });
    },
    async listTools() {
        return await this.request('/tools/list');
    },
    async getToolInfo(toolName) {
        return await this.request(`/tools/${toolName}`);
    },
    async executeTool(toolName, parameters) {
        return await this.request('/tools/execute', {
            method: 'POST',
            body: JSON.stringify({
                tool_name: toolName,
                parameters: parameters,
            }),
        });
    },
    async listUsers() {
        return await this.request('/users/list');
    },
    async createUser(username, email, password) {
        return await this.request('/users/create', {
            method: 'POST',
            body: JSON.stringify({ username, email, password }),
        });
    },
    async adminChangePassword(userId, newPassword) {
        return await this.request(`/users/admin/change-password/${userId}`, {
            method: 'PUT',
            body: JSON.stringify({ new_password: newPassword }),
        });
    },
    async toggleUserActive(userId) {
        return await this.request(`/users/admin/toggle-active/${userId}`, {
            method: 'PUT',
        });
    },
    async deleteUser(userId) {
        return await this.request(`/users/admin/delete/${userId}`, {
            method: 'DELETE',
        });
    },
};
const UI = {
    elements: {},
    init() {
        this.elements = {
            loadingScreen: document.getElementById('loading-screen'),
            loginPage: document.getElementById('login-page'),
            mainApp: document.getElementById('main-app'),
            loginForm: document.getElementById('login-form'),
            loginError: document.getElementById('login-error'),
            loginErrorText: document.getElementById('login-error-text'),
            sidebar: document.getElementById('sidebar'),
            sidebarToggle: document.getElementById('sidebar-toggle'),
            sidebarOverlay: document.getElementById('sidebar-overlay'),
            mobileMenuBtn: document.getElementById('mobile-menu-btn'),
            navItems: document.querySelectorAll('.nav-item'),
            views: document.querySelectorAll('.view'),
            chatMessages: document.getElementById('chat-messages'),
            chatInput: document.getElementById('chat-input'),
            sendBtn: document.getElementById('send-btn'),
            clearHistoryBtn: document.getElementById('clear-history-btn'),
            maxIterations: document.getElementById('max-iterations'),
            llmProvider: document.getElementById('llm-provider'),
            providerStatusText: document.getElementById('provider-status-text'),
            userProfileBtn: document.getElementById('user-profile-btn'),
            profileModal: document.getElementById('profile-modal'),
            closeProfileModal: document.getElementById('close-profile-modal'),
            changePasswordForm: document.getElementById('change-password-form'),
            passwordMessage: document.getElementById('password-message'),
            logoutBtn: document.getElementById('logout-btn'),
            historyList: document.getElementById('history-list'),
            toastContainer: document.getElementById('toast-container'),
        };
        this.bindEvents();
        this.checkAuth();
    },
    bindEvents() {
        this.elements.loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            Auth.login();
        });
        document.querySelectorAll('.toggle-password').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const input = e.target.closest('.input-wrapper').querySelector('input');
                input.type = input.type === 'password' ? 'text' : 'password';
            });
        });
        this.elements.sidebarToggle.addEventListener('click', () => {
            this.elements.sidebar.classList.toggle('collapsed');
        });
        if (this.elements.mobileMenuBtn) {
            this.elements.mobileMenuBtn.addEventListener('click', () => {
                this.toggleMobileSidebar();
            });
        }
        if (this.elements.sidebarOverlay) {
            this.elements.sidebarOverlay.addEventListener('click', () => {
                this.closeMobileSidebar();
            });
        }
        this.elements.navItems.forEach(item => {
            item.addEventListener('click', () => {
                const view = item.dataset.view;
                this.switchView(view);
                this.closeMobileSidebar();
            });
        });
        this.elements.sendBtn.addEventListener('click', () => Chat.send());
        this.elements.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                Chat.send();
            }
        });
        this.elements.chatInput.addEventListener('input', () => {
            this.autoResizeTextarea(this.elements.chatInput);
        });
        this.elements.clearHistoryBtn.addEventListener('click', () => {
            if (confirm('Clear all session history? This cannot be undone.')) {
                AppState.sessionHistory = [];
                localStorage.removeItem('scapyfy_history');
                this.renderHistory();
                Toast.show('History cleared', 'success');
            }
        });
        this.elements.llmProvider.addEventListener('change', (e) => {
            AppState.provider = e.target.value;
            this.updateProviderStatus();
        });
        this.elements.userProfileBtn.addEventListener('click', () => {
            this.openProfileModal();
        });
        this.elements.closeProfileModal.addEventListener('click', () => {
            this.closeProfileModal();
        });
        this.elements.profileModal.addEventListener('click', (e) => {
            if (e.target === this.elements.profileModal) {
                this.closeProfileModal();
            }
        });
        this.elements.changePasswordForm.addEventListener('submit', (e) => {
            e.preventDefault();
            Profile.changePassword();
        });
        this.elements.logoutBtn.addEventListener('click', () => Auth.logout());
    },
    async checkAuth() {
        setTimeout(() => {
            this.elements.loadingScreen.classList.add('fade-out');
        }, 800);
        setTimeout(() => {
            this.elements.loadingScreen.classList.add('hidden');
            if (AppState.token && AppState.user) {
                loadUserHistory();
                this.showMainApp();
                this.updateUserInfo();
                this.updateProviderStatus();
            } else {
                this.showLoginPage();
            }
        }, 1200);
    },
    showLoginPage() {
        this.elements.loginPage.classList.remove('hidden');
        this.elements.mainApp.classList.add('hidden');
    },
    showMainApp() {
        this.elements.loginPage.classList.add('hidden');
        this.elements.mainApp.classList.remove('hidden');
        this.renderHistory();
        DirectTools.init();
        if (isRootUser(AppState.user)) {
            Admin.init();
        }
        Router.init();
    },
    switchView(viewName) {
        Router.navigate(viewName);
    },
    switchViewInternal(viewName) {
        AppState.currentView = viewName;
        this.elements.navItems.forEach(item => {
            item.classList.toggle('active', item.dataset.view === viewName);
        });
        this.elements.views.forEach(view => {
            view.classList.toggle('active', view.id === `${viewName}-view`);
        });
        if (viewName === 'admin' && isRootUser(AppState.user)) {
            Admin.init();
            Admin.loadUsers();
        }
    },
    updateUserInfo() {
        if (!AppState.user) return;
        const initial = AppState.user.username.charAt(0).toUpperCase();
        const isAdmin = isRootUser(AppState.user);
        const role = isAdmin ? 'Root Admin' : 'User';
        document.getElementById('user-initial').textContent = initial;
        document.getElementById('user-display-name').textContent = AppState.user.username;
        document.getElementById('user-role').textContent = role;
        const adminNavItem = document.querySelector('.nav-item.admin-only');
        if (adminNavItem) {
            adminNavItem.classList.toggle('hidden', !isAdmin);
        }
    },
    async updateProviderStatus() {
        const statusDot = document.querySelector('.status-dot');
        const statusText = this.elements.providerStatusText;
        const providerSelect = this.elements.llmProvider;

        const allProviders = [
            { value: 'auto', label: 'Auto (Best Available)', alwaysEnabled: true },
            { value: 'openai', label: 'OpenAI GPT' },
            { value: 'gemini', label: 'Google Gemini' },
            { value: 'claude', label: 'Anthropic Claude' },
            { value: 'ollama', label: 'Ollama (Local)' }
        ];

        try {
            const status = await Api.getStatus();
            const availableProviders = status.available_providers || [];

            statusDot.classList.add('connected');
            statusDot.classList.remove('disconnected');

            if (availableProviders.length > 0) {
                statusText.textContent = `${availableProviders.length} provider(s) available`;
            } else {
                statusText.textContent = 'Ready';
            }

            const currentValue = providerSelect.value;
            providerSelect.innerHTML = '';

            allProviders.forEach(provider => {
                const option = document.createElement('option');
                option.value = provider.value;

                const isAvailable = provider.alwaysEnabled || availableProviders.includes(provider.value);

                if (isAvailable) {
                    option.textContent = provider.label;
                    option.disabled = false;
                } else {
                    option.textContent = `${provider.label} ⛔ (unavailable)`;
                    option.disabled = true;
                    option.style.color = '#666';
                }

                providerSelect.appendChild(option);
            });

            if (currentValue && !providerSelect.querySelector(`option[value="${currentValue}"]`)?.disabled) {
                providerSelect.value = currentValue;
            } else {
                providerSelect.value = 'auto';
            }

        } catch (error) {
            statusDot.classList.add('disconnected');
            statusDot.classList.remove('connected');
            statusText.textContent = 'Disconnected';
        }
    },
    openProfileModal() {
        if (!AppState.user) return;
        const initial = AppState.user.username.charAt(0).toUpperCase();
        document.getElementById('modal-user-initial').textContent = initial;
        document.getElementById('modal-username').textContent = AppState.user.username;
        document.getElementById('modal-email').textContent = AppState.user.email || 'Not available';
        document.getElementById('modal-user-id').textContent = AppState.user.id;
        document.getElementById('modal-status').textContent = 'Active';
        this.elements.profileModal.classList.add('active');
    },
    closeProfileModal() {
        this.elements.profileModal.classList.remove('active');
        this.elements.changePasswordForm.reset();
        this.elements.passwordMessage.classList.add('hidden');
    },
    toggleMobileSidebar() {
        this.elements.sidebar.classList.toggle('open');
        this.elements.sidebarOverlay?.classList.toggle('active');
        document.body.style.overflow = this.elements.sidebar.classList.contains('open') ? 'hidden' : '';
    },
    closeMobileSidebar() {
        this.elements.sidebar.classList.remove('open');
        this.elements.sidebarOverlay?.classList.remove('active');
        document.body.style.overflow = '';
    },
    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    },
    renderHistory() {
        const container = this.elements.historyList;
        if (AppState.sessionHistory.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <h3>No history yet</h3>
                    <p>Your packet crafting sessions will appear here</p>
                </div>
            `;
            return;
        }
        container.innerHTML = AppState.sessionHistory.map((item, index) => `
            <div class="history-item" onclick="Chat.loadFromHistory(${index})">
                <div class="history-item-header">
                    <span class="history-item-prompt">${this.escapeHtml(item.prompt.substring(0, 50))}${item.prompt.length > 50 ? '...' : ''}</span>
                    <span class="history-item-time">${this.formatTime(item.timestamp)}</span>
                </div>
                <p class="history-item-preview">${this.escapeHtml(item.response.substring(0, 100))}${item.response.length > 100 ? '...' : ''}</p>
            </div>
        `).join('');
    },
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return date.toLocaleDateString();
    },
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    showToast(type, title, message, duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icons = {
            success: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
            error: '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
            warning: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
            info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
        };
        toast.innerHTML = `
            <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                ${icons[type]}
            </svg>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        `;
        this.elements.toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },
};
const Auth = {
    async login() {
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        const submitBtn = UI.elements.loginForm.querySelector('button[type="submit"]');
        UI.elements.loginError.classList.add('hidden');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Signing in...</span>';
        try {
            const data = await Api.login(username, password);
            AppState.token = data.access_token;
            AppState.user = {
                id: data.user_id,
                username: data.username,
            };
            localStorage.setItem('scapyfy_token', data.access_token);
            localStorage.setItem('scapyfy_user', JSON.stringify(AppState.user));
            try {
                const userInfo = await Api.getCurrentUser();
                AppState.user = userInfo;
                localStorage.setItem('scapyfy_user', JSON.stringify(userInfo));
            } catch (e) {
            }
            loadUserHistory();
            UI.showMainApp();
            UI.updateUserInfo();
            UI.updateProviderStatus();
            UI.showToast('success', 'Welcome!', `Signed in as ${AppState.user.username}`);
        } catch (error) {
            UI.elements.loginError.classList.remove('hidden');
            document.getElementById('login-error-text').textContent = error.message;
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `
                <span>Sign In</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
            `;
        }
    },
    logout() {
        AppState.token = null;
        AppState.user = null;
        AppState.chatHistory = [];
        AppState.sessionHistory = [];
        localStorage.removeItem('scapyfy_token');
        localStorage.removeItem('scapyfy_user');
        history.replaceState(null, '', window.location.pathname);
        UI.closeProfileModal();
        UI.showLoginPage();
        UI.elements.loginForm.reset();
        Chat.clear();
        UI.showToast('info', 'Signed Out', 'You have been logged out');
    },
};
const Profile = {
    async changePassword() {
        const currentPassword = document.getElementById('current-password').value;
        const newPassword = document.getElementById('new-password').value;
        const confirmPassword = document.getElementById('confirm-password').value;
        const messageEl = UI.elements.passwordMessage;
        const submitBtn = UI.elements.changePasswordForm.querySelector('button[type="submit"]');
        if (newPassword !== confirmPassword) {
            messageEl.textContent = 'New passwords do not match';
            messageEl.className = 'form-message error';
            messageEl.classList.remove('hidden');
            return;
        }
        if (newPassword.length < 8) {
            messageEl.textContent = 'Password must be at least 8 characters';
            messageEl.className = 'form-message error';
            messageEl.classList.remove('hidden');
            return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = 'Updating...';
        try {
            await Api.changePassword(currentPassword, newPassword);
            messageEl.textContent = 'Password updated successfully!';
            messageEl.className = 'form-message success';
            messageEl.classList.remove('hidden');
            UI.elements.changePasswordForm.reset();
            UI.showToast('success', 'Success', 'Your password has been updated');
        } catch (error) {
            messageEl.textContent = error.message;
            messageEl.className = 'form-message error';
            messageEl.classList.remove('hidden');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Update Password';
        }
    },
};
const Chat = {
    addMessage(type, content, sender = null) {
        const welcomeMsg = UI.elements.chatMessages.querySelector('.welcome-message');
        if (welcomeMsg) welcomeMsg.remove();
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const avatar = type === 'user' ? AppState.user?.username?.charAt(0).toUpperCase() || 'U' : '🧙‍♂️';
        const senderName = type === 'user' ? (AppState.user?.username || 'You') : 'Prof. Packet Crafter';
        const messageEl = document.createElement('div');
        messageEl.className = `message ${type}`;
        messageEl.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-sender">${senderName}</span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-body">${this.formatMessage(content)}</div>
            </div>
        `;
        UI.elements.chatMessages.appendChild(messageEl);
        UI.elements.chatMessages.scrollTop = UI.elements.chatMessages.scrollHeight;
        return messageEl;
    },
    addLoadingMessage() {
        const messageEl = document.createElement('div');
        messageEl.className = 'message assistant loading';
        messageEl.id = 'loading-message';
        messageEl.innerHTML = `
            <div class="message-avatar">🧙‍♂️</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-sender">Prof. Packet Crafter</span>
                </div>
                <div class="message-body">
                    <div class="typing-indicator">
                        <span></span><span></span><span></span>
                    </div>
                    <span>Analyzing and crafting...</span>
                </div>
            </div>
        `;
        UI.elements.chatMessages.appendChild(messageEl);
        UI.elements.chatMessages.scrollTop = UI.elements.chatMessages.scrollHeight;
    },
    removeLoadingMessage() {
        const loadingMsg = document.getElementById('loading-message');
        if (loadingMsg) loadingMsg.remove();
    },
    formatMessage(content) {
        content = content.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre><code class="language-${lang}">${this.escapeHtml(code.trim())}</code></pre>`;
        });
        content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
        content = content.replace(/\n/g, '<br>');
        return content;
    },
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    async send() {
        const prompt = UI.elements.chatInput.value.trim();
        if (!prompt || AppState.isLoading) return;
        const maxIterations = parseInt(UI.elements.maxIterations.value) || 10;
        const provider = AppState.provider;
        this.addMessage('user', prompt);
        UI.elements.chatInput.value = '';
        UI.autoResizeTextarea(UI.elements.chatInput);
        AppState.isLoading = true;
        UI.elements.sendBtn.disabled = true;
        this.addLoadingMessage();
        try {
            const response = await Api.craft(prompt, maxIterations, provider);
            this.removeLoadingMessage();
            const reportContent = response.report || 'Task completed';
            this.addMessage('assistant', reportContent);
            this.saveToHistory(prompt, reportContent);
        } catch (error) {
            this.removeLoadingMessage();
            this.addMessage('assistant', `❌ Error: ${error.message}`);
            UI.showToast('error', 'Error', error.message);
        } finally {
            AppState.isLoading = false;
            UI.elements.sendBtn.disabled = false;
        }
    },
    clear() {
        UI.elements.chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">🧙‍♂️</div>
                <h3>Welcome to Scapyfy</h3>
                <p>I'm your AI-powered packet crafting assistant. I can help you with:</p>
                <div class="capabilities-grid">
                    <div class="capability-card">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                        </svg>
                        <span>Packet Crafting</span>
                    </div>
                    <div class="capability-card">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="2" y1="12" x2="22" y2="12"/>
                            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                        </svg>
                        <span>Network Scanning</span>
                    </div>
                    <div class="capability-card">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                        </svg>
                        <span>Traceroute</span>
                    </div>
                    <div class="capability-card">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                            <line x1="8" y1="21" x2="16" y2="21"/>
                            <line x1="12" y1="17" x2="12" y2="21"/>
                        </svg>
                        <span>Port Scanning</span>
                    </div>
                </div>
                <p class="welcome-hint">Try asking: "Scan ports 22, 80, and 443 on 192.168.1.1"</p>
            </div>
        `;
        AppState.chatHistory = [];
    },
    saveToHistory(prompt, response) {
        const historyItem = {
            prompt,
            response,
            timestamp: new Date().toISOString(),
            provider: AppState.provider,
        };
        AppState.sessionHistory.unshift(historyItem);
        if (AppState.sessionHistory.length > 50) {
            AppState.sessionHistory = AppState.sessionHistory.slice(0, 50);
        }
        saveUserHistory();
        UI.renderHistory();
    },
    loadFromHistory(index) {
        const item = AppState.sessionHistory[index];
        if (!item) return;
        UI.switchView('chat');
        this.clear();
        this.addMessage('user', item.prompt);
        this.addMessage('assistant', item.response);
    },
};
const DirectTools = {
    tools: [],
    currentTool: null,
    currentExample: null,
    toolDisplayInfo: {
        'ping_host': {
            name: 'Ping Host',
            description: 'Test if a host is reachable by sending ICMP echo requests. Returns response times and packet statistics.',
            icon: '📡',
            docs: `
                <h5>📡 Ping Host</h5>
                <p>Sends ICMP Echo Request packets to test network connectivity and measure round-trip time.</p>
                <h6>Parameters:</h6>
                <ul>
                    <li><strong>Target Host</strong> <span class="required-tag">Required</span><br>
                        IP address (e.g., <code>192.168.1.1</code>) or hostname (e.g., <code>google.com</code>)</li>
                    <li><strong>Packet Count</strong> <span class="optional-tag">Optional</span><br>
                        Number of ping requests to send (1-20). Default: 4</li>
                    <li><strong>Timeout</strong> <span class="optional-tag">Optional</span><br>
                        Seconds to wait for each response (1-10). Default: 2</li>
                </ul>
                <h6>Example Output:</h6>
                <p>Shows RTT min/avg/max and packet loss percentage.</p>
            `
        },
        'nmap_scan': {
            name: 'NMAP Scanner',
            description: 'Powerful network scanner for port discovery, service detection, and OS fingerprinting.',
            icon: '🔍',
            docs: `
                <h5>🔍 NMAP Scanner</h5>
                <p>Industry-standard network scanner. Requires NMAP to be installed on the server.</p>
                <h6>Parameters:</h6>
                <ul>
                    <li><strong>Target Host</strong> <span class="required-tag">Required</span><br>
                        IP address, hostname, or CIDR range (e.g., <code>192.168.1.0/24</code>)</li>
                    <li><strong>Scan Type</strong> <span class="optional-tag">Optional</span><br>
                        <code>basic</code> - Standard TCP connect scan<br>
                        <code>quick</code> - Ping scan only (host discovery)<br>
                        <code>intense</code> - SYN scan with version detection<br>
                        <code>version</code> - Service version detection<br>
                        <code>os</code> - OS fingerprinting (requires root)</li>
                    <li><strong>Ports</strong> <span class="optional-tag">Optional</span><br>
                        Comma-separated list or range: <code>22,80,443</code> or <code>1-1000</code></li>
                    <li><strong>Additional Arguments</strong> <span class="optional-tag">Optional</span><br>
                        Safe args only: <code>-v</code>, <code>-Pn</code>, <code>--open</code></li>
                </ul>
            `
        },
        'traceroute_host': {
            name: 'Traceroute',
            description: 'Discover the network path to a target by showing each hop along the route.',
            icon: '🌐',
            docs: `
                <h5>🌐 Traceroute</h5>
                <p>Maps the route packets take to reach a destination, showing each router hop.</p>
                <h6>Parameters:</h6>
                <ul>
                    <li><strong>Target Host</strong> <span class="required-tag">Required</span><br>
                        IP address or hostname to trace</li>
                    <li><strong>Maximum Hops</strong> <span class="optional-tag">Optional</span><br>
                        Max number of hops to trace (1-64). Default: 30</li>
                    <li><strong>Use Scapy</strong> <span class="optional-tag">Optional</span><br>
                        Use Scapy's traceroute or system traceroute command</li>
                </ul>
                <h6>Output:</h6>
                <p>Lists each hop with IP address and response time.</p>
            `
        },
        'hping3_probe': {
            name: 'Hping3 Probe',
            description: 'Advanced packet probing tool for TCP/UDP/ICMP testing with custom flags.',
            icon: '⚡',
            docs: `
                <h5>⚡ Hping3 Probe</h5>
                <p>Advanced packet crafting tool for security testing. Requires hping3 installed.</p>
                <h6>Parameters:</h6>
                <ul>
                    <li><strong>Target Host</strong> <span class="required-tag">Required</span><br>
                        IP address or hostname to probe</li>
                    <li><strong>Probe Mode</strong> <span class="optional-tag">Optional</span><br>
                        <code>syn</code> - TCP SYN packets (default)<br>
                        <code>ack</code> - TCP ACK packets<br>
                        <code>fin</code> - TCP FIN packets<br>
                        <code>udp</code> - UDP packets<br>
                        <code>icmp</code> - ICMP packets</li>
                    <li><strong>Target Port</strong> <span class="optional-tag">Optional</span><br>
                        Port number (1-65535). Default: 80</li>
                    <li><strong>Packet Count</strong> <span class="optional-tag">Optional</span><br>
                        Number of packets to send (1-100). Default: 4</li>
                    <li><strong>TCP Flags</strong> <span class="optional-tag">Optional</span><br>
                        Custom flags: S(YN), A(CK), F(IN), R(ST), U(RG), P(SH)</li>
                    <li><strong>Additional Arguments</strong> <span class="optional-tag">Optional</span><br>
                        Extra hping3 CLI arguments for advanced operations:<br>
                        <code>-i u1000</code> - Set interval (microseconds)<br>
                        <code>--ttl 64</code> - Set TTL value<br>
                        <code>-d 100</code> - Send data bytes<br>
                        <code>-a 1.2.3.4</code> - Spoof source IP<br>
                        <code>-T</code> - Traceroute mode<br>
                        <code>--rand-source</code> - Random source IP<br>
                        <code>-s 12345</code> - Base source port<br>
                        <code>-f</code> - Fragment packets</li>
                </ul>
            `
        },
        'quick_port_scan': {
            name: 'Quick Port Scan',
            description: 'Fast TCP port scanner using Scapy. Check if specific ports are open on a target.',
            icon: '🚪',
            docs: `
                <h5>🚪 Quick Port Scan</h5>
                <p>Lightweight TCP port scanner using Scapy. Sends SYN packets and checks for SYN-ACK responses.</p>
                <h6>Parameters:</h6>
                <ul>
                    <li><strong>Target Host</strong> <span class="required-tag">Required</span><br>
                        IP address to scan (e.g., <code>192.168.1.1</code>)</li>
                    <li><strong>Ports to Scan</strong> <span class="optional-tag">Optional</span><br>
                        Comma-separated port list. Default: <code>22,80,443,8080,8443</code><br>
                        Maximum 50 ports per scan</li>
                </ul>
                <h6>Output:</h6>
                <p>Shows each port status: OPEN, CLOSED, or FILTERED</p>
            `
        },
        'arp_scan': {
            name: 'ARP Scanner',
            description: 'Discover devices on your local network by sending ARP requests.',
            icon: '📋',
            docs: `
                <h5>📋 ARP Scanner</h5>
                <p>Discovers hosts on your local network segment using ARP (Address Resolution Protocol).</p>
                <h6>Parameters:</h6>
                <ul>
                    <li><strong>Network Range</strong> <span class="optional-tag">Optional</span><br>
                        CIDR notation (e.g., <code>192.168.1.0/24</code>)<br>
                        Default: <code>192.168.1.0/24</code></li>
                </ul>
                <h6>Output:</h6>
                <p>Lists discovered hosts with their IP and MAC addresses.</p>
                <h6>⚠️ Note:</h6>
                <p>Only works on local network (same subnet). Requires appropriate permissions.</p>
            `
        },
        'send_packet': {
            name: 'Send Custom Packet',
            description: 'Craft and send custom network packets with Scapy. Define IP, TCP, UDP, ICMP layers.',
            icon: '📦',
            docs: `
                <h5>📦 Send Custom Packet</h5>
                <p>Create and send arbitrary network packets using Scapy's packet crafting engine.</p>
                <h6>Parameters:</h6>
                <ul>
                    <li><strong>Packet Description (JSON)</strong> <span class="required-tag">Required</span><br>
                        JSON object defining packet layers. Example:<br>
                        <code>{"IP": {"dst": "192.168.1.1"}, "ICMP": {}}</code><br>
                        <code>{"IP": {"dst": "192.168.1.1"}, "TCP": {"dport": 80, "flags": "S"}}</code></li>
                    <li><strong>Use Ethernet Layer</strong> <span class="optional-tag">Optional</span><br>
                        Enable for Layer 2 packets with Ether header</li>
                    <li><strong>Wait for Response</strong> <span class="optional-tag">Optional</span><br>
                        If enabled, waits for and returns response packet</li>
                </ul>
                <h6>Supported Layers:</h6>
                <p><code>Ether</code>, <code>IP</code>, <code>ARP</code>, <code>TCP</code>, <code>UDP</code>, <code>ICMP</code>, <code>Raw</code></p>
            `
        },
        'dns_lookup_tool': {
            name: 'DNS Lookup',
            description: 'Query DNS records for any domain. Supports A, AAAA, MX, NS, TXT, SOA, CNAME, PTR, SRV, CAA.',
            icon: '🔎',
            docs: `
                <h5>🔎 DNS Lookup</h5>
                <p>Perform comprehensive DNS queries for multiple record types.</p>
                <h6>Parameters:</h6>
                <ul>
                    <li><strong>Target</strong> <span class="required-tag">Required</span><br>
                        Domain name to query (e.g., <code>google.com</code>)</li>
                    <li><strong>Record Types</strong> <span class="optional-tag">Optional</span><br>
                        Comma-separated list of record types:<br>
                        <code>A</code> - IPv4 addresses<br>
                        <code>AAAA</code> - IPv6 addresses<br>
                        <code>MX</code> - Mail servers<br>
                        <code>NS</code> - Name servers<br>
                        <code>TXT</code> - Text records (SPF, DKIM, etc.)<br>
                        <code>SOA</code> - Start of Authority<br>
                        <code>CNAME</code> - Canonical names<br>
                        <code>PTR</code> - Reverse DNS<br>
                        <code>SRV</code> - Service records<br>
                        <code>CAA</code> - Certificate Authority Authorization</li>
                    <li><strong>Nameserver</strong> <span class="optional-tag">Optional</span><br>
                        Custom DNS server (e.g., <code>8.8.8.8</code>, <code>1.1.1.1</code>)</li>
                </ul>
            `
        }
    },
    getDisplayName(toolName) {
        return this.toolDisplayInfo[toolName]?.name ||
            toolName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    },
    getDisplayDescription(toolName, originalDesc) {
        return this.toolDisplayInfo[toolName]?.description || originalDesc;
    },
    getToolDocs(toolName) {
        return this.toolDisplayInfo[toolName]?.docs || '';
    },
    formatToolResult(toolName, result) {
        if (typeof result === 'string') return this.escapeHtml(result);
        const data = result.result || result;
        const success = data.success !== false;
        const statusIcon = success ? '✅' : '❌';
        const statusClass = success ? 'success' : 'error';
        let html = `<div class="result-header ${statusClass}">${statusIcon} ${success ? 'Success' : 'Failed'}</div>`;
        if (data.target) {
            html += `<div class="result-row"><span class="result-label">Target:</span> <span class="result-value">${this.escapeHtml(data.target)}</span></div>`;
        }
        if (toolName === 'ping_host') {
            if (data.packets_sent !== undefined) {
                html += `<div class="result-row"><span class="result-label">Packets:</span> <span class="result-value">${data.packets_received}/${data.packets_sent} received (${data.packet_loss}% loss)</span></div>`;
            }
            if (data.rtt_avg !== undefined && data.rtt_avg !== null) {
                html += `<div class="result-row"><span class="result-label">RTT:</span> <span class="result-value">min=${data.rtt_min}ms, avg=${data.rtt_avg}ms, max=${data.rtt_max}ms</span></div>`;
            }
        } else if (toolName === 'traceroute_host') {
            if (data.hops && data.hops.length > 0) {
                html += `<div class="result-section"><span class="result-label">Hops (${data.hops.length}):</span></div>`;
                html += `<table class="result-table"><thead><tr><th>#</th><th>Hostname</th><th>IP Address</th><th>RTT</th></tr></thead><tbody>`;
                data.hops.forEach(hop => {
                    const hostname = hop.hostname && hop.hostname !== hop.ip ? hop.hostname : '-';
                    html += `<tr><td>${hop.hop}</td><td>${this.escapeHtml(hostname)}</td><td>${this.escapeHtml(hop.ip || '*')}</td><td>${this.escapeHtml(hop.rtt || '*')}</td></tr>`;
                });
                html += `</tbody></table>`;
            } else {
                html += `<div class="result-row"><span class="result-label">Hops:</span> <span class="result-value">No hops recorded</span></div>`;
            }
        } else if (toolName === 'nmap_scan') {
            if (data.scan_type) {
                html += `<div class="result-row"><span class="result-label">Scan Type:</span> <span class="result-value">${this.escapeHtml(data.scan_type)}</span></div>`;
            }
            if (data.open_ports && data.open_ports.length > 0) {
                html += `<div class="result-section"><span class="result-label">Open Ports:</span></div>`;
                html += `<table class="result-table"><thead><tr><th>Port</th><th>Protocol</th><th>Service</th><th>State</th></tr></thead><tbody>`;
                data.open_ports.forEach(port => {
                    html += `<tr><td>${port.port}</td><td>${port.protocol || 'tcp'}</td><td>${this.escapeHtml(port.service || '-')}</td><td class="state-${port.state || 'open'}">${port.state || 'open'}</td></tr>`;
                });
                html += `</tbody></table>`;
            } else {
                html += `<div class="result-row"><span class="result-label">Open Ports:</span> <span class="result-value">None found</span></div>`;
            }
        } else if (toolName === 'quick_port_scan') {
            if (typeof data === 'string') {
                const lines = data.split('\n').filter(l => l.trim());
                const portLines = lines.filter(l => /port\s*\d+|^\d+/i.test(l.trim()));
                if (portLines.length > 0) {
                    html += `<div class="result-section"><span class="result-label">Port Scan Results:</span></div>`;
                    html += `<table class="result-table"><thead><tr><th>Port</th><th>Protocol</th><th>State</th></tr></thead><tbody>`;
                    portLines.forEach(line => {
                        const match = line.match(/port\s*(\d+)\s*[:/]?\s*(tcp|udp)?\s*[:\-]?\s*(open|closed|filtered)/i) ||
                            line.match(/(\d+)\s*[:/]?\s*(tcp|udp)?\s*[:\-]?\s*(open|closed|filtered)/i);
                        if (match) {
                            const port = match[1];
                            const proto = match[2] || 'tcp';
                            const state = match[3].toLowerCase();
                            html += `<tr><td>${port}</td><td>${proto}</td><td class="state-${state}">${state.toUpperCase()}</td></tr>`;
                        }
                    });
                    html += `</tbody></table>`;
                } else {
                    html += `<div class="result-section"><pre class="result-pre">${this.escapeHtml(data)}</pre></div>`;
                }
            } else if (data.open_ports || data.results) {
                const ports = data.open_ports || data.results || [];
                if (ports.length > 0) {
                    html += `<div class="result-section"><span class="result-label">Port Scan Results:</span></div>`;
                    html += `<table class="result-table"><thead><tr><th>Port</th><th>Protocol</th><th>State</th></tr></thead><tbody>`;
                    ports.forEach(p => {
                        if (typeof p === 'object') {
                            html += `<tr><td>${p.port}</td><td>${p.protocol || 'tcp'}</td><td class="state-${(p.state || 'open').toLowerCase()}">${p.state || 'open'}</td></tr>`;
                        } else {
                            html += `<tr><td>${p}</td><td>tcp</td><td class="state-open">open</td></tr>`;
                        }
                    });
                    html += `</tbody></table>`;
                } else {
                    html += `<div class="result-row"><span class="result-value">No open ports found</span></div>`;
                }
            } else {
                html += `<div class="result-row"><span class="result-value">No open ports found</span></div>`;
            }
        } else if (toolName === 'arp_scan') {
            let hosts = [];
            if (typeof data === 'string') {
                const lines = data.split('\n').filter(l => l.trim());
                lines.forEach(line => {
                    const match = line.match(/IP:\s*(\d+\.\d+\.\d+\.\d+)\s+MAC:\s*([0-9a-fA-F:]{17})/i) ||
                        line.match(/(\d+\.\d+\.\d+\.\d+)\s+(?:is-at\s+)?([0-9a-fA-F:]{17}|[0-9a-fA-F-]{17})/);
                    if (match) {
                        hosts.push({ ip: match[1], mac: match[2] || '-' });
                    }
                });
                if (hosts.length === 0 && lines.length > 0) {
                    html += `<div class="result-section"><pre class="result-pre">${this.escapeHtml(data)}</pre></div>`;
                }
            } else if (data.hosts || Array.isArray(data)) {
                hosts = data.hosts || data;
            }
            if (hosts.length > 0) {
                html += `<div class="result-section"><span class="result-label">Discovered Hosts (${hosts.length}):</span></div>`;
                html += `<table class="result-table"><thead><tr><th>#</th><th>IP Address</th><th>MAC Address</th></tr></thead><tbody>`;
                hosts.forEach((h, i) => {
                    html += `<tr><td>${i + 1}</td><td>${this.escapeHtml(h.ip || h)}</td><td><code>${this.escapeHtml(h.mac || '-')}</code></td></tr>`;
                });
                html += `</tbody></table>`;
            } else if (!html.includes('result-pre')) {
                html += `<div class="result-row"><span class="result-value">No hosts found</span></div>`;
            }
        } else if (toolName === 'hping3_probe') {
            if (data.mode) {
                html += `<div class="result-row"><span class="result-label">Mode:</span> <span class="result-value">${this.escapeHtml(data.mode)}</span></div>`;
            }
            if (data.port) {
                html += `<div class="result-row"><span class="result-label">Port:</span> <span class="result-value">${data.port}</span></div>`;
            }
        } else if (toolName === 'send_packet') {
            const rawStr = typeof data === 'string' ? data : JSON.stringify(data);
            html += this.parseScapyPacket(rawStr);
        } else if (toolName === 'dns_lookup_tool') {
            const rawStr = typeof data === 'string' ? data : (data.result || JSON.stringify(data));
            html += this.formatDnsResults(rawStr);
        }
        if (data.raw_output) {
            html += `<details class="result-details"><summary>Raw Output</summary><pre class="result-pre">${this.escapeHtml(data.raw_output)}</pre></details>`;
        }
        if (!html.includes('result-row') && !html.includes('result-table') && !html.includes('result-pre') && !html.includes('packet-layer')) {
            html += `<pre class="result-pre">${this.escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
        }
        return html;
    },
    parseScapyPacket(packetStr) {
        let html = '';
        const layerRegex = /<(\w+)\s+([^|>]+)/g;
        let match;
        const layers = [];
        while ((match = layerRegex.exec(packetStr)) !== null) {
            const layerName = match[1];
            const fieldsStr = match[2].trim();
            const fields = [];
            const fieldRegex = /(\w+)=([^\s]+?)(?=\s+\w+=|$)/g;
            let fieldMatch;
            while ((fieldMatch = fieldRegex.exec(fieldsStr)) !== null) {
                fields.push({ name: fieldMatch[1], value: fieldMatch[2] });
            }
            layers.push({ name: layerName, fields });
        }
        if (layers.length === 0) {
            return `<div class="result-section"><pre class="result-pre">${this.escapeHtml(packetStr)}</pre></div>`;
        }
        html += `<div class="result-section"><span class="result-label">📦 Packet Response (${layers.length} layers):</span></div>`;
        const layerIcons = {
            'IP': '🌐', 'TCP': '🔗', 'UDP': '📨', 'ICMP': '📡', 'Ether': '🔌',
            'ARP': '📋', 'DNS': '🔍', 'Raw': '📄', 'Padding': '⬜'
        };
        const importantFields = {
            'IP': ['src', 'dst', 'proto', 'ttl', 'flags', 'len'],
            'TCP': ['sport', 'dport', 'flags', 'seq', 'ack', 'window'],
            'UDP': ['sport', 'dport', 'len'],
            'ICMP': ['type', 'code', 'id', 'seq'],
            'Ether': ['src', 'dst', 'type'],
            'ARP': ['op', 'hwsrc', 'psrc', 'hwdst', 'pdst']
        };
        const flagMeanings = {
            'S': 'SYN', 'A': 'ACK', 'F': 'FIN', 'R': 'RST', 'P': 'PSH', 'U': 'URG',
            'SA': 'SYN-ACK', 'FA': 'FIN-ACK', 'RA': 'RST-ACK', 'PA': 'PSH-ACK'
        };
        layers.forEach((layer, idx) => {
            const icon = layerIcons[layer.name] || '📦';
            html += `<div class="packet-layer ${layer.name.toLowerCase()}-layer">`;
            html += `<div class="layer-header">${icon} <strong>${layer.name}</strong></div>`;
            html += `<table class="result-table layer-fields"><tbody>`;
            const important = importantFields[layer.name] || [];
            const sortedFields = [...layer.fields].sort((a, b) => {
                const aImp = important.indexOf(a.name);
                const bImp = important.indexOf(b.name);
                if (aImp >= 0 && bImp >= 0) return aImp - bImp;
                if (aImp >= 0) return -1;
                if (bImp >= 0) return 1;
                return 0;
            });
            sortedFields.forEach(field => {
                let displayValue = field.value;
                let valueClass = '';
                if (field.name === 'flags' && layer.name === 'TCP') {
                    const flagStr = field.value.replace(/['"]/g, '');
                    const meaning = flagMeanings[flagStr] || flagStr;
                    displayValue = `<span class="tcp-flags">${flagStr}</span> <span class="flag-meaning">(${meaning})</span>`;
                    valueClass = 'flags-value';
                } else if (field.name === 'src' || field.name === 'psrc' || field.name === 'hwsrc') {
                    valueClass = 'src-addr';
                } else if (field.name === 'dst' || field.name === 'pdst' || field.name === 'hwdst') {
                    valueClass = 'dst-addr';
                } else if (field.name === 'sport' || field.name === 'dport') {
                    const portNames = {
                        'ssh': '22 (SSH)', 'http': '80 (HTTP)', 'https': '443 (HTTPS)',
                        'ftp': '21 (FTP)', 'ftp_data': '20 (FTP-DATA)', 'telnet': '23 (Telnet)',
                        'smtp': '25 (SMTP)', 'dns': '53 (DNS)', 'pop3': '110 (POP3)'
                    };
                    displayValue = portNames[field.value] || field.value;
                    valueClass = 'port-value';
                }
                const isImportant = important.includes(field.name);
                html += `<tr class="${isImportant ? 'important-field' : ''}">`;
                html += `<td class="field-name">${field.name}</td>`;
                html += `<td class="field-value ${valueClass}">${displayValue}</td>`;
                html += `</tr>`;
            });
            html += `</tbody></table></div>`;
        });
        html += `<details class="result-details"><summary>Raw Packet</summary><pre class="result-pre">${this.escapeHtml(packetStr)}</pre></details>`;
        return html;
    },
    formatDnsResults(rawStr) {
        let html = '';
        const lines = rawStr.split('\n').filter(l => l.trim());

        let currentSection = null;
        const sections = {};
        const recordIcons = {
            'A': '🌐', 'AAAA': '🌐', 'MX': '📧', 'NS': '🖥️', 'TXT': '📝',
            'SOA': '📋', 'CNAME': '🔗', 'PTR': '↩️', 'SRV': '⚙️', 'CAA': '🔒'
        };

        lines.forEach(line => {
            const sectionMatch = line.match(/^\[(\w+)\s+Records?\]$/i);
            if (sectionMatch) {
                currentSection = sectionMatch[1].toUpperCase();
                sections[currentSection] = [];
            } else if (currentSection && line.startsWith('  ')) {
                sections[currentSection].push(line.trim());
            }
        });

        const sectionKeys = Object.keys(sections);
        if (sectionKeys.length > 0) {
            html += `<div class="dns-results">`;
            sectionKeys.forEach(type => {
                const records = sections[type];
                const icon = recordIcons[type] || '📄';
                html += `<div class="dns-section">`;
                html += `<div class="dns-section-header">${icon} <strong>${type} Records</strong> <span class="record-count">(${records.length})</span></div>`;
                if (records.length > 0) {
                    html += `<table class="result-table dns-table"><tbody>`;
                    records.forEach(record => {
                        if (type === 'MX' && record.includes('Priority:')) {
                            const match = record.match(/Priority:\s*(\d+),?\s*Mail Server:\s*(.+)/i);
                            if (match) {
                                html += `<tr><td class="mx-priority">${match[1]}</td><td class="mx-server">${this.escapeHtml(match[2])}</td></tr>`;
                            } else {
                                html += `<tr><td colspan="2">${this.escapeHtml(record)}</td></tr>`;
                            }
                        } else if (type === 'SOA') {
                            const label = record.split(':')[0];
                            const value = record.split(':').slice(1).join(':').trim();
                            html += `<tr><td class="soa-label">${this.escapeHtml(label)}</td><td>${this.escapeHtml(value)}</td></tr>`;
                        } else if (type === 'SRV') {
                            const label = record.split(':')[0];
                            const value = record.split(':').slice(1).join(':').trim();
                            html += `<tr><td class="srv-label">${this.escapeHtml(label)}</td><td>${this.escapeHtml(value)}</td></tr>`;
                        } else {
                            html += `<tr><td colspan="2" class="dns-record">${this.escapeHtml(record)}</td></tr>`;
                        }
                    });
                    html += `</tbody></table>`;
                } else {
                    html += `<div class="dns-no-records">No records found</div>`;
                }
                html += `</div>`;
            });
            html += `</div>`;
        } else {
            html += `<pre class="result-pre">${this.escapeHtml(rawStr)}</pre>`;
        }
        return html;
    },
    escapeHtml(str) {
        if (typeof str !== 'string') return String(str);
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
    async init() {
        console.log('DirectTools: Initializing...');
        try {
            this.tools = await Api.listTools();
            console.log('DirectTools: Loaded tools:', this.tools);
            this.populateToolSelect();
            this.bindEvents();
            console.log('DirectTools: Initialization complete');
        } catch (error) {
            console.error('DirectTools: Failed to load tools:', error);
            const select = document.getElementById('tool-select');
            if (select) {
                select.innerHTML = '<option value="">Error loading tools</option>';
            }
        }
    },
    populateToolSelect() {
        const select = document.getElementById('tool-select');
        if (!select) return;
        select.innerHTML = '<option value="">-- Choose a tool --</option>';
        this.tools.forEach(tool => {
            const option = document.createElement('option');
            option.value = tool.name;
            option.textContent = this.getDisplayName(tool.name);
            select.appendChild(option);
        });
    },
    bindEvents() {
        const select = document.getElementById('tool-select');
        if (select) {
            select.addEventListener('change', (e) => this.onToolSelect(e.target.value));
        }
        const form = document.getElementById('tool-execute-form');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.executeCurrentTool();
            });
        }
        const clearBtn = document.getElementById('tool-clear-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearForm());
        }
        const loadExampleBtn = document.getElementById('load-example-btn');
        if (loadExampleBtn) {
            loadExampleBtn.addEventListener('click', () => this.loadExample());
        }
        const copyBtn = document.getElementById('copy-output-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => this.copyOutput());
        }
        const toggleDocsBtn = document.getElementById('toggle-docs-btn');
        if (toggleDocsBtn) {
            toggleDocsBtn.addEventListener('click', () => this.toggleDocumentation());
        }
        document.querySelectorAll('.tool-card[data-tool]').forEach(card => {
            card.addEventListener('click', () => {
                const toolName = card.dataset.tool;
                document.getElementById('tool-select').value = toolName;
                this.onToolSelect(toolName);
                document.querySelectorAll('.tool-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
            });
        });
    },
    toggleDocumentation() {
        const docsContent = document.getElementById('tool-docs-content');
        const toggleBtn = document.getElementById('toggle-docs-btn');
        if (!docsContent || !toggleBtn) return;
        const isHidden = docsContent.classList.toggle('hidden');
        toggleBtn.querySelector('span').textContent = isHidden ? 'Show Documentation' : 'Hide Documentation';
    },
    async onToolSelect(toolName) {
        const formContainer = document.getElementById('tool-form-container');
        const outputContainer = document.getElementById('tool-output-container');
        const docsPanel = document.getElementById('tool-docs-panel');
        const docsContent = document.getElementById('tool-docs-content');
        const toggleBtn = document.getElementById('toggle-docs-btn');
        if (!toolName) {
            formContainer.classList.add('hidden');
            outputContainer.classList.add('hidden');
            this.currentTool = null;
            document.querySelectorAll('.tool-card').forEach(c => c.classList.remove('selected'));
            return;
        }
        if (docsPanel && docsContent) {
            const docs = this.getToolDocs(toolName);
            if (docs) {
                docsContent.innerHTML = docs;
                docsPanel.classList.remove('hidden');
                docsContent.classList.add('hidden');
                if (toggleBtn) {
                    toggleBtn.querySelector('span').textContent = 'Show Documentation';
                }
            } else {
                docsPanel.classList.add('hidden');
            }
        }
        try {
            const toolInfo = await Api.getToolInfo(toolName);
            this.currentTool = toolInfo;
            this.currentExample = toolInfo.example_usage || {};
            document.getElementById('tool-form-title').textContent =
                this.getDisplayName(toolInfo.name);
            document.getElementById('tool-form-description').textContent =
                this.getDisplayDescription(toolInfo.name, toolInfo.description);
            this.buildParamForm(toolInfo.parameters);
            this.updateExampleBox();
            formContainer.classList.remove('hidden');
            outputContainer.classList.add('hidden');
            document.querySelectorAll('.tool-card').forEach(c => {
                c.classList.toggle('selected', c.dataset.tool === toolName);
            });
        } catch (error) {
            UI.showToast('error', 'Error', 'Failed to load tool info: ' + error.message);
        }
    },
    buildParamForm(parameters) {
        const container = document.getElementById('tool-params-container');
        container.innerHTML = '';
        const paramLabels = {
            'target': 'Target Host',
            'pkt_desc': 'Packet Description (JSON)',
            'is_ethernet': 'Use Ethernet Layer',
            'want_response': 'Wait for Response',
            'count': 'Packet Count',
            'timeout': 'Timeout (seconds)',
            'max_hops': 'Maximum Hops',
            'use_scapy': 'Use Scapy (vs System)',
            'scan_type': 'Scan Type',
            'ports': 'Ports to Scan',
            'arguments': 'Additional Arguments',
            'mode': 'Probe Mode',
            'port': 'Target Port',
            'flags': 'TCP Flags (S/A/F/R/U/P)',
            'network': 'Network Range (CIDR)',
            'record_types': 'Record Types (A,MX,NS,TXT...)',
            'nameserver': 'DNS Server',
            'rate': 'Packets Per Second',
            'use_sudo': 'Run with Sudo'
        };
        parameters.forEach(param => {
            const group = document.createElement('div');
            group.className = 'tool-param-group';
            const label = document.createElement('label');
            label.setAttribute('for', `param-${param.name}`);
            const displayLabel = paramLabels[param.name] || param.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            label.innerHTML = `
                ${displayLabel}
                ${param.required ? '<span class="required">*</span>' : '<span class="optional">(optional)</span>'}
            `;
            let input;
            if (param.type === 'boolean') {
                const wrapper = document.createElement('div');
                wrapper.className = 'checkbox-wrapper';
                input = document.createElement('input');
                input.type = 'checkbox';
                input.id = `param-${param.name}`;
                input.name = param.name;
                input.checked = param.default === true;
                const checkLabel = document.createElement('span');
                checkLabel.textContent = param.default ? 'Enabled' : 'Disabled';
                input.addEventListener('change', () => {
                    checkLabel.textContent = input.checked ? 'Enabled' : 'Disabled';
                    this.updateExampleBox();
                });
                wrapper.appendChild(input);
                wrapper.appendChild(checkLabel);
                group.appendChild(label);
                group.appendChild(wrapper);
            } else if (param.enum) {
                input = document.createElement('select');
                input.id = `param-${param.name}`;
                input.name = param.name;
                param.enum.forEach(val => {
                    const opt = document.createElement('option');
                    opt.value = val;
                    opt.textContent = val;
                    if (val === param.default) opt.selected = true;
                    input.appendChild(opt);
                });
                input.addEventListener('change', () => this.updateExampleBox());
                group.appendChild(label);
                group.appendChild(input);
            } else if (param.name.includes('desc') || param.name.includes('report')) {
                input = document.createElement('textarea');
                input.id = `param-${param.name}`;
                input.name = param.name;
                input.placeholder = param.description || `Enter ${param.name}`;
                if (param.default !== null && param.default !== undefined) {
                    input.value = param.default;
                }
                input.addEventListener('input', () => this.updateExampleBox());
                group.appendChild(label);
                group.appendChild(input);
            } else {
                input = document.createElement('input');
                input.type = param.type === 'integer' || param.type === 'number' ? 'number' : 'text';
                input.id = `param-${param.name}`;
                input.name = param.name;
                input.placeholder = param.description || `Enter ${param.name}`;
                if (param.default !== null && param.default !== undefined) {
                    input.value = param.default;
                }
                if (param.required) {
                    input.required = true;
                }
                input.addEventListener('input', () => this.updateExampleBox());
                group.appendChild(label);
                group.appendChild(input);
            }
            if (param.description) {
                const hint = document.createElement('span');
                hint.className = 'param-hint';
                hint.textContent = param.description;
                group.appendChild(hint);
            }
            container.appendChild(group);
        });
    },
    async executeCurrentTool() {
        if (!this.currentTool) return;
        const form = document.getElementById('tool-execute-form');
        const outputContainer = document.getElementById('tool-output-container');
        const output = document.getElementById('tool-output');
        const parameters = {};
        this.currentTool.parameters.forEach(param => {
            const input = document.getElementById(`param-${param.name}`);
            if (!input) return;
            let value;
            if (param.type === 'boolean') {
                value = input.checked;
            } else if (param.type === 'integer') {
                value = input.value ? parseInt(input.value, 10) : undefined;
            } else if (param.type === 'number') {
                value = input.value ? parseFloat(input.value) : undefined;
            } else {
                value = input.value || undefined;
            }
            if (value !== undefined && value !== '') {
                parameters[param.name] = value;
            }
        });
        form.classList.add('loading');
        output.textContent = 'Executing...';
        output.className = 'tool-output';
        outputContainer.classList.remove('hidden');
        try {
            const result = await Api.executeTool(this.currentTool.name, parameters);
            if (result.success) {
                output.innerHTML = this.formatToolResult(this.currentTool.name, result.result);
                output.className = 'tool-output';
            } else {
                output.textContent = `Error: ${result.error}`;
                output.className = 'tool-output error';
            }
            UI.showToast(
                result.success ? 'success' : 'error',
                result.success ? 'Success' : 'Error',
                result.success ? 'Tool executed successfully' : 'Tool execution failed'
            );
        } catch (error) {
            output.textContent = `Error: ${error.message}`;
            output.className = 'tool-output error';
            UI.showToast('error', 'Execution Error', error.message);
        } finally {
            form.classList.remove('loading');
        }
    },
    updateExampleBox() {
        if (!this.currentTool) return;
        const params = {};
        this.currentTool.parameters.forEach(param => {
            const input = document.getElementById(`param-${param.name}`);
            if (!input) return;
            let value;
            if (param.type === 'boolean') {
                value = input.checked;
            } else if (param.type === 'integer') {
                value = input.value ? parseInt(input.value, 10) : param.default;
            } else if (param.type === 'number') {
                value = input.value ? parseFloat(input.value) : param.default;
            } else {
                value = input.value || param.default || '';
            }
            if (value !== undefined && value !== '') {
                params[param.name] = value;
            }
        });
        const exampleBox = document.getElementById('tool-example-json');
        if (exampleBox) {
            exampleBox.textContent = JSON.stringify(params, null, 2);
        }
    },
    loadExample() {
        if (!this.currentExample || !this.currentTool) return;
        this.currentTool.parameters.forEach(param => {
            const input = document.getElementById(`param-${param.name}`);
            if (!input) return;
            const exampleValue = this.currentExample[param.name];
            if (exampleValue !== undefined) {
                if (param.type === 'boolean') {
                    input.checked = exampleValue;
                } else {
                    input.value = typeof exampleValue === 'object'
                        ? JSON.stringify(exampleValue)
                        : exampleValue;
                }
            }
        });
        this.updateExampleBox();
        UI.showToast('info', 'Example Loaded', 'Example parameters have been filled in');
    },
    clearForm() {
        this.currentTool?.parameters.forEach(param => {
            const input = document.getElementById(`param-${param.name}`);
            if (!input) return;
            if (param.type === 'boolean') {
                input.checked = param.default === true;
            } else {
                input.value = param.default !== null && param.default !== undefined
                    ? param.default
                    : '';
            }
        });
        this.updateExampleBox();
        document.getElementById('tool-output-container').classList.add('hidden');
    },
    copyOutput() {
        const output = document.getElementById('tool-output');
        navigator.clipboard.writeText(output.textContent).then(() => {
            UI.showToast('success', 'Copied', 'Output copied to clipboard');
        }).catch(() => {
            UI.showToast('error', 'Error', 'Failed to copy to clipboard');
        });
    }
};
const Admin = {
    users: [],
    initialized: false,
    init() {
        if (this.initialized) return;
        this.bindEvents();
        this.initialized = true;
        if (AppState.currentView === 'admin') {
            this.loadUsers();
        }
    },
    bindEvents() {
        const createForm = document.getElementById('create-user-form');
        if (createForm) {
            createForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.createUser();
            });
        }
        const toggleBtn = document.getElementById('toggle-create-form');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                const form = document.getElementById('create-user-form');
                form.classList.toggle('collapsed');
                toggleBtn.classList.toggle('rotated');
            });
        }
        const refreshBtn = document.getElementById('refresh-users-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadUsers());
        }
        const changePasswordForm = document.getElementById('admin-change-password-form');
        if (changePasswordForm) {
            changePasswordForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitPasswordChange();
            });
        }
        const closeChangePasswordModal = document.getElementById('close-change-password-modal');
        const cancelChangePassword = document.getElementById('cancel-change-password');
        if (closeChangePasswordModal) {
            closeChangePasswordModal.addEventListener('click', () => this.closeModal('change-user-password-modal'));
        }
        if (cancelChangePassword) {
            cancelChangePassword.addEventListener('click', () => this.closeModal('change-user-password-modal'));
        }
        const closeDeleteModal = document.getElementById('close-delete-modal');
        const cancelDelete = document.getElementById('cancel-delete');
        const confirmDelete = document.getElementById('confirm-delete');
        if (closeDeleteModal) {
            closeDeleteModal.addEventListener('click', () => this.closeModal('delete-user-modal'));
        }
        if (cancelDelete) {
            cancelDelete.addEventListener('click', () => this.closeModal('delete-user-modal'));
        }
        if (confirmDelete) {
            confirmDelete.addEventListener('click', () => this.confirmDeleteUser());
        }
        document.querySelectorAll('#change-user-password-modal, #delete-user-modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal.id);
                }
            });
        });
    },
    async loadUsers() {
        const tbody = document.getElementById('users-table-body');
        if (!tbody) return;
        if (!isRootUser(AppState.user)) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="error-cell">
                        <span class="error-text">Access denied. Only root user can view users.</span>
                    </td>
                </tr>
            `;
            return;
        }
        tbody.innerHTML = `
            <tr class="loading-row">
                <td colspan="6">
                    <div class="table-loading">
                        <div class="loading-spinner small"></div>
                        <span>Loading users...</span>
                    </div>
                </td>
            </tr>
        `;
        try {
            this.users = await Api.listUsers();
            this.renderUsersTable();
        } catch (error) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="error-cell">
                        <span class="error-text">Failed to load users: ${error.message}</span>
                        <button class="btn btn-ghost btn-sm" onclick="Admin.loadUsers()">Retry</button>
                    </td>
                </tr>
            `;
        }
    },
    renderUsersTable() {
        const tbody = document.getElementById('users-table-body');
        if (!tbody) return;
        if (!isRootUser(AppState.user)) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-cell">Access denied. Only root user can view users.</td>
                </tr>
            `;
            return;
        }
        if (this.users.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-cell">No users found</td>
                </tr>
            `;
            return;
        }
        tbody.innerHTML = this.users.map(user => {
            const isUserRoot = user.id === 0 && user.username === 'root';
            const isCurrentUser = AppState.user && user.id === AppState.user.id;
            const createdDate = user.created_at
                ? new Date(user.created_at).toLocaleDateString()
                : 'N/A';
            return `
                <tr data-user-id="${user.id}" class="${isUserRoot ? 'admin-row' : ''}">
                    <td class="id-cell">${user.id}</td>
                    <td class="username-cell">
                        <div class="user-info-cell">
                            <div class="user-avatar-small">${user.username.charAt(0).toUpperCase()}</div>
                            <span>${this.escapeHtml(user.username)}</span>
                            ${isUserRoot ? '<span class="badge badge-admin">Root</span>' : ''}
                        </div>
                    </td>
                    <td class="email-cell">${this.escapeHtml(user.email || '-')}</td>
                    <td class="status-cell">
                        <span class="status-badge ${user.is_active ? 'status-active' : 'status-inactive'}">
                            ${user.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </td>
                    <td class="date-cell">${createdDate}</td>
                    <td class="actions-cell">
                        <div class="action-buttons">
                            <button class="btn btn-icon btn-ghost" 
                                    title="Change Password"
                                    onclick="Admin.openChangePasswordModal(${user.id}, '${this.escapeHtml(user.username)}')">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                                </svg>
                            </button>
                            ${!isUserRoot ? `
                                <button class="btn btn-icon btn-ghost ${user.is_active ? 'btn-warning' : 'btn-success'}" 
                                        title="${user.is_active ? 'Deactivate' : 'Activate'} User"
                                        onclick="Admin.toggleUserStatus(${user.id})">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        ${user.is_active
                        ? '<circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>'
                        : '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'}
                                    </svg>
                                </button>
                                <button class="btn btn-icon btn-ghost btn-danger" 
                                        title="Delete User"
                                        onclick="Admin.openDeleteModal(${user.id}, '${this.escapeHtml(user.username)}')"
                                        ${isCurrentUser ? 'disabled' : ''}>
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <polyline points="3 6 5 6 21 6"/>
                                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                        <line x1="10" y1="11" x2="10" y2="17"/>
                                        <line x1="14" y1="11" x2="14" y2="17"/>
                                    </svg>
                                </button>
                            ` : `
                                <span class="protected-badge">Protected</span>
                            `}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    },
    async createUser() {
        if (!isRootUser(AppState.user)) {
            UI.showToast('error', 'Access Denied', 'Only root user can create users');
            return;
        }
        const username = document.getElementById('new-username').value.trim();
        const email = document.getElementById('new-email').value.trim();
        const password = document.getElementById('new-user-password').value;
        const confirmPassword = document.getElementById('confirm-new-user-password').value;
        const messageEl = document.getElementById('create-user-message');
        const submitBtn = document.querySelector('#create-user-form button[type="submit"]');
        if (password !== confirmPassword) {
            this.showFormMessage(messageEl, 'Passwords do not match', 'error');
            return;
        }
        if (password.length < 8) {
            this.showFormMessage(messageEl, 'Password must be at least 8 characters', 'error');
            return;
        }
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Creating...</span>';
        try {
            await Api.createUser(username, email, password);
            this.showFormMessage(messageEl, `User "${username}" created successfully!`, 'success');
            document.getElementById('create-user-form').reset();
            await this.loadUsers();
            UI.showToast('success', 'User Created', `User "${username}" has been created`);
        } catch (error) {
            this.showFormMessage(messageEl, error.message, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="8.5" cy="7" r="4" />
                    <line x1="20" y1="8" x2="20" y2="14" />
                    <line x1="23" y1="11" x2="17" y2="11" />
                </svg>
                Create User
            `;
        }
    },
    openChangePasswordModal(userId, username) {
        document.getElementById('change-password-user-id').value = userId;
        document.getElementById('change-password-username').textContent = username;
        document.getElementById('admin-new-password').value = '';
        document.getElementById('admin-confirm-password').value = '';
        document.getElementById('admin-password-message').classList.add('hidden');
        document.getElementById('change-user-password-modal').classList.add('active');
    },
    async submitPasswordChange() {
        if (!isRootUser(AppState.user)) {
            UI.showToast('error', 'Access Denied', 'Only root user can change user passwords');
            return;
        }
        const userId = document.getElementById('change-password-user-id').value;
        const newPassword = document.getElementById('admin-new-password').value;
        const confirmPassword = document.getElementById('admin-confirm-password').value;
        const messageEl = document.getElementById('admin-password-message');
        const submitBtn = document.querySelector('#admin-change-password-form button[type="submit"], .modal-footer button[type="submit"]');
        if (newPassword !== confirmPassword) {
            this.showFormMessage(messageEl, 'Passwords do not match', 'error');
            return;
        }
        if (newPassword.length < 8) {
            this.showFormMessage(messageEl, 'Password must be at least 8 characters', 'error');
            return;
        }
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Changing...';
        }
        try {
            await Api.adminChangePassword(userId, newPassword);
            this.closeModal('change-user-password-modal');
            UI.showToast('success', 'Password Changed', 'User password has been updated');
        } catch (error) {
            this.showFormMessage(messageEl, error.message, 'error');
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Change Password';
            }
        }
    },
    async toggleUserStatus(userId) {
        if (!isRootUser(AppState.user)) {
            UI.showToast('error', 'Access Denied', 'Only root user can modify users');
            return;
        }
        try {
            const result = await Api.toggleUserActive(userId);
            await this.loadUsers();
            UI.showToast('success', 'Status Updated', result.message);
        } catch (error) {
            UI.showToast('error', 'Error', error.message);
        }
    },
    openDeleteModal(userId, username) {
        document.getElementById('delete-user-id').value = userId;
        document.getElementById('delete-username').textContent = username;
        document.getElementById('delete-user-modal').classList.add('active');
    },
    async confirmDeleteUser() {
        if (!isRootUser(AppState.user)) {
            UI.showToast('error', 'Access Denied', 'Only root user can delete users');
            return;
        }
        const userId = document.getElementById('delete-user-id').value;
        const confirmBtn = document.getElementById('confirm-delete');
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Deleting...';
        try {
            const result = await Api.deleteUser(userId);
            this.closeModal('delete-user-modal');
            await this.loadUsers();
            UI.showToast('success', 'User Deleted', result.message);
        } catch (error) {
            UI.showToast('error', 'Error', error.message);
        } finally {
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Delete User';
        }
    },
    closeModal(modalId) {
        document.getElementById(modalId)?.classList.remove('active');
    },
    showFormMessage(element, message, type) {
        if (!element) return;
        element.textContent = message;
        element.className = `form-message ${type}`;
        element.classList.remove('hidden');
    },
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};
document.addEventListener('DOMContentLoaded', () => {
    UI.init();
});
window.Chat = Chat;
window.DirectTools = DirectTools;
window.Admin = Admin;
