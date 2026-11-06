import React, { useState } from "react";
import { motion } from "motion/react";
import {
  Terminal,
  Sun,
  Moon,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  GitBranch,
  Layers,
  FileCode2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function GoogleLogo({ className = "h-5 w-5" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.13-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96Z"
      />
    </svg>
  );
}

const PIPELINE_FEATURES = [
  {
    code: "01 // AST PARSER",
    icon: Layers,
    title: "Tree-Sitter Symbol Graph",
    desc: "Extracts classes, methods, inheritance chains, and 1-hop call edges across Python, TS, and JS.",
  },
  {
    code: "02 // HYBRID RRF",
    icon: GitBranch,
    title: "Semantic + BM25 Fusion",
    desc: "Combines 1024-dim Nemotron embeddings with exact identifier BM25 ranking and cross-encoder reranking.",
  },
  {
    code: "03 // VERIFIED PROOF",
    icon: FileCode2,
    title: "Line-Accurate Citations",
    desc: "Every architectural answer is grounded in clickable [file_path:Lstart-Lend] source spans.",
  },
];

const WORKSPACE_PERKS = [
  "Mount public GitHub repositories or local workspaces",
  "Incremental SHA-256 sync with zero-downtime index swaps",
  "Multi-turn architectural chat threads with rolling memory",
];

export default function AuthPage({
  onGoogleSignIn,
  isAuthenticating,
  authError,
  theme,
  onToggleTheme,
}) {
  const [mode, setMode] = useState("signup"); // "signup" | "signin"

  const isSignUp = mode === "signup";

  return (
    <div className="drafting-canvas relative flex min-h-screen w-screen flex-col overflow-y-auto overflow-x-hidden bg-background text-foreground select-none">
      {/* Ambient Decorative Spotlight */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
      >
        <div className="absolute -top-36 left-1/2 h-[420px] w-[780px] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px] dark:bg-primary/15" />
      </div>

      {/* Top Instrument Navigation Header */}
      <header className="relative z-10 flex h-16 shrink-0 items-center justify-between border-b border-border/80 bg-card/75 px-6 backdrop-blur-md sm:px-10">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
            <Terminal className="h-4 w-4" strokeWidth={2.3} />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="font-display text-lg font-bold tracking-tight text-foreground">
              Codebase
            </span>
            <span className="font-serif text-xl italic text-primary">
              Copilot
            </span>
          </div>
          <span className="ml-2 hidden rounded border border-border bg-muted/70 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground sm:inline-block">
            AUTH // GATEWAY
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 rounded-full border border-border bg-card/90 px-3 py-1 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground md:flex">
            <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.18)]" />
            <span>GOOGLE OAUTH 2.0 READY</span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={onToggleTheme}
            className="h-8 gap-1.5 rounded-md bg-card px-3 font-mono text-[10.5px] uppercase tracking-wider"
            aria-label="Toggle surface theme"
          >
            {theme === "light" ? (
              <>
                <Moon className="h-3.5 w-3.5 text-primary" />
                <span>Carbon</span>
              </>
            ) : (
              <>
                <Sun className="h-3.5 w-3.5 text-primary" />
                <span>Paper</span>
              </>
            )}
          </Button>
        </div>
      </header>

      {/* Main Split-Screen Content */}
      <main className="relative z-10 mx-auto flex w-full max-w-[1220px] flex-1 items-center justify-center px-6 py-10 sm:px-10 lg:py-14">
        <div className="grid w-full grid-cols-1 items-center gap-12 lg:grid-cols-12 lg:gap-12">
          {/* Left Column: Architectural Intelligence Showcase */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col justify-between lg:col-span-7 lg:pr-4"
          >
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 font-mono text-[10.5px] font-semibold uppercase tracking-[0.16em] text-primary">
                <Sparkles className="h-3 w-3" />
                <span>ARCHITECTURAL CODE INTELLIGENCE // REV 2.4</span>
              </div>

              <h1 className="font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-[52px] lg:leading-[1.08]">
                Interrogate any codebase at{" "}
                <span className="font-serif font-normal italic text-primary">
                  architectural depth.
                </span>
              </h1>

              <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                Mount repositories in seconds. Codebase Copilot parses AST symbols, traces cross-file call graphs, and synthesizes answers grounded in exact line citations.
              </p>
            </div>

            {/* Interactive Blueprint Preview Card */}
            <div className="tactile-card my-8 overflow-hidden rounded-xl border border-border bg-card/90">
              <div className="flex items-center justify-between border-b border-border bg-muted/45 px-4 py-2.5 font-mono text-[10.5px] text-muted-foreground">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-primary" />
                  <span className="font-semibold uppercase tracking-wider text-foreground">
                    LIVE TELEMETRY // RAG ENGINE
                  </span>
                </div>
                <span>1024-DIM NEMOTRON + BM25</span>
              </div>

              <div className="grid grid-cols-1 divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
                {PIPELINE_FEATURES.map((feat, idx) => {
                  const Icon = feat.icon;
                  return (
                    <motion.div
                      key={feat.code}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{
                        duration: 0.35,
                        delay: 0.12 + idx * 0.07,
                        ease: [0.16, 1, 0.3, 1],
                      }}
                      className="p-4"
                    >
                      <div className="mb-2.5 flex items-center justify-between">
                        <span className="font-mono text-[9.5px] font-semibold tracking-widest text-primary">
                          {feat.code}
                        </span>
                        <div className="flex h-6 w-6 items-center justify-center rounded border border-border bg-muted/60 text-foreground">
                          <Icon className="h-3.5 w-3.5 text-primary" />
                        </div>
                      </div>
                      <div className="font-display text-xs font-bold text-foreground">
                        {feat.title}
                      </div>
                      <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
                        {feat.desc}
                      </p>
                    </motion.div>
                  );
                })}
              </div>

              {/* Sample Grounded Citation Bar */}
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border bg-background/60 px-4 py-2.5 font-mono text-[11px]">
                <span className="text-muted-foreground">
                  GROUNDED CITATION TRACE:
                </span>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge
                    variant="outline"
                    className="gap-1 rounded border-primary/35 bg-primary/10 px-2 py-0.5 font-mono text-[10.5px] text-primary"
                  >
                    <FileCode2 className="h-3 w-3" />
                    <span>ingestion/vector_store.py:L501-L548</span>
                  </Badge>
                  <Badge
                    variant="outline"
                    className="gap-1 rounded border-primary/35 bg-primary/10 px-2 py-0.5 font-mono text-[10.5px] text-primary"
                  >
                    <FileCode2 className="h-3 w-3" />
                    <span>retrieval/reranker.py:L112-L168</span>
                  </Badge>
                </div>
              </div>
            </div>

            <div className="hidden items-center gap-6 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground sm:flex">
              <span className="inline-flex items-center gap-1.5">
                <Lock className="h-3 w-3 text-primary" />
                OAUTH 2.0 PKCE
              </span>
              <span>·</span>
              <span>ZERO PASSWORD STORAGE</span>
              <span>·</span>
              <span>AST-GROUNDED RAG</span>
            </div>
          </motion.div>

          {/* Right Column: Sleek Modern Signup / Signin Card */}
          <motion.div
            initial={{ opacity: 0, y: 18, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.48, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
            className="w-full max-w-[460px] justify-self-center lg:col-span-5 lg: max-w-none"
          >
            <div className="tactile-composer relative overflow-hidden rounded-2xl border border-border bg-card p-7 sm:p-8">
              {/* Top Accent Line */}
              <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary/40 via-primary to-primary/40" />

              {/* Card Telemetry Header + Mode Switcher */}
              <div className="mb-6 flex items-center justify-between gap-2">
                <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">
                  {isSignUp
                    ? "ONBOARDING // NEW OPERATOR"
                    : "ACCESS // OPERATOR"}
                </span>

                <div className="inline-flex rounded-lg border border-border bg-muted/60 p-0.5 font-mono text-[10.5px]">
                  <button
                    type="button"
                    onClick={() => setMode("signup")}
                    className={cn(
                      "rounded-md px-2.5 py-1 font-semibold uppercase tracking-wider transition-all cursor-pointer",
                      isSignUp
                        ? "bg-card text-foreground shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    Sign Up
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("signin")}
                    className={cn(
                      "rounded-md px-2.5 py-1 font-semibold uppercase tracking-wider transition-all cursor-pointer",
                      !isSignUp
                        ? "bg-card text-foreground shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    Sign In
                  </button>
                </div>
              </div>

              {/* Dynamic Title & Subtitle */}
              <div className="mb-6">
                <h2 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                  {isSignUp ? (
                    <>
                      Create your{" "}
                      <span className="font-serif font-normal italic text-primary">
                        workspace.
                      </span>
                    </>
                  ) : (
                    <>
                      Welcome{" "}
                      <span className="font-serif font-normal italic text-primary">
                        back.
                      </span>
                    </>
                  )}
                </h2>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground sm:text-[13px]">
                  {isSignUp
                    ? "Get started in one click with your Google account—no passwords or manual forms required."
                    : "Authenticate with your Google account to resume your mounted repositories and chat sessions."}
                </p>
              </div>

              {/* Error Banner */}
              {authError && (
                <div className="mb-5 flex items-start gap-2.5 rounded-lg border border-destructive/40 bg-destructive/10 p-3 font-mono text-xs text-destructive">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span className="leading-relaxed">{authError}</span>
                </div>
              )}

              {/* Primary Google OAuth Button */}
              <button
                type="button"
                onClick={onGoogleSignIn}
                disabled={isAuthenticating}
                className={cn(
                  "group relative flex w-full items-center justify-between overflow-hidden rounded-xl border border-foreground/15 bg-foreground px-4 py-3.5 text-background shadow-md transition-all duration-200 cursor-pointer",
                  "hover:-translate-y-0.5 hover:shadow-lg active:translate-y-0",
                  "disabled:pointer-events-none disabled:opacity-65"
                )}
              >
                <div className="flex items-center gap-3.5">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white shadow-xs">
                    {isAuthenticating ? (
                      <Loader2 className="h-4 w-4 animate-spin text-stone-900" />
                    ) : (
                      <GoogleLogo className="h-5 w-5" />
                    )}
                  </div>
                  <div className="text-left">
                    <div className="font-display text-sm font-bold tracking-tight">
                      {isAuthenticating
                        ? "Redirecting to Google..."
                        : isSignUp
                        ? "Sign up with Google"
                        : "Continue with Google"}
                    </div>
                    <div className="font-mono text-[10px] uppercase tracking-wider opacity-75">
                      Single Sign-On · OAuth 2.0
                    </div>
                  </div>
                </div>

                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-background/15 transition-transform duration-200 group-hover:translate-x-0.5">
                  <ArrowRight className="h-4 w-4" />
                </div>
              </button>

              {/* Divider with Provider Tag */}
              <div className="my-6 flex items-center gap-3">
                <div className="h-px flex-1 bg-border" />
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  {isSignUp ? "INCLUDED IN WORKSPACE" : "SECURITY PROTOCOL"}
                </span>
                <div className="h-px flex-1 bg-border" />
              </div>

              {/* Workspace Perks / Security Assurances */}
              <div className="space-y-2.5">
                {WORKSPACE_PERKS.map((perk) => (
                  <div
                    key={perk}
                    className="flex items-start gap-2.5 text-xs text-muted-foreground"
                  >
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                    <span>{perk}</span>
                  </div>
                ))}
              </div>

              {/* Passwordless Security Callout */}
              <div className="mt-6 flex items-start gap-3 rounded-xl border border-border bg-muted/40 p-3.5">
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-primary/25 bg-primary/10 text-primary">
                  <ShieldCheck className="h-4 w-4" />
                </div>
                <div className="space-y-0.5">
                  <div className="font-display text-xs font-bold text-foreground">
                    Google-Only Authentication
                  </div>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    Identity is verified directly via Google OAuth 2.0 with PKCE token exchange. We never store or handle passwords.
                  </p>
                </div>
              </div>

              {/* Bottom Mode Toggle Prompt */}
              <div className="mt-6 border-t border-border/80 pt-4 text-center text-xs text-muted-foreground">
                {isSignUp ? (
                  <>
                    Already have an account?{" "}
                    <button
                      type="button"
                      onClick={() => setMode("signin")}
                      className="font-display font-semibold text-primary underline-offset-4 hover:underline cursor-pointer"
                    >
                      Sign in with Google
                    </button>
                  </>
                ) : (
                  <>
                    New to Codebase Copilot?{" "}
                    <button
                      type="button"
                      onClick={() => setMode("signup")}
                      className="font-display font-semibold text-primary underline-offset-4 hover:underline cursor-pointer"
                    >
                      Create an account
                    </button>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        </div>
      </main>
    </div>
  );
}

