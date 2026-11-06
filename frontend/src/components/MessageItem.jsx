import React, { useState } from "react";
import { motion } from "motion/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Copy,
  Check,
  User,
  FileCode2,
  Terminal,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const FILE_REF_REGEX = /^\[?[a-zA-Z0-9_./-]+:L\d+(?:-L?\d+)?\]?$/;

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
        <Badge
          variant="outline"
          className="mx-0.5 inline-flex items-center gap-1 rounded border-primary/35 bg-primary/10 px-1.5 py-0.2 font-mono text-[11px] font-medium text-primary align-baseline"
          title={`Source reference: ${cleanRef}`}
        >
          <FileCode2 className="h-3 w-3 shrink-0" />
          <span>{cleanRef}</span>
        </Badge>
      );
    }
    return (
      <code
        className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[12px] text-foreground"
        {...props}
      >
        {children}
      </code>
    );
  }

  const language = match ? match[1] : "source";

  return (
    <div className="my-4 overflow-hidden rounded-lg border border-stone-800 bg-[#121110] text-stone-100 shadow-sm">
      <div className="flex items-center justify-between border-b border-stone-800 bg-[#1B1917] px-3.5 py-1.5 font-mono text-[11px] text-stone-400">
        <div className="flex items-center gap-2 uppercase tracking-wider">
          <span className="h-2 w-2 rounded-full bg-primary" />
          <span>{language}</span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          className="h-6 gap-1.5 rounded px-2 font-mono text-[10.5px] uppercase tracking-wider text-stone-300 hover:bg-stone-800 hover:text-white"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span>COPIED</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>COPY</span>
            </>
          )}
        </Button>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-stone-100">
        <code className={className} {...props}>
          {rawText}
        </code>
      </pre>
    </div>
  );
}

export default function MessageItem({ message }) {
  const [copiedMessage, setCopiedMessage] = useState(false);
  const isUser = message.role === "user";
  const isStreaming = Boolean(message.streaming);
  const statusStage = message.statusStage || "";

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
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
        className="flex items-start justify-end gap-3"
      >
        <div className="max-w-[78%] rounded-xl rounded-tr-xs border border-primary/30 bg-primary px-4 py-3 text-sm leading-relaxed text-primary-foreground shadow-xs">
          <div className="mb-1 font-mono text-[9.5px] uppercase tracking-widest opacity-80">
            QUERY // OPERATOR
          </div>
          <div className="whitespace-pre-wrap break-words font-medium">
            {message.content}
          </div>
        </div>
        <div
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-card text-foreground shadow-xs"
          title="Operator"
        >
          <User className="h-4 w-4" />
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
      className="flex items-start gap-3"
    >
      <div
        className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-xs"
        title="Codebase Copilot"
      >
        <Terminal className="h-4 w-4" />
      </div>

      <Card className="tactile-card min-w-0 flex-1 rounded-xl border-border bg-card px-5 py-4">
        <div className="mb-2.5 flex items-center justify-between border-b border-border/70 pb-2">
          <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            ANALYSIS // RESPONSE
          </span>
          {!isStreaming && message.content && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleCopyMessage}
              className="h-6 gap-1.5 rounded px-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground hover:text-foreground"
            >
              {copiedMessage ? (
                <>
                  <Check className="h-3 w-3 text-emerald-500" />
                  <span>COPIED</span>
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" />
                  <span>COPY LOG</span>
                </>
              )}
            </Button>
          )}
        </div>

        {isStreaming && !message.content ? (
          <div className="flex items-center gap-3 py-2 font-mono text-xs uppercase tracking-wider text-muted-foreground">
            <div className="thinking-dots">
              <span />
              <span />
              <span />
            </div>
            <span>{statusStage || "ANALYZING CODEBASE..."}</span>
          </div>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code: CodeBlock,
              }}
            >
              {message.content || ""}
            </ReactMarkdown>
            {isStreaming && <span className="streaming-cursor" />}
          </div>
        )}
      </Card>
    </motion.div>
  );
}
