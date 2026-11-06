import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { motion } from "motion/react";
import {
  PanelLeftOpen,
  RefreshCw,
  Plus,
  GitBranch,
  FolderGit2,
  ArrowUp,
  ArrowDown,
  Compass,
  Layers,
  Workflow,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  History,
  MessageSquare,
  ChevronDown,
  Search,
  Check,
  X,
  CornerDownLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import MessageItem from "./MessageItem";
import {
  formatRepoName,
  formatRelativeTime,
  groupConversationsByDate,
} from "../api";

const STARTER_PROMPTS = [
  {
    code: "01 // TOPOLOGY",
    icon: Compass,
    title: "System Topology & Modules",
    desc: "Map out the architectural boundaries and how core packages collaborate",
    prompt:
      "What does this repository do and how are the core modules organized?",
  },
  {
    code: "02 // EXECUTION",
    icon: Workflow,
    title: "Primary Data & Execution Path",
    desc: "Trace an end-to-end request from entry point through storage",
    prompt:
      "Walk me through the primary data flow and key entry points in this codebase.",
  },
  {
    code: "03 // ABSTRACTIONS",
    icon: Layers,
    title: "Domain Models & Contracts",
    desc: "Examine the central classes, interfaces, and state invariants",
    prompt:
      "What are the most important classes and abstractions in this project, and what are their responsibilities?",
  },
  {
    code: "04 // RESILIENCE",
    icon: ShieldCheck,
    title: "Fault Tolerance & Guardrails",
    desc: "Audit error recovery, boundary validation, and retry strategies",
    prompt:
      "How does this codebase handle errors, retries, and input validation?",
  },
];

export default function ChatWorkspace({
  activeRepo,
  conversations,
  activeConversation,
  activeConversationId,
  onSelectConversation,
  messages,
  loadingConversation,
  hasMoreMessages,
  loadingOlderMessages,
  onLoadOlderMessages,
  onSendMessage,
  isSending,
  onNewChat,
  isCreatingChat,
  onReindexRepo,
  isReindexing,
  onOpenIngestModal,
  health,
  isSidebarCollapsed,
  onExpandSidebar,
}) {
  const [input, setInput] = useState("");
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [chatSearch, setChatSearch] = useState("");

  const messagesContainerRef = useRef(null);
  const textareaRef = useRef(null);
  const prevScrollHeightRef = useRef(null);

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

  const scrollToBottom = useCallback((behavior = "smooth") => {
    const el = messagesContainerRef.current;
    if (!el) return;
    el.scrollTo({
      top: el.scrollHeight,
      behavior,
    });
  }, []);

  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    if (prevScrollHeightRef.current !== null) {
      const diff = el.scrollHeight - prevScrollHeightRef.current;
      el.scrollTop += diff;
      prevScrollHeightRef.current = null;
      return;
    }
    scrollToBottom("auto");
  }, [messages, activeConversation?.id, scrollToBottom]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 180)}px`;
  }, [input]);

  const handleScroll = () => {
    const el = messagesContainerRef.current;
    if (!el) return;

    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollBottom(distanceFromBottom > 220);

    if (el.scrollTop <= 12 && hasMoreMessages && !loadingOlderMessages) {
      prevScrollHeightRef.current = el.scrollHeight;
      onLoadOlderMessages();
    }
  };

  const handleLoadOlderClick = () => {
    const el = messagesContainerRef.current;
    if (el) {
      prevScrollHeightRef.current = el.scrollHeight;
    }
    onLoadOlderMessages();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isSending || !activeRepo) return;
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    onSendMessage(trimmed);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const activeTitle = activeConversation?.title || "Untitled Session";

  return (
    <TooltipProvider delayDuration={180}>
      <main className="drafting-canvas relative flex h-screen min-w-0 flex-1 flex-col">
        {/* Top Instrument Control Bar */}
        <header className="z-10 flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-card/85 px-6 backdrop-blur-md">
          <div className="flex min-w-0 items-center gap-3">
            {isSidebarCollapsed && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 shrink-0 rounded-md bg-background"
                    onClick={onExpandSidebar}
                    aria-label="Open repository dock"
                  >
                    <PanelLeftOpen className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">Open repo dock</TooltipContent>
              </Tooltip>
            )}

            <div className="flex min-w-0 flex-wrap items-center gap-2.5">
              {activeRepo ? (
                <>
                  <span className="hidden rounded border border-primary/30 bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-primary sm:inline-block">
                    TARGET
                  </span>
                  <div className="flex items-center gap-2 font-display text-sm font-bold tracking-tight text-foreground">
                    <FolderGit2 className="h-4 w-4 text-primary" />
                    <span className="truncate">
                      {formatRepoName(activeRepo.repo_url)}
                    </span>
                  </div>
                  <Badge
                    variant="outline"
                    className="rounded bg-muted/70 font-mono text-[10.5px] font-medium"
                  >
                    <GitBranch className="h-3 w-3 text-primary" />
                    <span>{activeRepo.branch || "main"}</span>
                  </Badge>
                </>
              ) : (
                <h1 className="font-mono text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  WORKSPACE // STANDBY
                </h1>
              )}
            </div>
          </div>

          {/* Right Side: Contained Session Archive Dropdown + Sync + New Session */}
          {activeRepo && (
            <div className="flex shrink-0 items-center gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="max-w-[260px] gap-2 rounded-md bg-background font-medium"
                  >
                    <MessageSquare className="h-3.5 w-3.5 text-primary shrink-0" />
                    <span className="truncate text-xs">{activeTitle}</span>
                    {conversations.length > 0 && (
                      <span className="rounded bg-muted px-1.5 py-0.2 font-mono text-[10px] text-muted-foreground">
                        {String(conversations.length).padStart(2, "0")}
                      </span>
                    )}
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  </Button>
                </DropdownMenuTrigger>

                <DropdownMenuContent align="end" className="w-80 rounded-lg p-2">
                  <div className="flex items-center justify-between px-2 py-1">
                    <span className="truncate font-mono text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Session Archive
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 gap-1 rounded px-2 font-mono text-[10.5px] font-semibold text-primary hover:text-primary"
                      onClick={onNewChat}
                      disabled={isCreatingChat || isSending}
                    >
                      <Plus className="h-3 w-3" />
                      <span>NEW THREAD</span>
                    </Button>
                  </div>

                  <DropdownMenuSeparator />

                  {conversations.length > 3 && (
                    <div
                      className="relative my-1.5 px-1"
                      onKeyDown={(e) => e.stopPropagation()}
                    >
                      <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                      <Input
                        type="text"
                        placeholder="Search sessions..."
                        value={chatSearch}
                        onChange={(e) => setChatSearch(e.target.value)}
                        className="h-8 rounded pl-8 pr-7 font-mono text-xs"
                      />
                      {chatSearch && (
                        <button
                          type="button"
                          onClick={() => setChatSearch("")}
                          className="absolute right-3 top-2.5 text-muted-foreground hover:text-foreground"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  )}

                  <div className="max-h-64 overflow-y-auto pr-0.5">
                    {conversationGroups.length === 0 ? (
                      <div className="py-6 text-center font-mono text-xs text-muted-foreground">
                        {chatSearch
                          ? "0 MATCHING SESSIONS"
                          : "NO SAVED SESSIONS"}
                      </div>
                    ) : (
                      conversationGroups.map((group) => (
                        <div key={group.label} className="mb-2 last:mb-0">
                          <DropdownMenuLabel className="px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                            {group.label}
                          </DropdownMenuLabel>
                          {group.items.map((chat) => {
                            const isSelected = chat.id === activeConversationId;
                            return (
                              <DropdownMenuItem
                                key={chat.id}
                                onSelect={() => {
                                  onSelectConversation(chat.id);
                                  setChatSearch("");
                                }}
                                className={cn(
                                  "flex items-center justify-between gap-2 rounded-md px-2.5 py-2 text-xs",
                                  isSelected &&
                                    "bg-primary/10 font-semibold text-primary focus:bg-primary/15 focus:text-primary"
                                )}
                              >
                                <div className="flex min-w-0 items-center gap-2">
                                  <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-75" />
                                  <span className="truncate">
                                    {chat.title || "Untitled Session"}
                                  </span>
                                </div>
                                <div className="flex shrink-0 items-center gap-1.5">
                                  <span className="font-mono text-[10px] text-muted-foreground">
                                    {formatRelativeTime(
                                      chat.updated_at || chat.created_at
                                    )}
                                  </span>
                                  {isSelected && (
                                    <Check className="h-3.5 w-3.5 text-primary" />
                                  )}
                                </div>
                              </DropdownMenuItem>
                            );
                          })}
                        </div>
                      ))
                    )}
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>

              <Button
                variant="outline"
                size="sm"
                onClick={onReindexRepo}
                disabled={isReindexing}
                className="rounded-md bg-background font-mono text-[11px]"
                title="Sync incremental file changes"
              >
                <RefreshCw
                  className={cn(
                    "h-3.5 w-3.5",
                    isReindexing && "animate-spin text-primary"
                  )}
                />
                <span>{isReindexing ? "SYNCING..." : "SYNC"}</span>
              </Button>

              <Button
                variant="default"
                size="sm"
                onClick={onNewChat}
                disabled={isSending || isCreatingChat}
                className="rounded-md font-display text-xs font-semibold"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>New Thread</span>
              </Button>
            </div>
          )}
        </header>

        {/* Contained In-Workspace Conversation Thread Tape */}
        {activeRepo && conversations.length > 0 && (
          <div className="z-10 shrink-0 border-b border-border bg-card/65 px-6 py-1.5 backdrop-blur-sm">
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
              <span className="shrink-0 font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-foreground pr-1">
                THREADS //
              </span>
              {conversations.map((chat, idx) => {
                const isActive = chat.id === activeConversationId;
                return (
                  <button
                    type="button"
                    key={chat.id}
                    onClick={() => onSelectConversation(chat.id)}
                    title={chat.title || "Untitled Session"}
                    className={cn(
                      "relative inline-flex max-w-[220px] shrink-0 items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors cursor-pointer",
                      isActive
                        ? "border-primary/45 bg-card text-foreground font-semibold shadow-xs"
                        : "border-transparent text-muted-foreground hover:border-border hover:bg-card/60 hover:text-foreground"
                    )}
                  >
                    <span className="font-mono text-[10px] text-primary">
                      #{String(idx + 1).padStart(2, "0")}
                    </span>
                    <span className="truncate">
                      {chat.title || "Untitled Session"}
                    </span>
                    {isActive && (
                      <motion.span
                        layoutId="active-thread-dot"
                        className="ml-0.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0"
                      />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Setup / Configuration Alert Banner */}
        {!health.loading && !health.ok && health.issues?.length > 0 && (
          <div className="mx-6 mt-4 flex items-start gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-xs">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
            <div>
              <strong className="font-mono text-[11px] uppercase tracking-wider text-foreground">
                Environment Configuration Required
              </strong>
              <ul className="mt-1 list-disc pl-4 text-muted-foreground">
                {health.issues.map((issue, idx) => (
                  <li key={idx}>{issue}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Conversation Viewport */}
        <div
          className="flex-1 overflow-y-auto px-6 pt-8 pb-4"
          ref={messagesContainerRef}
          onScroll={handleScroll}
        >
          <div className="mx-auto flex min-h-full max-w-[840px] flex-col">
            {!activeRepo ? (
              <motion.div
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="m-auto w-full max-w-xl rounded-xl border border-border bg-card/90 p-9 text-center tactile-card"
              >
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary">
                  <FolderGit2 className="h-6 w-6" strokeWidth={1.8} />
                </div>
                <div className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.2em] text-primary">
                  SYSTEM STANDBY
                </div>
                <h2 className="mt-1 font-display text-3xl font-bold tracking-tight text-foreground">
                  Mount a codebase{" "}
                  <span className="font-serif font-normal italic text-primary">
                    to begin.
                  </span>
                </h2>
                <p className="mx-auto mt-2.5 mb-6 max-w-md text-sm leading-relaxed text-muted-foreground">
                  Connect any GitHub repository or index your local workspace directory to inspect architecture, trace execution paths, and query implementation details.
                </p>
                <Button
                  size="lg"
                  onClick={onOpenIngestModal}
                  className="rounded-md font-mono text-xs uppercase tracking-wider"
                >
                  <Plus className="h-4 w-4" />
                  <span>Mount Repository</span>
                </Button>
              </motion.div>
            ) : loadingConversation ? (
              <div className="m-auto flex items-center gap-2.5 font-mono text-xs uppercase tracking-wider text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span>LOADING SESSION TRANSCRIPT...</span>
              </div>
            ) : messages.length === 0 ? (
              <div className="m-auto w-full max-w-2xl py-6">
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.42, ease: [0.16, 1, 0.3, 1] }}
                  className="mb-8 text-left"
                >
                  <div className="mb-2 inline-flex items-center gap-2 rounded border border-border bg-card px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                    <span>INSPECTING // {formatRepoName(activeRepo.repo_url)}</span>
                  </div>

                  <h2 className="font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                    Interrogate the{" "}
                    <span className="font-serif font-normal italic text-primary">
                      architecture.
                    </span>
                  </h2>
                  <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
                    Select a diagnostic blueprint below or enter a direct query to trace symbols, call graphs, and module boundaries across{" "}
                    <span className="font-mono text-xs text-foreground">
                      {formatRepoName(activeRepo.repo_url)}
                    </span>
                    .
                  </p>
                </motion.div>

                <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
                  {STARTER_PROMPTS.map((item, idx) => {
                    const IconComponent = item.icon;
                    return (
                      <motion.button
                        type="button"
                        key={item.title}
                        initial={{ opacity: 0, y: 14 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{
                          duration: 0.38,
                          delay: 0.08 + idx * 0.06,
                          ease: [0.16, 1, 0.3, 1],
                        }}
                        onClick={() => !isSending && onSendMessage(item.prompt)}
                        disabled={isSending}
                        className="tactile-card group relative flex flex-col justify-between rounded-lg border border-border bg-card/90 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/55 cursor-pointer"
                      >
                        <div className="mb-3 flex w-full items-center justify-between">
                          <span className="font-mono text-[10px] font-semibold tracking-widest text-muted-foreground group-hover:text-primary transition-colors">
                            {item.code}
                          </span>
                          <div className="flex h-7 w-7 items-center justify-center rounded border border-border bg-muted/60 text-foreground group-hover:border-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                            <IconComponent className="h-3.5 w-3.5" />
                          </div>
                        </div>

                        <div>
                          <div className="font-display text-sm font-bold tracking-tight text-foreground">
                            {item.title}
                          </div>
                          <div className="mt-1 text-xs leading-relaxed text-muted-foreground">
                            {item.desc}
                          </div>
                        </div>
                      </motion.button>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-6 pb-4">
                {hasMoreMessages && (
                  <div className="flex justify-center">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleLoadOlderClick}
                      disabled={loadingOlderMessages}
                      className="rounded-md bg-card font-mono text-[11px] text-muted-foreground"
                    >
                      {loadingOlderMessages ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                          <span>FETCHING EARLIER LOGS...</span>
                        </>
                      ) : (
                        <>
                          <History className="h-3.5 w-3.5 text-primary" />
                          <span>LOAD EARLIER MESSAGES</span>
                        </>
                      )}
                    </Button>
                  </div>
                )}

                {messages.map((msg, idx) => (
                  <MessageItem key={msg.id || `temp-${idx}`} message={msg} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Floating Scroll-to-Bottom Button */}
        {showScrollBottom && messages.length > 0 && (
          <Button
            variant="outline"
            size="icon"
            onClick={() => scrollToBottom("smooth")}
            className="absolute bottom-32 left-1/2 z-15 h-8 w-8 -translate-x-1/2 rounded-md bg-card shadow-md"
            title="Scroll to latest message"
            aria-label="Scroll to latest message"
          >
            <ArrowDown className="h-4 w-4 text-primary" />
          </Button>
        )}

        {/* Bottom Tactile Command Console */}
        <div className="shrink-0 bg-gradient-to-b from-transparent via-background/80 to-background px-6 pt-2 pb-5">
          <form
            onSubmit={handleSubmit}
            className="tactile-composer mx-auto max-w-[840px] rounded-xl border border-border bg-card p-3 transition-all focus-within:border-primary"
          >
            <Textarea
              ref={textareaRef}
              rows={1}
              placeholder={
                activeRepo
                  ? `Query ${formatRepoName(activeRepo.repo_url)} architecture, symbols, or data flow...`
                  : "Mount a repository first to begin querying..."
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!activeRepo || isSending}
              className="min-h-[38px] max-h-[180px] resize-none border-0 bg-transparent px-1.5 py-1 text-sm shadow-none focus-visible:ring-0"
            />

            <div className="mt-2 flex items-center justify-between gap-3 border-t border-border/80 pt-2">
              <div className="flex flex-wrap items-center gap-2.5">
                {activeRepo ? (
                  <span className="inline-flex items-center gap-1.5 rounded border border-border bg-muted/60 px-2 py-0.5 font-mono text-[10.5px] text-foreground">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                    <span className="max-w-[220px] truncate">{activeTitle}</span>
                  </span>
                ) : (
                  <span className="rounded border border-border bg-muted/40 px-2 py-0.5 font-mono text-[10.5px] text-muted-foreground">
                    NO REPO MOUNTED
                  </span>
                )}
                <span className="hidden font-mono text-[10.5px] text-muted-foreground sm:inline">
                  <kbd className="rounded border border-border bg-muted px-1 py-0.2 text-foreground">
                    ENTER
                  </kbd>{" "}
                  SEND ·{" "}
                  <kbd className="rounded border border-border bg-muted px-1 py-0.2 text-foreground">
                    SHIFT+ENTER
                  </kbd>{" "}
                  NEWLINE
                </span>
              </div>

              <Button
                type="submit"
                size="sm"
                className="h-8 gap-1.5 rounded-md px-3 font-mono text-[11px] font-semibold uppercase tracking-wider shrink-0"
                disabled={!activeRepo || !input.trim() || isSending}
                title="Transmit query"
                aria-label="Transmit query"
              >
                {isSending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>RUNNING</span>
                  </>
                ) : (
                  <>
                    <span>ASK</span>
                    <CornerDownLeft className="h-3.5 w-3.5" />
                  </>
                )}
              </Button>
            </div>
          </form>
        </div>
      </main>
    </TooltipProvider>
  );
}
