/**
 * StockSense AI - Intelligent Stock Analysis Chatbot Client
 * Integrates with POST /api/chat
 */

(function () {
  'use strict';

  // State
  let activeSymbol = 'RELIANCE';
  let isGenerating = false;
  let isOpen = false;
  let lastFailedMessage = null;
  let conversationHistory = [];

  // DOM Elements
  let launcherBtn = null;
  let panelElem = null;
  let messagesContainer = null;
  let inputField = null;
  let sendBtn = null;
  let typingIndicator = null;
  let symbolBadge = null;
  let stockChips = [];

  // Default suggested questions
  const DEFAULT_PROMPTS = [
    "What is the current price?",
    "What does the RSI indicate?",
    "Explain the MACD.",
    "Why is the recommendation HOLD?",
    "What is the predicted price?"
  ];

  document.addEventListener('DOMContentLoaded', () => {
    initChatbot();
  });

  function initChatbot() {
    launcherBtn = document.getElementById('chatbot-launcher');
    panelElem = document.getElementById('chatbot-panel');
    messagesContainer = document.getElementById('chatbot-messages');
    inputField = document.getElementById('chatbot-input-field');
    sendBtn = document.getElementById('chatbot-send-btn');
    typingIndicator = document.getElementById('chatbot-typing-indicator');
    symbolBadge = document.getElementById('chatbot-active-symbol-badge');
    stockChips = document.querySelectorAll('.chatbot-stock-chip');

    if (!launcherBtn || !panelElem) return;

    // 1. Detect currently active symbol on the page
    detectCurrentPageSymbol();

    // 2. Setup Event Listeners
    launcherBtn.addEventListener('click', toggleChatbot);

    const closeBtn = document.getElementById('chatbot-close-btn');
    if (closeBtn) closeBtn.addEventListener('click', () => toggleChatbot(false));

    const clearBtn = document.getElementById('chatbot-clear-btn');
    if (clearBtn) clearBtn.addEventListener('click', clearChatHistory);

    const inputForm = document.getElementById('chatbot-input-form');
    if (inputForm) {
      inputForm.addEventListener('submit', (e) => {
        e.preventDefault();
        handleFormSubmit();
      });
    }

    if (inputField) {
      inputField.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          handleFormSubmit();
        }
      });
    }

    // Quick stock selector chips
    stockChips.forEach(chip => {
      chip.addEventListener('click', () => {
        const sym = chip.getAttribute('data-symbol');
        if (sym) {
          setChatbotSymbol(sym);
          // If on analysis page, optionally switch the page stock too
          if (typeof window.switchToStock === 'function') {
            window.switchToStock(sym);
          }
        }
      });
    });

    // Listen for custom stock change events from stock_analysis.js or page changes
    window.addEventListener('stocksense:symbolChange', (e) => {
      if (e.detail && e.detail.symbol) {
        setChatbotSymbol(e.detail.symbol);
      }
    });

    // Render initial welcome message
    renderWelcomeMessage();
  }

  /**
   * Detects the currently selected stock symbol from the page URL or global variables.
   */
  function detectCurrentPageSymbol() {
    let sym = null;

    // Check window.currentSymbol (set by stock_analysis.js)
    if (window.currentSymbol && typeof window.currentSymbol === 'string') {
      sym = window.currentSymbol;
    }

    // Check pathname /analysis/<symbol>
    if (!sym && window.location.pathname.includes('/analysis/')) {
      const parts = window.location.pathname.split('/');
      if (parts.length >= 3 && parts[2]) {
        sym = decodeURIComponent(parts[2]).replace('.NS', '').replace('.BO', '');
      }
    }

    // Check URL query param ?symbol=...
    if (!sym) {
      const param = new URLSearchParams(window.location.search).get('symbol');
      if (param) sym = param.replace('.NS', '').replace('.BO', '');
    }

    // Check #stock-symbol-text DOM element
    if (!sym) {
      const elem = document.getElementById('stock-symbol-text');
      if (elem && elem.textContent && elem.textContent.trim() !== '--') {
        sym = elem.textContent.trim();
      }
    }

    // Default to RELIANCE or TCS
    if (!sym) {
      sym = 'RELIANCE';
    }

    setChatbotSymbol(sym);
  }

  /**
   * Updates the active stock symbol in the chatbot and reflects it in the UI.
   */
  function setChatbotSymbol(symbol) {
    if (!symbol) return;
    activeSymbol = symbol.trim().toUpperCase();

    if (symbolBadge) {
      symbolBadge.textContent = activeSymbol;
    }

    if (inputField) {
      inputField.placeholder = `Ask about ${activeSymbol} (e.g. price, RSI, MACD, ML forecast)...`;
    }

    // Update active state on stock chips
    stockChips.forEach(chip => {
      if (chip.getAttribute('data-symbol') === activeSymbol) {
        chip.classList.add('active');
      } else {
        chip.classList.remove('active');
      }
    });
  }

  /**
   * Opens or closes the chatbot panel.
   */
  function toggleChatbot(forceState) {
    isOpen = typeof forceState === 'boolean' ? forceState : !isOpen;

    if (isOpen) {
      // Re-check current page symbol in case user navigated
      detectCurrentPageSymbol();
      panelElem.classList.add('open');
      if (inputField) setTimeout(() => inputField.focus(), 150);
      scrollToBottom();
    } else {
      panelElem.classList.remove('open');
    }
  }

  /**
   * Renders the initial greeting / onboarding message with quick question chips.
   */
  function renderWelcomeMessage() {
    if (!messagesContainer) return;
    messagesContainer.innerHTML = '';

    const welcomeHtml = `
      <div class="chat-msg assistant">
        <div class="chat-bubble">
          <p><strong>Hello! I am your StockSense AI Assistant 👋</strong></p>
          <p>I am ready to analyze <strong>${activeSymbol}</strong> (NSE/BSE) using live quotes, mathematical quantitative indicators, and ML forecasting models.</p>
          <p style="margin-bottom: 0.5rem; font-size: 0.775rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;">Suggested Questions:</p>
          <div class="chat-quick-suggestions" id="welcome-quick-suggestions">
            ${DEFAULT_PROMPTS.map(p => `<button type="button" class="chat-suggestion-chip" data-query="${escapeHtml(p)}">${escapeHtml(p)}</button>`).join('')}
          </div>
        </div>
        <div class="chat-meta">
          <span>StockSense AI</span> • <span>Just now</span>
        </div>
      </div>
    `;

    messagesContainer.innerHTML = welcomeHtml;

    // Attach click listeners to chips
    bindSuggestionChips(messagesContainer);
  }

  /**
   * Binds click handlers to question chips.
   */
  function bindSuggestionChips(container) {
    const chips = container.querySelectorAll('.chat-suggestion-chip');
    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        const query = chip.getAttribute('data-query');
        if (query) {
          sendUserMessage(query);
        }
      });
    });
  }

  /**
   * Handles user submission from the input field.
   */
  function handleFormSubmit() {
    if (!inputField || isGenerating) return;
    const text = inputField.value.trim();
    if (!text) return;
    sendUserMessage(text);
  }

  /**
   * Sends user message to POST /api/chat.
   */
  async function sendUserMessage(text) {
    if (!text || isGenerating) return;
    const cleanText = text.trim();
    lastFailedMessage = cleanText;

    // 1. Append user message to thread
    appendMessage('user', cleanText);
    if (inputField) {
      inputField.value = '';
    }

    // 2. Set loading state
    setLoadingState(true);
    scrollToBottom();

    // 3. Prepare payload for POST /api/chat
    const payload = {
      user_message: cleanText,
      symbol: activeSymbol,
      history: conversationHistory.slice(-10)
    };

    // Track user message in local history
    conversationHistory.push({ role: 'user', content: cleanText });

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      const resData = await response.json().catch(() => ({}));

      if (!response.ok || resData.status === 'error') {
        const errMsg = resData.message || `Server error (${response.status}). Please try again.`;
        throw new Error(errMsg);
      }

      const data = resData.data || {};
      const answerText = data.response || data.answer || "I received your query, but could not produce an answer.";
      const provider = data.provider === 'gemini' ? 'Gemini AI' : (data.provider === 'openai' ? 'OpenAI' : 'StockSense Quant Engine');
      const followUps = data.suggested_questions || [];

      // Track assistant response in local history
      conversationHistory.push({ role: 'assistant', content: answerText });
      if (conversationHistory.length > 20) {
        conversationHistory = conversationHistory.slice(-20);
      }

      // 4. Append assistant response
      appendMessage('assistant', answerText, {
        provider: provider,
        symbol: data.symbol || activeSymbol,
        suggestions: followUps
      });

      lastFailedMessage = null;

    } catch (err) {
      console.error('[Chatbot Error]:', err);
      renderErrorMessage(err.message || 'Unable to connect to the chatbot service. Please check your connection.');
    } finally {
      setLoadingState(false);
      scrollToBottom();
      if (inputField) inputField.focus();
    }
  }

  /**
   * Appends a message bubble into the conversation stream.
   */
  function appendMessage(role, text, meta = {}) {
    if (!messagesContainer) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${role}`;

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (role === 'user') {
      msgDiv.innerHTML = `
        <div class="chat-bubble">
          ${escapeHtml(text)}
        </div>
        <div class="chat-meta">
          <span>You</span> • <span>${timeStr}</span>
        </div>
      `;
    } else {
      const formattedHtml = formatChatMarkdown(text);
      const providerLabel = meta.provider || 'StockSense AI';
      const symbolLabel = meta.symbol ? ` [${escapeHtml(meta.symbol)}]` : '';

      let suggestionsHtml = '';
      if (meta.suggestions && meta.suggestions.length > 0) {
        suggestionsHtml = `
          <div class="chat-quick-suggestions" style="margin-top: 0.65rem;">
            ${meta.suggestions.slice(0, 4).map(s => `<button type="button" class="chat-suggestion-chip" data-query="${escapeHtml(s)}">${escapeHtml(s)}</button>`).join('')}
          </div>
        `;
      }

      msgDiv.innerHTML = `
        <div class="chat-bubble">
          ${formattedHtml}
          ${suggestionsHtml}
        </div>
        <div class="chat-meta">
          <span>${providerLabel}${symbolLabel}</span> • <span>${timeStr}</span>
        </div>
      `;

      bindSuggestionChips(msgDiv);
    }

    messagesContainer.appendChild(msgDiv);
  }

  /**
   * Displays an error message bubble with retry button.
   */
  function renderErrorMessage(message) {
    if (!messagesContainer) return;

    const errorDiv = document.createElement('div');
    errorDiv.className = 'chat-msg assistant';
    errorDiv.innerHTML = `
      <div class="chat-bubble" style="background-color: rgba(229, 57, 53, 0.06); border-color: rgba(229, 57, 53, 0.25); color: #b91c1c;">
        <div class="d-flex align-items-center gap-2 mb-1">
          <span>⚠️</span>
          <strong>Chatbot Error</strong>
        </div>
        <p style="margin-bottom: 0.4rem;">${escapeHtml(message)}</p>
        ${lastFailedMessage ? `<button type="button" class="btn btn-sm btn-outline-danger py-0 px-2" style="font-size: 0.75rem;" id="chat-retry-btn">Retry Question</button>` : ''}
      </div>
      <div class="chat-meta">
        <span>System Alert</span> • <span>Failed</span>
      </div>
    `;

    const retryBtn = errorDiv.querySelector('#chat-retry-btn');
    if (retryBtn) {
      retryBtn.addEventListener('click', () => {
        if (lastFailedMessage) {
          sendUserMessage(lastFailedMessage);
          errorDiv.remove();
        }
      });
    }

    messagesContainer.appendChild(errorDiv);
  }

  /**
   * Toggles the loading animation and disables/enables input controls.
   */
  function setLoadingState(loading) {
    isGenerating = loading;

    if (typingIndicator) {
      if (loading) {
        typingIndicator.classList.add('active');
        messagesContainer.appendChild(typingIndicator);
      } else {
        typingIndicator.classList.remove('active');
      }
    }

    if (sendBtn) {
      sendBtn.disabled = loading;
    }
    if (inputField) {
      inputField.disabled = loading;
    }
  }

  /**
   * Clears the chat history and resets to the welcome message.
   */
  function clearChatHistory() {
    conversationHistory = [];
    renderWelcomeMessage();
    if (inputField) inputField.focus();
  }

  /**
   * Automatically scrolls the message container to the bottom.
   */
  function scrollToBottom() {
    if (messagesContainer) {
      setTimeout(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }, 50);
    }
  }

  /**
   * Simple, safe Markdown formatter for financial responses.
   */
  function formatChatMarkdown(text) {
    if (!text) return '';

    // 1. Escape basic HTML tags to avoid XSS
    let html = escapeHtml(text);

    // 2. Headings (### Title)
    html = html.replace(/^### (.*$)/gim, '<h6>$1</h6>');
    html = html.replace(/^## (.*$)/gim, '<h5>$1</h5>');
    html = html.replace(/^# (.*$)/gim, '<h4>$1</h4>');

    // 3. Bold (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // 4. Italic (*text*)
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // 5. Bullet list items (• or -)
    const lines = html.split('\n');
    let inList = false;
    let processed = [];

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].trim();

      if (line.startsWith('•') || line.startsWith('- ')) {
        const itemContent = line.replace(/^(•|-)\s*/, '');
        if (!inList) {
          processed.push('<ul>');
          inList = true;
        }
        processed.push(`<li>${itemContent}</li>`);
      } else {
        if (inList) {
          processed.push('</ul>');
          inList = false;
        }
        if (line) {
          if (!line.startsWith('<h') && !line.startsWith('<ul>') && !line.startsWith('<li>')) {
            processed.push(`<p>${line}</p>`);
          } else {
            processed.push(line);
          }
        }
      }
    }

    if (inList) {
      processed.push('</ul>');
    }

    return processed.join('');
  }

  function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Export functions to window for global access if needed
  window.StockSenseChatbot = {
    open: () => toggleChatbot(true),
    close: () => toggleChatbot(false),
    toggle: () => toggleChatbot(),
    setSymbol: (sym) => setChatbotSymbol(sym),
    ask: (q) => {
      toggleChatbot(true);
      sendUserMessage(q);
    }
  };

})();
