/**
 * Smart Community Platform - Floating AI Citizen Chat Widget
 * Integrates with /api/agents/chat and CommunityAgent.
 */

document.addEventListener('DOMContentLoaded', () => {
    AgentChatWidget.init();
});

const AgentChatWidget = {
    isOpen: false,
    messages: [],

    init() {
        if (document.getElementById('ai-chat-btn')) return;
        this.injectStyles();
        this.injectHTML();
        this.bindEvents();
        this.loadHistory();
    },

    injectStyles() {
        const style = document.createElement('style');
        style.textContent = `
            #ai-chat-btn {
                position: fixed;
                bottom: 24px;
                right: 24px;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: linear-gradient(135deg, #2563EB, #1D4ED8);
                color: white;
                border: none;
                box-shadow: 0 4px 20px rgba(37, 99, 235, 0.4);
                cursor: pointer;
                z-index: 9999;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 26px;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            #ai-chat-btn:hover {
                transform: scale(1.08);
                box-shadow: 0 6px 24px rgba(37, 99, 235, 0.5);
            }
            #ai-chat-window {
                position: fixed;
                bottom: 96px;
                right: 24px;
                width: 380px;
                height: 540px;
                max-width: calc(100vw - 32px);
                max-height: calc(100vh - 120px);
                background: white;
                border-radius: 16px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
                z-index: 9998;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                transition: opacity 0.2s ease, transform 0.2s ease;
            }
            #ai-chat-window.hidden {
                display: none;
                opacity: 0;
                transform: translateY(20px);
            }
            .ai-chat-header {
                background: linear-gradient(135deg, #1E40AF, #2563EB);
                color: white;
                padding: 16px;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .ai-chat-header-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .ai-chat-avatar {
                width: 36px;
                height: 36px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
            }
            .ai-chat-messages {
                flex: 1;
                overflow-y: auto;
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 12px;
                background: #F8FAFC;
            }
            .chat-msg {
                max-width: 85%;
                padding: 12px 16px;
                border-radius: 14px;
                font-size: 0.9rem;
                line-height: 1.45;
                word-wrap: break-word;
            }
            .chat-msg.bot {
                background: white;
                color: #1E293B;
                align-self: flex-start;
                border-bottom-left-radius: 4px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                border: 1px solid #E2E8F0;
            }
            .chat-msg.user {
                background: #2563EB;
                color: white;
                align-self: flex-end;
                border-bottom-right-radius: 4px;
            }
            .ai-chat-actions {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                padding: 8px 16px;
                background: white;
                border-top: 1px solid #F1F5F9;
            }
            .chip-btn {
                background: #EFF6FF;
                color: #2563EB;
                border: 1px solid #BFDBFE;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 0.78rem;
                cursor: pointer;
                transition: background 0.15s;
            }
            .chip-btn:hover {
                background: #DBEAFE;
            }
            .ai-chat-footer {
                padding: 12px;
                background: white;
                border-top: 1px solid #E2E8F0;
                display: flex;
                gap: 8px;
            }
            .ai-chat-footer input {
                flex: 1;
                padding: 10px 14px;
                border: 1px solid #CBD5E1;
                border-radius: 20px;
                font-size: 0.9rem;
                outline: none;
            }
            .ai-chat-footer input:focus {
                border-color: #2563EB;
            }
            .ai-chat-footer button {
                background: #2563EB;
                color: white;
                border: none;
                padding: 0 16px;
                border-radius: 20px;
                cursor: pointer;
                font-weight: 600;
            }
            .typing-indicator {
                display: inline-flex;
                gap: 4px;
                align-items: center;
            }
            .typing-dot {
                width: 6px;
                height: 6px;
                background: #94A3B8;
                border-radius: 50%;
                animation: typing 1.4s infinite ease-in-out both;
            }
            .typing-dot:nth-child(1) { animation-delay: 0s; }
            .typing-dot:nth-child(2) { animation-delay: 0.2s; }
            .typing-dot:nth-child(3) { animation-delay: 0.4s; }
            @keyframes typing {
                0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
                40% { transform: scale(1); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    },

    injectHTML() {
        const btn = document.createElement('button');
        btn.id = 'ai-chat-btn';
        btn.title = 'Ask AI Community Assistant';
        btn.innerHTML = '🤖';

        const win = document.createElement('div');
        win.id = 'ai-chat-window';
        win.className = 'hidden';
        win.innerHTML = `
            <div class="ai-chat-header">
                <div class="ai-chat-header-info">
                    <div class="ai-chat-avatar">🤖</div>
                    <div>
                        <div style="font-weight: 600; font-size: 0.95rem;">Community AI Assistant</div>
                        <div style="font-size: 0.75rem; opacity: 0.85;">⚡ 24/7 Active • Powered by RAG</div>
                    </div>
                </div>
                <button id="ai-chat-close" style="background:none; border:none; color:white; font-size:18px; cursor:pointer;">✕</button>
            </div>
            <div class="ai-chat-messages" id="ai-chat-msgs"></div>
            <div class="ai-chat-actions" id="ai-chat-chips">
                <button class="chip-btn" onclick="AgentChatWidget.sendQuick('Report an Issue')">📝 Report Issue</button>
                <button class="chip-btn" onclick="AgentChatWidget.sendQuick('Check my issue status')">🔍 My Status</button>
                <button class="chip-btn" onclick="AgentChatWidget.sendQuick('How does voting work?')">💡 How to Vote</button>
                <button class="chip-btn" onclick="AgentChatWidget.sendQuick('Community statistics')">📊 Stats</button>
            </div>
            <form class="ai-chat-footer" id="ai-chat-form">
                <input type="text" id="ai-chat-input" placeholder="Ask a question..." autocomplete="off" />
                <button type="submit">Send</button>
            </form>
        `;

        document.body.appendChild(btn);
        document.body.appendChild(win);
    },

    bindEvents() {
        const btn = document.getElementById('ai-chat-btn');
        const win = document.getElementById('ai-chat-window');
        const closeBtn = document.getElementById('ai-chat-close');
        const form = document.getElementById('ai-chat-form');

        btn.addEventListener('click', () => this.toggleWindow());
        closeBtn.addEventListener('click', () => this.toggleWindow(false));

        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const input = document.getElementById('ai-chat-input');
            const q = input.value.trim();
            if (!q) return;
            input.value = '';
            this.sendQuestion(q);
        });
    },

    toggleWindow(forceState) {
        const win = document.getElementById('ai-chat-window');
        this.isOpen = forceState !== undefined ? forceState : !this.isOpen;
        if (this.isOpen) {
            win.classList.remove('hidden');
            if (this.messages.length === 0) {
                this.addBotMessage(
                    "Hello! 👋 I'm your 24/7 AI Community Assistant. How can I help you today? Ask me about reporting issues, checking status, or platform stats!"
                );
            }
        } else {
            win.classList.add('hidden');
        }
    },

    sendQuick(text) {
        if (!this.isOpen) this.toggleWindow(true);
        this.sendQuestion(text);
    },

    async sendQuestion(q) {
        this.addUserMessage(q);
        this.showTyping();

        try:
            const token = localStorage.getItem('access_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch('/api/agents/chat', {
                method: 'POST',
                headers,
                body: JSON.stringify({ question: q })
            });

            this.removeTyping();

            if (response.ok) {
                const data = await response.json();
                this.addBotMessage(data.answer, data.suggested_actions, data.sources);
            } else {
                this.addBotMessage("Sorry, I am having trouble connecting right now. Please try again in a moment.");
            }
        } catch (err) {
            this.removeTyping();
            this.addBotMessage("Unable to connect to AI Assistant. Please check your network connection.");
        }
    },

    addUserMessage(text) {
        this.messages.push({ role: 'user', text });
        this.renderMessages();
        this.saveHistory();
    },

    addBotMessage(text, actions = [], sources = []) {
        this.messages.push({ role: 'bot', text, actions, sources });
        this.renderMessages();
        this.saveHistory();
    },

    showTyping() {
        const container = document.getElementById('ai-chat-msgs');
        const typingEl = document.createElement('div');
        typingEl.id = 'ai-typing';
        typingEl.className = 'chat-msg bot';
        typingEl.innerHTML = `
            <div class="typing-indicator">
                <span>AI is thinking</span>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        container.appendChild(typingEl);
        container.scrollTop = container.scrollHeight;
    },

    removeTyping() {
        const typingEl = document.getElementById('ai-typing');
        if (typingEl) typingEl.remove();
    },

    renderMessages() {
        const container = document.getElementById('ai-chat-msgs');
        container.innerHTML = '';

        this.messages.forEach(msg => {
            const div = document.createElement('div');
            div.className = `chat-msg ${msg.role}`;
            let html = msg.text;

            if (msg.actions && msg.actions.length > 0) {
                html += '<div style="margin-top:8px; font-size:0.8rem; color:#475569;"><strong>Suggested Next Steps:</strong><ul style="margin:4px 0 0 16px; padding:0;">';
                msg.actions.forEach(act => {
                    html += `<li>${act}</li>`;
                });
                html += '</ul></div>';
            }

            div.innerHTML = html;
            container.appendChild(div);
        });

        container.scrollTop = container.scrollHeight;
    },

    saveHistory() {
        try {
            localStorage.setItem('ai_chat_history', JSON.stringify(this.messages.slice(-20)));
        } catch (e) {}
    },

    loadHistory() {
        try {
            const saved = localStorage.getItem('ai_chat_history');
            if (saved) {
                this.messages = JSON.parse(saved);
            }
        } catch (e) {}
    }
};
