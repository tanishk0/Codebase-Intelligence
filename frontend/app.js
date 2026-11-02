const state = { repos: [], activeRepoId: null, activeRepoUrl: null, conversations: [], conversationId: null, oldestMessageId: null, hasMoreMessages: false, loadingOlder: false, authToken: null };
const els = {
  ingestForm: document.getElementById("ingest-form"), repoUrlInput: document.getElementById("repo-url"), repoBranchInput: document.getElementById("repo-branch"), llmSummariesInput: document.getElementById("llm-summaries"), ingestBtn: document.getElementById("ingest-btn"), ingestLocalBtn: document.getElementById("ingest-local-btn"), ingestStatus: document.getElementById("ingest-status"), reposList: document.getElementById("repos-list"), refreshReposBtn: document.getElementById("refresh-repos-btn"), activeRepoLabel: document.getElementById("active-repo-label"), healthBanner: document.getElementById("health-banner"), healthAlert: document.getElementById("health-alert"), reindexRepoBtn: document.getElementById("reindex-repo-btn"), newChatBtn: document.getElementById("new-chat-btn"), newSidebarChatBtn: document.getElementById("new-sidebar-chat-btn"), conversationsList: document.getElementById("conversations-list"), chatMessages: document.getElementById("chat-messages"), chatForm: document.getElementById("chat-form"), chatInput: document.getElementById("chat-input"), sendBtn: document.getElementById("send-btn"),
};

function escapeHtml(value) { return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function renderMarkdownLite(text) {
  let html = escapeHtml(text);
  html = html.replace(/```(?:\w+)?\n([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`).replace(/`([^`\n]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return html.split(/(<pre>[\s\S]*?<\/pre>)/g).map((part) => part.startsWith("<pre>") ? part : part.replace(/\n/g, "<br/>")) .join("");
}
function welcome() { return `<div class="welcome-state"><h3>Ask anything about your codebase</h3><p>Select a repository, start a chat, and your conversation will be saved here.</p></div>`; }
function scrollBottom() { els.chatMessages.scrollTop = els.chatMessages.scrollHeight; }
async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.authToken) headers["Authorization"] = `Bearer ${state.authToken}`;
  const res = await fetch(url, { ...options, headers });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

async function checkHealth() {
  try {
    const data = await api("/api/health");
    if (data.ok) { els.healthBanner.textContent = `Ready • ${data.chat_model} + BM25/vector retrieval`; els.healthAlert.classList.add("hidden"); }
    else { els.healthBanner.textContent = "Configuration check needed"; els.healthAlert.innerHTML = `<strong>Setup Check:</strong><br/>${data.issues.map((item) => `• ${escapeHtml(item)}`).join("<br/>")}`; els.healthAlert.classList.remove("hidden"); }
  } catch { els.healthBanner.textContent = "Backend unreachable"; }
}

function renderRepos() {
  if (!state.repos.length) { els.reposList.innerHTML = `<div class="empty-hint">No repositories indexed yet.</div>`; return; }
  els.reposList.innerHTML = state.repos.map((repo) => `<div class="repo-item ${repo.id === state.activeRepoId ? "active" : ""}" data-id="${escapeHtml(repo.id)}"><div class="repo-name">${escapeHtml(repo.repo_url.replace("https://github.com/", ""))}</div><div class="repo-meta">${repo.chunk_count || 0} chunks • ${escapeHtml(repo.branch || "main")}</div></div>`).join("");
  els.reposList.querySelectorAll(".repo-item").forEach((item) => item.addEventListener("click", async () => { const repo = state.repos.find((entry) => entry.id === item.dataset.id); if (repo) await selectRepo(repo); }));
}
async function loadRepositories() {
  try { const data = await api("/api/repos"); state.repos = data.repos || []; renderRepos(); if (!state.activeRepoId && state.repos.length) await selectRepo(state.repos[0]); }
  catch (err) { els.reposList.innerHTML = `<div class="empty-hint">${escapeHtml(err.message)}</div>`; }
}

function renderConversations() {
  if (!state.activeRepoId) { els.conversationsList.innerHTML = `<div class="empty-hint">Select a repository to view its chats.</div>`; return; }
  if (!state.conversations.length) { els.conversationsList.innerHTML = `<div class="empty-hint">No chats yet.</div>`; return; }
  els.conversationsList.innerHTML = state.conversations.map((chat) => `<div class="conversation-item ${chat.id === state.conversationId ? "active" : ""}" data-id="${escapeHtml(chat.id)}"><div class="conversation-title">${escapeHtml(chat.title || "New chat")}</div><div class="conversation-date">${new Date(chat.updated_at).toLocaleString()}</div></div>`).join("");
  els.conversationsList.querySelectorAll(".conversation-item").forEach((item) => item.addEventListener("click", () => loadConversation(item.dataset.id)));
}
async function loadConversations(selectLatest = false) {
  if (!state.activeRepoId) return;
  const repoId = state.activeRepoId; const data = await api(`/api/repos/${encodeURIComponent(repoId)}/conversations`);
  if (state.activeRepoId !== repoId) return;
  state.conversations = data.conversations || []; renderConversations();
  if (selectLatest && state.conversations.length) await loadConversation(state.conversations[0].id);
}
async function selectRepo(repo) {
  state.activeRepoId = repo.id; state.activeRepoUrl = repo.repo_url; state.conversationId = null; state.oldestMessageId = null; state.hasMoreMessages = false;
  els.activeRepoLabel.textContent = `${repo.repo_url.replace("https://github.com/", "")} (${repo.chunk_count} chunks)`; els.chatMessages.innerHTML = welcome(); renderRepos(); await loadConversations(true);
}

function appendStoredMessage(message, prepend = false) {
  const div = document.createElement("div"); div.className = `msg ${message.role}`;
  if (message.role === "assistant") div.innerHTML = `<div class="msg-content">${renderMarkdownLite(message.content)}</div>`; else div.textContent = message.content;
  if (prepend) els.chatMessages.prepend(div); else els.chatMessages.appendChild(div);
}
function renderMessagePage(messages, prepend = false) {
  els.chatMessages.querySelector(".welcome-state")?.remove(); els.chatMessages.querySelector(".load-older")?.remove();
  if (prepend) [...messages].reverse().forEach((message) => appendStoredMessage(message, true)); else messages.forEach((message) => appendStoredMessage(message));
  if (state.hasMoreMessages) { const button = document.createElement("button"); button.className = "load-older"; button.textContent = "Load older messages"; button.addEventListener("click", loadOlderMessages); els.chatMessages.prepend(button); }
}
async function fetchMessagePage(beforeId = null) {
  const query = new URLSearchParams({ limit: "4" }); if (beforeId) query.set("before_id", beforeId);
  return api(`/api/conversations/${encodeURIComponent(state.conversationId)}/messages?${query}`);
}
async function loadConversation(conversationId) {
  state.conversationId = conversationId; state.oldestMessageId = null; state.hasMoreMessages = false; renderConversations(); els.chatMessages.innerHTML = `<div class="empty-hint">Loading chat...</div>`;
  try {
    const data = await fetchMessagePage(); state.hasMoreMessages = Boolean(data.has_more); state.oldestMessageId = data.next_before_id || (data.messages[0] && data.messages[0].id) || null;
    els.chatMessages.innerHTML = ""; renderMessagePage(data.messages || []); if (!data.messages.length) els.chatMessages.innerHTML = welcome(); scrollBottom();
  } catch (err) { els.chatMessages.innerHTML = `<div class="empty-hint">${escapeHtml(err.message)}</div>`; }
}
async function loadOlderMessages() {
  if (state.loadingOlder || !state.hasMoreMessages || !state.oldestMessageId) return;
  state.loadingOlder = true; const oldHeight = els.chatMessages.scrollHeight; const oldTop = els.chatMessages.scrollTop;
  try {
    const data = await fetchMessagePage(state.oldestMessageId); state.hasMoreMessages = Boolean(data.has_more); state.oldestMessageId = data.next_before_id || (data.messages[0] && data.messages[0].id) || null;
    renderMessagePage(data.messages || [], true); els.chatMessages.scrollTop = oldTop + els.chatMessages.scrollHeight - oldHeight;
  } catch (err) { console.error(err); } finally { state.loadingOlder = false; }
}

async function newConversation() {
  if (!state.activeRepoId) { els.ingestStatus.textContent = "Select a repository before starting a chat."; return; }
  try { const data = await api(`/api/repos/${encodeURIComponent(state.activeRepoId)}/conversations`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "New chat" }) }); await loadConversations(); await loadConversation(data.conversation.id); }
  catch (err) { els.ingestStatus.textContent = `✗ ${err.message}`; }
}
function appendAssistantResponse(data) {
  const div = document.createElement("div"); div.className = "msg assistant";
  const chunks = (data.chunks || []).map((chunk, index) => `<div class="chunk-card"><div class="chunk-card-header"><span>#${index + 1} ${escapeHtml(chunk.file_path)}:L${chunk.start_line}-L${chunk.end_line}</span></div><pre>${escapeHtml(chunk.content)}</pre></div>`).join("");
  div.innerHTML = `<div class="msg-content">${renderMarkdownLite(data.answer)}</div>${chunks ? `<details class="chunks-drawer"><summary>Inspect Retrieved Chunks (${data.chunks.length})</summary>${chunks}</details>` : ""}`; els.chatMessages.appendChild(div);
}
async function refreshActivePageState() { if (!state.conversationId) return; const data = await fetchMessagePage(); state.hasMoreMessages = Boolean(data.has_more); state.oldestMessageId = data.next_before_id || (data.messages[0] && data.messages[0].id) || null; }
async function sendChatMessage(message) {
  if (!state.activeRepoId) { els.ingestStatus.textContent = "Select a repository before sending a message."; return; }
  appendStoredMessage({ role: "user", content: message }); els.sendBtn.disabled = true; els.chatInput.disabled = true;
  const thinking = document.createElement("div"); thinking.className = "msg assistant"; thinking.textContent = "Searching the codebase..."; els.chatMessages.appendChild(thinking); scrollBottom();
  try {
    const data = await api("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, repo_id: state.activeRepoId, conversation_id: state.conversationId }) });
    thinking.remove(); state.conversationId = data.conversation_id; appendAssistantResponse(data); await refreshActivePageState(); await loadConversations(); renderConversations();
  } catch (err) { thinking.textContent = `Error: ${err.message}`; }
  finally { els.sendBtn.disabled = false; els.chatInput.disabled = false; els.chatInput.focus(); }
}
function formatSyncMessage(data) {
  if (typeof data.unchanged_files === "number" && data.unchanged_files > 0) {
    if ((data.changed_files || 0) === 0 && (data.deleted_files || 0) === 0) {
      return `✓ Up to date: ${data.unchanged_files} files unchanged (0 chunks re-embedded).`;
    }
    return `✓ Synced: ${data.changed_files || 0} changed, ${data.unchanged_files} unchanged (${data.embedded_chunks || 0} chunks re-embedded).`;
  }
  return `✓ Indexed ${data.file_count} files (${data.total_indexed_chunks} chunks).`;
}

async function triggerIngest(repoUrl, branch, llmSummaries) {
  els.ingestBtn.disabled = true; els.ingestLocalBtn.disabled = true; els.reindexRepoBtn.disabled = true; els.ingestStatus.textContent = `Indexing ${repoUrl}...`;
  try { const data = await api("/api/ingest", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ repo_url: repoUrl, branch: branch || null, llm_summaries: llmSummaries }) }); els.ingestStatus.textContent = formatSyncMessage(data); await checkHealth(); await loadRepositories(); const created = state.repos.find((repo) => repo.id === data.repo_id); if (created) await selectRepo(created); }
  catch (err) { els.ingestStatus.textContent = `✗ ${err.message}`; } finally { els.ingestBtn.disabled = false; els.ingestLocalBtn.disabled = false; els.reindexRepoBtn.disabled = false; }
}

async function reindexActiveRepo() {
  if (!state.activeRepoId) { els.ingestStatus.textContent = "Select a repository to re-index."; return; }
  els.reindexRepoBtn.disabled = true; els.ingestBtn.disabled = true; els.ingestLocalBtn.disabled = true;
  els.ingestStatus.textContent = `Re-indexing changed files in ${state.activeRepoUrl || "repository"}...`;
  try {
    const data = await api(`/api/repos/${encodeURIComponent(state.activeRepoId)}/reindex`, { method: "POST" });
    els.ingestStatus.textContent = formatSyncMessage(data);
    await loadRepositories();
    const updated = state.repos.find((repo) => repo.id === state.activeRepoId);
    if (updated) els.activeRepoLabel.textContent = `${updated.repo_url.replace("https://github.com/", "")} (${updated.chunk_count} chunks)`;
  } catch (err) {
    els.ingestStatus.textContent = `✗ ${err.message}`;
  } finally {
    els.reindexRepoBtn.disabled = false; els.ingestBtn.disabled = false; els.ingestLocalBtn.disabled = false;
  }
}

els.ingestForm.addEventListener("submit", (event) => { event.preventDefault(); triggerIngest(els.repoUrlInput.value.trim(), els.repoBranchInput.value.trim(), els.llmSummariesInput.checked); });
els.ingestLocalBtn.addEventListener("click", () => { els.repoUrlInput.value = "local"; triggerIngest("local", "main", els.llmSummariesInput.checked); });
els.reindexRepoBtn.addEventListener("click", reindexActiveRepo);
els.refreshReposBtn.addEventListener("click", loadRepositories); els.newChatBtn.addEventListener("click", newConversation); els.newSidebarChatBtn.addEventListener("click", newConversation);
els.chatForm.addEventListener("submit", (event) => { event.preventDefault(); const message = els.chatInput.value.trim(); if (!message) return; els.chatInput.value = ""; sendChatMessage(message); });
els.chatInput.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); els.chatForm.requestSubmit(); } });
els.chatMessages.addEventListener("scroll", () => { if (els.chatMessages.scrollTop <= 8) loadOlderMessages(); });
document.querySelectorAll(".prompt-chip").forEach((chip) => chip.addEventListener("click", () => chip.dataset.prompt && sendChatMessage(chip.dataset.prompt)));
checkHealth(); loadRepositories();
