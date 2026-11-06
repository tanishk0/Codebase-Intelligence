/**
 * API client and formatting helpers for Codebase Copilot.
 */

export async function apiFetch(url, options = {}) {
  const headers = {
    ...(options.headers || {}),
  };

  const res = await fetch(url, {
    ...options,
    headers,
  });

  let data = null;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await res.json();
  } else {
    const text = await res.text();
    data = { detail: text };
  }

  if (!res.ok) {
    throw new Error((data && data.detail) || `Request failed (${res.status})`);
  }
  return data;
}

export async function fetchHealth() {
  return apiFetch("/api/health");
}

export async function fetchRepositories() {
  const data = await apiFetch("/api/repos");
  return data.repos || [];
}

export async function fetchConversations(repoId) {
  const data = await apiFetch(`/api/repos/${encodeURIComponent(repoId)}/conversations`);
  return data.conversations || [];
}

export async function createConversation(repoId, title = "New chat") {
  const data = await apiFetch(`/api/repos/${encodeURIComponent(repoId)}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  return data.conversation;
}

export async function fetchConversationMessages(conversationId, { limit = 12, beforeId = null } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (beforeId) {
    params.set("before_id", String(beforeId));
  }
  return apiFetch(`/api/conversations/${encodeURIComponent(conversationId)}/messages?${params}`);
}

export async function ingestRepository({ repoUrl, branch = null, llmSummaries = false }) {
  return apiFetch("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_url: repoUrl,
      branch: branch || null,
      llm_summaries: Boolean(llmSummaries),
    }),
  });
}

export async function triggerReindex(repoId) {
  return apiFetch(`/api/repos/${encodeURIComponent(repoId)}/reindex`, {
    method: "POST",
  });
}

export async function fetchJobStatus(jobId) {
  const data = await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}`);
  return data.job || data;
}

/**
 * Streams a chat message response via SSE (/api/chat/stream) with automatic fallback to /api/chat.
 */
export async function streamChatMessage({
  message,
  repoId,
  conversationId,
  onMetadata,
  onToken,
  onDone,
}) {
  const payload = {
    message,
    repo_id: repoId,
    conversation_id: conversationId,
  };

  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok || !res.body) {
    const fallbackData = await apiFetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (onMetadata) onMetadata(fallbackData);
    if (onDone) onDone(fallbackData);
    return fallbackData;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let fullAnswer = "";
  let resolvedConversationId = conversationId;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const line = rawEvent.trim();
      if (!line.startsWith("data:")) continue;
      const evt = JSON.parse(line.slice(5).trim());

      if (evt.type === "error") {
        throw new Error(evt.detail || "Failed to generate response.");
      }

      if (evt.type === "metadata") {
        if (evt.conversation_id) {
          resolvedConversationId = evt.conversation_id;
        }
        if (onMetadata) onMetadata(evt);
      } else if (evt.type === "token") {
        const delta = evt.delta || "";
        fullAnswer += delta;
        if (onToken) onToken(delta, fullAnswer);
      } else if (evt.type === "done") {
        if (evt.conversation_id) {
          resolvedConversationId = evt.conversation_id;
        }
        fullAnswer = evt.answer || fullAnswer;
        if (onDone) {
          onDone({
            ...evt,
            conversation_id: resolvedConversationId,
            answer: fullAnswer,
          });
        }
      }
    }
  }
}

/**
 * Formats a repository URL into a clean `owner/repo` display name.
 */
export function formatRepoName(repoUrl) {
  if (!repoUrl) return "Select repository";
  const cleaned = String(repoUrl)
    .trim()
    .replace(/^https?:\/\/(www\.)?github\.com\//i, "")
    .replace(/\.git$/i, "")
    .replace(/\/$/, "");
  if (cleaned.toLowerCase() === "local/codebase-copilot" || cleaned.toLowerCase() === "local") {
    return "local / codebase-copilot";
  }
  return cleaned;
}

/**
 * Formats an ISO timestamp into a concise relative string.
 */
export function formatRelativeTime(dateInput) {
  if (!dateInput) return "";
  const date = new Date(dateInput);
  if (Number.isNaN(date.getTime())) return "";

  const diffSeconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diffSeconds < 45) return "Just now";
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Groups conversations into chronological buckets for the sidebar.
 */
export function groupConversationsByDate(conversations) {
  const groups = {
    Today: [],
    Yesterday: [],
    "Previous 7 Days": [],
    Earlier: [],
  };

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - 86400000;
  const startOfWeek = startOfToday - 7 * 86400000;

  for (const chat of conversations) {
    const timestamp = new Date(chat.updated_at || chat.created_at || Date.now()).getTime();
    if (timestamp >= startOfToday) {
      groups.Today.push(chat);
    } else if (timestamp >= startOfYesterday) {
      groups.Yesterday.push(chat);
    } else if (timestamp >= startOfWeek) {
      groups["Previous 7 Days"].push(chat);
    } else {
      groups.Earlier.push(chat);
    }
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}

/**
 * Formats a repository sync response into a clean, non-technical status message (without chunk counts).
 */
export function formatSyncSummary(stats = {}) {
  if (typeof stats.unchanged_files === "number" && stats.unchanged_files > 0) {
    if ((stats.changed_files || 0) === 0 && (stats.deleted_files || 0) === 0) {
      return `Repository is up to date (${stats.unchanged_files} files verified).`;
    }
    return `Repository synced (${stats.changed_files || 0} updated, ${stats.unchanged_files} unchanged).`;
  }
  if (typeof stats.file_count === "number") {
    return `Repository indexed (${stats.file_count} files ready).`;
  }
  return "Repository synchronized.";
}
