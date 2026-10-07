/**
 * Core Application State & Chat Management
 * Low-Resource & Multilingual In-Context Learning Chatbot
 */

const App = {
  state: {
    selectedLanguage: "auto",
    detectedLanguage: null,
    languages: {},
    tiers: {},
    strategy: "chain_of_thought",
    kShots: 3,
    grounding: true,
    messageCount: 0,
    totalLatency: 0,
    history: [],
    lastInspectionData: null
  },

  // API Client
  api: {
    async getLanguages() {
      const res = await fetch("/api/languages");
      return await res.json();
    },

    async sendChatMessage(message, language, strategy, kShots, grounding) {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          language,
          strategy,
          k_shots: kShots,
          grounding
        })
      });
      return await res.json();
    },

    async getExemplars(lang = "", intent = "") {
      const url = `/api/exemplars?lang=${encodeURIComponent(lang)}&intent=${encodeURIComponent(intent)}`;
      const res = await fetch(url);
      return await res.json();
    },

    async runBenchmark(languages = null) {
      const res = await fetch("/api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ languages })
      });
      return await res.json();
    }
  },

  async init() {
    console.log("[App] Initializing Multilingual Chatbot Client...");
    try {
      const langData = await this.api.getLanguages();
      this.state.languages = langData.languages || {};
      this.state.tiers = langData.tiers || {};
      UI.initLanguageSelect(this.state.languages);
      this.renderWelcomeMessage();
      UI.updateQuickScenarios("sw"); // Default quick suggestions with Swahili low-resource
    } catch (err) {
      console.error("[App] Initialization error:", err);
      UI.showToast("Failed to load languages from backend server.");
    }
  },

  renderWelcomeMessage() {
    const container = document.getElementById("chatMessages");
    container.innerHTML = `
      <div class="welcome-banner">
        <h3>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2a10 10 0 0 1 10 10c0 5.523-4.477 10-10 10S2 17.523 2 12 6.477 2 12 2z"></path>
            <path d="m9 12 2 2 4-4"></path>
          </svg>
          Enterprise Multilingual & Low-Resource Support System Active
        </h3>
        <p>
          This system demonstrates In-Context Learning (ICL) and Prompt Engineering specifically applied to <strong>low-resource languages</strong> (Swahili, Yoruba, Quechua, Bengali, Tamil, Basque, Tagalog, Amharic) alongside medium and high-resource languages.
        </p>
        <div class="feature-badges">
          <span class="feature-tag">✨ Subword Character N-Gram Retrieval</span>
          <span class="feature-tag">🎯 Dynamic k-Shot Exemplar Memory</span>
          <span class="feature-tag">🧠 Multilingual Chain-of-Thought (X-CoT)</span>
          <span class="feature-tag">📚 Low-Resource Lexical Grounding</span>
          <span class="feature-tag">⚡ Zero-Shot Comparative Baseline</span>
        </div>
      </div>
    `;
  },

  async handleUserSubmit(messageText) {
    if (!messageText || !messageText.trim()) return;
    const cleanMsg = messageText.trim();

    // 1. Render User Message
    this.renderMessageRow("user", cleanMsg);
    this.state.messageCount++;
    UI.updateMessageStats();

    // 2. Render Typing Indicator
    const typingId = this.renderTypingIndicator();

    try {
      // 3. Dispatch API call to backend
      const response = await this.api.sendChatMessage(
        cleanMsg,
        this.state.selectedLanguage,
        this.state.strategy,
        this.state.kShots,
        this.state.grounding
      );

      // Remove typing bubble
      this.removeTypingIndicator(typingId);

      // 4. Update Latency Stats
      this.state.totalLatency += (response.latency_ms || 150);
      this.state.lastInspectionData = response;
      UI.updateMessageStats();

      // 5. Update Status Bar if Auto-Detected
      if (this.state.selectedLanguage === "auto" && response.target_language) {
        UI.updateActiveStatusPill(response.target_language);
      }

      // 6. Render Bot Message with full NLP badges
      this.renderMessageRow("bot", response.response, response);

      // 7. Update Suggestion Chips based on intent
      UI.updateSuggestionChips(response.intent, response.target_language.code);

      // 8. Auto-update drawer if open
      if (UI.isDrawerOpen()) {
        UI.populateInspector(response);
      }

    } catch (err) {
      console.error("[App] Chat send error:", err);
      this.removeTypingIndicator(typingId);
      this.renderMessageRow("bot", "An error occurred while connecting to the NLP inference engine. Please make sure the backend server is running.");
    }
  },

  renderMessageRow(sender, text, nlpData = null) {
    const container = document.getElementById("chatMessages");
    const row = document.createElement("div");
    row.className = `message-row ${sender}`;

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = sender === "user" ? "👤" : (nlpData?.target_language?.flag || "🤖");

    const body = document.createElement("div");
    body.className = "msg-body";

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.textContent = text;
    body.appendChild(bubble);

    if (sender === "bot" && nlpData) {
      // NLP Metadata Strip
      const meta = document.createElement("div");
      meta.className = "msg-meta-strip";

      const langChip = document.createElement("span");
      langChip.className = "meta-chip";
      langChip.innerHTML = `${nlpData.target_language.flag} ${nlpData.target_language.name} (${nlpData.target_language.tier.toUpperCase()})`;
      meta.appendChild(langChip);

      const intentChip = document.createElement("span");
      intentChip.className = "meta-chip intent-chip";
      intentChip.textContent = `🎯 ${nlpData.intent} (${Math.round(nlpData.intent_confidence * 100)}%)`;
      meta.appendChild(intentChip);

      const sentimentChip = document.createElement("span");
      sentimentChip.className = `meta-chip sentiment-${nlpData.sentiment.toLowerCase()}`;
      sentimentChip.textContent = `Mood: ${nlpData.sentiment}`;
      meta.appendChild(sentimentChip);

      const latencyChip = document.createElement("span");
      latencyChip.className = "meta-chip latency-chip";
      latencyChip.textContent = `⚡ ${nlpData.latency_ms}ms`;
      meta.appendChild(latencyChip);

      body.appendChild(meta);

      // Action Buttons
      const actions = document.createElement("div");
      actions.className = "msg-actions";

      const btnInspect = document.createElement("button");
      btnInspect.className = "btn-inspect";
      btnInspect.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        Inspect ICL Prompt
      `;
      btnInspect.addEventListener("click", () => {
        UI.openDrawer();
        UI.populateInspector(nlpData);
      });
      actions.appendChild(btnInspect);

      const btnCopy = document.createElement("button");
      btnCopy.className = "btn-copy";
      btnCopy.textContent = "Copy";
      btnCopy.addEventListener("click", () => {
        navigator.clipboard.writeText(text);
        UI.showToast("Response copied to clipboard");
      });
      actions.appendChild(btnCopy);

      const btnTts = document.createElement("button");
      btnTts.className = "btn-tts";
      btnTts.title = "Speak Response";
      btnTts.textContent = "🔊 Listen";
      btnTts.addEventListener("click", () => {
        this.speakText(text, nlpData.target_language.code);
      });
      actions.appendChild(btnTts);

      body.appendChild(actions);
    }

    row.appendChild(avatar);
    row.appendChild(body);
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
  },

  renderTypingIndicator() {
    const container = document.getElementById("chatMessages");
    const id = "typing-" + Date.now();
    const row = document.createElement("div");
    row.id = id;
    row.className = "message-row bot";
    row.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-body">
        <div class="typing-bubble">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
    return id;
  },

  removeTypingIndicator(id) {
    const elem = document.getElementById(id);
    if (elem) elem.remove();
  },

  speakText(text, langCode) {
    if (!('speechSynthesis' in window)) {
      UI.showToast("Speech synthesis is not supported on this browser.");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = langCode || "en";
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  }
};

window.addEventListener("DOMContentLoaded", () => {
  App.init();
});
