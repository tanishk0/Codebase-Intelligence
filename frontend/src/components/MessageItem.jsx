import React, { useState, useMemo, useId } from "react";
import { motion } from "motion/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Copy,
  Check,
  FileText,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const FILE_REF_REGEX = /^\[?[a-zA-Z0-9_./-]+:L\d+(?:-L?\d+)?\]?$/;
const GLOBAL_FILE_REF_REGEX = /`?\[?([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+):L(\d+(?:-L?\d+)?)\]?`?/g;

function DiamondSparkleIcon({ className = "w-4 h-4 text-[#e5e5e5]" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 2L14.3 9.7L22 12L14.3 14.3L12 22L9.7 14.3L2 12L9.7 9.7L12 2Z" />
    </svg>
  );
}

function CodeBlock({ inline, className, children, ...props }) {
  const [copied, setCopied] = useState(false);
  const rawText = String(children || "").replace(/\n$/, "");
  const match = /language-(\w+)/.exec(className || "");

  const isBlock = !inline && (Boolean(match) || rawText.includes("\n"));

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(rawText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard fallback ignored
    }
  };

  if (!isBlock) {
    const cleanRef = rawText.replace(/^\[|\]$/g, "");
    if (FILE_REF_REGEX.test(rawText.trim())) {
      return (
        <span
          className="mx-0.5 inline-flex items-center gap-1 rounded-[5px] border border-[#343434] bg-[#1c1c1c] px-1.5 py-0.5 font-mono text-[11.5px] font-medium text-[#d4d4d4] align-baseline"
          title={`Source reference: ${cleanRef}`}
        >
          <FileText className="h-3 w-3 shrink-0 text-[#d4d4d4]" />
          <span>{cleanRef}</span>
        </span>
      );
    }
    return (
      <code
        className="mx-0.5 inline-block rounded-[4px] border border-[#313131] bg-[#222222] px-1.5 py-0.5 font-mono text-[12px] font-medium text-[#e5e5e5]"
        {...props}
      >
        {children}
      </code>
    );
  }

  const language = match ? match[1] : "code";

  return (
    <div className="my-3.5 overflow-hidden rounded-[10px] border border-[#2a2a2a] bg-[#000000] text-[#e5e5e5]">
      <div className="flex items-center justify-between border-b border-[#262626] bg-[#171717] px-3.5 py-1.5 font-mono text-[11px] text-[#a3a3a3]">
        <span className="lowercase">{language}</span>
        <Button
          variant="ghost"
          size="sm"
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 font-inter text-[11px] text-[#a3a3a3] transition-colors hover:bg-[#202020] hover:text-white cursor-pointer"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span>Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </Button>
      </div>
      <pre className="landing-dark-code-scroll overflow-x-auto p-3.5 font-mono text-[12.5px] leading-relaxed text-[#e5e5e5]">
        <code className={className} {...props}>
          {rawText}
        </code>
      </pre>
    </div>
  );
}

export default function MessageItem({ message }) {
  const [copiedMessage, setCopiedMessage] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const sourcesId = useId();
  const isUser = message.role === "user";
  const isStreaming = Boolean(message.streaming);
  const statusStage = message.statusStage || "";

  // Extract unique file citations from the message content or message.sources
  const extractedSources = useMemo(() => {
    if (isUser || !message.content) return [];
    const map = new Map();
    const text = String(message.content);
    let m;
    const regex = new RegExp(GLOBAL_FILE_REF_REGEX.source, "g");
    while ((m = regex.exec(text)) !== null) {
      const path = m[1];
      const rawLines = m[2];
      const formattedLines = rawLines.includes("-")
        ? `L${rawLines.replace(/-L?/i, "–")}`
        : `L${rawLines}`;
      const key = `${path}:${formattedLines}`;
      if (!map.has(key)) {
        map.set(key, { path, lines: formattedLines });
      }
    }
    return Array.from(map.values());
  }, [isUser, message.content]);

  const handleCopyMessage = async () => {
    if (!message.content) return;
    try {
      await navigator.clipboard.writeText(message.content);
      setCopiedMessage(true);
      setTimeout(() => setCopiedMessage(false), 1800);
    } catch {
      // Ignore clipboard errors
    }
  };

  if (isUser) {
    return (
      <motion.article
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        className="flex justify-end"
      >
        <div className="max-w-[88%] rounded-2xl bg-secondary px-4 py-3 font-inter text-[15px] leading-relaxed text-foreground sm:max-w-[78%]">
          <div className="whitespace-pre-wrap break-words">
            {message.content}
          </div>
        </div>
      </motion.article>
    );
  }

  return (
    <motion.article
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
      className="group relative min-w-0 py-3"
      aria-label="Arcline response"
      aria-busy={isStreaming}
    >
      <div className="flex items-start gap-3">
        <div className="mt-1 flex h-4 w-4 shrink-0 items-center justify-center">
          <DiamondSparkleIcon className="h-4 w-4 text-[#e5e5e5]" />
        </div>

        <div className="min-w-0 flex-1">
          {isStreaming && !message.content ? (
            <div role="status" className="flex min-h-7 items-center gap-3 font-inter text-sm text-muted-foreground">
              <div className="thinking-dots">
                <span />
                <span />
                <span />
              </div>
              <span>{statusStage || "Analyzing codebase..."}</span>
            </div>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code: CodeBlock,
                  pre: ({ children }) => <>{children}</>,
                }}
              >
                {message.content || ""}
              </ReactMarkdown>
              {isStreaming && <span className="streaming-cursor" />}
            </div>
          )}

          {!isStreaming && message.content && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleCopyMessage}
              className="mt-3 h-8 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
              aria-label={copiedMessage ? "Response copied" : "Copy response"}
            >
              {copiedMessage ? <Check /> : <Copy />}
              {copiedMessage ? "Copied" : "Copy response"}
            </Button>
          )}

          {/* Sources appear once the response is complete. */}
          {!isStreaming && extractedSources.length > 0 && (
            <div className="mt-3 border-t border-border/60 pt-3">
              <Button
                variant="ghost"
                size="sm"
                type="button"
                onClick={() => setSourcesOpen((prev) => !prev)}
                aria-expanded={sourcesOpen}
                aria-controls={sourcesId}
                className="h-8 gap-1.5 px-2 font-inter text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                <span>Sources ({extractedSources.length})</span>
                <ChevronDown
                  className={cn(
                    "h-3 w-3 transition-transform",
                    sourcesOpen && "rotate-180"
                  )}
                />
              </Button>

              {sourcesOpen && (
                <div id={sourcesId} className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                  {extractedSources.map((src) => (
                    <div
                      key={`${src.path}:${src.lines}`}
                      className="flex items-center justify-between rounded-[8px] border border-[#272727] bg-[#191919] px-3 py-1.5 text-[12px] transition-colors hover:border-[#393939] hover:bg-[#212121]"
                    >
                      <div className="flex items-center gap-2 truncate pr-2">
                        <FileText className="h-3.5 w-3.5 shrink-0 text-[#a3a3a3]" />
                        <span className="truncate font-inter text-[#d4d4d4]">
                          {src.path}
                        </span>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <span className="rounded-[4px] bg-[#262626] px-1.5 py-0.5 font-mono text-[10.5px] text-[#a3a3a3]">
                          {src.lines}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.article>
  );
}
