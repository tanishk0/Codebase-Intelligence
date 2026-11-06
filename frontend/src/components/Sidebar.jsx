import React, { useState, useRef, useEffect, useMemo } from "react";
import {
  Code2,
  ChevronDown,
  Plus,
  Search,
  MessageSquare,
  GitBranch,
  Check,
  FolderGit2,
  Sun,
  Moon,
  PanelLeftClose,
  RefreshCw,
  X,
  Sparkles,
} from "lucide-react";
import {
  formatRepoName,
  formatRelativeTime,
  groupConversationsByDate,
} from "../api";

export default function Sidebar({
  repos,
  activeRepo,
  onSelectRepo,
  onOpenIngestModal,
  onReindexRepo,
  isReindexing,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  isCreatingChat,
  health,
  theme,
  onToggleTheme,
  isCollapsed,
  onToggleCollapse,
}) {
  const [repoMenuOpen, setRepoMenuOpen] = useState(false);
  const [repoFilter, setRepoFilter] = useState("");
  const [chatSearch, setChatSearch] = useState("");
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setRepoMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredRepos = useMemo(() => {
    const q = repoFilter.trim().toLowerCase();
    if (!q) return repos;
    return repos.filter(
      (r) =>
        formatRepoName(r.repo_url).toLowerCase().includes(q) ||
        (r.branch || "").toLowerCase().includes(q)
    );
  }, [repos, repoFilter]);

  const filteredConversations = useMemo(() => {
    const q = chatSearch.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) =>
      (c.title || "New chat").toLowerCase().includes(q)
    );
  }, [conversations, chatSearch]);

  const conversationGroups = useMemo(
    () => groupConversationsByDate(filteredConversations),
    [filteredConversations]
  );

  return (
    <aside className={`sidebar ${isCollapsed ? "collapsed" : ""}`}>
      {/* Brand Header */}
      <div className="sidebar-brand">
        <div className="brand-identity">
          <div className="brand-logo">
            <Code2 size={18} strokeWidth={2.2} />
          </div>
          <div className="brand-text">
            <span className="brand-title">Codebase Copilot</span>
            <span className="brand-badge">Workspace</span>
          </div>
        </div>
        <button
          type="button"
          className="icon-button subtle"
          onClick={onToggleCollapse}
          title="Collapse sidebar"
          aria-label="Collapse sidebar"
        >
          <PanelLeftClose size={17} />
        </button>
      </div>

      {/* Repository Switcher */}
      <div className="repo-switcher-container" ref={dropdownRef}>
        <div className="section-caption">
          <span>Active Repository</span>
          <button
            type="button"
            className="caption-action"
            onClick={onOpenIngestModal}
            title="Index a new repository"
          >
            <Plus size={13} />
            <span>Add Repo</span>
          </button>
        </div>

        <button
          type="button"
          className={`repo-switcher-trigger ${repoMenuOpen ? "open" : ""}`}
          onClick={() => setRepoMenuOpen((prev) => !prev)}
        >
          <div className="repo-trigger-left">
            <div className="repo-icon-box">
              <FolderGit2 size={16} />
            </div>
            <div className="repo-trigger-details">
              <div className="repo-trigger-name">
                {activeRepo
                  ? formatRepoName(activeRepo.repo_url)
                  : "Select a repository"}
              </div>
              <div className="repo-trigger-meta">
                {activeRepo ? (
                  <>
                    <GitBranch size={11} />
                    <span>{activeRepo.branch || "main"}</span>
                  </>
                ) : (
                  <span>{repos.length ? `${repos.length} available` : "No repositories indexed"}</span>
                )}
              </div>
            </div>
          </div>
          <ChevronDown
            size={15}
            className={`chevron-icon ${repoMenuOpen ? "rotated" : ""}`}
          />
        </button>

        {repoMenuOpen && (
          <div className="repo-dropdown-popover">
            {repos.length > 3 && (
              <div className="dropdown-search">
                <Search size={14} className="search-icon" />
                <input
                  type="text"
                  placeholder="Filter repositories..."
                  value={repoFilter}
                  onChange={(e) => setRepoFilter(e.target.value)}
                  autoFocus
                />
              </div>
            )}

            <div className="dropdown-list">
              {filteredRepos.length === 0 ? (
                <div className="dropdown-empty">No matching repositories</div>
              ) : (
                filteredRepos.map((repo) => {
                  const isSelected = activeRepo && repo.id === activeRepo.id;
                  return (
                    <button
                      type="button"
                      key={repo.id}
                      className={`dropdown-repo-item ${isSelected ? "selected" : ""}`}
                      onClick={() => {
                        onSelectRepo(repo);
                        setRepoMenuOpen(false);
                        setRepoFilter("");
                      }}
                    >
                      <div className="dropdown-repo-main">
                        <span className="dropdown-repo-name">
                          {formatRepoName(repo.repo_url)}
                        </span>
                        <span className="dropdown-repo-branch">
                          <GitBranch size={11} />
                          {repo.branch || "main"}
                        </span>
                      </div>
                      {isSelected && <Check size={15} className="check-icon" />}
                    </button>
                  );
                })
              )}
            </div>

            <div className="dropdown-footer">
              {activeRepo && (
                <button
                  type="button"
                  className="dropdown-action-btn secondary"
                  onClick={() => {
                    setRepoMenuOpen(false);
                    onReindexRepo();
                  }}
                  disabled={isReindexing}
                >
                  <RefreshCw size={14} className={isReindexing ? "spin" : ""} />
                  <span>{isReindexing ? "Syncing..." : "Sync Changes"}</span>
                </button>
              )}
              <button
                type="button"
                className="dropdown-action-btn primary"
                onClick={() => {
                  setRepoMenuOpen(false);
                  onOpenIngestModal();
                }}
              >
                <Plus size={14} />
                <span>Connect Repository</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Primary New Chat + Search Bar */}
      <div className="sidebar-controls">
        <button
          type="button"
          className="new-chat-primary-btn"
          onClick={onNewChat}
          disabled={!activeRepo || isCreatingChat}
        >
          <span className="btn-left">
            <Plus size={16} strokeWidth={2.3} />
            <span>New Conversation</span>
          </span>
          <kbd className="kbd-badge">New</kbd>
        </button>

        {conversations.length > 0 && (
          <div className="sidebar-search">
            <Search size={14} className="sidebar-search-icon" />
            <input
              type="text"
              placeholder="Search conversations..."
              value={chatSearch}
              onChange={(e) => setChatSearch(e.target.value)}
            />
            {chatSearch && (
              <button
                type="button"
                className="clear-search-btn"
                onClick={() => setChatSearch("")}
                aria-label="Clear search"
              >
                <X size={13} />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Conversations Thread List */}
      <div className="sidebar-chats-scroll">
        {!activeRepo ? (
          <div className="sidebar-empty-state">
            <div className="empty-icon-circle">
              <FolderGit2 size={18} />
            </div>
            <p className="empty-title">No repository selected</p>
            <p className="empty-desc">
              Connect a GitHub repository or index your local workspace to start chatting.
            </p>
            <button
              type="button"
              className="empty-cta-btn"
              onClick={onOpenIngestModal}
            >
              <Plus size={14} />
              <span>Connect Repository</span>
            </button>
          </div>
        ) : conversationGroups.length === 0 ? (
          <div className="sidebar-empty-state">
            <div className="empty-icon-circle">
              <Sparkles size={18} />
            </div>
            <p className="empty-title">
              {chatSearch ? "No matching chats" : "No conversations yet"}
            </p>
            <p className="empty-desc">
              {chatSearch
                ? "Try a different search term."
                : "Ask a question in the workspace to start your first thread."}
            </p>
          </div>
        ) : (
          conversationGroups.map((group) => (
            <div key={group.label} className="chat-group">
              <div className="chat-group-header">{group.label}</div>
              <div className="chat-group-items">
                {group.items.map((chat) => {
                  const isActive = chat.id === activeConversationId;
                  return (
                    <button
                      type="button"
                      key={chat.id}
                      className={`chat-thread-item ${isActive ? "active" : ""}`}
                      onClick={() => onSelectConversation(chat.id)}
                    >
                      <MessageSquare
                        size={15}
                        className="chat-thread-icon"
                        strokeWidth={isActive ? 2.2 : 1.8}
                      />
                      <span className="chat-thread-title">
                        {chat.title || "New conversation"}
                      </span>
                      <span className="chat-thread-time">
                        {formatRelativeTime(chat.updated_at || chat.created_at)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Sidebar Footer */}
      <div className="sidebar-footer">
        <div className="system-status" title={health.ok ? "All services operational" : "Configuration required"}>
          <span
            className={`status-dot ${
              health.loading ? "loading" : health.ok ? "online" : "warning"
            }`}
          />
          <span className="status-label">
            {health.loading
              ? "Connecting..."
              : health.ok
              ? "Workspace Ready"
              : "Setup Needed"}
          </span>
        </div>

        <button
          type="button"
          className="theme-toggle-btn"
          onClick={onToggleTheme}
          title={
            theme === "light" ? "Switch to dark mode" : "Switch to light mode"
          }
          aria-label="Toggle color theme"
        >
          {theme === "light" ? (
            <>
              <Moon size={14} />
              <span>Dark</span>
            </>
          ) : (
            <>
              <Sun size={14} />
              <span>Light</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
