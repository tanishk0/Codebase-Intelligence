const state = {
  repos: [],
  activeRepoId: null,
  activeRepoUrl: null,
  conversationId: null,
  history: [],
};

const els = {
  ingestForm: document.getElementById("ingest-form"),
  repoUrlInput: document.getElementById("repo-url"),
  repoBranchInput: document.getElementById("repo-branch"),
  llmSummariesInput: document.getElementById("llm-summaries"),
  ingestBtn: document.getElementById("ingest-btn"),
  ingestLocalBtn: document.getElementById("ingest-local-btn"),
  ingestStatus: document.getElementById("ingest-status"),
  reposList: document.getElementById("repos-list"),
  refreshReposBtn: document.getElementById("refresh-repos-btn"),
  activeRepoLabel: document.getElementById("active-repo-label"),
  healthBanner: document.getElementById("health-banner"),
  healthAlert: document.getElementById("health-alert"),
  newChatBtn: document.getElementById("new-chat-btn"),
  chatMessages: document.getElementById("chat-messages"),
  chatForm: document.getElementById("chat-form"),
  chatInput: document.getElementById("chat-input"),
  sendBtn: document.getElementById("send-btn"),
};

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderMarkdownLite(text) {
  let html = escapeHtml(text);
  html = html.replace(/```(?:\w+)?\n([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`);
  html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  const parts = html.split(/(<pre>[\s\S]*?<\/pre>)/g);
  return parts
    .map((p) => (p.startsWith("<pre>") ? p : p.replace(/\n/g, "<br/>")))
    .join("");
}

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.ok) {
      els.healthBanner.textContent = `Ready • ${data.chat_model} + Hybrid RRF (${data.embed_model})`;
      els.healthAlert.classList.add("hidden");
    } else {
      els.healthBanner.textContent = "Configuration check needed";
      els.healthAlert.innerHTML =
        `<strong>Setup Check:</strong><br/>` +
        data.issues.map((i) => `• ${escapeHtml(i)}`).join("<br/>");
      els.healthAlert.classList.remove("hidden");
    }
  } catch (err) {
    els.healthBanner.textContent = "Backend unreachable";
  }
}

async function loadRepositories() {
  try {
    const res = await fetch("/api/repos");
    if (!res.ok) {
      const err = await res.json();
      els.reposList.innerHTML = `<div class="empty-hint">${escapeHtml(err.detail || "Unable to load repos")}</div>`;
      return;
    }
    const data = await res.json();
    state.repos = data.repos || [];
    renderRepos();
    if (!state.activeRepoId && state.repos.length > 0) {
      selectRepo(state.repos[0]);
    }
  } catch (err) {
    els.reposList.innerHTML = `<div class="empty-hint">Connect Supabase to view indexed repos.</div>`;
  }
}

function renderRepos() {
  if (!state.repos.length) {
    els.reposList.innerHTML = `<div class="empty-hint">No repositories indexed yet. Click <strong>⚡ Index Local</strong> above to test immediately!</div>`;
    return;
  }

  els.reposList.innerHTML = state.repos
    .map((r) => {
      const isActive = r.id === state.activeRepoId ? "active" : "";
      const shortName = r.repo_url.replace("https://github.com/", "");
      return `
        <div class="repo-item ${isActive}" data-id="${escapeHtml(r.id)}">
          <div class="repo-name">${escapeHtml(shortName)}</div>
          <div class="repo-meta">${r.chunk_count || 0} chunks • branch: ${escapeHtml(r.branch || "main")}</div>
        </div>
      `;
    })
    .join("");

  els.reposList.querySelectorAll(".repo-item").forEach((item) => {
    item.addEventListener("click", () => {
      const repo = state.repos.find((r) => r.id === item.dataset.id);
      if (repo) selectRepo(repo);
    });
  });
}

function selectRepo(repo) {
  state.activeRepoId = repo.id;
  state.activeRepoUrl = repo.repo_url;
  state.conversationId = null;
  state.history = [];
  els.activeRepoLabel.textContent = `${repo.repo_url.replace("https://github.com/", "")} (${repo.chunk_count} chunks)`;
  renderRepos();
}

async function triggerIngest(repoUrl, branch, llmSummaries) {
  els.ingestBtn.disabled = true;
  els.ingestLocalBtn.disabled = true;
  els.ingestStatus.textContent = `Indexing ${repoUrl} (chunking + NVIDIA embeddings + Supabase)...`;

  try {
    const res = await fetch("/api/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_url: repoUrl,
        branch: branch || null,
        llm_summaries: llmSummaries,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Ingestion failed");
    }
    els.ingestStatus.textContent = `✓ Indexed ${data.file_count} files (${data.total_indexed_chunks} total chunks including file summaries).`;
    await checkHealth();
    await loadRepositories();
    const created = state.repos.find((r) => r.id === data.repo_id);
    if (created) selectRepo(created);
  } catch (err) {
    els.ingestStatus.textContent = `✗ ${err.message}`;
  } finally {
    els.ingestBtn.disabled = false;
    els.ingestLocalBtn.disabled = false;
  }
}

function appendUserMessage(text) {
  const welcome = els.chatMessages.querySelector(".welcome-state");
  if (welcome) welcome.remove();

  const div = document.createElement("div");
  div.className = "msg user";
  div.textContent = text;
  els.chatMessages.appendChild(div);
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
}

function appendAssistantMessage(data) {
  const div = document.createElement("div");
  div.className = "msg assistant";

  const badges = [];
  if (data.standalone_query && data.standalone_query !== data.original_query) {
    badges.push(`<span class="badge highlight" title="Follow-up rewritten for hybrid search">Rewritten: ${escapeHtml(data.standalone_query)}</span>`);
  }
  if (!data.needs_retrieval) {
    badges.push(`<span class="badge">Answered from conversation history</span>`);
  } else {
    badges.push(`<span class="badge">${(data.chunks || []).length} hybrid chunks</span>`);
  }
  if (data.target_symbol) {
    badges.push(`<span class="badge">symbol: ${escapeHtml(data.target_symbol)}</span>`);
  }
  if (data.target_file) {
    badges.push(`<span class="badge">file: ${escapeHtml(data.target_file)}</span>`);
  }

  const chunksHtml = (data.chunks || [])
    .map(
      (c, i) => `
      <div class="chunk-card">
        <div class="chunk-card-header">
          <span>#${i + 1} ${escapeHtml(c.file_path)}:L${c.start_line}-L${c.end_line} [${escapeHtml(c.is_context_expansion ? "context header" : c.node_type)}]</span>
          <span class="chunk-scores">rerank=${c.rerank_score} • rrf=${c.rrf_score} • sim=${c.similarity}</span>
        </div>
        <pre>${escapeHtml(c.content)}</pre>
      </div>
    `
    )
    .join("");

  const drawerHtml =
    data.chunks && data.chunks.length
      ? `<details class="chunks-drawer">
          <summary>Inspect Retrieved Chunks (${data.chunks.length})</summary>
          ${chunksHtml}
        </details>`
      : "";

  div.innerHTML = `
    <div class="msg-meta-bar">${badges.join("")}</div>
    <div class="msg-content">${renderMarkdownLite(data.answer)}</div>
    ${drawerHtml}
  `;
  els.chatMessages.appendChild(div);
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
}

async function sendChatMessage(message) {
  appendUserMessage(message);
  els.sendBtn.disabled = true;
  els.chatInput.disabled = true;

  const thinkingDiv = document.createElement("div");
  thinkingDiv.className = "msg assistant";
  thinkingDiv.textContent = "Running hybrid search & generating answer...";
  els.chatMessages.appendChild(thinkingDiv);
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        repo_id: state.activeRepoId,
        conversation_id: state.conversationId,
        history: state.history,
      }),
    });
    const data = await res.json();
    thinkingDiv.remove();

    if (!res.ok) {
      throw new Error(data.detail || "Chat request failed");
    }

    state.conversationId = data.conversation_id || state.conversationId;
    state.history.push({ role: "user", content: message });
    state.history.push({
      role: "assistant",
      content: data.answer,
      cited_chunk_ids: data.cited_chunk_ids || [],
    });

    appendAssistantMessage(data);
  } catch (err) {
    thinkingDiv.textContent = `Error: ${err.message}`;
  } finally {
    els.sendBtn.disabled = false;
    els.chatInput.disabled = false;
    els.chatInput.focus();
  }
}

// Event Listeners
els.ingestForm.addEventListener("submit", (e) => {
  e.preventDefault();
  triggerIngest(
    els.repoUrlInput.value.trim(),
    els.repoBranchInput.value.trim(),
    els.llmSummariesInput.checked
  );
});

els.ingestLocalBtn.addEventListener("click", () => {
  els.repoUrlInput.value = "local";
  triggerIngest("local", "main", els.llmSummariesInput.checked);
});

els.refreshReposBtn.addEventListener("click", loadRepositories);

els.newChatBtn.addEventListener("click", () => {
  state.conversationId = null;
  state.history = [];
  els.chatMessages.innerHTML = `<div class="welcome-state"><h3>Started a new conversation</h3><p>Ask a question about ${escapeHtml(state.activeRepoUrl || "your repository")}.</p></div>`;
});

els.chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const msg = els.chatInput.value.trim();
  if (!msg) return;
  els.chatInput.value = "";
  sendChatMessage(msg);
});

els.chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    els.chatForm.requestSubmit();
  }
});

document.querySelectorAll(".prompt-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const prompt = chip.dataset.prompt;
    if (prompt) sendChatMessage(prompt);
  });
});

// Initialize
checkHealth();
loadRepositories();

