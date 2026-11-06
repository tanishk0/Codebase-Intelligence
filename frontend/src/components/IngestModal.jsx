import React, { useState } from "react";
import {
  X,
  FolderGit2,
  GitBranch,
  Laptop,
  Globe,
  Loader2,
  Sparkles,
  ArrowRight,
  AlertCircle,
} from "lucide-react";

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

  if (!isOpen) return null;

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
    <div className="modal-backdrop" onClick={!isIngesting ? onClose : undefined}>
      <div
        className="modal-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-icon-badge">
              <FolderGit2 size={18} />
            </div>
            <div>
              <h2 id="modal-title">Connect Repository</h2>
              <p className="modal-subtitle">
                Index a repository to search and chat with its codebase
              </p>
            </div>
          </div>
          <button
            type="button"
            className="icon-button subtle"
            onClick={onClose}
            disabled={isIngesting}
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Source Selector Tabs */}
        <div className="source-tabs">
          <button
            type="button"
            className={`source-tab ${sourceType === "github" ? "active" : ""}`}
            onClick={() => setSourceType("github")}
            disabled={isIngesting}
          >
            <Globe size={15} />
            <span>GitHub Repository</span>
          </button>
          <button
            type="button"
            className={`source-tab ${sourceType === "local" ? "active" : ""}`}
            onClick={() => setSourceType("local")}
            disabled={isIngesting}
          >
            <Laptop size={15} />
            <span>Local Workspace</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {sourceType === "github" ? (
            <>
              <div className="form-field">
                <label htmlFor="repo-url-input">Repository HTTPS URL</label>
                <div className="input-with-icon">
                  <FolderGit2 size={15} className="field-icon" />
                  <input
                    id="repo-url-input"
                    type="url"
                    placeholder="https://github.com/organization/repository"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    disabled={isIngesting}
                    required
                    autoFocus
                  />
                </div>
              </div>

              <div className="form-field">
                <label htmlFor="repo-branch-input">
                  Branch <span className="optional-tag">Optional</span>
                </label>
                <div className="input-with-icon">
                  <GitBranch size={15} className="field-icon" />
                  <input
                    id="repo-branch-input"
                    type="text"
                    placeholder="Default branch (e.g. main)"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    disabled={isIngesting}
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
