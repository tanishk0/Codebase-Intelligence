import React from "react";
import { CheckCircle2, AlertCircle, Loader2, X } from "lucide-react";
import Sidebar from "../components/Sidebar";
import ChatWorkspace from "../components/ChatWorkspace";
import IngestModal from "../components/IngestModal";

export default function WorkspacePage({
  user,
  isSidebarCollapsed,
  onToggleSidebarCollapse,
  onExpandSidebar,
  onGoogleSignIn,
  isAuthenticating,
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
  return (
    <div className="saas-shell">
      <Sidebar
        repos={repos}
        activeRepo={activeRepo}
        onSelectRepo={onSelectRepo}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={onSelectConversation}
        onNewChat={onNewChat}
        isCreatingChat={isCreatingChat}
        isSending={isSending}
        onOpenIngestModal={onOpenIngestModal}
        onReindexRepo={onReindexRepo}
        isReindexing={isReindexing}
        onDeleteRepo={onDeleteRepo}
        deletingRepoId={deletingRepoId}
        health={health}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={onToggleSidebarCollapse}
        user={user}
        onGoogleSignIn={onGoogleSignIn}
        isAuthenticating={isAuthenticating}
        onSignOut={onSignOut}
        onNavigateToLanding={onNavigateToLanding}
      />

      <ChatWorkspace
        activeRepo={activeRepo}
        activeConversation={activeConversation}
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
        onIngestRepository={onIngestRepository}
        isIngesting={isIngesting}
        ingestError={ingestError}
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
          {toast.type === "info" && (
            <Loader2 size={16} className="animate-spin" />
          )}
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
