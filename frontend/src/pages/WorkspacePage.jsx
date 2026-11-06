import React from "react";
import { CheckCircle2, AlertCircle, Loader2, X, Compass } from "lucide-react";
import Sidebar from "../components/Sidebar";
import ChatWorkspace from "../components/ChatWorkspace";
import IngestModal from "../components/IngestModal";
import AuthPage from "../components/AuthPage";

export default function WorkspacePage({
  user,
  theme,
  onToggleTheme,
  isSidebarCollapsed,
  onToggleSidebarCollapse,
  onExpandSidebar,
  onGoogleSignIn,
  isAuthenticating,
  authError,
  onSignOut,
  health,
  repos,
  activeRepo,
  onSelectRepo,
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
  ingestModalOpen,
  onOpenIngestModal,
  onCloseIngestModal,
  onIngestRepository,
  isIngesting,
  ingestError,
  onReindexRepo,
  isReindexing,
  onDeleteRepo,
  deletingRepoId,
  toast,
  onDismissToast,
  onNavigateToLanding,
}) {
  if (!user) {
    return (
      <div className="relative h-screen w-screen overflow-hidden">
        {onNavigateToLanding && (
          <div className="fixed bottom-5 left-6 z-50">
            <button
              type="button"
              onClick={onNavigateToLanding}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-card/90 px-3.5 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground shadow-lg backdrop-blur-md transition-all hover:-translate-y-0.5 hover:border-primary cursor-pointer"
            >
              <Compass className="h-3.5 w-3.5 text-primary" />
              <span>← Back to Landing</span>
            </button>
          </div>
        )}

        <AuthPage
          onGoogleSignIn={onGoogleSignIn}
          isAuthenticating={isAuthenticating}
          authError={authError}
          theme={theme}
          onToggleTheme={onToggleTheme}
        />

        {toast && (
          <div className={`toast-notification ${toast.type}`}>
            {toast.type === "success" && <CheckCircle2 size={16} />}
            {toast.type === "error" && <AlertCircle size={16} />}
            {toast.type === "info" && <Loader2 size={16} className="spin" />}
            <span>{toast.message}</span>
            <button
              type="button"
              className="toast-close"
              onClick={onDismissToast}
              aria-label="Dismiss notification"
            >
              <X size={14} />
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="saas-shell">
      <Sidebar
        repos={repos}
        activeRepo={activeRepo}
        onSelectRepo={onSelectRepo}
        onOpenIngestModal={onOpenIngestModal}
        onReindexRepo={onReindexRepo}
        isReindexing={isReindexing}
        onDeleteRepo={onDeleteRepo}
        deletingRepoId={deletingRepoId}
        health={health}
        theme={theme}
        onToggleTheme={onToggleTheme}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={onToggleSidebarCollapse}
        user={user}
        onSignOut={onSignOut}
        onNavigateToLanding={onNavigateToLanding}
      />

      <ChatWorkspace
        activeRepo={activeRepo}
        conversations={conversations}
        activeConversation={activeConversation}
        activeConversationId={activeConversationId}
        onSelectConversation={onSelectConversation}
        messages={messages}
        loadingConversation={loadingConversation}
        hasMoreMessages={hasMoreMessages}
        loadingOlderMessages={loadingOlderMessages}
        onLoadOlderMessages={onLoadOlderMessages}
        onSendMessage={onSendMessage}
        isSending={isSending}
        onNewChat={onNewChat}
        isCreatingChat={isCreatingChat}
        onReindexRepo={onReindexRepo}
        isReindexing={isReindexing}
        onOpenIngestModal={onOpenIngestModal}
        health={health}
        isSidebarCollapsed={isSidebarCollapsed}
        onExpandSidebar={onExpandSidebar}
      />

      <IngestModal
        isOpen={ingestModalOpen}
        onClose={onCloseIngestModal}
        onIngest={onIngestRepository}
        isIngesting={isIngesting}
        error={ingestError}
      />

      {/* Floating Toast Notification */}
      {toast && (
        <div className={`toast-notification ${toast.type}`}>
          {toast.type === "success" && <CheckCircle2 size={16} />}
          {toast.type === "error" && <AlertCircle size={16} />}
          {toast.type === "info" && <Loader2 size={16} className="spin" />}
          <span>{toast.message}</span>
          <button
            type="button"
            className="toast-close"
            onClick={onDismissToast}
            aria-label="Dismiss notification"
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

