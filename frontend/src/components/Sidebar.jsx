import React, { useState, useMemo, useRef, useEffect } from "react";
import {
  Plus,
  Search,
  GitBranch,
  Laptop,
  PanelLeftClose,
  RefreshCw,
  Trash2,
  Loader2,
  AlertTriangle,
  X,
  LogOut,
  MessageSquare,
  ChevronDown,
  Check,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import ArclineLogo from "./ArclineLogo";
import { formatRepoName, formatRelativeTime } from "../api";

function GitHubIcon({ className = "h-3.5 w-3.5" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 15 15"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M7.49933 0.25C3.49635 0.25 0.25 3.49593 0.25 7.50024C0.25 10.703 2.32715 13.4206 5.2081 14.3797C5.57084 14.446 5.70302 14.2222 5.70302 14.0299C5.70302 13.8576 5.69679 13.4019 5.69323 12.797C3.67661 13.235 3.25112 11.825 3.25112 11.825C2.92132 10.9874 2.44599 10.7644 2.44599 10.7644C1.78773 10.3149 2.49584 10.3238 2.49584 10.3238C3.22353 10.375 3.60629 11.0711 3.60629 11.0711C4.25298 12.1788 5.30335 11.8588 5.71638 11.6732C5.78225 11.205 5.96962 10.8854 6.17658 10.7043C4.56675 10.5209 2.87415 9.89918 2.87415 7.12104C2.87415 6.32925 3.15677 5.68257 3.62053 5.17563C3.54576 4.99226 3.29697 4.25521 3.69174 3.25691C3.69174 3.25691 4.30015 3.06196 5.68522 3.99973C6.26337 3.83906 6.8838 3.75895 7.50022 3.75583C8.1162 3.75895 8.73619 3.83906 9.31523 3.99973C10.6994 3.06196 11.3069 3.25691 11.3069 3.25691C11.7026 4.25521 11.4538 4.99226 11.3795 5.17563C11.8441 5.68257 12.1245 6.32925 12.1245 7.12104C12.1245 9.9063 10.4292 10.5192 8.81452 10.6985C9.07444 10.9224 9.30633 11.3648 9.30633 12.0413C9.30633 13.0102 9.29742 13.7922 9.29742 14.0299C9.29742 14.2239 9.42828 14.4496 9.79591 14.3788C12.6746 13.4179 14.75 10.7025 14.75 7.50024C14.75 3.49593 11.5036 0.25 7.49933 0.25Z"
        fill="currentColor"
        fillRule="evenodd"
        clipRule="evenodd"
      />
    </svg>
  );
}

export default function Sidebar({
  repos = [],
  activeRepo,
  onSelectRepo,
  conversations = [],
  activeConversationId,
  onSelectConversation,
  onNewChat,
  isCreatingChat,
  isSending,
  onOpenIngestModal,
  onReindexRepo,
  isReindexing,
  onDeleteRepo,
  deletingRepoId,
  health,
  isCollapsed,
  onToggleCollapse,
  user,
  onGoogleSignIn,
  isAuthenticating,
  onSignOut,
  onNavigateToLanding,
}) {
  const [repoDropdownOpen, setRepoDropdownOpen] = useState(false);
  const [repoSearch, setRepoSearch] = useState("");
  const [repoPendingDelete, setRepoPendingDelete] = useState(null);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setRepoDropdownOpen(false);
      }
    };
    if (repoDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [repoDropdownOpen]);

  const filteredRepos = useMemo(() => {
    const q = repoSearch.trim().toLowerCase();
    if (!q) return repos;
    return repos.filter(
      (r) =>
        formatRepoName(r.repo_url).toLowerCase().includes(q) ||
        (r.branch || "").toLowerCase().includes(q)
    );
  }, [repos, repoSearch]);

  const isLocalRepo = (url) => {
    const str = String(url || "").toLowerCase();
    return (
      str === "local" ||
      str.includes("local/codebase-copilot") ||
      str.includes("local/arcline")
    );
  };

  const handleConfirmDelete = async () => {
    if (!repoPendingDelete || !onDeleteRepo) return;
    await onDeleteRepo(repoPendingDelete);
    setRepoPendingDelete(null);
  };

  return (
    <TooltipProvider delayDuration={180}>
      <aside
        className={cn(
          "flex h-screen flex-col border-r border-[#1E2636] bg-[#0F141E] transition-all duration-300 select-none shrink-0 font-inter",
          isCollapsed
            ? "w-0 min-w-0 overflow-hidden border-r-0 opacity-0 pointer-events-none"
            : "w-[248px] min-w-[248px]"
        )}
      >
        {/* Top Brand + Collapse Row */}
        <div className="flex h-12 shrink-0 items-center justify-between px-3.5">
          <button
            type="button"
            onClick={onNavigateToLanding}
            title="Return to Landing Page"
            className="flex items-center gap-2 text-left focus:outline-none cursor-pointer group"
          >
            <ArclineLogo
              iconClassName="h-6 w-6 transition-transform group-hover:scale-105"
              textClassName="font-inter text-[15.5px] font-semibold tracking-[-0.02em] text-white"
            />
          </button>

          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={onToggleCollapse}
                aria-label="Collapse sidebar"
                className="flex h-7 w-7 items-center justify-center rounded-[6px] text-[#9CA3AF] transition-colors hover:bg-[#1A2232] hover:text-white cursor-pointer"
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Collapse sidebar</TooltipContent>
          </Tooltip>
        </div>

        {/* Repository Switcher Dropdown */}
        <div className="px-3 pb-2" ref={dropdownRef}>
          <div className="relative">
            <button
              type="button"
              onClick={() => setRepoDropdownOpen((prev) => !prev)}
              className="flex w-full items-center justify-between rounded-[8px] border border-[#202838] bg-[#141B27] px-2.5 py-2 text-left font-inter text-[12.5px] font-medium text-[#E5E7EB] transition-colors hover:border-[#2E3A4F] hover:bg-[#192231] cursor-pointer"
            >
              <div className="flex min-w-0 items-center gap-2">
                {activeRepo && isLocalRepo(activeRepo.repo_url) ? (
                  <Laptop className="h-3.5 w-3.5 shrink-0 text-[#7DB4FF]" />
                ) : (
                  <GitHubIcon className="h-3.5 w-3.5 shrink-0 text-[#E5E7EB]" />
                )}
                <span className="truncate">
                  {activeRepo
                    ? formatRepoName(activeRepo.repo_url)
                    : "Select repository"}
                </span>
              </div>
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 shrink-0 text-[#9CA3AF] transition-transform",
                  repoDropdownOpen && "rotate-180"
                )}
              />
            </button>

            {repoDropdownOpen && (
              <div className="absolute top-full left-0 z-40 mt-1.5 w-full rounded-[10px] border border-[#243041] bg-[#111827] p-1.5 shadow-2xl">
                {repos.length > 4 && (
                  <div className="relative mb-1.5">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-[#6B7280]" />
                    <input
                      type="text"
                      placeholder="Filter repos..."
                      value={repoSearch}
                      onChange={(e) => setRepoSearch(e.target.value)}
                      className="w-full rounded-[6px] border border-[#202838] bg-[#0B0F16] py-1 pl-7 pr-6 font-inter text-[11.5px] text-[#E5E7EB] placeholder:text-[#6B7280] focus:border-[#7DB4FF] focus:outline-none"
                    />
                    {repoSearch && (
                      <button
                        type="button"
                        onClick={() => setRepoSearch("")}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-white cursor-pointer"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                )}

                <div className="max-h-56 overflow-y-auto space-y-0.5 landing-dark-code-scroll">
                  {filteredRepos.length === 0 ? (
                    <div className="px-2.5 py-3 text-center font-inter text-[11.5px] text-[#6B7280]">
                      {repos.length === 0
                        ? "No repositories mounted"
                        : "No matching repositories"}
                    </div>
                  ) : (
                    filteredRepos.map((repo) => {
                      const isSelected =
                        activeRepo && repo.id === activeRepo.id;
                      const isDeletingThis = deletingRepoId === repo.id;
                      const local = isLocalRepo(repo.repo_url);

                      return (
                        <div
                          key={repo.id}
                          onClick={() => {
                            onSelectRepo(repo);
                            setRepoDropdownOpen(false);
                          }}
                          className={cn(
                            "group flex w-full items-center justify-between gap-1.5 rounded-[6px] px-2 py-1.5 text-left font-inter text-[12px] transition-colors cursor-pointer",
                            isSelected
                              ? "bg-[#1A2232] font-medium text-white"
                              : "text-[#9CA3AF] hover:bg-[#1A2232]/60 hover:text-white"
                          )}
                        >
                          <div className="flex min-w-0 items-center gap-2">
                            {local ? (
                              <Laptop className="h-3.5 w-3.5 shrink-0 text-[#7DB4FF]" />
                            ) : (
                              <GitHubIcon className="h-3.5 w-3.5 shrink-0 opacity-80" />
                            )}
                            <div className="min-w-0">
                              <div className="truncate">
                                {formatRepoName(repo.repo_url)}
                              </div>
                              <div className="flex items-center gap-1.5 font-mono text-[10px] text-[#6B7280]">
                                <GitBranch className="h-2.5 w-2.5" />
                                <span>{repo.branch || "main"}</span>
                              </div>
                            </div>
                          </div>

                          <div className="flex shrink-0 items-center gap-1">
                            {isSelected && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onReindexRepo();
                                }}
                                disabled={isReindexing || isDeletingThis}
                                title="Sync changes"
                                className="rounded p-1 text-[#9CA3AF] hover:bg-[#243041] hover:text-white cursor-pointer"
                              >
                                <RefreshCw
                                  className={cn(
                                    "h-3 w-3",
                                    isReindexing &&
                                      "animate-spin text-[#7DB4FF]"
                                  )}
                                />
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setRepoPendingDelete(repo);
                                setRepoDropdownOpen(false);
                              }}
                              disabled={isDeletingThis}
                              title="Delete repository"
                              className="rounded p-1 text-[#6B7280] opacity-0 group-hover:opacity-100 hover:bg-red-500/15 hover:text-red-400 transition-opacity cursor-pointer"
                            >
                              {isDeletingThis ? (
                                <Loader2 className="h-3 w-3 animate-spin text-red-400" />
                              ) : (
                                <Trash2 className="h-3 w-3" />
                              )}
                            </button>
                            {isSelected && (
                              <Check className="h-3.5 w-3.5 text-[#7DB4FF]" />
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>

                <div className="mt-1 border-t border-[#1E2636] pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setRepoDropdownOpen(false);
                      onOpenIngestModal();
                    }}
                    className="flex w-full items-center gap-2 rounded-[6px] px-2 py-1.5 font-inter text-[12px] text-[#7DB4FF] transition-colors hover:bg-[#1A2232] cursor-pointer"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Add repository</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Middle Section: Flat List of Chat Threads */}
        <div className="flex items-center justify-between px-3.5 pt-3 pb-1.5">
          <span className="font-inter text-[11px] font-medium text-[#6B7280]">
            Threads
          </span>
          {activeRepo && onNewChat && (
            <button
              type="button"
              onClick={onNewChat}
              disabled={isCreatingChat || isSending}
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-inter text-[11px] font-medium text-[#9CA3AF] transition-colors hover:bg-[#1A2232] hover:text-white disabled:opacity-40 cursor-pointer"
            >
              <Plus className="h-3 w-3" />
              <span>New</span>
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-2.5 py-1 space-y-0.5 landing-dark-code-scroll">
          {!activeRepo ? (
            <div className="px-2 py-6 text-center font-inter text-[12px] text-[#6B7280]">
              Connect a repository to start chatting.
            </div>
          ) : conversations.length === 0 ? (
            <div className="px-2 py-6 text-center font-inter text-[12px] text-[#6B7280]">
              No threads yet. Ask a question to begin.
            </div>
          ) : (
            conversations.map((chat) => {
              const isCurrent = chat.id === activeConversationId;
              return (
                <button
                  key={chat.id}
                  type="button"
                  onClick={() => onSelectConversation(chat.id)}
                  className={cn(
                    "group flex w-full items-center justify-between gap-2 rounded-[7px] px-2.5 py-1.5 text-left font-inter text-[12.5px] transition-colors cursor-pointer",
                    isCurrent
                      ? "bg-[#222B3B] font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
                      : "text-[#9CA3AF] hover:bg-[#161D2A] hover:text-[#E5E7EB]"
                  )}
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-75" />
                    <span className="truncate">
                      {chat.title || "Untitled thread"}
                    </span>
                  </div>
                  {chat.updated_at && (
                    <span className="shrink-0 font-mono text-[10px] text-[#6B7280] opacity-0 group-hover:opacity-100 transition-opacity">
                      {formatRelativeTime(chat.updated_at || chat.created_at)}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Bottom Section: "+ Add repository" + Compact User Profile */}
        <div className="border-t border-[#1E2636] p-2.5 space-y-1.5">
          <button
            type="button"
            onClick={onOpenIngestModal}
            className="flex w-full items-center gap-2 rounded-[7px] px-2.5 py-1.5 font-inter text-[12.5px] font-normal text-[#9CA3AF] transition-colors hover:bg-[#161D2A] hover:text-[#E5E7EB] cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add repository</span>
          </button>

          {user ? (
            <div className="flex items-center justify-between gap-2 rounded-[7px] border border-[#1B2230] bg-[#121722] px-2.5 py-1.5">
              <div className="flex min-w-0 items-center gap-2">
                <div className="relative shrink-0">
                  {user.avatarUrl ? (
                    <img
                      src={user.avatarUrl}
                      alt={user.name || "User"}
                      referrerPolicy="no-referrer"
                      className="h-6 w-6 rounded-full object-cover"
                    />
                  ) : (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#263042] font-inter text-[11px] font-medium text-[#D1D5DB]">
                      {(user.name || user.email || "U")[0].toUpperCase()}
                    </div>
                  )}
                  <span
                    title={
                      health?.loading
                        ? "Syncing..."
                        : health?.ok
                        ? "System Online"
                        : "Check Configuration"
                    }
                    className={cn(
                      "absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full ring-2 ring-[#121722]",
                      health?.loading
                        ? "bg-[#7DB4FF]"
                        : health?.ok
                        ? "bg-emerald-400"
                        : "bg-amber-400"
                    )}
                  />
                </div>
                <div className="min-w-0">
                  <div className="truncate font-inter text-[12px] font-medium text-[#E5E7EB]">
                    {user.name || "Developer"}
                  </div>
                </div>
              </div>

              {onSignOut && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={onSignOut}
                      aria-label="Sign out"
                      className="rounded p-1 text-[#6B7280] transition-colors hover:bg-[#1E2636] hover:text-[#E5E7EB] cursor-pointer"
                    >
                      <LogOut className="h-3.5 w-3.5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top">Sign out</TooltipContent>
                </Tooltip>
              )}
            </div>
          ) : (
            onGoogleSignIn && (
              <button
                type="button"
                onClick={onGoogleSignIn}
                disabled={isAuthenticating}
                className="flex w-full items-center justify-center gap-2 rounded-[7px] border border-[#243041] bg-[#141B27] px-2.5 py-1.5 font-inter text-[12px] font-medium text-[#E5E7EB] transition-colors hover:border-[#2E3B52] hover:bg-[#1A2232] hover:text-white disabled:opacity-50 cursor-pointer"
              >
                {isAuthenticating ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#7DB4FF]" />
                ) : null}
                <span>Sign in with Google</span>
              </button>
            )
          )}
        </div>

        {/* Delete Repository Confirmation Dialog */}
        <Dialog
          open={Boolean(repoPendingDelete)}
          onOpenChange={(open) => {
            if (!open && !deletingRepoId) setRepoPendingDelete(null);
          }}
        >
          <DialogContent className="sm:max-w-[420px] rounded-[16px] border border-[#243041] bg-[#111827] text-[#E5E7EB]">
            <DialogHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 text-red-400">
                  <AlertTriangle className="h-4 w-4" />
                </div>
                <div className="text-left">
                  <DialogTitle className="font-inter text-[15px] font-semibold text-white">
                    Remove repository?
                  </DialogTitle>
                </div>
              </div>
              <DialogDescription className="pt-2 text-left font-inter text-[13px] leading-relaxed text-[#9CA3AF]">
                This will permanently remove{" "}
                <span className="font-mono font-medium text-white">
                  {repoPendingDelete
                    ? formatRepoName(repoPendingDelete.repo_url)
                    : ""}
                </span>{" "}
                and its saved conversation history.
              </DialogDescription>
            </DialogHeader>

            <DialogFooter className="mt-3 gap-2 sm:gap-2">
              <button
                type="button"
                onClick={() => setRepoPendingDelete(null)}
                disabled={Boolean(deletingRepoId)}
                className="rounded-[8px] border border-[#243041] bg-[#171F2E] px-3.5 py-1.5 font-inter text-[12.5px] font-medium text-[#D1D5DB] hover:bg-[#1F293C] hover:text-white cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={Boolean(deletingRepoId)}
                className="inline-flex items-center gap-1.5 rounded-[8px] bg-red-500/90 px-3.5 py-1.5 font-inter text-[12.5px] font-medium text-white hover:bg-red-500 disabled:opacity-50 cursor-pointer"
              >
                {deletingRepoId ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Removing...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>Remove</span>
                  </>
                )}
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </aside>
    </TooltipProvider>
  );
}
