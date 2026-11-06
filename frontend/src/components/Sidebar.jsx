import React, { useState, useMemo } from "react";
import { motion } from "motion/react";
import {
  Terminal,
  Plus,
  Search,
  GitBranch,
  FolderGit2,
  Laptop,
  Sun,
  Moon,
  PanelLeftClose,
  RefreshCw,
  Trash2,
  Loader2,
  AlertTriangle,
  X,
  Clock,
  LogOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
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
import { formatRepoName, formatRelativeTime } from "../api";

export default function Sidebar({
  repos,
  activeRepo,
  onSelectRepo,
  onOpenIngestModal,
  onReindexRepo,
  isReindexing,
  onDeleteRepo,
  deletingRepoId,
  health,
  theme,
  onToggleTheme,
  isCollapsed,
  onToggleCollapse,
  user,
  onSignOut,
  onNavigateToLanding,
}) {
  const [repoSearch, setRepoSearch] = useState("");
  const [repoPendingDelete, setRepoPendingDelete] = useState(null);

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
    return str === "local" || str.includes("local/codebase-copilot");
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
          "sidebar-instrument flex h-screen flex-col border-r border-border transition-all duration-300 select-none shrink-0",
          isCollapsed
            ? "w-0 min-w-0 overflow-hidden border-r-0 opacity-0 pointer-events-none"
            : "w-[300px] min-w-[300px]"
        )}
      >
        {/* Top Instrument Plate Header */}
        <div className="border-b border-border px-4 pt-4 pb-3.5">
          <div className="mb-1 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
            {onNavigateToLanding ? (
              <button
                type="button"
                onClick={onNavigateToLanding}
                className="hover:text-foreground transition-colors cursor-pointer"
                title="Return to Landing Page"
              >
                ← LANDING // CB-COPILOT
              </button>
            ) : (
              <span>UNIT // CB-COPILOT</span>
            )}
            <span>REV 2.4</span>
          </div>

          <div className="flex items-center justify-between">
            <div
              onClick={onNavigateToLanding}
              role={onNavigateToLanding ? "button" : undefined}
              tabIndex={onNavigateToLanding ? 0 : undefined}
              className={cn(
                "flex items-center gap-2.5",
                onNavigateToLanding && "cursor-pointer group"
              )}
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-xs">
                <Terminal className="h-4 w-4" strokeWidth={2.2} />
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="font-display text-base font-bold tracking-tight text-foreground">
                  Codebase
                </span>
                <span className="font-serif text-lg italic text-primary">
                  Copilot
                </span>
              </div>
            </div>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 rounded-md text-muted-foreground hover:text-foreground"
                  onClick={onToggleCollapse}
                  aria-label="Collapse repository dock"
                >
                  <PanelLeftClose className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Collapse dock</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Primary Action & Filter Controls */}
        <div className="flex flex-col gap-2.5 border-b border-border bg-muted/35 p-3.5">
          <Button
            variant="default"
            onClick={onOpenIngestModal}
            className="group relative w-full justify-between overflow-hidden rounded-md px-3.5 py-2 font-display text-xs font-semibold tracking-tight shadow-xs transition-transform active:scale-[0.99]"
          >
            <span className="flex items-center gap-2">
              <Plus className="h-4 w-4 transition-transform duration-200 group-hover:rotate-90" />
              <span>Mount Repository</span>
            </span>
            <span className="rounded bg-black/15 px-1.5 py-0.5 font-mono text-[10px] tracking-wider uppercase">
              +INDEX
            </span>
          </Button>

          {repos.length > 0 && (
            <div className="relative flex items-center">
              <Search className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Filter mounted repos..."
                value={repoSearch}
                onChange={(e) => setRepoSearch(e.target.value)}
                className="h-8 rounded-md bg-card pl-8 pr-7 font-mono text-[11.5px]"
              />
              {repoSearch && (
                <button
                  type="button"
                  onClick={() => setRepoSearch("")}
                  className="absolute right-2 text-muted-foreground hover:text-foreground cursor-pointer"
                  aria-label="Clear filter"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Registry Section Header */}
        <div className="flex items-center justify-between px-4 pt-3.5 pb-2">
          <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Mounted Repositories
          </span>
          <span className="rounded border border-border bg-muted px-1.5 py-0.2 font-mono text-[10px] font-medium text-foreground">
            {String(repos.length).padStart(2, "0")}
          </span>
        </div>

        {/* Indexed Repositories Registry */}
        <ScrollArea className="flex-1 px-3.5 py-1">
          {repos.length === 0 ? (
            <div className="my-4 rounded-lg border border-dashed border-border bg-card/70 p-5 text-center">
              <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-md border border-primary/25 bg-primary/10 text-primary">
                <FolderGit2 className="h-4 w-4" />
              </div>
              <p className="font-display text-xs font-semibold text-foreground">
                No repositories mounted
              </p>
              <p className="mt-1 mb-3.5 text-xs leading-relaxed text-muted-foreground">
                Connect a GitHub URL or mount your local project directory to start inspecting code.
              </p>
              <Button
                size="sm"
                onClick={onOpenIngestModal}
                className="w-full font-mono text-[11px]"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>MOUNT FIRST REPO</span>
              </Button>
            </div>
          ) : filteredRepos.length === 0 ? (
            <div className="my-4 rounded-lg border border-dashed border-border bg-card/70 p-5 text-center">
              <p className="font-mono text-xs font-medium text-foreground">
                0 MATCHES
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                No mounted repository matches your filter.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2 pb-4">
              {filteredRepos.map((repo, index) => {
                const isSelected = activeRepo && repo.id === activeRepo.id;
                const isDeletingThis = deletingRepoId === repo.id;
                const local = isLocalRepo(repo.repo_url);
                const RepoIcon = local ? Laptop : FolderGit2;
                const indexCode = String(index + 1).padStart(2, "0");

                return (
                  <motion.div
                    key={repo.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: 0.28,
                      delay: Math.min(index * 0.045, 0.25),
                      ease: [0.16, 1, 0.3, 1],
                    }}
                    role="button"
                    tabIndex={0}
                    onClick={() => onSelectRepo(repo)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelectRepo(repo);
                      }
                    }}
                    className={cn(
                      "tactile-card group relative flex items-center gap-3 overflow-hidden rounded-lg border p-3 text-left transition-all cursor-pointer",
                      isSelected
                        ? "border-primary/50 bg-card"
                        : "border-border bg-card/65 hover:border-foreground/25 hover:bg-card"
                    )}
                  >
                    {isSelected && (
                      <motion.div
                        layoutId="active-repo-indicator"
                        className="absolute left-0 top-0 bottom-0 w-1 bg-primary"
                        transition={{
                          type: "spring",
                          stiffness: 380,
                          damping: 30,
                        }}
                      />
                    )}

                    <div className="flex flex-col items-center gap-1 shrink-0">
                      <span
                        className={cn(
                          "font-mono text-[9.5px] font-semibold tracking-wider",
                          isSelected
                            ? "text-primary"
                            : "text-muted-foreground/70"
                        )}
                      >
                        {indexCode}
                      </span>
                      <div
                        className={cn(
                          "flex h-7 w-7 items-center justify-center rounded border transition-colors",
                          isSelected
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-muted/60 text-muted-foreground group-hover:text-foreground"
                        )}
                      >
                        <RepoIcon className="h-3.5 w-3.5" />
                      </div>
                    </div>

                    <div className="min-w-0 flex-1">
                      <div
                        className={cn(
                          "truncate font-display text-[13px] font-semibold tracking-tight",
                          isSelected ? "text-foreground" : "text-foreground/90"
                        )}
                      >
                        {formatRepoName(repo.repo_url)}
                      </div>

                      <div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-[10.5px] text-muted-foreground">
                        <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-foreground/80">
                          <GitBranch className="h-2.5 w-2.5 text-primary" />
                          {repo.branch || "main"}
                        </span>
                        {repo.indexed_at && (
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-2.5 w-2.5" />
                            {formatRelativeTime(repo.indexed_at)}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Repository Card Actions (Sync + Delete) */}
                    <div className="flex shrink-0 items-center gap-1">
                      {isSelected && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-7 w-7 rounded-md bg-background"
                              onClick={(e) => {
                                e.stopPropagation();
                                onReindexRepo();
                              }}
                              disabled={isReindexing || isDeletingThis}
                              aria-label="Sync repository changes"
                            >
                              <RefreshCw
                                className={cn(
                                  "h-3.5 w-3.5",
                                  isReindexing && "animate-spin text-primary"
                                )}
                              />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent side="top">
                            Sync incremental changes
                          </TooltipContent>
                        </Tooltip>
                      )}

                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className={cn(
                              "h-7 w-7 rounded-md text-muted-foreground hover:bg-destructive/15 hover:text-destructive transition-opacity",
                              isSelected
                                ? "opacity-100"
                                : "opacity-0 group-hover:opacity-100 focus:opacity-100"
                            )}
                            onClick={(e) => {
                              e.stopPropagation();
                              setRepoPendingDelete(repo);
                            }}
                            disabled={isDeletingThis}
                            aria-label={`Delete ${formatRepoName(repo.repo_url)}`}
                          >
                            {isDeletingThis ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin text-destructive" />
                            ) : (
                              <Trash2 className="h-3.5 w-3.5" />
                            )}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top">
                          Delete repository
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </ScrollArea>

        {/* Authenticated Operator Profile Pod */}
        {user && (
          <div className="flex items-center justify-between gap-2.5 border-t border-border bg-card/75 px-3.5 py-2.5">
            <div className="flex min-w-0 items-center gap-2.5">
              {user.avatarUrl ? (
                <img
                  src={user.avatarUrl}
                  alt={user.name || "Operator"}
                  referrerPolicy="no-referrer"
                  className="h-8 w-8 shrink-0 rounded-md border border-border object-cover"
                />
              ) : (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/30 bg-primary/10 font-mono text-xs font-bold uppercase text-primary">
                  {(user.name || user.email || "OP").slice(0, 2)}
                </div>
              )}
              <div className="min-w-0">
                <div className="truncate font-display text-xs font-bold text-foreground">
                  {user.name || "Operator"}
                </div>
                {user.email && (
                  <div className="truncate font-mono text-[10px] text-muted-foreground">
                    {user.email}
                  </div>
                )}
              </div>
            </div>

            {onSignOut && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={onSignOut}
                    className="h-7 w-7 shrink-0 rounded-md text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
                    aria-label="Sign out"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">Sign out</TooltipContent>
              </Tooltip>
            )}
          </div>
        )}

        {/* Telemetry & Surface Mode Footer */}
        <div className="flex items-center justify-between border-t border-border bg-muted/35 px-3.5 py-2.5">
          <div className="flex items-center gap-2 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                health.loading
                  ? "bg-primary animate-pulse"
                  : health.ok
                  ? "bg-emerald-600 dark:bg-emerald-400 shadow-[0_0_0_3px_rgba(16,185,129,0.18)]"
                  : "bg-amber-500 shadow-[0_0_0_3px_rgba(245,158,11,0.2)]"
              )}
            />
            <span>
              {health.loading
                ? "SYNCING..."
                : health.ok
                ? "SYS // ONLINE"
                : "SYS // CHECK"}
            </span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={onToggleTheme}
            className="h-7 gap-1.5 rounded-md bg-card px-2.5 font-mono text-[10.5px] uppercase tracking-wider"
            aria-label="Toggle surface theme"
          >
            {theme === "light" ? (
              <>
                <Moon className="h-3 w-3 text-primary" />
                <span>Carbon</span>
              </>
            ) : (
              <>
                <Sun className="h-3 w-3 text-primary" />
                <span>Paper</span>
              </>
            )}
          </Button>
        </div>

        {/* Delete Repository Confirmation Dialog */}
        <Dialog
          open={Boolean(repoPendingDelete)}
          onOpenChange={(open) => {
            if (!open && !deletingRepoId) setRepoPendingDelete(null);
          }}
        >
          <DialogContent className="sm:max-w-[430px] rounded-xl border-border bg-card">
            <DialogHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-destructive/30 bg-destructive/10 text-destructive">
                  <AlertTriangle className="h-5 w-5" />
                </div>
                <div className="text-left">
                  <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-destructive">
                    DESTRUCTIVE ACTION // UNMOUNT
                  </div>
                  <DialogTitle className="font-display text-base font-bold">
                    Delete Repository?
                  </DialogTitle>
                </div>
              </div>
              <DialogDescription className="pt-2 text-left text-xs leading-relaxed">
                This will permanently remove{" "}
                <span className="font-mono font-semibold text-foreground">
                  {repoPendingDelete
                    ? formatRepoName(repoPendingDelete.repo_url)
                    : ""}
                </span>{" "}
                along with its indexed code symbols and saved conversation threads.
              </DialogDescription>
            </DialogHeader>

            <DialogFooter className="mt-2 gap-2 sm:gap-0">
              <Button
                type="button"
                variant="outline"
                onClick={() => setRepoPendingDelete(null)}
                disabled={Boolean(deletingRepoId)}
                className="font-mono text-xs uppercase"
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={handleConfirmDelete}
                disabled={Boolean(deletingRepoId)}
                className="font-mono text-xs uppercase tracking-wider"
              >
                {deletingRepoId ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>DELETING...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>DELETE REPOSITORY</span>
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </aside>
    </TooltipProvider>
  );
}
