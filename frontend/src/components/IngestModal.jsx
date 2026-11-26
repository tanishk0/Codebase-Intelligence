import React, { useState } from "react";
import {
  GitBranch,
  Laptop,
  Loader2,
  FileText,
  ArrowRight,
  AlertCircle,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

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
      <DialogContent className="sm:max-w-[500px] rounded-[16px] border border-[#2a2a2a] bg-[#111111] p-6 text-[#e5e5e5] shadow-2xl font-inter">
        <DialogHeader>
          <DialogTitle className="font-inter text-[18px] font-semibold tracking-tight text-white">
            Connect repository
          </DialogTitle>
          <DialogDescription className="font-inter text-[13px] text-[#a3a3a3]">
            Index a public GitHub repository or mount your local workspace.
          </DialogDescription>
        </DialogHeader>

        {/* Source Switcher Pills */}
        <div className="mt-2 inline-flex rounded-[8px] border border-[#272727] bg-[#000000] p-1">
          <button
            type="button"
            disabled={isIngesting}
            onClick={() => setSourceType("github")}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-[6px] px-3 py-1.5 font-inter text-[12.5px] font-medium transition-colors cursor-pointer",
              sourceType === "github"
                ? "bg-[#262626] text-white"
                : "text-[#a3a3a3] hover:text-white"
            )}
          >
            <GitHubIcon className="h-3.5 w-3.5" />
            <span>GitHub URL</span>
          </button>
          <button
            type="button"
            disabled={isIngesting}
            onClick={() => setSourceType("local")}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-[6px] px-3 py-1.5 font-inter text-[12.5px] font-medium transition-colors cursor-pointer",
              sourceType === "local"
                ? "bg-[#262626] text-white"
                : "text-[#a3a3a3] hover:text-white"
            )}
          >
            <Laptop className="h-3.5 w-3.5" />
            <span>Local Workspace</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3.5">
          {sourceType === "github" ? (
            <>
              {/* Screenshot-Matched Repo Link Bar */}
              <div className="flex items-center gap-3 rounded-[8px] border border-[#333333] bg-[#000000] px-3.5 py-2.5 transition-colors focus-within:border-[#d4d4d4]/70">
                <GitHubIcon className="h-5 w-5 shrink-0 text-[#e5e5e5]" />
                <input
                  id="repo-url-input"
                  type="url"
                  placeholder="Enter a repo link"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  disabled={isIngesting}
                  required={sourceType === "github"}
                  autoFocus
                  className="w-full bg-transparent font-inter text-[13.5px] text-[#e5e5e5] placeholder:text-[#858585] focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={isIngesting || !repoUrl.trim()}
                  aria-label="Connect repository"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#e5e5e5] text-[#000000] transition-all hover:bg-white disabled:opacity-40 cursor-pointer"
                >
                  {isIngesting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowRight className="h-4 w-4 stroke-[2]" />
                  )}
                </button>
              </div>

              <div className="flex items-center gap-2.5 rounded-[8px] border border-[#262626] bg-[#000000]/60 px-3 py-2">
                <GitBranch className="h-3.5 w-3.5 shrink-0 text-[#858585]" />
                <input
                  id="repo-branch-input"
                  type="text"
                  placeholder="Branch (optional, defaults to main)"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  disabled={isIngesting}
                  className="w-full bg-transparent font-mono text-[12px] text-[#d4d4d4] placeholder:text-[#858585] focus:outline-none"
                />
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between gap-3 rounded-[10px] border border-[#2a2a2a] bg-[#000000] p-3.5">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#2a2a2a] bg-[#1b1b1b] text-[#d4d4d4]">
                  <Laptop className="h-4 w-4" />
                </div>
                <div>
                  <div className="font-inter text-[13px] font-medium text-white">
                    Mount Local Workspace
                  </div>
                  <div className="font-inter text-[11.5px] text-[#a3a3a3]">
                    Indexes the local directory with SHA-256 incremental sync
                  </div>
                </div>
              </div>

              <button
                type="submit"
                disabled={isIngesting}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#e5e5e5] text-[#000000] transition-all hover:bg-white disabled:opacity-40 cursor-pointer"
              >
                {isIngesting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4 stroke-[2]" />
                )}
              </button>
            </div>
          )}

          {/* Deep Summaries Toggle */}
          <div className="flex items-center justify-between gap-3 rounded-[10px] border border-[#262626] bg-[#131313] px-3.5 py-2.5">
            <div className="flex items-center gap-2.5">
              <FileText className="h-4 w-4 shrink-0 text-[#d4d4d4]" />
              <div>
                <div className="font-inter text-[12.5px] font-medium text-[#e5e5e5]">
                  Deep file summaries
                </div>
                <div className="font-inter text-[11px] text-[#a3a3a3]">
                  Generate LLM architectural overviews during indexing
                </div>
              </div>
            </div>
            <Switch
              checked={deepSummaries}
              onCheckedChange={setDeepSummaries}
              disabled={isIngesting}
              aria-label="Toggle deep file summaries"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-[8px] border border-red-500/35 bg-red-950/30 px-3 py-2 font-inter text-[12px] text-red-200">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
              <span>{error}</span>
            </div>
          )}
        </form>
      </DialogContent>
    </Dialog>
  );
}
