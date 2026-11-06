import React, { useState, useEffect, useCallback } from "react";
import { Loader2, Terminal } from "lucide-react";
import LandingPage from "./pages/LandingPage";
import WorkspacePage from "./pages/WorkspacePage";
import {
  initializeAuth,
  signInWithGoogle,
  signOutUser,
  consumeUrlAuthError,
} from "./lib/auth";
import {
  fetchHealth,
  fetchRepositories,
  deleteRepository,
  fetchConversations,
  createConversation,
  fetchConversationMessages,
  ingestRepository,
  triggerReindex,
  fetchJobStatus,
  streamChatMessage,
  formatRepoName,
  formatSyncSummary,
} from "./api";

function resolveInitialPage() {
  if (typeof window === "undefined") return "landing";
  const path = window.location.pathname.toLowerCase();
  const hasOAuthCallback =
    window.location.search.includes("code=") ||
    window.location.hash.includes("access_token=");
  const pendingPostAuth =
    sessionStorage.getItem("copilot-post-auth-page") === "workspace";

  if (hasOAuthCallback || pendingPostAuth) {
    sessionStorage.removeItem("copilot-post-auth-page");
    return "workspace";
  }
  if (path.startsWith("/workspace")) {
    return "workspace";
  }
  return "landing";
}

export default function App() {
  // Page navigation state ("landing" | "workspace")
  const [currentPage, setCurrentPage] = useState(resolveInitialPage);

  // Default to Clean Light Mode with persistence for Workspace
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem("copilot-theme");
    return saved === "dark" ? "dark" : "light";
  });
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // Authentication state (Google OAuth via Supabase)
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [authError, setAuthError] = useState("");

  // Health & system status
  const [health, setHealth] = useState({
    loading: true,
    ok: true,
    issues: [],
  });

  // Repositories & Conversations state
  const [repos, setRepos] = useState([]);
  const [activeRepoId, setActiveRepoId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);

  // Messages & pagination state
  const [messages, setMessages] = useState([]);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [oldestMessageId, setOldestMessageId] = useState(null);
  const [loadingOlderMessages, setLoadingOlderMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isCreatingChat, setIsCreatingChat] = useState(false);

  // Ingestion, Re-indexing & Deletion state
  const [ingestModalOpen, setIngestModalOpen] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestError, setIngestError] = useState("");
  const [isReindexing, setIsReindexing] = useState(false);
  const [deletingRepoId, setDeletingRepoId] = useState(null);

  // Toast notification state
  const [toast, setToast] = useState(null);

  const navigateToPage = useCallback((targetPage) => {
    setCurrentPage(targetPage);
    if (typeof window !== "undefined") {
      const nextUrl = targetPage === "workspace" ? "/workspace" : "/";
      if (window.location.pathname !== nextUrl) {
        window.history.pushState({ page: targetPage }, "", nextUrl);
      }
    }
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname.toLowerCase();
      setCurrentPage(path.startsWith("/workspace") ? "workspace" : "landing");
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    localStorage.setItem("copilot-theme", theme);
  }, [theme]);

  const showToast = useCallback((type, message, duration = 4500) => {
    setToast({ type, message });
    if (duration > 0) {
      setTimeout(() => {
        setToast((current) =>
          current && current.message === message ? null : current
        );
      }, duration);
    }
  }, []);

  const checkSystemHealth = useCallback(async () => {
    try {
      const data = await fetchHealth();
      setHealth({
        loading: false,
        ok: Boolean(data.ok),
        issues: data.issues || [],
      });
    } catch {
      setHealth({
        loading: false,
        ok: false,
        issues: ["Unable to reach backend server on port 8000."],
      });
    }
  }, []);

  const loadConversationThread = useCallback(
    async (conversationId) => {
      setActiveConversationId(conversationId);
      if (!conversationId) {
        setMessages([]);
        setHasMoreMessages(false);
        setOldestMessageId(null);
        return;
      }

      setLoadingConversation(true);
      try {
        const data = await fetchConversationMessages(conversationId, {
          limit: 12,
        });
        const fetchedMessages = data.messages || [];
        setMessages(fetchedMessages);
        setHasMoreMessages(Boolean(data.has_more));
        setOldestMessageId(
          data.next_before_id ||
            (fetchedMessages[0] && fetchedMessages[0].id) ||
            null
        );
      } catch (err) {
        showToast("error", err.message || "Failed to load conversation.");
      } finally {
        setLoadingConversation(false);
      }
    },
    [showToast]
  );

  const loadRepoConversations = useCallback(
    async (repoId, { selectLatest = false } = {}) => {
      if (!repoId) {
        setConversations([]);
        return [];
      }
      try {
        const list = await fetchConversations(repoId);
        setConversations(list);
        if (selectLatest) {
          if (list.length > 0) {
            await loadConversationThread(list[0].id);
          } else {
            setActiveConversationId(null);
            setMessages([]);
            setHasMoreMessages(false);
            setOldestMessageId(null);
          }
        }
        return list;
      } catch (err) {
        showToast("error", err.message || "Failed to load conversations.");
        return [];
      }
    },
    [loadConversationThread, showToast]
  );

  const selectRepository = useCallback(
    async (repo) => {
      if (!repo) return;
      setActiveRepoId(repo.id);
      setActiveConversationId(null);
      setMessages([]);
      setHasMoreMessages(false);
      setOldestMessageId(null);
      await loadRepoConversations(repo.id, { selectLatest: true });
    },
    [loadRepoConversations]
  );

  const loadAllRepositories = useCallback(
    async (preferredRepoId = null) => {
      try {
        const list = await fetchRepositories();
        setRepos(list);
        if (list.length > 0) {
          const target =
            (preferredRepoId && list.find((r) => r.id === preferredRepoId)) ||
            (activeRepoId && list.find((r) => r.id === activeRepoId)) ||
            list[0];
          if (!activeRepoId || preferredRepoId) {
            await selectRepository(target);
          }
        }
        return list;
      } catch {
        return [];
      }
    },
    [activeRepoId, selectRepository]
  );

  useEffect(() => {
    const urlErr = consumeUrlAuthError();
    if (urlErr) {
      setAuthError(urlErr);
    }

    let unsubscribe = () => {};
    initializeAuth(({ user: nextUser }) => {
      setUser(nextUser);
      setAuthLoading(false);
    }).then((unsub) => {
      if (typeof unsub === "function") {
        unsubscribe = unsub;
      }
    });

    return () => {
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!user) return;
    checkSystemHealth();
    loadAllRepositories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const handleGoogleSignIn = async () => {
    if (isAuthenticating) return;
    setIsAuthenticating(true);
    setAuthError("");
    try {
      sessionStorage.setItem("copilot-post-auth-page", "workspace");
      await signInWithGoogle();
    } catch (err) {
      sessionStorage.removeItem("copilot-post-auth-page");
      setAuthError(err.message || "Could not sign in with Google.");
      setIsAuthenticating(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await signOutUser();
      setUser(null);
      setActiveRepoId(null);
      setConversations([]);
      setActiveConversationId(null);
      setMessages([]);
      showToast("info", "Signed out of workspace.", 3000);
    } catch (err) {
      showToast("error", err.message || "Failed to sign out.");
    }
  };

  const activeRepo = repos.find((r) => r.id === activeRepoId) || null;
  const activeConversation =
    conversations.find((c) => c.id === activeConversationId) || null;

  const handleLoadOlderMessages = async () => {
    if (
      loadingOlderMessages ||
      !hasMoreMessages ||
      !oldestMessageId ||
      !activeConversationId
    ) {
      return;
    }
    setLoadingOlderMessages(true);
    try {
      const data = await fetchConversationMessages(activeConversationId, {
        limit: 12,
        beforeId: oldestMessageId,
      });
      const older = data.messages || [];
      setMessages((prev) => [...older, ...prev]);
      setHasMoreMessages(Boolean(data.has_more));
      setOldestMessageId(
        data.next_before_id || (older[0] && older[0].id) || null
      );
    } catch (err) {
      showToast("error", err.message || "Could not load earlier messages.");
    } finally {
      setLoadingOlderMessages(false);
    }
  };

  const handleNewChat = async () => {
    if (!activeRepoId || isCreatingChat) return;
    setIsCreatingChat(true);
    try {
      const created = await createConversation(activeRepoId, "New chat");
      await loadRepoConversations(activeRepoId);
      if (created && created.id) {
        setActiveConversationId(created.id);
        setMessages([]);
        setHasMoreMessages(false);
        setOldestMessageId(null);
      }
    } catch (err) {
      showToast("error", err.message || "Could not create new chat.");
    } finally {
      setIsCreatingChat(false);
    }
  };

  const handleSendMessage = async (text) => {
    if (!activeRepoId || isSending) return;
    setIsSending(true);

    const tempUserId = `user-${Date.now()}`;
    const tempAssistantId = `assistant-${Date.now()}`;

    setMessages((prev) => [
      ...prev,
      { id: tempUserId, role: "user", content: text },
      {
        id: tempAssistantId,
        role: "assistant",
        content: "",
        streaming: true,
        statusStage: "Searching codebase...",
      },
    ]);

    let resolvedConvId = activeConversationId;

    try {
      await streamChatMessage({
        message: text,
        repoId: activeRepoId,
        conversationId: activeConversationId,
        onMetadata: (meta) => {
          if (meta.conversation_id) {
            resolvedConvId = meta.conversation_id;
            setActiveConversationId(meta.conversation_id);
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId
                ? { ...m, statusStage: "Synthesizing response..." }
                : m
            )
          );
        },
        onToken: (_delta, fullAnswer) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId ? { ...m, content: fullAnswer } : m
            )
          );
        },
        onDone: (doneEvt) => {
          if (doneEvt.conversation_id) {
            resolvedConvId = doneEvt.conversation_id;
            setActiveConversationId(doneEvt.conversation_id);
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId
                ? {
                    ...m,
                    content: doneEvt.answer || m.content,
                    streaming: false,
                    statusStage: "",
                  }
                : m
            )
          );
        },
      });

      await loadRepoConversations(activeRepoId);

      if (resolvedConvId) {
        const page = await fetchConversationMessages(resolvedConvId, {
          limit: 12,
        });
        setHasMoreMessages(Boolean(page.has_more));
        setOldestMessageId(
          page.next_before_id ||
            (page.messages?.[0] && page.messages[0].id) ||
            null
        );
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tempAssistantId
            ? {
                ...m,
                content: `Unable to complete request: ${err.message}`,
                streaming: false,
                statusStage: "",
              }
            : m
        )
      );
      showToast("error", err.message || "Failed to send message.");
    } finally {
      setIsSending(false);
    }
  };

  const handleIngestRepository = async ({ repoUrl, branch, llmSummaries }) => {
    setIsIngesting(true);
    setIngestError("");
    try {
      const data = await ingestRepository({ repoUrl, branch, llmSummaries });
      await checkSystemHealth();
      await loadAllRepositories(data.repo_id);
      setIngestModalOpen(false);
      showToast("success", formatSyncSummary(data));
    } catch (err) {
      setIngestError(err.message || "Failed to index repository.");
    } finally {
      setIsIngesting(false);
    }
  };

  const pollJobUntilFinished = async (jobId) => {
    for (let i = 0; i < 300; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const job = await fetchJobStatus(jobId);
      if (job.status === "queued" || job.status === "running") {
        continue;
      }
      if (job.status === "failed") {
        throw new Error(job.error || "Background sync job failed.");
      }
      if (job.status === "succeeded") {
        return job.stats || {};
      }
    }
    throw new Error("Timed out waiting for repository sync.");
  };

  const handleReindexActiveRepo = async () => {
    if (!activeRepo || isReindexing) return;
    setIsReindexing(true);
    showToast(
      "info",
      `Syncing ${formatRepoName(activeRepo.repo_url)}...`,
      0
    );
    try {
      const data = await triggerReindex(activeRepo.id);
      const stats = data.job_id
        ? await pollJobUntilFinished(data.job_id)
        : data;
      const list = await fetchRepositories();
      setRepos(list);
      showToast("success", formatSyncSummary(stats));
    } catch (err) {
      showToast("error", err.message || "Failed to sync repository.");
    } finally {
      setIsReindexing(false);
    }
  };

  const handleDeleteRepository = async (repoToDelete) => {
    if (!repoToDelete || deletingRepoId) return;
    const repoId = repoToDelete.id;
    const repoLabel = formatRepoName(repoToDelete.repo_url);
    setDeletingRepoId(repoId);

    try {
      await deleteRepository(repoId);
      const remaining = repos.filter((r) => r.id !== repoId);
      setRepos(remaining);

      if (activeRepoId === repoId) {
        if (remaining.length > 0) {
          await selectRepository(remaining[0]);
        } else {
          setActiveRepoId(null);
          setConversations([]);
          setActiveConversationId(null);
          setMessages([]);
          setHasMoreMessages(false);
          setOldestMessageId(null);
        }
      }

      showToast("success", `Deleted repository ${repoLabel}.`);
    } catch (err) {
      showToast("error", err.message || "Failed to delete repository.");
    } finally {
      setDeletingRepoId(null);
    }
  };

  const toggleTheme = () =>
    setTheme((prev) => (prev === "light" ? "dark" : "light"));

  if (currentPage === "landing") {
    return (
      <LandingPage
        user={user}
        onEnterWorkspace={() => navigateToPage("workspace")}
        onGoogleSignIn={handleGoogleSignIn}
        isAuthenticating={isAuthenticating}
        authError={authError}
      />
    );
  }

  if (authLoading) {
    return (
      <div className="drafting-canvas flex h-screen w-screen flex-col items-center justify-center gap-3 bg-background text-foreground">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
          <Terminal className="h-5 w-5" />
        </div>
        <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
          <span>VERIFYING SESSION...</span>
        </div>
      </div>
    );
  }

  return (
    <WorkspacePage
      user={user}
      theme={theme}
      onToggleTheme={toggleTheme}
      isSidebarCollapsed={isSidebarCollapsed}
      onToggleSidebarCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
      onExpandSidebar={() => setIsSidebarCollapsed(false)}
      onGoogleSignIn={handleGoogleSignIn}
      isAuthenticating={isAuthenticating}
      authError={authError}
      onSignOut={handleSignOut}
      health={health}
      repos={repos}
      activeRepo={activeRepo}
      onSelectRepo={selectRepository}
      conversations={conversations}
      activeConversation={activeConversation}
      activeConversationId={activeConversationId}
      onSelectConversation={loadConversationThread}
      messages={messages}
      loadingConversation={loadingConversation}
      hasMoreMessages={hasMoreMessages}
      loadingOlderMessages={loadingOlderMessages}
      onLoadOlderMessages={handleLoadOlderMessages}
      onSendMessage={handleSendMessage}
      isSending={isSending}
      onNewChat={handleNewChat}
      isCreatingChat={isCreatingChat}
      ingestModalOpen={ingestModalOpen}
      onOpenIngestModal={() => {
        setIngestError("");
        setIngestModalOpen(true);
      }}
      onCloseIngestModal={() => !isIngesting && setIngestModalOpen(false)}
      onIngestRepository={handleIngestRepository}
      isIngesting={isIngesting}
      ingestError={ingestError}
      onReindexRepo={handleReindexActiveRepo}
      isReindexing={isReindexing}
      onDeleteRepo={handleDeleteRepository}
      deletingRepoId={deletingRepoId}
      toast={toast}
      onDismissToast={() => setToast(null)}
      onNavigateToLanding={() => navigateToPage("landing")}
    />
  );
}
