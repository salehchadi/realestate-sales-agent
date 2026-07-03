/* ═══════════════════════════════════════════════════════════════════════
   MOS3AD — Elite AI Real Estate Concierge
   Client-Side Application Logic
   ═══════════════════════════════════════════════════════════════════════ */

(function () {
    'use strict';

    // ── DOM References ───────────────────────────────────────────────────
    const conciergeCanvas = document.getElementById('concierge-canvas');
    const messagesContainer = document.getElementById('messages-container');
    const welcomeScreen = document.getElementById('welcome-screen');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const thinkingPulse = document.getElementById('thinking-pulse');
    const suggestionChips = document.querySelectorAll('.suggestion-chip');

    // ── State ────────────────────────────────────────────────────────────
    let isProcessing = false;
    let sessionId = generateSessionId();
    let cardGradientIndex = 0;

    // ── Utility Functions ────────────────────────────────────────────────

    function generateSessionId() {
        return 'mos3ad_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
    }

    /**
     * Detect if a string is predominantly Arabic.
     * Checks if the ratio of Arabic characters exceeds a threshold.
     */
    function isArabic(text) {
        const arabicRegex = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/g;
        const matches = text.match(arabicRegex);
        if (!matches) return false;
        const cleanText = text.replace(/\s+/g, '');
        return matches.length / cleanText.length > 0.3;
    }

    /**
     * Format a number as a price string with commas.
     */
    function formatPrice(price) {
        if (!price || price <= 0) return 'Price on Request';
        return price.toLocaleString('en-US') + ' EGP';
    }

    /**
     * Format area with unit.
     */
    function formatArea(area) {
        if (!area || area <= 0) return 'Area on Request';
        return area.toLocaleString('en-US') + ' sqm';
    }

    /**
     * Get the next gradient class for card visual variety.
     */
    function getNextGradient() {
        cardGradientIndex = (cardGradientIndex % 4) + 1;
        return 'gradient-' + cardGradientIndex;
    }

    /**
     * Convert basic markdown-like formatting to HTML.
     * Handles bold, italic, bullet lists, and newlines.
     */
    function formatMessageText(text) {
        if (!text) return '';

        // Escape HTML
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Bold: **text** or __text__
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');

        // Italic: *text* or _text_ (not inside words)
        html = html.replace(/(?<!\w)\*(?!\s)(.*?)(?<!\s)\*(?!\w)/g, '<em>$1</em>');

        // Headers: ## Header
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

        // Bullet points: - item or * item or • item
        html = html.replace(/^[\-\*•]\s+(.+)$/gm, '<li>$1</li>');
        html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

        // Numbered list: 1. item
        html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');

        // Line breaks to paragraphs (double newline = new paragraph)
        html = html.replace(/\n\n+/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');

        // Wrap in paragraph if not already
        if (!html.startsWith('<h') && !html.startsWith('<ul') && !html.startsWith('<p>')) {
            html = '<p>' + html + '</p>';
        }

        return html;
    }

    /**
     * Auto-resize textarea to fit content.
     */
    function autoResize(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    /**
     * Smoothly scroll the canvas to the bottom.
     */
    function scrollToBottom() {
        requestAnimationFrame(() => {
            conciergeCanvas.scrollTo({
                top: conciergeCanvas.scrollHeight,
                behavior: 'smooth'
            });
        });
    }

    // ── Message Rendering ────────────────────────────────────────────────

    /**
     * Render a user message in the chat.
     * Frosted glass container with champagne gold active edge.
     */
    function renderUserMessage(text) {
        const messageNode = document.createElement('div');
        const arabic = isArabic(text);
        messageNode.className = 'message-node message-user' + (arabic ? ' rtl' : '');

        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = text;

        messageNode.appendChild(content);
        messagesContainer.appendChild(messageNode);
        scrollToBottom();
    }

    /**
     * Render a Mos3ad (agent) message.
     * Borderless elegant typography — no bubbles.
     */
    function renderMos3adMessage(text) {
        const messageNode = document.createElement('div');
        messageNode.className = 'message-node message-mos3ad';

        // Sender label
        const sender = document.createElement('div');
        sender.className = 'message-sender';
        sender.textContent = 'Mos3ad';

        // Content — formatted text
        const content = document.createElement('div');
        content.className = 'message-content';
        content.innerHTML = formatMessageText(text);

        messageNode.appendChild(sender);
        messageNode.appendChild(content);
        messagesContainer.appendChild(messageNode);
        scrollToBottom();
    }

    /**
     * Render a PropertyShowcaseCard from structured property data.
     * Cinematic gradient hero, specs grid, champagne gold CTA.
     */
    function renderPropertyCard(property) {
        const card = document.createElement('div');
        card.className = 'property-showcase-card';

        const gradient = getNextGradient();

        card.innerHTML = `
            <div class="property-card-hero">
                <div class="property-card-gradient ${gradient}"></div>
                <span class="property-card-badge">${escapeHtml(property.unit_type)}</span>
                <div class="property-card-hero-content">
                    <div class="property-card-developer">${escapeHtml(property.developer || 'Premium Developer')}</div>
                    <h3 class="property-card-title">${escapeHtml(property.project_name)} — ${escapeHtml(property.bedrooms)}</h3>
                </div>
            </div>
            <div class="property-card-specs">
                <div class="property-spec-item">
                    <span class="property-spec-label">Location</span>
                    <span class="property-spec-value">${escapeHtml(property.location || 'Egypt')}</span>
                </div>
                <div class="property-spec-item">
                    <span class="property-spec-label">Delivery</span>
                    <span class="property-spec-value">${property.delivery_year || 'TBA'}</span>
                </div>
                <div class="property-spec-item">
                    <span class="property-spec-label">Starting Price</span>
                    <span class="property-spec-value price">${formatPrice(property.starting_price)}</span>
                </div>
                <div class="property-spec-item">
                    <span class="property-spec-label">Area</span>
                    <span class="property-spec-value">${formatArea(property.area_sqm)}</span>
                </div>
                <div class="property-spec-item full-width">
                    <span class="property-spec-label">Payment Plan</span>
                    <span class="property-spec-value">${escapeHtml(property.payment_plan || 'Contact for details')}</span>
                </div>
            </div>
            <div class="property-card-cta">
                <button class="cta-button" onclick="window.Mos3ad.scheduleViewing('${escapeHtml(property.project_name)}')">
                    Schedule Private Viewing
                </button>
            </div>
        `;

        messagesContainer.appendChild(card);

        // Stagger animation for multiple cards
        const cards = messagesContainer.querySelectorAll('.property-showcase-card');
        const index = cards.length - 1;
        card.style.animationDelay = (index > 0 ? '0.15s' : '0s');

        scrollToBottom();
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ── Thinking Indicator ───────────────────────────────────────────────

    function showThinking() {
        thinkingPulse.classList.add('active');
        sendButton.disabled = true;
    }

    function hideThinking() {
        thinkingPulse.classList.remove('active');
        sendButton.disabled = false;
    }

    // ── API Communication ────────────────────────────────────────────────

    /**
     * Send a message to the backend and render the response.
     */
    async function sendMessage(text) {
        if (!text || !text.trim() || isProcessing) return;

        text = text.trim();
        isProcessing = true;

        // Hide welcome screen on first message
        if (welcomeScreen) {
            welcomeScreen.style.display = 'none';
        }

        // Render user message
        renderUserMessage(text);

        // Clear input
        chatInput.value = '';
        autoResize(chatInput);

        // Show thinking animation
        showThinking();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    session_id: sessionId
                })
            });

            if (!response.ok) {
                throw new Error('Server error: ' + response.status);
            }

            const data = await response.json();

            // Hide thinking
            hideThinking();

            // Render agent text response
            if (data.text) {
                renderMos3adMessage(data.text);
            }

            // Render property cards if any
            if (data.properties && data.properties.length > 0) {
                data.properties.forEach(function (property, index) {
                    setTimeout(function () {
                        renderPropertyCard(property);
                    }, index * 200); // Staggered reveal
                });
            }

        } catch (error) {
            hideThinking();
            renderMos3adMessage('I apologize for the inconvenience. There was an issue processing your request. Please try again in a moment.');
            console.error('Mos3ad Error:', error);
        }

        isProcessing = false;
    }

    /**
     * Handle the "Schedule Private Viewing" CTA.
     */
    function scheduleViewing(projectName) {
        const message = "I'd like to schedule a private viewing for " + projectName;
        sendMessage(message);
    }

    // ── Event Listeners ──────────────────────────────────────────────────

    // Send button click
    sendButton.addEventListener('click', function () {
        sendMessage(chatInput.value);
    });

    // Enter key to send (Shift+Enter for newline)
    chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(chatInput.value);
        }
    });

    // Auto-resize textarea
    chatInput.addEventListener('input', function () {
        autoResize(this);
    });

    // Suggestion chips
    suggestionChips.forEach(function (chip) {
        chip.addEventListener('click', function () {
            const query = this.getAttribute('data-query');
            if (query) {
                sendMessage(query);
            }
        });
    });

    // Focus input on page load
    chatInput.focus();

    // ── Expose Public API ────────────────────────────────────────────────
    window.Mos3ad = {
        sendMessage: sendMessage,
        scheduleViewing: scheduleViewing
    };

})();
