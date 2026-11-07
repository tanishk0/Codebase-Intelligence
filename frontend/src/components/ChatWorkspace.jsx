import React, { useState, useRef, useEffect, useCallback } from "react";
import { motion } from "motion/react";
import {
  PanelLeftOpen,
  RefreshCw,
  Plus,
  GitBranch,
  ArrowRight,
  ArrowDown,
  Compass,
  Layers,
  Workflow,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  History,
  Laptop,
  AlertCircle,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import MessageItem from "./MessageItem";
import { formatRepoName } from "../api";

function GitHubIcon({ className = "h-5 w-5" }) {
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

const STARTER_PROMPTS = [
  {
    icon: Compass,
    title: "System Topology & Modules",
    desc: "Map out the architectural boundaries and how core packages collaborate",
    prompt:
      "What does this repository do and how are the core modules organized?",
  },
  {
    icon: Workflow,
    title: "Primary Data & Execution Path",
    desc: "Trace an end-to-end request from entry point through storage",
    prompt:
      "Walk me through the primary data flow and key entry points in this codebase.",
  },
  {
    icon: Layers,
    title: "Domain Models & Contracts",
    desc: "Examine the central classes, interfaces, and state invariants",
    prompt:
      "What are the most important classes and abstractions in this project, and what are their responsibilities?",
  },
  {
    icon: ShieldCheck,
    title: "Fault Tolerance & Guardrails",
    desc: "Audit error recovery, boundary validation, and retry strategies",
    prompt:
      "How does this codebase handle errors, retries, and input validation?",
  },
];

export default function ChatWorkspace({
  activeRepo,
  activeConversation,
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
  onIngestRepository,
  isIngesting,
  ingestError,
  health,
  isSidebarCollapsed,
  onExpandSidebar,
}) {
  const [input, setInput] = useState("");
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  // Inline repository ingestion state when no repo is mounted
  const [inlineRepoUrl, setInlineRepoUrl] = useState("");
  const [inlineBranch, setInlineBranch] = useState("");

  const messagesContainerRef = useRef(null);
  const textareaRef = useRef(null);
  const prevScrollHeightRef = useRef(null);

  const isLocalRepo = (url) => {
    const str = String(url || "").toLowerCase();
    return (
      str === "local" ||
      str.includes("local/codebase-copilot") ||
      str.includes("local/arcline")
    );
  };

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
    ta.style.height = `${Math.min(ta.scrollHeight, 140)}px`;
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

  const handleInlineRepoSubmit = async (e) => {
    e.preventDefault();
    const trimmed = inlineRepoUrl.trim();
    if (!trimmed || isIngesting || !onIngestRepository) return;
    await onIngestRepository({
      repoUrl: trimmed,
      branch: inlineBranch.trim() || null,
      llmSummaries: false,
    });
  };

  const handleMountLocalWorkspace = async () => {
    if (isIngesting || !onIngestRepository) return;
    await onIngestRepository({
      repoUrl: "local",
      branch: "main",
      llmSummaries: false,
    });
  };

  const activeTitle = activeConversation?.title || "New thread";

  return (
    <TooltipProvider delayDuration={180}>
      <main className="landing-dark-canvas relative flex h-screen min-w-0 flex-1 flex-col bg-[#0B0F16] text-[#E5E7EB]">
        {/* Minimal Top Header Bar */}
        <header className="z-10 flex h-12 shrink-0 items-center justify-between gap-4 border-b border-[#1E2636] bg-[#0B0F16]/85 px-5 backdrop-blur-md">
          <div className="flex min-w-0 items-center gap-2.5">
            {isSidebarCollapsed && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={onExpandSidebar}
                    aria-label="Expand sidebar"
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] text-[#9CA3AF] transition-colors hover:bg-[#1A2232] hover:text-white cursor-pointer"
                  >
                    <PanelLeftOpen className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom">Expand sidebar</TooltipContent>
              </Tooltip>
            )}

            {activeRepo ? (
              <div className="flex min-w-0 items-center gap-2 font-inter text-[13px]">
                {isLocalRepo(activeRepo.repo_url) ? (
                  <Laptop className="h-3.5 w-3.5 shrink-0 text-[#7DB4FF]" />
                ) : (
                  <GitHubIcon className="h-3.5 w-3.5 shrink-0 text-[#9CA3AF]" />
                )}
                <span className="truncate font-medium text-[#F3F4F6]">
                  {formatRepoName(activeRepo.repo_url)}
                </span>
                <span className="inline-flex items-center gap-1 rounded-[5px] border border-[#243041] bg-[#141A26] px-1.5 py-0.5 font-mono text-[10.5px] text-[#9CA3AF]">
                  <GitBranch className="h-2.5 w-2.5 text-[#7DB4FF]" />
                  <span>{activeRepo.branch || "main"}</span>
                </span>
                <span className="hidden text-[#374151] sm:inline">/</span>
                <span className="hidden truncate text-[#9CA3AF] sm:inline">
                  {activeTitle}
                </span>
              </div>
            ) : (
              <span className="font-inter text-[13px] font-medium text-[#9CA3AF]">
                Workspace
              </span>
            )}
          </div>

          {activeRepo && (
            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={onReindexRepo}
                disabled={isReindexing}
                title="Sync incremental file changes"
                className="inline-flex items-center gap-1.5 rounded-[7px] border border-[#243041] bg-[#131822] px-2.5 py-1 font-inter text-[12px] font-medium text-[#D1D5DB] transition-colors hover:border-[#2E3B52] hover:bg-[#1A2232] hover:text-white disabled:opacity-50 cursor-pointer"
              >
                <RefreshCw
                  className={cn(
                    "h-3 w-3",
                    isReindexing && "animate-spin text-[#7DB4FF]"
                  )}
                />
                <span>{isReindexing ? "Syncing..." : "Sync"}</span>
              </button>

              <button
                type="button"
                onClick={onNewChat}
                disabled={isSending || isCreatingChat}
                className="inline-flex items-center gap-1.5 rounded-[7px] border border-[#263246] bg-[#172030] px-2.5 py-1 font-inter text-[12px] font-medium text-white transition-colors hover:bg-[#1E2A3F] disabled:opacity-50 cursor-pointer"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>New chat</span>
              </button>
            </div>
          )}
        </header>

        {/* Setup / Configuration Alert Banner */}
        {!health?.loading && !health?.ok && health?.issues?.length > 0 && (
          <div className="mx-6 mt-4 flex items-start gap-3 rounded-[10px] border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <div>
              <strong className="font-inter text-[12px] font-semibold text-white">
                Environment Configuration Required
              </strong>
              <ul className="mt-1 list-disc pl-4 text-[#D1D5DB]">
                {health.issues.map((issue, idx) => (
                  <li key={idx}>{issue}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Main Viewport */}
        <div
          className="flex-1 overflow-y-auto px-5 pt-6 pb-4 landing-dark-code-scroll"
          ref={messagesContainerRef}
          onScroll={handleScroll}
        >
          <div className="mx-auto flex min-h-full max-w-[780px] flex-col">
            {!activeRepo ? (
              /* Inline "Enter a repo link" Empty State matching the screenshot */
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                className="m-auto w-full max-w-[600px] py-8"
              >
                <div className="mb-6 text-center">
                  <h2 className="font-inter text-[28px] font-medium tracking-[-0.025em] text-white sm:text-[34px]">
                    Connect your{" "}
                    <span className="font-fraunces italic font-normal text-[#7DB4FF]">
                      repository
                    </span>
                  </h2>
                  <p className="mx-auto mt-2 max-w-[440px] font-inter text-[14px] leading-relaxed text-[#9CA3AF]">
                    Paste a GitHub repository link below to index AST symbols,
                    trace call graphs, and query your codebase.
                  </p>
                </div>

                {/* Screenshot-matched Repo Link Input Bar */}
                <form onSubmit={handleInlineRepoSubmit} className="w-full">
                  <div className="flex items-center gap-3.5 rounded-[8px] border border-[#2A3446] bg-[#10141D] px-4 py-2.5 shadow-[0_12px_36px_rgba(0,0,0,0.5)] transition-colors focus-within:border-[#7DB4FF]/70">
                    <GitHubIcon className="h-5 w-5 shrink-0 text-[#E5E7EB]" />
                    <input
                      type="url"
                      placeholder="Enter a repo link"
                      value={inlineRepoUrl}
                      onChange={(e) => setInlineRepoUrl(e.target.value)}
                      disabled={isIngesting}
                      required
                      className="w-full bg-transparent font-inter text-[14px] text-[#E5E7EB] placeholder:text-[#6B7280] focus:outline-none"
                    />
                    <button
                      type="submit"
                      disabled={isIngesting || !inlineRepoUrl.trim()}
                      aria-label="Connect repository"
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#E5E7EB] text-[#0B0F16] transition-all hover:bg-white disabled:opacity-40 cursor-pointer"
                    >
                      {isIngesting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <ArrowRight className="h-4 w-4 stroke-[2]" />
                      )}
                    </button>
                  </div>

                  {/* Secondary inline options: Optional branch + Mount local workspace */}
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 px-1 text-[12px] text-[#9CA3AF]">
                    <div className="flex items-center gap-2">
                      <GitBranch className="h-3.5 w-3.5 text-[#6B7280]" />
                      <input
                        type="text"
                        placeholder="Branch (default: main)"
                        value={inlineBranch}
                        onChange={(e) => setInlineBranch(e.target.value)}
                        disabled={isIngesting}
                        className="w-40 rounded-[6px] border border-transparent bg-transparent px-1.5 py-0.5 font-mono text-[11.5px] text-[#D1D5DB] placeholder:text-[#6B7280] focus:border-[#243041] focus:bg-[#131822] focus:outline-none"
                      />
                    </div>

                    <button
                      type="button"
                      onClick={handleMountLocalWorkspace}
                      disabled={isIngesting}
                      className="inline-flex items-center gap-1.5 font-inter text-[12px] text-[#9CA3AF] transition-colors hover:text-[#7DB4FF] disabled:opacity-40 cursor-pointer"
                    >
                      <Laptop className="h-3.5 w-3.5" />
                      <span>Mount local workspace</span>
                    </button>
                  </div>
                </form>

                {isIngesting && (
                  <div className="mt-4 flex items-center justify-center gap-2.5 rounded-[8px] border border-[#243041] bg-[#131822]/90 px-4 py-2.5 font-inter text-[12.5px] text-[#D1D5DB]">
                    <Loader2 className="h-4 w-4 animate-spin text-[#7DB4FF]" />
                    <span>
                      Indexing repository AST symbols & vector embeddings...
                    </span>
                  </div>
                )}

                {ingestError && (
                  <div className="mt-4 flex items-center gap-2 rounded-[8px] border border-red-500/35 bg-red-950/30 px-3.5 py-2.5 font-inter text-[12.5px] text-red-200">
                    <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
                    <span>{ingestError}</span>
                  </div>
                )}
              </motion.div>
            ) : loadingConversation ? (
              <div className="m-auto flex items-center gap-2.5 font-inter text-[13px] text-[#9CA3AF]">
                <Loader2 className="h-4 w-4 animate-spin text-[#7DB4FF]" />
                <span>Loading conversation...</span>
              </div>
            ) : messages.length === 0 ? (
              <div className="m-auto w-full max-w-[660px] py-6">
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  className="mb-7 text-center"
                >
                  <h2 className="font-inter text-[26px] font-medium tracking-[-0.025em] text-white sm:text-[32px]">
                    Ask anything about{" "}
                    <span className="font-fraunces italic font-normal text-[#7DB4FF]">
                      {formatRepoName(activeRepo.repo_url)}
                    </span>
                  </h2>
                  <p className="mx-auto mt-2 max-w-[460px] font-inter text-[13.5px] leading-relaxed text-[#9CA3AF]">
                    Trace execution paths, symbol definitions, and module
                    boundaries with line-accurate file citations.
                  </p>
                </motion.div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {STARTER_PROMPTS.map((item, idx) => {
                    const IconComponent = item.icon;
                    return (
                      <motion.button
                        type="button"
                        key={item.title}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{
                          duration: 0.32,
                          delay: 0.05 + idx * 0.05,
                          ease: [0.16, 1, 0.3, 1],
                        }}
                        onClick={() => !isSending && onSendMessage(item.prompt)}
                        disabled={isSending}
                        className="group flex flex-col justify-between rounded-[10px] border border-[#1E2636] bg-[#111621]/90 p-4 text-left transition-all hover:border-[#2E3B52] hover:bg-[#161D2B] cursor-pointer"
                      >
                        <div className="mb-2.5 flex items-center justify-between">
                          <span className="font-inter text-[13px] font-semibold text-[#F3F4F6] group-hover:text-white">
                            {item.title}
                          </span>
                          <IconComponent className="h-4 w-4 text-[#6B7280] transition-colors group-hover:text-[#7DB4FF]" />
                        </div>
                        <p className="font-inter text-[12px] leading-relaxed text-[#9CA3AF]">
                          {item.desc}
                        </p>
                      </motion.button>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-5 pb-4">
                {hasMoreMessages && (
                  <div className="flex justify-center">
                    <button
                      type="button"
                      onClick={handleLoadOlderClick}
                      disabled={loadingOlderMessages}
                      className="inline-flex items-center gap-1.5 rounded-[8px] border border-[#243041] bg-[#131822] px-3 py-1.5 font-inter text-[12px] text-[#9CA3AF] transition-colors hover:bg-[#1A2232] hover:text-white cursor-pointer"
                    >
                      {loadingOlderMessages ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-[#7DB4FF]" />
                          <span>Loading earlier messages...</span>
                        </>
                      ) : (
                        <>
                          <History className="h-3.5 w-3.5 text-[#7DB4FF]" />
                          <span>Load earlier messages</span>
                        </>
                      )}
                    </button>
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
          <button
            type="button"
            onClick={() => scrollToBottom("smooth")}
            className="absolute bottom-24 left-1/2 z-20 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full border border-[#243041] bg-[#131822] text-[#E5E7EB] shadow-lg transition-colors hover:bg-[#1A2232] cursor-pointer"
            title="Scroll to latest message"
            aria-label="Scroll to latest message"
          >
            <ArrowDown className="h-4 w-4 text-[#7DB4FF]" />
          </button>
        )}

        {/* Bottom Chat Input Bar — Matching the Screenshot UI */}
        {activeRepo && (
          <div className="shrink-0 bg-gradient-to-t from-[#0B0F16] via-[#0B0F16]/95 to-transparent px-5 pt-2 pb-5">
            <form
              onSubmit={handleSubmit}
              className="mx-auto flex w-full max-w-[780px] items-center gap-3.5 rounded-[8px] border border-[#2A3446] bg-[#10141D] px-4 py-2.5 shadow-[0_12px_36px_rgba(0,0,0,0.5)] transition-colors focus-within:border-[#7DB4FF]/70"
            >
              {isLocalRepo(activeRepo.repo_url) ? (
                <Laptop className="h-5 w-5 shrink-0 text-[#9CA3AF]" />
              ) : (
                <GitHubIcon className="h-5 w-5 shrink-0 text-[#E5E7EB]" />
              )}

              <textarea
                ref={textareaRef}
                rows={1}
                placeholder={`Ask ${formatRepoName(activeRepo.repo_url)} a question...`}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isSending}
                className="max-h-[140px] min-h-[24px] flex-1 resize-none bg-transparent font-inter text-[14px] leading-6 text-[#E5E7EB] placeholder:text-[#6B7280] focus:outline-none landing-dark-code-scroll"
              />

              <button
                type="submit"
                disabled={!input.trim() || isSending}
                title="Send message"
                aria-label="Send message"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#E5E7EB] text-[#0B0F16] transition-all hover:bg-white disabled:opacity-35 cursor-pointer"
              >
                {isSending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4 stroke-[2]" />
                )}
              </button>
            </form>
          </div>
        )}
      </main>
    </TooltipProvider>
  );
}
