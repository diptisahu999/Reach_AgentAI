// Agent Reach ChatGPT-style UI Frontend Controller

document.addEventListener("DOMContentLoaded", () => {
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const messagesContainer = document.getElementById("messagesContainer");
  const heroScreen = document.getElementById("heroScreen");
  const chatViewport = document.getElementById("chatViewport");
  const newChatBtn = document.getElementById("newChatBtn");
  const clearChatBtn = document.getElementById("clearChatBtn");
  const sidebar = document.getElementById("sidebar");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const historyList = document.getElementById("historyList");
  const suggestionCards = document.querySelectorAll(".suggestion-card");

  let chatHistory = JSON.parse(localStorage.getItem("agent_reach_history") || "[]");
  let isSearching = false;

  // Initialize UI
  renderHistory();
  autoResizeTextarea();

  // Sidebar toggle
  sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
  });

  // Auto-resize textarea
  chatInput.addEventListener("input", autoResizeTextarea);

  function autoResizeTextarea() {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + "px";
  }

  // Handle keypress (Enter to submit, Shift+Enter for newline)
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Shortcut Ctrl + K for New Chat
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      startNewChat();
    }
  });

  sendBtn.addEventListener("click", handleSend);
  newChatBtn.addEventListener("click", startNewChat);
  clearChatBtn.addEventListener("click", startNewChat);

  // Click on suggestion cards
  suggestionCards.forEach((card) => {
    card.addEventListener("click", () => {
      const prompt = card.getAttribute("data-prompt");
      if (prompt) {
        chatInput.value = prompt;
        handleSend();
      }
    });
  });

  function startNewChat() {
    messagesContainer.innerHTML = "";
    heroScreen.style.display = "flex";
    chatInput.value = "";
    autoResizeTextarea();
    chatInput.focus();
  }

  async function handleSend() {
    const text = chatInput.value.trim();
    if (!text || isSearching) return;

    // Hide hero welcome screen
    heroScreen.style.display = "none";

    // Append User Message
    appendUserMessage(text);
    chatInput.value = "";
    autoResizeTextarea();

    // Save to history
    saveSearchQuery(text);

    // Append Bot Thinking Message
    const botMsgId = "msg-" + Date.now();
    const botRow = createBotMessageElement(botMsgId, text);
    messagesContainer.appendChild(botRow);
    scrollToBottom();

    isSearching = true;
    sendBtn.disabled = true;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, num_results: 5 }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Search request failed with status " + res.status);
      }

      const data = await res.json();
      populateBotResponse(botMsgId, data);
    } catch (err) {
      displayBotError(botMsgId, err.message);
    } finally {
      isSearching = false;
      sendBtn.disabled = false;
      scrollToBottom();
      chatInput.focus();
    }
  }

  function appendUserMessage(text) {
    const row = document.createElement("div");
    row.className = "message-row user";
    row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
    messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function createBotMessageElement(id, query) {
    const row = document.createElement("div");
    row.className = "message-row bot";
    row.id = id;

    const isYoutube = /(youtube\.com|youtu\.be)/i.test(query);
    const isUrl = query.startsWith("http://") || query.startsWith("https://") || query.includes("http://") || query.includes("https://");

    let statusText = "Searching the live web via Exa AI...";
    if (isYoutube) {
      statusText = "Extracting video details & metadata via yt-dlp...";
    } else if (isUrl) {
      statusText = "Fetching and cleaning page via Jina Reader...";
    }

    row.innerHTML = `
      <div class="bot-avatar">👁️</div>
      <div class="bot-content-area">
        <div class="search-badge-step">
          <div class="spinner"></div>
          <span class="status-label">${statusText}</span>
        </div>
        <div class="sources-carousel" style="display: none;"></div>
        <div class="markdown-body"></div>
      </div>
    `;
    return row;
  }

  function populateBotResponse(id, data) {
    const row = document.getElementById(id);
    if (!row) return;

    const badge = row.querySelector(".search-badge-step");
    const sourcesContainer = row.querySelector(".sources-carousel");
    const markdownBody = row.querySelector(".markdown-body");

    // Update status badge
    if (data.type === "youtube_video") {
      if (data.metadata && data.metadata.error) {
        badge.style.borderColor = "rgba(239, 68, 68, 0.4)";
        badge.style.background = "rgba(239, 68, 68, 0.1)";
        badge.style.color = "#fca5a5";
        badge.innerHTML = `⚠️ <span>YouTube video could not be loaded</span>`;
      } else {
        const dur = data.metadata && data.metadata.duration ? ` (${data.metadata.duration})` : "";
        badge.innerHTML = `📺 <span>YouTube video extracted via yt-dlp${dur}</span>`;
      }
    } else if (data.type === "url_read") {
      if (data.metadata && data.metadata.error) {
        badge.style.borderColor = "rgba(245, 158, 11, 0.4)";
        badge.style.background = "rgba(245, 158, 11, 0.1)";
        badge.style.color = "#fcd34d";
        badge.innerHTML = `⚠️ <span>Webpage access restricted (${data.metadata.status_code || "error"})</span>`;
      } else {
        badge.innerHTML = `✅ <span>Webpage successfully extracted (${data.metadata.total_characters || 0} chars)</span>`;
      }
    } else {
      badge.innerHTML = `✅ <span>Found ${data.sources.length} sources via Exa Neural Search</span>`;
    }

    // Render source pills if any
    if (data.sources && data.sources.length > 0) {
      sourcesContainer.style.display = "flex";
      sourcesContainer.innerHTML = data.sources
        .map((src, i) => {
          const domain = getDomain(src.url);
          return `
            <a href="${src.url}" target="_blank" rel="noopener noreferrer" class="source-pill" title="${escapeHtml(src.title)}">
              <span class="source-pill-num">${i + 1}</span>
              <span>${escapeHtml(src.title.length > 28 ? src.title.slice(0, 28) + '...' : src.title)}</span>
              <span style="font-size: 10px; color: #64748b;">(${domain})</span>
            </a>
          `;
        })
        .join("");
    }

    // Render markdown content
    if (window.marked && data.summary) {
      markdownBody.innerHTML = marked.parse(data.summary);
    } else {
      markdownBody.textContent = data.summary || "No response data available.";
    }
  }

  function displayBotError(id, errorMsg) {
    const row = document.getElementById(id);
    if (!row) return;

    const badge = row.querySelector(".search-badge-step");
    const markdownBody = row.querySelector(".markdown-body");

    badge.style.borderColor = "rgba(239, 68, 68, 0.4)";
    badge.style.background = "rgba(239, 68, 68, 0.1)";
    badge.style.color = "#fca5a5";
    badge.innerHTML = `⚠️ <span>Error during search request</span>`;

    markdownBody.innerHTML = `
      <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); padding: 12px 16px; border-radius: 8px; color: #fca5a5;">
        <strong>Failed to retrieve results:</strong>
        <p style="margin-top: 6px; font-size: 13px;">${escapeHtml(errorMsg)}</p>
      </div>
    `;
  }

  function saveSearchQuery(query) {
    if (!chatHistory.includes(query)) {
      chatHistory.unshift(query);
      if (chatHistory.length > 25) chatHistory.pop();
      localStorage.setItem("agent_reach_history", JSON.stringify(chatHistory));
      renderHistory();
    }
  }

  function renderHistory() {
    if (!historyList) return;
    if (chatHistory.length === 0) {
      historyList.innerHTML = `<div style="padding: 8px 10px; font-size: 12px; color: var(--text-dim);">No previous searches</div>`;
      return;
    }
    historyList.innerHTML = chatHistory
      .map(
        (item) => `
        <div class="history-item" title="${escapeHtml(item)}" data-query="${escapeHtml(item)}">
          ${escapeHtml(item)}
        </div>
      `
      )
      .join("");

    historyList.querySelectorAll(".history-item").forEach((el) => {
      el.addEventListener("click", () => {
        const query = el.getAttribute("data-query");
        if (query) {
          chatInput.value = query;
          handleSend();
        }
      });
    });
  }

  function getDomain(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return "web";
    }
  }

  function scrollToBottom() {
    chatViewport.scrollTop = chatViewport.scrollHeight;
  }

  function escapeHtml(str) {
    return (str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
