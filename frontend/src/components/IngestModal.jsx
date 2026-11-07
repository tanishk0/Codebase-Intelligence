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
            </TabsContent>

            <TabsContent value="local" className="mt-4">
              <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/45 p-3.5">
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/25 bg-primary/10 text-primary">
                  <Laptop className="h-4 w-4" />
                </div>
                <div className="space-y-1">
                  <h4 className="font-display text-xs font-bold text-foreground">
                    Mount Local Project Directory
                  </h4>
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    Indexes the local workspace directory directly with automatic SHA-256 incremental synchronization.
                  </p>
                </div>
              </div>
            </TabsContent>
          </Tabs>

          {/* Enhanced Architectural Summaries Toggle */}
          <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/25 bg-primary/10 text-primary">
                <FileText className="h-4 w-4" />
              </div>
              <div>
                <div className="font-display text-xs font-bold text-foreground">
                  Architectural File Dossiers
                </div>
                <div className="text-[11px] text-muted-foreground">
                  Synthesize structural module overviews during AST indexing
                </div>
              </div>
            </div>
            <Switch
              checked={deepSummaries}
              onCheckedChange={setDeepSummaries}
              disabled={isIngesting}
              aria-label="Toggle architectural file dossiers"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2.5 font-mono text-xs text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter className="mt-1 gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isIngesting}
              className="font-mono text-xs uppercase"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={
                isIngesting || (sourceType === "github" && !repoUrl.trim())
              }
              className="font-mono text-xs uppercase tracking-wider"
            >
              {isIngesting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>INDEXING AST...</span>
                </>
              ) : (
                <>
                  <span>
                    {sourceType === "local"
                      ? "MOUNT LOCAL WORKSPACE"
                      : "MOUNT & INDEX"}
                  </span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
