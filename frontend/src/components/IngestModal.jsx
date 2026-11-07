import React, { useState } from "react";
import {
  FolderGit2,
  GitBranch,
  Laptop,
  Globe,
  Loader2,
  FileText,
  ArrowRight,
  AlertCircle,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";

export default function IngestModal({
  isOpen,
  onClose,
  onIngest,
  isIngesting,
  error,
}) {
  const [sourceType, setSourceType] = useState("github"); // "github" | "local"
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [deepSummaries, setDeepSummaries] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const targetUrl = sourceType === "local" ? "local" : repoUrl.trim();
    if (!targetUrl) return;
    await onIngest({
      repoUrl: targetUrl,
      branch: sourceType === "local" ? "main" : branch.trim() || null,
      llmSummaries: deepSummaries,
    });
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open && !isIngesting) onClose();
      }}
    >
      <DialogContent className="sm:max-w-[490px] rounded-xl border-border bg-card">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary">
              <FolderGit2 className="h-5 w-5" />
            </div>
            <div className="text-left">
              <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">
                INDEXER // MOUNT
              </div>
              <DialogTitle className="font-display text-lg font-bold">
                Mount Repository
              </DialogTitle>
              <DialogDescription className="text-xs">
                Parse AST symbols, call graphs, and module boundaries for codebase queries.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="mt-2 flex flex-col gap-4">
          <Tabs
            value={sourceType}
            onValueChange={setSourceType}
            className="w-full"
          >
            <TabsList className="grid w-full grid-cols-2 rounded-lg">
              <TabsTrigger
                value="github"
                disabled={isIngesting}
                className="font-mono text-[11px] uppercase tracking-wider"
              >
                <Globe className="h-3.5 w-3.5" />
                <span>GitHub URL</span>
              </TabsTrigger>
              <TabsTrigger
                value="local"
                disabled={isIngesting}
                className="font-mono text-[11px] uppercase tracking-wider"
              >
                <Laptop className="h-3.5 w-3.5" />
                <span>Local Workspace</span>
              </TabsTrigger>
            </TabsList>

            <TabsContent value="github" className="mt-4 space-y-3.5">
              <div className="space-y-1.5">
                <label
                  htmlFor="repo-url-input"
                  className="font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground"
                >
                  Repository HTTPS URL
                </label>
                <div className="relative flex items-center">
                  <FolderGit2 className="pointer-events-none absolute left-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="repo-url-input"
                    type="url"
                    placeholder="https://github.com/organization/repository"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    disabled={isIngesting}
                    required={sourceType === "github"}
                    className="pl-9 font-mono text-xs"
                    autoFocus
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="repo-branch-input"
                    className="font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground"
                  >
                    Target Branch
                  </label>
                  <span className="font-mono text-[10px] uppercase text-muted-foreground">
                    Optional
                  </span>
                </div>
                <div className="relative flex items-center">
                  <GitBranch className="pointer-events-none absolute left-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="repo-branch-input"
                    type="text"
                    placeholder="main"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    disabled={isIngesting}
                    className="pl-9 font-mono text-xs"
                  />
                </div>
              </div>
            </>
          ) : (
            <div className="local-workspace-card">
              <div className="local-card-icon">
                <Laptop size={20} />
              </div>
              <div className="local-card-info">
                <h4>Index Local Project Workspace</h4>
                <p>
                  Scans and indexes the local project files directly from your workspace directory with automatic incremental sync.
                </p>
              </div>
            </div>
          )}

          {/* Deep Summaries Option (No AI model names) */}
          <label className="feature-toggle-card">
            <div className="feature-toggle-left">
              <div className="feature-icon">
                <Sparkles size={15} />
              </div>
              <div>
                <div className="feature-title">Enhanced Architectural Summaries</div>
                <div className="feature-desc">
                  Generate high-level file and module overviews during indexing
                </div>
              </div>
            </div>
            <input
              type="checkbox"
              className="toggle-checkbox"
              checked={deepSummaries}
              onChange={(e) => setDeepSummaries(e.target.checked)}
              disabled={isIngesting}
            />
          </label>

          {error && (
            <div className="modal-error-banner">
              <AlertCircle size={15} />
              <span>{error}</span>
            </div>
          )}

          <div className="modal-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={isIngesting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={
                isIngesting || (sourceType === "github" && !repoUrl.trim())
              }
            >
              {isIngesting ? (
                <>
                  <Loader2 size={16} className="spin" />
                  <span>Indexing Codebase...</span>
                </>
              ) : (
                <>
                  <span>
                    {sourceType === "local"
                      ? "Index Local Workspace"
                      : "Connect & Index"}
                  </span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
