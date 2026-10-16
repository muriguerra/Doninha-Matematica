console.log('[Doninha] app.js v2 carregado (LaTeX spacing fix ativo).');

// ─── Configuração ────────────────────────────────────────────────────────────

// Se estiver rodando como arquivo local, aponta pro localhost:8000. Se estiver no ngrok, usa a URL atual.
const API_BASE = window.location.protocol === 'file:' ? "http://127.0.0.1:8000" : "";
const API_CHAT = `${API_BASE}/chat`;

// ─── Estado ──────────────────────────────────────────────────────────────────

let sessionId = localStorage.getItem('doninha_session_id');
let currentModel = localStorage.getItem('doninha_model') || 'llama3.2';
let isStreaming = false;

// ─── Identificação do Dispositivo ─────────────────────────────────────────────
let deviceId = localStorage.getItem('doninha_device_id');
if (!deviceId) {
    deviceId = 'dev_' + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
    localStorage.setItem('doninha_device_id', deviceId);
}

// ─── DOM ─────────────────────────────────────────────────────────────────────

const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const newChatBtn = document.getElementById('newChatBtn');
const sessionList = document.getElementById('sessionList');
const modelSelect = document.getElementById('modelSelect');
const modelBadge = document.getElementById('modelBadge');
const connectionStatus = document.getElementById('connectionStatus');
const statusIndicator = document.getElementById('statusIndicator');


// ═══════════════════════════════════════════════════════════════════════════════
//  RENDERIZAÇÃO
// ═══════════════════════════════════════════════════════════════════════════════

function sanitizeLatex(text) {
    let s = text;

    // ── 1. Converter delimitadores alternativos para o padrão $ / $$ ──
    // \( ... \)  →  $ ... $
    s = s.replace(/\\\(/g, '$').replace(/\\\)/g, '$');
    // \[ ... \]  →  $$ ... $$
    s = s.replace(/\\\[/g, '$$').replace(/\\\]/g, '$$');

    // ── 2. Corrigir $$ usado como inline (sem quebra de linha ao redor) ──
    // Ex: "the result is $$ x+1 $$ which means" → "the result is $x+1$ which means"
    s = s.replace(/([^\n])\$\$\s*([^$\n]+?)\s*\$\$([^\n])/g, '$1$$$2$$$3');

    // ── 3. Comandos LaTeX órfãos (sem delimitadores) ──
    // Detecta \frac, \sqrt, \lim, \int, \sum, \prod, \infty, \alpha, etc. fora de $ $
    const latexCmds = /\\(?:frac|sqrt|lim|int|sum|prod|infty|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|omega|partial|nabla|cdot|times|div|pm|mp|leq|geq|neq|approx|equiv|sim|subset|supset|cup|cap|in|notin|forall|exists|to|rightarrow|leftarrow|Rightarrow|Leftarrow|vec|hat|bar|dot|ddot|text|mathrm|mathbf|mathbb|log|ln|sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan)\b/;

    // Processa linha por linha para não quebrar blocos $$ ... $$ multi-linha
    const lines = s.split('\n');
    const processedLines = lines.map(line => {
        // Pula linhas que já estão dentro de blocos $$
        if (line.trim().startsWith('$$') || line.trim().endsWith('$$')) return line;

        // Encontra comandos LaTeX fora de delimitadores $
        let result = '';
        let inMath = false;
        let i = 0;

        while (i < line.length) {
            if (line[i] === '$') {
                inMath = !inMath;
                result += line[i];
                i++;
            } else if (!inMath && line[i] === '\\' && latexCmds.test(line.slice(i))) {
                // Encontrou comando LaTeX solto! Extrair a expressão completa
                let expr = '';
                let braceDepth = 0;
                let j = i;

                // Captura o comando e seus argumentos {...}
                while (j < line.length) {
                    const ch = line[j];
                    if (ch === '{') braceDepth++;
                    else if (ch === '}') {
                        braceDepth--;
                        if (braceDepth === 0) {
                            expr += ch;
                            j++;
                            // Verifica se há mais argumentos {} logo em seguida
                            if (j < line.length && line[j] === '{') continue;
                            break;
                        }
                    } else if (braceDepth === 0 && (ch === ' ' || ch === ',' || ch === '.' || ch === ')' || ch === ':')) {
                        // Fim natural da expressão (sem chaves)
                        if (expr.length > 1) break;
                    }
                    expr += ch;
                    j++;
                }

                result += '$' + expr.trim() + '$';
                i = j;
            } else {
                result += line[i];
                i++;
            }
        }

        return result;
    });
    s = processedLines.join('\n');

    // ── 4. Corrigir espaçamento APENAS dentro dos delimitadores ($ ... $) ──
    // "$ x + 1 $" → "$x + 1$" sem engolir os espaços externos entre texto e fórmulas
    const trimSingleDollar = (match, pre, math, post) => `${pre}$${math.trim()}$${post}`;
    s = s.replace(/(^|[^\$])\$([^$\n]+?)\$([^$]|$)/g, trimSingleDollar);
    s = s.replace(/(^|[^\$])\$([^$\n]+?)\$([^$]|$)/g, trimSingleDollar);

    // ── 5. Corrigir delimitadores desbalanceados ──
    // Conta $ simples (não $$) e fecha se ímpar
    let dollarCount = 0;
    for (let i = 0; i < s.length; i++) {
        if (s[i] === '$' && (i === 0 || s[i - 1] !== '$') && (i === s.length - 1 || s[i + 1] !== '$')) {
            dollarCount++;
        }
    }
    if (dollarCount % 2 !== 0) {
        s += '$'; // Fecha o delimitador perdido
    }

    return s;
}

function renderMarkdownAndMath(text) {
    // 1. Processar tags <think> do DeepSeek para exibição bonita
    let processedText = text.replace(/<think>/g, '<div class="think-block"><strong>🤔 Thinking Process:</strong><br>');
    processedText = processedText.replace(/<\/think>/g, '</div>');

    // Se estiver streamando e a tag não fechou, fechar artificialmente no fim
    if (processedText.includes('<div class="think-block">') && !processedText.includes('</div>')) {
        processedText += '</div>';
    }

    // 2. Sanitizar LaTeX antes de renderizar
    processedText = sanitizeLatex(processedText);

    const html = (typeof marked !== 'undefined')
        ? marked.parse(processedText)
        : `<pre style="white-space:pre-wrap">${escapeHtml(processedText)}</pre>`;
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;

    if (typeof renderMathInElement === 'function') {
        renderMathInElement(tempDiv, {
            delimiters: [
                { left: '$$', right: '$$', display: true },
                { left: '$', right: '$', display: false }
            ],
            throwOnError: false,
        });
    }
    return tempDiv.innerHTML;
}

/** Escapa caracteres HTML para evitar XSS em texto do usuário. */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

/**
 * Adiciona uma mensagem completa ao chat (usada para histórico e mensagens do sistema).
 */
function addMessage(content, role) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', role);

    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');

    if (role === 'assistant') {
        contentDiv.innerHTML = renderMarkdownAndMath(content);
    } else {
        // Mensagem do usuário: exibe com prefixo > estilo terminal
        contentDiv.innerHTML = `<span class="user-prompt-arrow">❯</span> ${escapeHtml(content)}`;
    }

    msgDiv.appendChild(contentDiv);
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
}

/**
 * Cria um div de mensagem "vazio" para o streaming da IA.
 * Retorna referências para o msgDiv e contentDiv para atualização incremental.
 */
function createStreamingMessageDiv() {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', 'assistant', 'streaming');

    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');
    contentDiv.innerHTML = '<span class="streaming-cursor"></span>';

    msgDiv.appendChild(contentDiv);
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return { msgDiv, contentDiv };
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}


// ═══════════════════════════════════════════════════════════════════════════════
//  STATUS BAR
// ═══════════════════════════════════════════════════════════════════════════════

function setStatus(text, isLoading = false) {
    connectionStatus.textContent = text;
    statusIndicator.classList.toggle('loading', isLoading);
}


// ═══════════════════════════════════════════════════════════════════════════════
//  MODELOS
// ═══════════════════════════════════════════════════════════════════════════════

async function loadModels() {
    try {
        const res = await fetch(`${API_BASE}/models`);
        const models = await res.json();

        modelSelect.innerHTML = '';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m === currentModel) opt.selected = true;
            modelSelect.appendChild(opt);
        });

        // Se o modelo salvo não está na lista, usa o primeiro disponível
        if (!models.includes(currentModel) && models.length > 0) {
            currentModel = models[0];
            localStorage.setItem('doninha_model', currentModel);
        }

        updateModelBadge();
    } catch (e) {
        console.warn('[Doninha] Não foi possível carregar modelos:', e);
        // Mantém a opção padrão que já está no HTML
    }
}

function updateModelBadge() {
    if (modelBadge) modelBadge.textContent = currentModel;
    if (modelSelect) modelSelect.value = currentModel;
}


// ═══════════════════════════════════════════════════════════════════════════════
//  SESSÕES (SIDEBAR DINÂMICA)
// ═══════════════════════════════════════════════════════════════════════════════

function timeAgo(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const seconds = Math.floor((Date.now() - date) / 1000);

    if (seconds < 60) return 'agora mesmo';
    if (seconds < 3600) return `há ${Math.floor(seconds / 60)} min`;
    if (seconds < 86400) return `há ${Math.floor(seconds / 3600)}h`;
    if (seconds < 604800) return `há ${Math.floor(seconds / 86400)} dias`;
    return date.toLocaleDateString('pt-BR');
}

async function loadSessions() {
    try {
        const res = await fetch(`${API_BASE}/sessions`, {
            headers: { 'Device-ID': deviceId }
        });
        const sessions = await res.json();

        sessionList.innerHTML = '';

        if (sessions.length === 0) {
            sessionList.innerHTML = '<div class="history-empty">Nenhuma sessão ainda.</div>';
            return;
        }

        sessions.forEach(s => {
            const item = document.createElement('div');
            item.classList.add('history-item');
            if (s.id === sessionId) item.classList.add('active');
            item.dataset.sessionId = s.id;
            item.innerHTML = `
                <span class="title">${escapeHtml(s.title)}</span>
                <span class="date">${timeAgo(s.created_at)}</span>
            `;
            item.addEventListener('click', () => loadSession(s.id));
            sessionList.appendChild(item);
        });
    } catch (e) {
        sessionList.innerHTML = '<div class="history-empty">Backend offline.</div>';
    }
}

async function loadSession(id) {
    try {
        const res = await fetch(`${API_BASE}/sessions/${id}/messages`);

        if (res.status === 404) {
            // Sessão não existe mais — limpa o localStorage
            sessionId = null;
            localStorage.removeItem('doninha_session_id');
            return;
        }
        if (!res.ok) return;

        const messages = await res.json();

        // Atualiza estado
        sessionId = id;
        localStorage.setItem('doninha_session_id', sessionId);

        // Renderiza histórico
        chatMessages.innerHTML = '';
        messages.forEach(m => addMessage(m.content, m.role));

        // Atualiza item ativo na sidebar
        document.querySelectorAll('.history-item').forEach(el => {
            el.classList.toggle('active', el.dataset.sessionId === id);
        });

        setStatus('Sessão carregada.', false);
    } catch (e) {
        console.warn('[Doninha] Erro ao carregar sessão:', e);
    }
}


// ═══════════════════════════════════════════════════════════════════════════════
//  ENVIO DE MENSAGEM — SSE STREAMING
// ═══════════════════════════════════════════════════════════════════════════════

async function sendMessage() {
    if (isStreaming) return;

    const text = userInput.value.trim();
    if (!text) return;

    isStreaming = true;
    userInput.value = '';
    userInput.style.height = 'auto'; // reset auto-resize
    userInput.disabled = true;

    // Exibe mensagem do usuário
    addMessage(text, 'user');

    // Cria div de streaming para a IA
    const { msgDiv, contentDiv } = createStreamingMessageDiv();
    let streamedContent = '';

    setStatus('Gerando resposta...', true);

    try {
        const payload = { mensagem: text, model: currentModel };
        if (sessionId) payload.session_id = sessionId;

        const response = await fetch(API_CHAT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Device-ID': deviceId
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) throw new Error(`Erro HTTP ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? ''; // guarda linha incompleta para o próximo chunk

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;

                let data;
                try { data = JSON.parse(line.slice(6)); } catch { continue; }

                switch (data.type) {

                    case 'chunk':
                        streamedContent += data.content;
                        // Renderização AO VIVO de Markdown e Math + bloco <think>
                        contentDiv.innerHTML = renderMarkdownAndMath(streamedContent) + '<span class="streaming-cursor"></span>';
                        scrollToBottom();
                        break;

                    case 'status':
                        // Feedback visual dos agentes no pipeline
                        if (!streamedContent) {
                            contentDiv.innerHTML =
                                `<span class="tool-indicator">🔍 ${escapeHtml(data.message)}</span>` +
                                '<span class="streaming-cursor"></span>';
                        }
                        setStatus(data.message, true);
                        scrollToBottom();
                        break;

                    case 'tool_use':
                        // Feedback visual enquanto o SymPy calcula
                        contentDiv.innerHTML =
                            `<span class="tool-indicator">⚙ ${escapeHtml(data.message)}</span>` +
                            '<span class="streaming-cursor"></span>';
                        scrollToBottom();
                        break;

                    case 'done':
                        // Renderização final: Markdown + LaTeX
                        contentDiv.innerHTML = renderMarkdownAndMath(streamedContent);
                        msgDiv.classList.remove('streaming');
                        sessionId = data.session_id;
                        localStorage.setItem('doninha_session_id', sessionId);
                        setStatus('Terminal Ready', false);
                        loadSessions(); // Atualiza sidebar sem await para não travar
                        break;

                    case 'error':
                        contentDiv.innerHTML =
                            `<span class="error-text">❌ Erro: ${escapeHtml(data.message)}</span>`;
                        msgDiv.classList.remove('streaming');
                        setStatus('Erro no servidor.', false);
                        break;
                }
            }
        }

    } catch (error) {
        console.error('[Doninha] Erro de streaming:', error);
        contentDiv.innerHTML =
            '<span class="error-text">❌ Erro de conexão. Verifique se o backend está rodando!</span>';
        msgDiv.classList.remove('streaming');
        setStatus('Erro de conexão.', false);
    } finally {
        isStreaming = false;
        userInput.disabled = false;
        userInput.focus();
    }
}


// ═══════════════════════════════════════════════════════════════════════════════
//  EVENT LISTENERS
// ═══════════════════════════════════════════════════════════════════════════════

// Enviar com Enter (Shift+Enter = nova linha)
userInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Auto-resize do textarea
userInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

// Novo chat
newChatBtn.addEventListener('click', () => {
    if (isStreaming) return; // não interrompe streaming
    sessionId = null;
    localStorage.removeItem('doninha_session_id');
    chatMessages.innerHTML = `
        <div class="message assistant">
            <div class="message-content">New session started! What would you like to learn today?</div>
        </div>
    `;
    document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
    setStatus('Nova sessão.', false);
    userInput.focus();
});

// Troca de modelo
modelSelect.addEventListener('change', function () {
    currentModel = this.value;
    localStorage.setItem('doninha_model', currentModel);
    updateModelBadge();
});

// Atalhos de teclado globais
document.addEventListener('keydown', function (e) {
    // "I" foca no input (estilo Vim) — funciona quando o foco NÃO está no textarea
    if (e.key === 'i' && document.activeElement !== userInput && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        userInput.focus();
    }
    // Nota: Ctrl+N foi removido — o browser intercepta esse atalho antes do JavaScript
});


// ═══════════════════════════════════════════════════════════════════════════════
//  INICIALIZAÇÃO
// ═══════════════════════════════════════════════════════════════════════════════

async function init() {
    setStatus('Conectando...', true);
    // Carrega modelos e sessões em paralelo
    await Promise.all([loadModels(), loadSessions()]);

    // Se há uma sessão salva, carrega o histórico
    if (sessionId) {
        await loadSession(sessionId);
    }

    setStatus('Terminal Ready', false);
}

init();
