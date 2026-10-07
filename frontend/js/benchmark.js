/**
 * NLP Evaluation Benchmark Suite & Exemplar Memory Explorer
 */

const BenchmarkUI = {
  elements: {},

  init() {
    this.cacheElements();
    this.bindEvents();
  },

  cacheElements() {
    this.elements = {
      benchmarkModal: document.getElementById("benchmarkModal"),
      btnOpenBenchmark: document.getElementById("btnOpenBenchmark"),
      btnCloseBenchmark: document.getElementById("btnCloseBenchmark"),
      btnRunBenchmark: document.getElementById("btnRunBenchmark"),
      benchmarkStatus: document.getElementById("benchmarkStatus"),
      benchmarkResults: document.getElementById("benchmarkResults"),
      benchmarkTableBody: document.getElementById("benchmarkTableBody"),
      chartComparisons: document.getElementById("chartComparisons"),

      exemplarsModal: document.getElementById("exemplarsModal"),
      btnOpenExemplars: document.getElementById("btnOpenExemplars"),
      btnCloseExemplars: document.getElementById("btnCloseExemplars"),
      exemplarLangFilter: document.getElementById("exemplarLangFilter"),
      exemplarIntentFilter: document.getElementById("exemplarIntentFilter"),
      bankList: document.getElementById("bankList"),

      databaseModal: document.getElementById("databaseModal"),
      btnOpenDatabase: document.getElementById("btnOpenDatabase"),
      btnCloseDatabase: document.getElementById("btnCloseDatabase"),
      btnRefreshDb: document.getElementById("btnRefreshDb"),
      dbConnStatus: document.getElementById("dbConnStatus"),
      dbTargetUri: document.getElementById("dbTargetUri"),
      dbTargetName: document.getElementById("dbTargetName"),
      dbCountConversations: document.getElementById("dbCountConversations"),
      dbCountExemplars: document.getElementById("dbCountExemplars"),
      dbHistoryList: document.getElementById("dbHistoryList"),
      headerDbStatusText: document.getElementById("headerDbStatusText")
    };
  },

  bindEvents() {
    // Benchmark Modal Open/Close
    this.elements.btnOpenBenchmark.addEventListener("click", () => {
      this.elements.benchmarkModal.classList.add("open");
    });

    this.elements.btnCloseBenchmark.addEventListener("click", () => {
      this.elements.benchmarkModal.classList.remove("open");
    });

    // Run Benchmark
    this.elements.btnRunBenchmark.addEventListener("click", () => {
      this.executeBenchmark();
    });

    // Exemplars Modal Open/Close
    this.elements.btnOpenExemplars.addEventListener("click", () => {
      this.elements.exemplarsModal.classList.add("open");
      this.loadExemplarBank();
    });

    this.elements.btnCloseExemplars.addEventListener("click", () => {
      this.elements.exemplarsModal.classList.remove("open");
    });

    this.elements.exemplarLangFilter.addEventListener("change", () => {
      this.loadExemplarBank();
    });

    this.elements.exemplarIntentFilter.addEventListener("change", () => {
      this.loadExemplarBank();
    });

    // Database Modal Open/Close & Refresh
    if (this.elements.btnOpenDatabase) {
      this.elements.btnOpenDatabase.addEventListener("click", () => {
        this.elements.databaseModal.classList.add("open");
        this.loadDatabaseTelemetry();
      });
    }

    if (this.elements.btnCloseDatabase) {
      this.elements.btnCloseDatabase.addEventListener("click", () => {
        this.elements.databaseModal.classList.remove("open");
      });
    }

    if (this.elements.btnRefreshDb) {
      this.elements.btnRefreshDb.addEventListener("click", () => {
        this.loadDatabaseTelemetry();
      });
    }

    // Initial check of DB status to reflect in UI
    setTimeout(() => {
      this.checkInitialDbStatus();
    }, 500);
  },

  async executeBenchmark() {
    this.elements.btnRunBenchmark.disabled = true;
    this.elements.benchmarkStatus.innerHTML = `<span style="color: var(--accent-amber);">⚡ Running multi-strategy test across low-resource languages (Swahili, Yoruba, Quechua, Bengali, Basque, Tagalog, Amharic)...</span>`;

    try {
      const data = await App.api.runBenchmark();
      this.renderBenchmarkResults(data);
      this.elements.benchmarkStatus.innerHTML = `<span style="color: var(--accent-emerald);">✔ Benchmark successfully completed across ${data.languages_tested.length} languages!</span>`;
    } catch (err) {
      console.error("[Benchmark] Run error:", err);
      this.elements.benchmarkStatus.innerHTML = `<span style="color: var(--accent-rose);">❌ Benchmark execution failed.</span>`;
    } finally {
      this.elements.btnRunBenchmark.disabled = false;
    }
  },

  renderBenchmarkResults(data) {
    const summary = data.summary || {};
    this.elements.benchmarkTableBody.innerHTML = "";
    this.elements.chartComparisons.innerHTML = "";

    const rows = [
      { key: "zero_shot", label: "Zero-Shot Baseline", class: "zero-shot" },
      { key: "few_shot", label: "Monolingual Few-Shot ICL", class: "few-shot" },
      { key: "cross_lingual_icl", label: "Cross-Lingual ICL (X-ICL)", class: "x-icl" },
      { key: "chain_of_thought", label: "Multilingual Chain-of-Thought (X-CoT)", class: "cot" },
      { key: "pivot_grounding", label: "Pivot Lexicon Grounding", class: "pivot" }
    ];

    rows.forEach((r) => {
      const metrics = summary[r.key];
      if (!metrics) return;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${r.label}</strong></td>
        <td><span class="badge ${metrics.intent_accuracy >= 80 ? 'tier-low' : 'tier-high'}">${metrics.intent_accuracy}%</span></td>
        <td><span class="badge">${metrics.policy_adherence}%</span></td>
        <td><span class="badge">${metrics.lexical_overlap_rouge}%</span></td>
        <td><span class="badge tier-low">${metrics.vocab_grounding}%</span></td>
        <td style="font-family: var(--font-mono); font-size: 0.75rem;">${metrics.avg_latency_ms}ms</td>
      `;
      this.elements.benchmarkTableBody.appendChild(tr);

      // Visual Progress Chart
      const chartRow = document.createElement("div");
      chartRow.className = "chart-row";
      chartRow.innerHTML = `
        <div class="chart-label-row">
          <span><strong>${r.label}</strong> (Intent Accuracy)</span>
          <span style="font-family: var(--font-mono); font-weight: 600;">${metrics.intent_accuracy}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill ${r.class}" style="width: ${metrics.intent_accuracy}%;"></div>
        </div>
      `;
      this.elements.chartComparisons.appendChild(chartRow);
    });

    this.elements.benchmarkResults.style.display = "block";
  },

  async loadExemplarBank() {
    const lang = this.elements.exemplarLangFilter.value;
    const intent = this.elements.exemplarIntentFilter.value;
    this.elements.bankList.innerHTML = `<div style="color: var(--text-dim);">Loading memory bank...</div>`;

    try {
      const data = await App.api.getExemplars(lang, intent);
      const exemplars = data.exemplars || [];
      this.elements.bankList.innerHTML = "";

      if (exemplars.length === 0) {
        this.elements.bankList.innerHTML = `<div style="color: var(--text-dim); padding: 12px;">No exemplars found for this filter criteria.</div>`;
        return;
      }

      exemplars.forEach((ex) => {
        const item = document.createElement("div");
        item.className = "exemplar-card";
        item.innerHTML = `
          <div class="ex-top">
            <span class="badge tier-badge tier-low">Language: ${ex.language.toUpperCase()}</span>
            <span class="badge tier-badge tier-high">Intent: ${ex.intent}</span>
          </div>
          <div class="ex-query"><strong>Customer:</strong> "${ex.user_query}"</div>
          ${ex.thought ? `<div class="ex-thought"><strong>Reasoning Trace:</strong> ${ex.thought}</div>` : ''}
          <div class="ex-response"><strong>Reference Response:</strong> ${ex.bot_response}</div>
        `;
        this.elements.bankList.appendChild(item);
      });
    } catch (err) {
      console.error("[Benchmark] Exemplar bank error:", err);
      this.elements.bankList.innerHTML = `<div style="color: var(--accent-rose);">Failed to load exemplars.</div>`;
    }
  },

  async checkInitialDbStatus() {
    try {
      const status = await App.api.getDbStatus();
      if (this.elements.headerDbStatusText) {
        if (status.connected) {
          this.elements.headerDbStatusText.textContent = "🍃 MongoDB: Connected";
          this.elements.headerDbStatusText.style.color = "var(--accent-emerald)";
        } else {
          this.elements.headerDbStatusText.textContent = "🍃 MongoDB: Standby";
        }
      }
    } catch (e) {
      console.warn("[Benchmark] DB status check error:", e);
    }
  },

  async loadDatabaseTelemetry() {
    if (!this.elements.dbConnStatus) return;
    this.elements.dbConnStatus.textContent = "Connecting...";

    try {
      const status = await App.api.getDbStatus();
      if (status.connected) {
        this.elements.dbConnStatus.textContent = "Connected (Online)";
        this.elements.dbConnStatus.style.color = "var(--accent-emerald)";
        if (this.elements.headerDbStatusText) {
          this.elements.headerDbStatusText.textContent = "🍃 MongoDB: Connected";
        }
      } else {
        this.elements.dbConnStatus.textContent = "Standby (Memory Fallback)";
        this.elements.dbConnStatus.style.color = "var(--accent-amber)";
        if (this.elements.headerDbStatusText) {
          this.elements.headerDbStatusText.textContent = "🍃 MongoDB: Standby";
        }
      }

      this.elements.dbTargetUri.textContent = `URI: ${status.uri_configured || "mongodb://localhost:27017"}`;
      this.elements.dbTargetName.textContent = status.database_name || "customersupport_chatbot";
      this.elements.dbCountConversations.textContent = status.counts?.conversations ?? 0;
      this.elements.dbCountExemplars.textContent = status.counts?.exemplars ?? 0;

      // Fetch persisted history
      this.elements.dbHistoryList.innerHTML = `<div style="color: var(--text-dim); padding: 8px;">Loading chat records...</div>`;
      const histData = await App.api.getHistory(30);
      const history = histData.history || [];
      this.elements.dbHistoryList.innerHTML = "";

      if (history.length === 0) {
        this.elements.dbHistoryList.innerHTML = `
          <div class="empty-state" style="padding: 1.5rem; text-align: center; color: var(--text-dim);">
            No conversations logged yet. Send messages in the chat window to view stored telemetry records.
          </div>
        `;
        return;
      }

      history.forEach((rec, idx) => {
        const card = document.createElement("div");
        card.className = "db-history-card";
        const dateStr = rec.timestamp ? new Date(rec.timestamp).toLocaleTimeString() : `#${idx+1}`;
        const langCode = rec.target_language?.code || rec.language_code || "en";
        const langFlag = rec.target_language?.flag || "🌐";
        const langName = rec.target_language?.name || langCode.toUpperCase();

        card.innerHTML = `
          <div class="db-history-header">
            <span><strong>${langFlag} ${langName}</strong> • Intent: <code>${rec.intent}</code></span>
            <span>⏱️ ${rec.latency_ms || 0}ms • ${dateStr}</span>
          </div>
          <div class="db-history-msg"><strong>User:</strong> "${rec.user_message}"</div>
          <div class="db-history-resp"><strong>Bot:</strong> ${rec.response}</div>
        `;
        this.elements.dbHistoryList.appendChild(card);
      });
    } catch (err) {
      console.error("[Benchmark] Failed to load database telemetry:", err);
      this.elements.dbConnStatus.textContent = "Connection Error";
      this.elements.dbConnStatus.style.color = "var(--accent-rose)";
    }
  }
};

window.addEventListener("DOMContentLoaded", () => {
  BenchmarkUI.init();
});
