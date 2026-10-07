/**
 * UI Controller & DOM Event Handlers
 */

const UI = {
  elements: {},

  init() {
    this.cacheElements();
    this.bindEvents();
  },

  cacheElements() {
    this.elements = {
      langSelect: document.getElementById("languageSelect"),
      langMetaCard: document.getElementById("langMetaCard"),
      metaTier: document.getElementById("metaTier"),
      metaFamily: document.getElementById("metaFamily"),
      metaScript: document.getElementById("metaScript"),
      headerLanguagePill: document.getElementById("headerLanguagePill"),
      activeFlag: document.getElementById("activeFlag"),
      activeLanguageText: document.getElementById("activeLanguageText"),
      activeTierTag: document.getElementById("activeTierTag"),
      strategySelect: document.getElementById("strategySelect"),
      strategyExplanation: document.getElementById("strategyExplanation"),
      kShotsSlider: document.getElementById("kShotsSlider"),
      kShotsValue: document.getElementById("kShotsValue"),
      groundingToggle: document.getElementById("groundingToggle"),
      quickScenarios: document.getElementById("quickScenarios"),
      chatForm: document.getElementById("chatForm"),
      chatInput: document.getElementById("chatInput"),
      chatMessages: document.getElementById("chatMessages"),
      statMessageCount: document.getElementById("statMessageCount"),
      statAvgLatency: document.getElementById("statAvgLatency"),
      inspectorDrawer: document.getElementById("inspectorDrawer"),
      btnCloseDrawer: document.getElementById("btnCloseDrawer"),
      btnClearChat: document.getElementById("btnClearChat"),
      btnExportChat: document.getElementById("btnExportChat"),
      themeToggle: document.getElementById("themeToggle"),
      toastContainer: document.getElementById("toastContainer"),
      chipsContainer: document.getElementById("chipsContainer")
    };
  },

  bindEvents() {
    // Language Selection Changed
    this.elements.langSelect.addEventListener("change", (e) => {
      const code = e.target.value;
      App.state.selectedLanguage = code;
      this.updateLanguageMeta(code);
      this.updateQuickScenarios(code);
    });

    // Strategy Selection Changed
    this.elements.strategySelect.addEventListener("change", (e) => {
      const strat = e.target.value;
      App.state.strategy = strat;
      this.updateStrategyExplanation(strat);
      if (strat === "zero_shot") {
        this.elements.kShotsSlider.value = 0;
        this.elements.kShotsValue.textContent = "0";
        App.state.kShots = 0;
      } else if (App.state.kShots === 0) {
        this.elements.kShotsSlider.value = 3;
        this.elements.kShotsValue.textContent = "3";
        App.state.kShots = 3;
      }
    });

    // k-Shots Slider
    this.elements.kShotsSlider.addEventListener("input", (e) => {
      const val = parseInt(e.target.value, 10);
      App.state.kShots = val;
      this.elements.kShotsValue.textContent = val;
      if (val === 0 && App.state.strategy !== "zero_shot") {
        this.elements.strategySelect.value = "zero_shot";
        App.state.strategy = "zero_shot";
        this.updateStrategyExplanation("zero_shot");
      }
    });

    // Grounding Toggle
    this.elements.groundingToggle.addEventListener("change", (e) => {
      App.state.grounding = e.target.checked;
    });

    // Chat Form Submit
    this.elements.chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const val = this.elements.chatInput.value;
      if (!val.trim()) return;
      this.elements.chatInput.value = "";
      this.elements.chatInput.style.height = "auto";
      App.handleUserSubmit(val);
    });

    // Auto-expand textarea on typing & Enter to send
    this.elements.chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.elements.chatForm.dispatchEvent(new Event("submit"));
      }
    });

    this.elements.chatInput.addEventListener("input", () => {
      this.elements.chatInput.style.height = "auto";
      this.elements.chatInput.style.height = Math.min(this.elements.chatInput.scrollHeight, 120) + "px";
    });

    // Drawer Tabs
    document.querySelectorAll(".drawer-tabs .tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".drawer-tabs .tab-btn").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".drawer-content .tab-pane").forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        const tabId = btn.getAttribute("data-tab");
        const pane = document.getElementById(tabId);
        if (pane) pane.classList.add("active");
      });
    });

    // Close Drawer
    this.elements.btnCloseDrawer.addEventListener("click", () => {
      this.closeDrawer();
    });

    // Clear Chat
    this.elements.btnClearChat.addEventListener("click", () => {
      this.elements.chatMessages.innerHTML = "";
      App.renderWelcomeMessage();
      App.state.messageCount = 0;
      App.state.totalLatency = 0;
      this.updateMessageStats();
      this.showToast("Conversation cleared");
    });

    // Export Chat Transcript
    this.elements.btnExportChat.addEventListener("click", () => {
      this.exportTranscript();
    });

    // Theme Toggle
    this.elements.themeToggle.addEventListener("click", () => {
      document.body.classList.toggle("theme-light");
      document.body.classList.toggle("theme-dark");
    });
  },

  initLanguageSelect(languages) {
    // Populate or sync state
    this.updateLanguageMeta(App.state.selectedLanguage);
  },

  updateLanguageMeta(code) {
    if (code === "auto") {
      this.elements.activeFlag.textContent = "🌐";
      this.elements.activeLanguageText.textContent = "Auto-Detect Language";
      this.elements.activeTierTag.className = "tier-tag tier-low";
      this.elements.activeTierTag.textContent = "Dynamic Subwords";

      this.elements.metaTier.textContent = "Dynamic Auto-Detect";
      this.elements.metaTier.className = "meta-value tier-badge tier-low";
      this.elements.metaFamily.textContent = "Multi-Lingual Character N-Gram";
      this.elements.metaScript.textContent = "Cross-Script Parser";
      return;
    }

    const info = App.state.languages[code];
    if (!info) return;

    this.elements.activeFlag.textContent = info.flag || "🌐";
    this.elements.activeLanguageText.textContent = `${info.name} (${info.native_name})`;
    
    const tierClass = info.tier === "high" ? "tier-high" : (info.tier === "medium" ? "tier-med" : "tier-low");
    this.elements.activeTierTag.className = `tier-tag ${tierClass}`;
    this.elements.activeTierTag.textContent = `${info.tier.toUpperCase()} Resource`;

    this.elements.metaTier.textContent = `${info.tier.toUpperCase()} Resource Tier`;
    this.elements.metaTier.className = `meta-value tier-badge ${tierClass}`;
    this.elements.metaFamily.textContent = info.family || "N/A";
    this.elements.metaScript.textContent = info.script || "Latin";
  },

  updateActiveStatusPill(targetLangInfo) {
    this.elements.activeFlag.textContent = targetLangInfo.flag || "🌐";
    this.elements.activeLanguageText.textContent = `${targetLangInfo.name} (${targetLangInfo.native_name})`;
    const tierClass = targetLangInfo.tier === "high" ? "tier-high" : (targetLangInfo.tier === "medium" ? "tier-med" : "tier-low");
    this.elements.activeTierTag.className = `tier-tag ${tierClass}`;
    this.elements.activeTierTag.textContent = `${targetLangInfo.tier.toUpperCase()} Resource`;
  },

  updateStrategyExplanation(strat) {
    const explanations = {
      "few_shot": "Monolingual Few-Shot ICL: Leverages target-language in-context demonstrations to guide response format, polite tone, and entity binding.",
      "cross_lingual_icl": "Cross-Lingual ICL (X-ICL): Uses high-resource (English) demonstrations as a cognitive scaffold to transfer reasoning to low-resource languages.",
      "chain_of_thought": "Multilingual Chain-of-Thought (X-CoT): Enforces step-by-step cognitive decomposition: Language ID → Intent Classification → Entity Slot-Filling → Policy Resolution → Target Generation.",
      "pivot_grounding": "Pivot Lexicon Grounding: Injects verified low-resource bilingual customer support dictionaries into context to avoid hallucination and lexical drift.",
      "zero_shot": "Zero-Shot Baseline: Direct instruction without exemplars. Used to illustrate the stark accuracy and policy differences compared to In-Context Learning."
    };
    this.elements.strategyExplanation.textContent = explanations[strat] || "";
  },

  updateQuickScenarios(langCode) {
    const container = this.elements.quickScenarios;
    container.innerHTML = "";

    const targetCode = langCode === "auto" ? "sw" : langCode;
    const langInfo = App.state.languages[targetCode] || App.state.languages["sw"];
    const queries = langInfo?.sample_queries || [];

    queries.forEach((q) => {
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "scenario-pill";
      pill.innerHTML = `
        <span class="pill-intent">${q.intent.replace('_', ' ')}</span>
        <span class="pill-text">${q.text}</span>
      `;
      pill.addEventListener("click", () => {
        this.elements.chatInput.value = q.text;
        this.elements.chatInput.focus();
      });
      container.appendChild(pill);
    });
  },

  updateSuggestionChips(intent, langCode) {
    const container = this.elements.chipsContainer;
    container.innerHTML = "";

    const intentFollowups = {
      "order_tracking": [
        "What is the carrier name?",
        "Can I change the delivery address?",
        "Notify me upon dispatch"
      ],
      "refund_cancellation": [
        "How do I print the return label?",
        "Can I choose store credit instead?",
        "When does the refund hit my card?"
      ],
      "account_access": [
        "I did not receive the email link",
        "Can I verify via SMS OTP?",
        "Unlock my account immediately"
      ],
      "billing_issues": [
        "Download invoice PDF copy",
        "Verify bank credit memo",
        "Remove expired payment card"
      ],
      "technical_support": [
        "Device won't restart",
        "Send replacement under warranty",
        "Find nearest authorized repair"
      ],
      "human_escalation": [
        "How long is the supervisor wait?",
        "Send transcript to my email",
        "Add urgent dispute note"
      ]
    };

    const chips = intentFollowups[intent] || intentFollowups["order_tracking"];
    chips.forEach((chipText) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "suggest-chip";
      chip.textContent = chipText;
      chip.addEventListener("click", () => {
        this.elements.chatInput.value = chipText;
        this.elements.chatForm.dispatchEvent(new Event("submit"));
      });
      container.appendChild(chip);
    });
  },

  updateMessageStats() {
    this.elements.statMessageCount.textContent = App.state.messageCount;
    const avg = App.state.messageCount > 0 ? Math.round(App.state.totalLatency / App.state.messageCount) : 0;
    this.elements.statAvgLatency.textContent = `${avg}ms`;
  },

  openDrawer() {
    this.elements.inspectorDrawer.classList.add("open");
  },

  closeDrawer() {
    this.elements.inspectorDrawer.classList.remove("open");
  },

  isDrawerOpen() {
    return this.elements.inspectorDrawer.classList.contains("open");
  },

  populateInspector(nlpData) {
    const promptInfo = nlpData.prompt_inspection || {};

    // Badges
    document.getElementById("inspStrategyBadge").textContent = `Strategy: ${promptInfo.strategy || App.state.strategy}`;
    document.getElementById("inspLanguageBadge").textContent = `Target: ${nlpData.target_language.name} (${nlpData.target_language.tier.toUpperCase()})`;
    document.getElementById("inspTokensBadge").textContent = `~${promptInfo.token_estimate || 0} tokens`;

    // Assembled Code Boxes
    document.getElementById("inspSystemPrompt").textContent = promptInfo.system_prompt || "No system prompt.";
    document.getElementById("inspDemoBlock").textContent = promptInfo.demonstrations_block || "(Zero-Shot Mode: No exemplars in context)";
    document.getElementById("inspUserTurn").textContent = promptInfo.user_turn || nlpData.user_message || "";

    // Exemplars List
    const exContainer = document.getElementById("inspExemplarsList");
    exContainer.innerHTML = "";
    const exemplars = promptInfo.exemplars_used || [];

    if (exemplars.length === 0) {
      exContainer.innerHTML = `<div class="empty-state">No exemplars retrieved (Zero-Shot paradigm active).</div>`;
    } else {
      exemplars.forEach((ex, idx) => {
        const card = document.createElement("div");
        card.className = "exemplar-card";
        card.innerHTML = `
          <div class="ex-top">
            <span class="badge">Demonstration #${idx + 1} [${ex.language.toUpperCase()}]</span>
            <span class="ex-sim-score">BM25 / Cosine Sim: ${ex.similarity_score}</span>
          </div>
          <div class="ex-query"><strong>Customer:</strong> "${ex.user_query}"</div>
          <div class="ex-thought"><strong>Target Intent:</strong> ${ex.intent}</div>
        `;
        exContainer.appendChild(card);
      });
    }

    // Chain-of-Thought Trace
    const cotContainer = document.getElementById("inspCotTimeline");
    cotContainer.innerHTML = "";
    const steps = nlpData.cot_trace || [];
    steps.forEach((s) => {
      const item = document.createElement("div");
      item.className = "cot-item";
      item.innerHTML = `
        <div class="cot-title">Step ${s.step}: ${s.name}</div>
        <div class="cot-detail">${s.detail}</div>
      `;
      cotContainer.appendChild(item);
    });

    // Lexical Grounding
    const tableBody = document.getElementById("inspGroundingTableBody");
    tableBody.innerHTML = "";
    const sampleTerms = promptInfo.glossary_sample || [];
    if (sampleTerms.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="2" style="text-align: center; color: var(--text-dim);">No low-resource glossary entries needed for this language/strategy.</td></tr>`;
    } else {
      sampleTerms.forEach(([enTerm, targetTerm]) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td><strong>${enTerm}</strong></td>
          <td><span style="color: var(--accent-emerald); font-weight: 500;">${targetTerm}</span></td>
        `;
        tableBody.appendChild(row);
      });
    }
  },

  showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    this.elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 2800);
  },

  exportTranscript() {
    const rows = document.querySelectorAll(".message-row");
    if (rows.length <= 1) {
      this.showToast("No active conversation to export.");
      return;
    }

    let transcript = "# Customer Support Conversation Transcript\n";
    transcript += `Generated: ${new Date().toISOString()}\n`;
    transcript += `Paradigm: ${App.state.strategy}\n\n`;

    rows.forEach((r) => {
      const isUser = r.classList.contains("user");
      const bubble = r.querySelector(".msg-bubble");
      if (bubble) {
        transcript += `**${isUser ? 'Customer' : 'Bot Specialist'}**: ${bubble.textContent.trim()}\n\n`;
      }
    });

    const blob = new Blob([transcript], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `support_chat_transcript_${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    this.showToast("Transcript downloaded as Markdown.");
  }
};

window.addEventListener("DOMContentLoaded", () => {
  UI.init();
});
