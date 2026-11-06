import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Terminal,
  ArrowUpRight,
  ArrowRight,
  GitBranch,
  Layers,
  FileCode2,
  Cpu,
  ShieldCheck,
  Sparkles,
  RefreshCw,
  CheckCircle2,
  Activity,
  Database,
  Network,
  Code2,
  Eye,
  Compass,
  Sun,
  Moon,
  Play,
  Lock,
  Binary,
  Sliders,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

function GoogleLogo({ className = "h-4 w-4" }) {
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

const INTERACTIVE_SCENARIOS = [
  {
    id: "rrf-fusion",
    code: "01 // HYBRID_RRF",
    label: "Hybrid RRF & Reranker",
    repo: "codebase-copilot/core",
    branch: "main",
    latency: "18.4ms",
    query:
      "How does HybridRetriever fuse dense Nemotron embeddings with BM25 scores?",
    summary:
      "HybridRetriever executes parallel dense cosine search (1024-dim Nemotron) and sparse lexical BM25 lookup, merges candidate ranks via Reciprocal Rank Fusion (k=60), and passes top-24 spans to CrossEncoderReranker.",
    metrics: [
      { label: "Dense Vector (1024-d)", score: 94, tag: "COSINE: 0.914" },
      { label: "Sparse Lexical (BM25)", score: 88, tag: "EXACT ID: +14.2" },
      { label: "Cross-Encoder Rerank", score: 99, tag: "FINAL RRF: 0.986" },
    ],
    nodes: [
      { id: "q", label: "QueryRouter", x: 70, y: 55, type: "entry" },
      { id: "v", label: "NemotronEmbed", x: 215, y: 28, type: "vector" },
      { id: "b", label: "BM25Lexical", x: 215, y: 84, type: "lexical" },
      { id: "r", label: "RRF_Fuser(k=60)", x: 375, y: 55, type: "fusion" },
      { id: "c", label: "CrossReranker", x: 520, y: 55, type: "output" },
    ],
    citations: [
      {
        file: "retrieval/hybrid_retriever.py",
        span: "L142-L189",
        symbol: "HybridRetriever.retrieve_fused()",
        snippet: `def retrieve_fused(self, query: str, top_k: int = 8) -> list[CodeSpan]:
    dense_hits = self.vector_store.similarity_search(query, k=32)
    bm25_hits = self.lexical_index.query_identifiers(query, k=32)
    fused = reciprocal_rank_fusion([dense_hits, bm25_hits], k=60)
    return self.reranker.score_and_filter(query, fused[:24], top_k=top_k)`,
      },
      {
        file: "retrieval/reranker.py",
        span: "L64-L108",
        symbol: "CrossEncoderReranker.score_and_filter()",
        snippet: `def score_and_filter(self, query: str, spans: list[CodeSpan], top_k: int):
    pairs = [(query, s.contextualized_ast_body) for s in spans]
    logits = self.model.predict(pairs, batch_size=16)
    return [s for _, s in sorted(zip(logits, spans), reverse=True)[:top_k]]`,
      },
    ],
  },
  {
    id: "ast-graph",
    code: "02 // AST_TOPOLOGY",
    label: "Tree-Sitter Call Graph",
    repo: "codebase-copilot/parser",
    branch: "main",
    latency: "11.2ms",
    query:
      "How are class methods and 1-hop caller/callee edges extracted during AST parsing?",
    summary:
      "ASTSymbolExtractor walks the concrete syntax tree via Tree-sitter queries, binding each method chunk to its parent class signature, docstring, and resolved 1-hop call graph edges before embedding.",
    metrics: [
      { label: "AST Scope Integrity", score: 100, tag: "0 BROKEN FUNCS" },
      { label: "1-Hop Edge Resolution", score: 92, tag: "CALL GRAPH: ON" },
      { label: "Parent Context Header", score: 96, tag: "CLASS+DOCSTRING" },
    ],
    nodes: [
      { id: "q", label: "SourceFile.py", x: 70, y: 55, type: "entry" },
      { id: "v", label: "TreeSitterCST", x: 215, y: 28, type: "vector" },
      { id: "b", label: "ScopeBinder", x: 215, y: 84, type: "lexical" },
      { id: "r", label: "CallGraph1Hop", x: 375, y: 55, type: "fusion" },
      { id: "c", label: "ContextualChunk", x: 520, y: 55, type: "output" },
    ],
    citations: [
      {
        file: "parsing/ast_extractor.py",
        span: "L210-L264",
        symbol: "ASTSymbolExtractor.extract_symbols()",
        snippet: `def extract_symbols(self, tree: Tree, source_bytes: bytes) -> list[SymbolNode]:
    captures = self.query.captures(tree.root_node)
    symbols = self._bind_class_hierarchy(captures, source_bytes)
    return self._attach_one_hop_call_edges(symbols, tree.root_node)`,
      },
      {
        file: "parsing/call_graph.py",
        span: "L88-L134",
        symbol: "CallGraphBuilder.resolve_edges()",
        snippet: `def resolve_edges(self, symbol: SymbolNode, index: SymbolTable) -> EdgeSet:
    callees = [index.lookup(id_tok) for id_tok in symbol.invoked_identifiers]
    return EdgeSet(callers=index.get_callers(symbol.fqn), callees=callees)`,
      },
    ],
  },
  {
    id: "sha-sync",
    code: "03 // DELTA_MERKLE",
    label: "Incremental SHA-256 Sync",
    repo: "codebase-copilot/indexer",
    branch: "main",
    latency: "9.7ms",
    query:
      "What happens during a repository re-index when only a few files changed?",
    summary:
      "IncrementalSyncEngine computes SHA-256 digests for every tracked file in the working tree, diffs against the stored manifest, and atomically swaps vectors only for modified or deleted file hashes.",
    metrics: [
      { label: "Unchanged Cache Hit", score: 98, tag: "1,417 / 1,420 FILES" },
      { label: "Atomic Index Swap", score: 100, tag: "ZERO DOWNTIME" },
      { label: "Delta Compute Time", score: 95, tag: "180ms WALL" },
    ],
    nodes: [
      { id: "q", label: "GitWorktree", x: 70, y: 55, type: "entry" },
      { id: "v", label: "SHA256Manifest", x: 215, y: 28, type: "vector" },
      { id: "b", label: "DeltaDiffSet", x: 215, y: 84, type: "lexical" },
      { id: "r", label: "SelectiveEmbed", x: 375, y: 55, type: "fusion" },
      { id: "c", label: "AtomicCommit", x: 520, y: 55, type: "output" },
    ],
    citations: [
      {
        file: "ingestion/incremental_sync.py",
        span: "L304-L352",
        symbol: "IncrementalSyncEngine.sync_delta()",
        snippet: `def sync_delta(self, repo_id: str, current_hashes: dict[str, str]) -> SyncStats:
    added, modified, deleted = self.manifest.compute_diff(repo_id, current_hashes)
    self.vector_store.delete_by_paths(repo_id, deleted | modified)
    new_chunks = self.parser.parse_files(added | modified)
    return self.vector_store.upsert_atomic(repo_id, new_chunks)`,
      },
      {
        file: "ingestion/manifest_store.py",
        span: "L45-L89",
        symbol: "HashManifest.compute_diff()",
        snippet: `def compute_diff(self, repo_id: str, live: dict[str, str]) -> DiffTuple:
    stored = self.db.fetch_file_hashes(repo_id)
    dirty = {p for p, h in live.items() if stored.get(p) != h}
    return dirty - stored.keys(), dirty & stored.keys(), stored.keys() - live.keys()`,
      },
    ],
  },
];

const PIPELINE_STAGES = [
  {
    idx: "01",
    code: "STAGE_01 // AST_DECOMPOSE",
    title: "Tree-Sitter Symbol Graph",
    subtitle: "Syntactic boundary preservation",
    icon: Layers,
    spec: "PY · TS · JS · TSX",
    detail:
      "Never slices a function in half. Extracts complete classes, methods, type signatures, docstrings, and 1-hop caller/callee edges into self-contained architectural units.",
  },
  {
    idx: "02",
    code: "STAGE_02 // DUAL_INDEX",
    title: "1024-Dim + BM25 Lexical",
    subtitle: "Semantic & exact-token encoding",
    icon: Database,
    spec: "NEMOTRON + BM25",
    detail:
      "Pairs deep semantic embeddings for conceptual queries with high-precision BM25 lexical inverted indices so exact camelCase or snake_case symbol names never miss.",
  },
  {
    idx: "03",
    code: "STAGE_03 // RRF_RERANK",
    title: "Reciprocal Rank + Cross-Encoder",
    subtitle: "Multi-stage mathematical fusion",
    icon: Sliders,
    spec: "RRF (k=60) + LOGITS",
    detail:
      "Merges dense and sparse retrieval rankings via Reciprocal Rank Fusion, then scores every candidate code span jointly against your prompt with a Cross-Encoder.",
  },
  {
    idx: "04",
    code: "STAGE_04 // PROOF_SYNTHESIS",
    title: "Line-Accurate Citations",
    subtitle: "Verifiable architectural truth",
    icon: FileCode2,
    spec: "FILE // LSTART-LEND",
    detail:
      "Streams architectural answers anchored to clickable source citations. Every claim links directly to the exact file path and line range that proved it.",
  },
];

const INITIAL_SYNC_FILES = [
  { path: "src/retrieval/hybrid_retriever.py", hash: "8f4a9c2e", lines: 342, status: "CACHED" },
  { path: "src/parsing/ast_extractor.py", hash: "3b7d1e09", lines: 518, status: "CACHED" },
  { path: "src/ingestion/vector_store.py", hash: "c91e44a1", lines: 612, status: "CACHED" },
  { path: "src/retrieval/reranker.py", hash: "7d2b08f4", lines: 194, status: "CACHED" },
  { path: "src/api/chat_stream.py", hash: "1a9f55c3", lines: 288, status: "CACHED" },
];

const MUTATED_SYNC_FILES = [
  { path: "src/retrieval/hybrid_retriever.py", hash: "e29b71d0", lines: 356, status: "RE-INDEXED (62ms)" },
  { path: "src/parsing/ast_extractor.py", hash: "3b7d1e09", lines: 518, status: "SHA-256 HIT (0ms)" },
  { path: "src/ingestion/vector_store.py", hash: "f04c88b2", lines: 629, status: "RE-INDEXED (78ms)" },
  { path: "src/retrieval/reranker.py", hash: "7d2b08f4", lines: 194, status: "SHA-256 HIT (0ms)" },
  { path: "src/api/chat_stream.py", hash: "9d3e12a7", lines: 301, status: "RE-INDEXED (41ms)" },
];

export default function LandingPage({
  user,
  onEnterWorkspace,
  onGoogleSignIn,
  isAuthenticating,
  authError,
}) {
  // Landing page exclusive atmosphere mode: "day" (Sunlit Glacial Aero) vs "night" (Abyssal Bio-Night)
  const [aeroMode, setAeroMode] = useState("day");
  const isDay = aeroMode === "day";

  // Interactive Hero Sandbox state
  const [activeScenarioIdx, setActiveScenarioIdx] = useState(0);
  const [activeCiteIdx, setActiveCiteIdx] = useState(0);
  const [inspectorTab, setInspectorTab] = useState("synthesis"); // "synthesis" | "topology"
  const [chunkComparisonMode, setChunkComparisonMode] = useState("ast"); // "ast" | "naive"
  const [syncSimulated, setSyncSimulated] = useState(false);
  const [coords, setCoords] = useState({ x: 640, y: 320 });

  const scenario = INTERACTIVE_SCENARIOS[activeScenarioIdx];
  const activeCitation = scenario.citations[activeCiteIdx] || scenario.citations[0];
  const syncFiles = syncSimulated ? MUTATED_SYNC_FILES : INITIAL_SYNC_FILES;

  useEffect(() => {
    setActiveCiteIdx(0);
  }, [activeScenarioIdx]);

  const handleMouseMove = (e) => {
    setCoords({
      x: Math.round(e.clientX),
      y: Math.round(e.clientY),
    });
  };

  const scrollToSection = (id) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <div
      onMouseMove={handleMouseMove}
      className={cn(
        "aero-utilitarian-shell relative h-screen w-screen overflow-y-auto overflow-x-hidden select-none transition-colors duration-500",
        isDay ? "aero-canvas-day" : "aero-canvas-night"
      )}
    >
      {/* ====================================================================
          ATMOSPHERIC FRUTIGER AERO HORIZON + UTILITARIAN CAD GRID BACKDROP
          ==================================================================== */}
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none fixed inset-0 z-0",
          isDay ? "aero-cad-grid-day" : "aero-cad-grid-night"
        )}
      >
        {/* Sweeping Frutiger Aero Translucent Vector Aurora Ribbons */}
        <svg
          className="absolute inset-x-0 top-0 h-[620px] w-full opacity-75"
          viewBox="0 0 1440 620"
          fill="none"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="aeroRibbon1" x1="0%" y1="0%" x2="100%" y2="20%">
              <stop
                offset="0%"
                stopColor={isDay ? "#00b4ff" : "#00d4ff"}
                stopOpacity={isDay ? "0.26" : "0.18"}
              />
              <stop
                offset="50%"
                stopColor={isDay ? "#00e5a3" : "#00ffb2"}
                stopOpacity={isDay ? "0.22" : "0.14"}
              />
              <stop
                offset="100%"
                stopColor="#0284c7"
                stopOpacity="0.04"
              />
            </linearGradient>
            <linearGradient id="aeroRibbon2" x1="100%" y1="0%" x2="0%" y2="100%">
              <stop
                offset="0%"
                stopColor="#38bdf8"
                stopOpacity={isDay ? "0.32" : "0.2"}
              />
              <stop
                offset="60%"
                stopColor="#10b981"
                stopOpacity={isDay ? "0.16" : "0.1"}
              />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M-120 140 C 320 -40, 740 340, 1560 80 L 1560 420 C 980 560, 420 180, -120 390 Z"
            fill="url(#aeroRibbon1)"
          />
          <path
            d="M-80 280 C 480 460, 920 20, 1520 240 L 1520 520 C 860 320, 380 590, -80 460 Z"
            fill="url(#aeroRibbon2)"
          />
          {/* Crisp Optical Vector Wave Hairline */}
          <path
            d="M-100 210 C 380 10, 820 380, 1540 120"
            stroke={isDay ? "rgba(2, 132, 199, 0.28)" : "rgba(0, 212, 255, 0.3)"}
            strokeWidth="1.2"
            strokeDasharray="6 6"
          />
        </svg>

        {/* Floating 3D Refractive Hydro-Spheres (Frutiger Aero Signature) */}
        <div className="aero-hydro-orb aero-float absolute -top-12 right-[8%] h-44 w-44 opacity-60 blur-[0.5px]" />
        <div className="aero-hydro-orb aero-float-delayed absolute top-[440px] left-[4%] h-24 w-24 opacity-50" />
      </div>

      {/* ====================================================================
          TOP UTILITARIAN + AERO GLASS TELEMETRY TASKBAR
          ==================================================================== */}
      <header
        className={cn(
          "sticky top-0 z-40 border-b backdrop-blur-xl transition-colors",
          isDay
            ? "border-sky-700/20 bg-white/75"
            : "border-cyan-400/20 bg-[#041122]/80"
        )}
      >
        {/* Ultra-thin Top Hardware Ruler / Coordinate Strip */}
        <div
          className={cn(
            "hidden h-6 items-center justify-between border-b px-6 font-mono text-[10px] tracking-[0.16em] uppercase sm:flex",
            isDay
              ? "border-sky-700/15 bg-sky-500/8 text-sky-900/75"
              : "border-cyan-400/15 bg-cyan-950/40 text-cyan-200/75"
          )}
        >
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1.5 font-semibold">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_#10b981]" />
              SYS.AERO // HYDRO-OPTICAL RAG v2.4
            </span>
            <span className="opacity-40">|</span>
            <span>REFRACTION INDEX: n = 1.333</span>
            <span className="hidden opacity-40 md:inline">|</span>
            <span className="hidden md:inline">
              AST PARSER: TREE-SITTER [PY/TS/JS]
            </span>
          </div>

          <div className="flex items-center gap-4">
            <span>
              CURSOR // X:{String(coords.x).padStart(4, "0")} Y:
              {String(coords.y).padStart(4, "0")}
            </span>
            <span className="opacity-40">|</span>
            <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
              STATUS: NOMINAL
            </span>
          </div>
        </div>

        {/* Main Navigation Bar */}
        <div className="mx-auto flex h-16 max-w-[1340px] items-center justify-between gap-4 px-5 sm:px-8">
          {/* Brand Identity */}
          <div className="flex items-center gap-3">
            <div className="aero-gel-cta flex h-10 w-10 items-center justify-center rounded-xl shadow-md">
              <Terminal className="relative z-10 h-5 w-5 text-white" strokeWidth={2.3} />
            </div>
            <div>
              <div className="flex items-baseline gap-1.5">
                <span className="font-display text-lg font-bold tracking-tight">
                  Codebase
                </span>
                <span
                  className={cn(
                    "font-serif text-xl italic",
                    isDay ? "text-sky-600" : "text-cyan-300"
                  )}
                >
                  Copilot
                </span>
                <span
                  className={cn(
                    "ml-1 rounded border px-1.5 py-0.5 font-mono text-[9.5px] font-semibold uppercase tracking-widest",
                    isDay
                      ? "border-sky-600/30 bg-sky-500/10 text-sky-800"
                      : "border-cyan-400/30 bg-cyan-400/10 text-cyan-200"
                  )}
                >
                  AERO.OS
                </span>
              </div>
              <div
                className={cn(
                  "font-mono text-[9.5px] tracking-widest uppercase",
                  isDay ? "text-slate-500" : "text-cyan-200/60"
                )}
              >
                UTILITARIAN CODE INTELLIGENCE
              </div>
            </div>
          </div>

          {/* Center Utilitarian Section Jump Tabs */}
          <nav
            aria-label="Landing sections"
            className={cn(
              "hidden items-center gap-1 rounded-full border p-1 font-mono text-[10.5px] lg:flex",
              isDay
                ? "border-sky-700/20 bg-sky-100/65 text-slate-700"
                : "border-cyan-400/20 bg-cyan-950/50 text-cyan-100"
            )}
          >
            {[
              { id: "hero-sandbox", label: "01 // SANDBOX" },
              { id: "pipeline-matrix", label: "02 // PIPELINE" },
              { id: "chunk-comparator", label: "03 // AST VS NAIVE" },
              { id: "merkle-sync", label: "04 // SHA-256 SYNC" },
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => scrollToSection(item.id)}
                className={cn(
                  "rounded-full px-3 py-1 font-semibold uppercase tracking-wider transition-all cursor-pointer",
                  isDay
                    ? "hover:bg-white hover:text-sky-700 hover:shadow-xs"
                    : "hover:bg-cyan-400/15 hover:text-cyan-200"
                )}
              >
                {item.label}
              </button>
            ))}
          </nav>

          {/* Right Controls: Atmosphere Toggle + Workspace Launch */}
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setAeroMode((m) => (m === "day" ? "night" : "day"))}
              className={cn(
                "inline-flex h-9 items-center gap-2 rounded-full px-3.5 font-mono text-[10.5px] font-semibold uppercase tracking-wider cursor-pointer",
                isDay ? "aero-acrylic-btn-day" : "aero-acrylic-btn-night"
              )}
              title="Switch atmospheric refraction mode"
            >
              {isDay ? (
                <>
                  <Moon className="h-3.5 w-3.5 text-sky-600" />
                  <span className="hidden sm:inline">Abyssal Night</span>
                </>
              ) : (
                <>
                  <Sun className="h-3.5 w-3.5 text-cyan-300" />
                  <span className="hidden sm:inline">Aero Daylight</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={onEnterWorkspace}
              className="aero-gel-cta inline-flex h-9 items-center gap-2 rounded-full px-4 font-mono text-[11px] font-semibold uppercase tracking-wider cursor-pointer"
            >
              <span className="relative z-10">
                {user ? "Open Workspace" : "Workspace Console"}
              </span>
              <ArrowUpRight className="relative z-10 h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* ====================================================================
          MAIN CONTENT CONTAINER
          ==================================================================== */}
      <main className="relative z-10 mx-auto max-w-[1340px] px-5 pt-8 pb-24 sm:px-8 sm:pt-12">
        {/* Auth Error Alert if present */}
        {authError && (
          <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 font-mono text-xs text-red-600 dark:text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{authError}</span>
          </div>
        )}

        {/* ==================================================================
            01 // HERO SECTION: ASYMMETRIC UTILITARIAN + AERO GLASS INSTRUMENT
            ================================================================== */}
        <section
          id="hero-sandbox"
          className="grid grid-cols-1 items-start gap-10 lg:grid-cols-12 lg:gap-8"
        >
          {/* Left Column (5 Cols): Architectural Manifesto & Hardware Spec Table */}
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col justify-between lg:col-span-5"
          >
            {/* Refractive Status Pill */}
            <div className="mb-5 flex flex-wrap items-center gap-2">
              <div
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border px-3.5 py-1 font-mono text-[10.5px] font-semibold uppercase tracking-[0.15em] shadow-xs",
                  isDay
                    ? "border-sky-500/35 bg-white/80 text-sky-800"
                    : "border-cyan-400/35 bg-cyan-950/60 text-cyan-200"
                )}
              >
                <Sparkles className="h-3 w-3 text-emerald-500" />
                <span>HYDRO-OPTICAL AST ENGINE // REV 2.4</span>
              </div>
              {user && (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-emerald-700 dark:text-emerald-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  SESSION: {user.name}
                </span>
              )}
            </div>

            {/* Hero Display Headline */}
            <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl lg:text-[50px] lg:leading-[1.06]">
              X-ray any repository with{" "}
              <span
                className={cn(
                  "font-serif font-normal italic",
                  isDay ? "text-sky-600" : "text-cyan-300"
                )}
              >
                crystalline
              </span>{" "}
              <span
                className={cn(
                  "underline decoration-1 underline-offset-8",
                  isDay ? "decoration-emerald-500/60" : "decoration-emerald-400/60"
                )}
              >
                precision.
              </span>
            </h1>

            <p
              className={cn(
                "mt-5 text-[15px] leading-relaxed",
                isDay ? "text-slate-600" : "text-cyan-100/75"
              )}
            >
              Generic RAG chops source files into blind character windows.{" "}
              <strong className={isDay ? "text-slate-900" : "text-white"}>
                Codebase Copilot
              </strong>{" "}
              extracts complete{" "}
              <span className="font-mono text-xs font-semibold">
                Tree-sitter AST symbol graphs
              </span>
              , fuses 1024-dim semantic vectors with exact BM25 identifiers, and
              grounds every architectural answer in verifiable{" "}
              <span
                className={cn(
                  "rounded border px-1.5 py-0.5 font-mono text-xs font-medium",
                  isDay
                    ? "border-sky-500/30 bg-sky-500/10 text-sky-800"
                    : "border-cyan-400/30 bg-cyan-400/10 text-cyan-200"
                )}
              >
                {"[file:Lstart-Lend]"}
              </span>{" "}
              citations.
            </p>

            {/* Primary & Secondary Tactile Aero CTAs */}
            <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
              {user ? (
                <button
                  type="button"
                  onClick={onEnterWorkspace}
                  className="aero-gel-cta group inline-flex items-center justify-between gap-4 rounded-2xl px-6 py-4 text-left cursor-pointer"
                >
                  <div className="relative z-10">
                    <div className="font-display text-sm font-bold tracking-tight text-white">
                      Launch Active Workspace
                    </div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-sky-100">
                      Operator: {user.email || user.name}
                    </div>
                  </div>
                  <div className="relative z-10 flex h-8 w-8 items-center justify-center rounded-xl bg-white/20 transition-transform group-hover:translate-x-0.5">
                    <ArrowRight className="h-4 w-4 text-white" />
                  </div>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onGoogleSignIn}
                  disabled={isAuthenticating}
                  className="aero-gel-cta group inline-flex items-center justify-between gap-4 rounded-2xl px-5 py-3.5 text-left cursor-pointer disabled:opacity-60"
                >
                  <div className="relative z-10 flex items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm">
                      {isAuthenticating ? (
                        <Loader2 className="h-4 w-4 animate-spin text-sky-700" />
                      ) : (
                        <GoogleLogo className="h-5 w-5" />
                      )}
                    </div>
                    <div>
                      <div className="font-display text-sm font-bold tracking-tight text-white">
                        {isAuthenticating
                          ? "Connecting OAuth..."
                          : "Initialize with Google"}
                      </div>
                      <div className="font-mono text-[10px] uppercase tracking-wider text-sky-100/90">
                        OAuth 2.0 PKCE · Instant Mount
                      </div>
                    </div>
                  </div>
                  <div className="relative z-10 flex h-7 w-7 items-center justify-center rounded-lg bg-white/20 transition-transform group-hover:translate-x-0.5">
                    <ArrowRight className="h-4 w-4 text-white" />
                  </div>
                </button>
              )}

              <button
                type="button"
                onClick={onEnterWorkspace}
                className={cn(
                  "inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3.5 font-mono text-xs font-semibold uppercase tracking-wider cursor-pointer",
                  isDay ? "aero-acrylic-btn-day" : "aero-acrylic-btn-night"
                )}
              >
                <Terminal className="h-4 w-4 text-sky-600 dark:text-cyan-300" />
                <span>{user ? "Mount Repo" : "Workspace Gateway"}</span>
              </button>
            </div>

            {/* Exposed Utilitarian 4-Cell Spec Matrix */}
            <div
              className={cn(
                "mt-8 overflow-hidden rounded-2xl border",
                isDay
                  ? "aero-glass-panel-day border-sky-700/20"
                  : "aero-glass-panel-night border-cyan-400/20"
              )}
            >
              <div
                className={cn(
                  "flex items-center justify-between border-b px-4 py-2 font-mono text-[10px] uppercase tracking-widest",
                  isDay
                    ? "border-sky-700/15 bg-sky-500/8 text-sky-900/75"
                    : "border-cyan-400/15 bg-cyan-950/50 text-cyan-200/75"
                )}
              >
                <span>HARDWARE SPECIFICATION // TELEMETRY</span>
                <span>4X4 MATRIX</span>
              </div>

              <div
                className={cn(
                  "grid grid-cols-2 divide-x divide-y",
                  isDay
                    ? "divide-sky-700/15"
                    : "divide-cyan-400/15"
                )}
              >
                {[
                  {
                    id: "SPEC.01",
                    label: "AST SYMBOL GRAPH",
                    val: "Tree-Sitter CST",
                    sub: "1-Hop Call Edges",
                  },
                  {
                    id: "SPEC.02",
                    label: "VECTOR DIMENSION",
                    val: "1024-D Nemotron",
                    sub: "+ Sparse BM25",
                  },
                  {
                    id: "SPEC.03",
                    label: "RANK FUSION",
                    val: "RRF (k=60)",
                    sub: "+ Cross-Encoder",
                  },
                  {
                    id: "SPEC.04",
                    label: "DELTA INDEXING",
                    val: "SHA-256 Merkle",
                    sub: "Zero-Downtime Swap",
                  },
                ].map((spec) => (
                  <div key={spec.id} className="p-3.5">
                    <div className="flex items-center justify-between font-mono text-[9.5px] uppercase tracking-widest opacity-60">
                      <span>{spec.id}</span>
                      <span>+</span>
                    </div>
                    <div className="mt-1 font-display text-sm font-bold tracking-tight">
                      {spec.val}
                    </div>
                    <div
                      className={cn(
                        "mt-0.5 font-mono text-[10.5px]",
                        isDay ? "text-sky-700" : "text-cyan-300"
                      )}
                    >
                      {spec.label} · {spec.sub}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Right Column (7 Cols): Interactive Aero-Glass Live Codebase Interrogator */}
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
            className="relative lg:col-span-7"
          >
            {/* Floating Optical Lens Badge */}
            <div
              className={cn(
                "hidden sm:flex absolute -top-4 right-6 z-20 items-center gap-2 rounded-full border px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-widest shadow-md backdrop-blur-md",
                isDay
                  ? "border-white bg-gradient-to-r from-sky-500/90 to-emerald-500/90 text-white"
                  : "border-cyan-300/40 bg-gradient-to-r from-cyan-500/90 to-emerald-500/90 text-slate-950"
              )}
            >
              <Activity className="h-3 w-3 animate-pulse" />
              <span>INTERACTIVE SANDBOX // CLICK PRESETS BELOW</span>
            </div>

            <div
              className={cn(
                "overflow-hidden rounded-2xl",
                isDay ? "aero-glass-panel-day" : "aero-glass-panel-night"
              )}
            >
              {/* Glossy Longhorn / Aqua Window Titlebar */}
              <div
                className={cn(
                  "flex flex-wrap items-center justify-between gap-2 px-4 py-3",
                  isDay ? "aero-titlebar-day" : "aero-titlebar-night"
                )}
              >
                <div className="flex items-center gap-3">
                  {/* Hydro-Gel Window Control Dots (Cyan / Emerald / Cobalt — Zero Orange!) */}
                  <div className="flex items-center gap-1.5">
                    <span className="h-3 w-3 rounded-full border border-white/60 bg-gradient-to-b from-sky-300 to-sky-600 shadow-inner" />
                    <span className="h-3 w-3 rounded-full border border-white/60 bg-gradient-to-b from-emerald-300 to-emerald-600 shadow-inner" />
                    <span className="h-3 w-3 rounded-full border border-white/60 bg-gradient-to-b from-cyan-200 to-blue-700 shadow-inner" />
                  </div>
                  <div className="font-mono text-[11px] font-semibold tracking-wider uppercase">
                    WIN_0x7F // AST_HYDRO_INTERROGATOR.EXE
                  </div>
                </div>

                <div className="flex items-center gap-2 font-mono text-[10px]">
                  <span
                    className={cn(
                      "rounded border px-2 py-0.5 font-semibold",
                      isDay
                        ? "border-sky-600/30 bg-white/70 text-sky-800"
                        : "border-cyan-400/30 bg-cyan-950/80 text-cyan-200"
                    )}
                  >
                    LATENCY: {scenario.latency}
                  </span>
                  <span
                    className={cn(
                      "hidden rounded border px-2 py-0.5 sm:inline-block",
                      isDay
                        ? "border-emerald-600/30 bg-emerald-500/10 text-emerald-800"
                        : "border-emerald-400/30 bg-emerald-500/15 text-emerald-300"
                    )}
                  >
                    CITATIONS: VERIFIED
                  </span>
                </div>
              </div>

              {/* Scenario Preset Switcher Bar */}
              <div
                className={cn(
                  "grid grid-cols-1 divide-y border-b sm:grid-cols-3 sm:divide-x sm:divide-y-0",
                  isDay
                    ? "divide-sky-700/15 border-sky-700/20 bg-sky-50/50"
                    : "divide-cyan-400/15 border-cyan-400/20 bg-[#051529]/70"
                )}
              >
                {INTERACTIVE_SCENARIOS.map((item, idx) => {
                  const active = idx === activeScenarioIdx;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setActiveScenarioIdx(idx)}
                      className={cn(
                        "relative flex flex-col items-start p-3 text-left transition-all cursor-pointer",
                        active
                          ? isDay
                            ? "bg-white/95 shadow-inner"
                            : "bg-cyan-500/15"
                          : "opacity-70 hover:opacity-100"
                      )}
                    >
                      {active && (
                        <motion.div
                          layoutId="aero-scenario-bar"
                          className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-sky-500 via-cyan-400 to-emerald-400"
                        />
                      )}
                      <span
                        className={cn(
                          "font-mono text-[9.5px] font-semibold uppercase tracking-widest",
                          active
                            ? isDay
                              ? "text-sky-600"
                              : "text-cyan-300"
                            : "opacity-70"
                        )}
                      >
                        {item.code}
                      </span>
                      <span className="mt-0.5 font-display text-xs font-bold">
                        {item.label}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Active Query Prompt Bar */}
              <div
                className={cn(
                  "flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3",
                  isDay
                    ? "border-sky-700/15 bg-white/50"
                    : "border-cyan-400/15 bg-slate-950/40"
                )}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="rounded bg-gradient-to-r from-sky-500 to-emerald-500 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-white">
                    PROMPT
                  </span>
                  <span className="truncate font-mono text-xs font-medium">
                    &ldquo;{scenario.query}&rdquo;
                  </span>
                </div>

                {/* Sub-mode toggle: Synthesis vs Node Graph */}
                <div
                  className={cn(
                    "inline-flex rounded-lg border p-0.5 font-mono text-[10px]",
                    isDay
                      ? "border-sky-700/20 bg-sky-100/70"
                      : "border-cyan-400/25 bg-cyan-950/60"
                  )}
                >
                  <button
                    type="button"
                    onClick={() => setInspectorTab("synthesis")}
                    className={cn(
                      "rounded-md px-2.5 py-1 font-semibold uppercase transition-all cursor-pointer",
                      inspectorTab === "synthesis"
                        ? isDay
                          ? "bg-white text-sky-800 shadow-xs"
                          : "bg-cyan-400/20 text-cyan-100"
                        : "opacity-65 hover:opacity-100"
                    )}
                  >
                    Synthesis + Proof
                  </button>
                  <button
                    type="button"
                    onClick={() => setInspectorTab("topology")}
                    className={cn(
                      "rounded-md px-2.5 py-1 font-semibold uppercase transition-all cursor-pointer",
                      inspectorTab === "topology"
                        ? isDay
                          ? "bg-white text-sky-800 shadow-xs"
                          : "bg-cyan-400/20 text-cyan-100"
                        : "opacity-65 hover:opacity-100"
                    )}
                  >
                    AST + RRF Telemetry
                  </button>
                </div>
              </div>

              {/* Main Interactive Viewport inside the Aero Window */}
              <div className="p-4 sm:p-5">
                <AnimatePresence mode="wait">
                  {inspectorTab === "synthesis" ? (
                    <motion.div
                      key={`${scenario.id}-synthesis`}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.22 }}
                      className="space-y-4"
                    >
                      {/* Synthesized Architectural Response */}
                      <div
                        className={cn(
                          "rounded-xl border p-4",
                          isDay
                            ? "border-sky-600/20 bg-white/75"
                            : "border-cyan-400/20 bg-[#041224]/80"
                        )}
                      >
                        <div className="mb-2 flex items-center justify-between font-mono text-[10px] uppercase tracking-wider opacity-70">
                          <span className="inline-flex items-center gap-1.5">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                            ARCHITECTURAL SYNTHESIS // GROUNDED
                          </span>
                          <span>REPO: {scenario.repo}</span>
                        </div>
                        <p className="text-xs sm:text-[13.5px] leading-relaxed">
                          {scenario.summary}
                        </p>

                        {/* Clickable Citation Pills */}
                        <div className="mt-3.5 flex flex-wrap items-center gap-2 border-t border-sky-500/15 pt-3">
                          <span className="font-mono text-[10px] uppercase tracking-wider opacity-65">
                            INSPECT SOURCE CITATION:
                          </span>
                          {scenario.citations.map((cite, cIdx) => {
                            const isSelectedCite = cIdx === activeCiteIdx;
                            return (
                              <button
                                key={cite.file}
                                type="button"
                                onClick={() => setActiveCiteIdx(cIdx)}
                                className={cn(
                                  "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 font-mono text-[11px] font-medium transition-all cursor-pointer",
                                  isSelectedCite
                                    ? "border-sky-500 bg-gradient-to-r from-sky-500 to-emerald-500 text-white shadow-sm"
                                    : isDay
                                    ? "border-sky-600/25 bg-sky-50 text-sky-900 hover:border-sky-500"
                                    : "border-cyan-400/25 bg-cyan-950/50 text-cyan-200 hover:border-cyan-400"
                                )}
                              >
                                <FileCode2 className="h-3 w-3" />
                                <span>
                                  {cite.file}:{cite.span}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* Live Source Code Span Inspector Drawer */}
                      <div
                        className={cn(
                          "overflow-hidden rounded-xl border font-mono text-xs",
                          isDay
                            ? "border-slate-800 bg-[#071526] text-sky-100"
                            : "border-cyan-400/30 bg-[#020913] text-cyan-100"
                        )}
                      >
                        <div className="flex items-center justify-between border-b border-sky-400/20 bg-sky-950/60 px-3.5 py-2 text-[10.5px]">
                          <div className="flex items-center gap-2">
                            <Code2 className="h-3.5 w-3.5 text-emerald-400" />
                            <span className="font-semibold text-white">
                              {activeCitation.file}
                            </span>
                            <span className="rounded bg-emerald-500/20 px-1.5 py-0.2 text-[10px] text-emerald-300">
                              {activeCitation.span}
                            </span>
                          </div>
                          <span className="text-sky-300/75 truncate max-w-[200px]">
                            SYMBOL: {activeCitation.symbol}
                          </span>
                        </div>
                        <pre className="overflow-x-auto p-3.5 text-[11.5px] leading-relaxed text-sky-100/95">
                          <code>{activeCitation.snippet}</code>
                        </pre>
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div
                      key={`${scenario.id}-topology`}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.22 }}
                      className="space-y-4"
                    >
                      {/* Interactive SVG AST & Retrieval Node Topology */}
                      <div
                        className={cn(
                          "overflow-hidden rounded-xl border p-3.5",
                          isDay
                            ? "border-sky-600/20 bg-[#07182c] text-white"
                            : "border-cyan-400/25 bg-[#020a14] text-white"
                        )}
                      >
                        <div className="mb-2 flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-cyan-300/80">
                          <span>EXECUTION TOPOLOGY // 1-HOP SYMBOL GRAPH</span>
                          <span>NODES: 05 · EDGES: 05</span>
                        </div>
                        <svg
                          viewBox="0 0 600 115"
                          className="h-28 w-full overflow-visible"
                        >
                          <defs>
                            <linearGradient
                              id="edgeGrad"
                              x1="0%"
                              y1="0%"
                              x2="100%"
                              y2="0%"
                            >
                              <stop offset="0%" stopColor="#38bdf8" />
                              <stop offset="100%" stopColor="#10b981" />
                            </linearGradient>
                          </defs>
                          {/* Directed Graph Edges */}
                          <path
                            d="M 115 55 L 170 28 M 115 55 L 170 84 M 265 28 L 325 55 M 265 84 L 325 55 M 425 55 L 472 55"
                            stroke="url(#edgeGrad)"
                            strokeWidth="2"
                            strokeDasharray="4 3"
                            fill="none"
                          />
                          {scenario.nodes.map((node) => (
                            <g
                              key={node.id}
                              transform={`translate(${node.x}, ${node.y})`}
                            >
                              <rect
                                x="-48"
                                y="-16"
                                width="96"
                                height="32"
                                rx="8"
                                fill="rgba(6, 28, 52, 0.92)"
                                stroke={
                                  node.type === "output"
                                    ? "#10b981"
                                    : "#38bdf8"
                                }
                                strokeWidth="1.5"
                              />
                              <text
                                textAnchor="middle"
                                dy="4"
                                fill="#e0f2fe"
                                fontSize="9.5"
                                fontFamily="Azeret Mono, monospace"
                                fontWeight="600"
                              >
                                {node.label}
                              </text>
                            </g>
                          ))}
                        </svg>
                      </div>

                      {/* Liquid-Glass Telemetry Tubes (Dense vs BM25 vs Reranker) */}
                      <div
                        className={cn(
                          "rounded-xl border p-4 space-y-3",
                          isDay
                            ? "border-sky-600/20 bg-white/80"
                            : "border-cyan-400/20 bg-slate-950/60"
                        )}
                      >
                        <div className="font-mono text-[10px] font-semibold uppercase tracking-widest opacity-70">
                          HYBRID RETRIEVAL SCORE TELEMETRY
                        </div>
                        {scenario.metrics.map((m) => (
                          <div key={m.label} className="space-y-1">
                            <div className="flex items-center justify-between font-mono text-[11px]">
                              <span className="font-semibold">{m.label}</span>
                              <span
                                className={cn(
                                  "rounded px-1.5 py-0.2 text-[10px] font-bold",
                                  isDay
                                    ? "bg-sky-500/12 text-sky-800"
                                    : "bg-cyan-400/15 text-cyan-200"
                                )}
                              >
                                {m.tag} ({m.score}%)
                              </span>
                            </div>
                            <div
                              className={cn(
                                "h-2.5 w-full overflow-hidden rounded-full border p-0.5",
                                isDay
                                  ? "border-sky-600/25 bg-sky-100"
                                  : "border-cyan-400/25 bg-cyan-950"
                              )}
                            >
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${m.score}%` }}
                                transition={{ duration: 0.55, ease: "easeOut" }}
                                className="h-full rounded-full bg-gradient-to-r from-sky-500 via-cyan-400 to-emerald-400 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Window Bottom Status Bar */}
              <div
                className={cn(
                  "flex flex-wrap items-center justify-between gap-2 border-t px-4 py-2.5 font-mono text-[10px]",
                  isDay
                    ? "border-sky-700/15 bg-sky-50/75 text-slate-600"
                    : "border-cyan-400/15 bg-[#030e1c] text-cyan-200/70"
                )}
              >
                <span>STREAM_PROTOCOL: SSE // CHUNKED_TOKENS</span>
                <span>0 HALLUCINATED PATHS // 100% AST-GROUNDED</span>
              </div>
            </div>
          </motion.div>
        </section>

        {/* ==================================================================
            UTILITARIAN TELEMETRY SLIPSTREAM RIBBON
            ================================================================== */}
        <div
          className={cn(
            "my-14 flex flex-wrap items-center justify-between gap-4 rounded-xl border px-5 py-3 font-mono text-[11px] uppercase tracking-widest",
            isDay
              ? "border-sky-700/20 bg-white/65 text-sky-950 shadow-xs"
              : "border-cyan-400/20 bg-cyan-950/35 text-cyan-100"
          )}
        >
          <div className="flex items-center gap-3">
            <Binary className="h-4 w-4 text-sky-500" />
            <span className="font-semibold">
              OPTICAL TELEMETRY BUS // RRF FORMULA:
            </span>
            <span
              className={cn(
                "rounded border px-2 py-0.5 font-mono text-[10.5px]",
                isDay
                  ? "border-sky-600/25 bg-sky-500/10 text-sky-800"
                  : "border-cyan-400/25 bg-cyan-400/10 text-cyan-200"
              )}
            >
              SCORE(d) = Σ 1 / (60 + rank_i(d))
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-[10.5px] opacity-80">
            <span>LOCAL + GITHUB REPOS</span>
            <span>·</span>
            <span>MULTI-TURN THREAD ARCHIVE</span>
            <span>·</span>
            <span>OAUTH 2.0 PKCE</span>
          </div>
        </div>

        {/* ==================================================================
            02 // 4-STAGE HYDRO-OPTICAL RAG PIPELINE MATRIX
            ================================================================== */}
        <section id="pipeline-matrix" className="scroll-mt-24">
          <div className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <div
                className={cn(
                  "mb-2 inline-flex items-center gap-2 font-mono text-[10.5px] font-semibold uppercase tracking-[0.18em]",
                  isDay ? "text-sky-700" : "text-cyan-300"
                )}
              >
                <span>02 // ARCHITECTURAL PIPELINE SCHEMATIC</span>
              </div>
              <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
                Four stages of{" "}
                <span
                  className={cn(
                    "font-serif font-normal italic",
                    isDay ? "text-sky-600" : "text-cyan-300"
                  )}
                >
                  hydro-optical
                </span>{" "}
                retrieval.
              </h2>
            </div>
            <p
              className={cn(
                "max-w-md text-xs sm:text-sm leading-relaxed",
                isDay ? "text-slate-600" : "text-cyan-100/70"
              )}
            >
              Every repository query passes through a deterministic 4-stage
              instrument pipeline designed to eliminate broken syntax blocks and
              unverified guesses.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PIPELINE_STAGES.map((stage, idx) => {
              const Icon = stage.icon;
              return (
                <motion.div
                  key={stage.idx}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.2 }}
                  transition={{ duration: 0.38, delay: idx * 0.06 }}
                  className={cn(
                    "group relative flex flex-col justify-between overflow-hidden rounded-2xl p-5 transition-all hover:-translate-y-1",
                    isDay ? "aero-glass-panel-day" : "aero-glass-panel-night"
                  )}
                >
                  {/* Top Specular Highlight Bar */}
                  <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-sky-400 via-cyan-300 to-emerald-400 opacity-75 group-hover:opacity-100" />

                  <div>
                    {/* Stage Utilitarian Header */}
                    <div className="mb-4 flex items-center justify-between">
                      <span
                        className={cn(
                          "font-mono text-[10px] font-bold uppercase tracking-widest",
                          isDay ? "text-sky-700" : "text-cyan-300"
                        )}
                      >
                        {stage.code}
                      </span>
                      <div className="aero-gel-cta flex h-9 w-9 items-center justify-center rounded-xl">
                        <Icon className="relative z-10 h-4 w-4 text-white" />
                      </div>
                    </div>

                    <div className="font-display text-lg font-bold tracking-tight">
                      {stage.title}
                    </div>
                    <div
                      className={cn(
                        "mt-0.5 font-serif text-sm italic",
                        isDay ? "text-sky-700" : "text-cyan-300"
                      )}
                    >
                      {stage.subtitle}
                    </div>

                    <p
                      className={cn(
                        "mt-3 text-xs leading-relaxed",
                        isDay ? "text-slate-600" : "text-cyan-100/75"
                      )}
                    >
                      {stage.detail}
                    </p>
                  </div>

                  <div
                    className={cn(
                      "mt-5 flex items-center justify-between border-t pt-3 font-mono text-[10px] uppercase tracking-wider",
                      isDay
                        ? "border-sky-700/15 text-sky-900/75"
                        : "border-cyan-400/15 text-cyan-200/75"
                    )}
                  >
                    <span>SPEC // {stage.spec}</span>
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">
                      STAGE {stage.idx} →
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </section>

        {/* ==================================================================
            03 // INTERACTIVE AST-RAG VS NAIVE CHUNKING COMPARATOR + BENTO
            ================================================================== */}
        <section
          id="chunk-comparator"
          className="mt-16 grid grid-cols-1 gap-6 scroll-mt-24 lg:grid-cols-12"
        >
          {/* Left 7 Columns: Interactive AST vs Naive Chunking Diagnostic */}
          <div
            className={cn(
              "flex flex-col justify-between overflow-hidden rounded-2xl lg:col-span-7",
              isDay ? "aero-glass-panel-day" : "aero-glass-panel-night"
            )}
          >
            <div
              className={cn(
                "flex flex-wrap items-center justify-between gap-3 px-5 py-3.5",
                isDay ? "aero-titlebar-day" : "aero-titlebar-night"
              )}
            >
              <div className="flex items-center gap-2 font-mono text-[11px] font-bold uppercase tracking-wider">
                <Compass className="h-4 w-4 text-sky-600 dark:text-cyan-300" />
                <span>DIAGNOSTIC // CHUNKING TOPOLOGY COMPARATOR</span>
              </div>

              <div
                className={cn(
                  "inline-flex rounded-full border p-0.5 font-mono text-[10px]",
                  isDay
                    ? "border-sky-700/25 bg-white/80"
                    : "border-cyan-400/25 bg-[#041224]"
                )}
              >
                <button
                  type="button"
                  onClick={() => setChunkComparisonMode("ast")}
                  className={cn(
                    "rounded-full px-3 py-1 font-semibold uppercase transition-all cursor-pointer",
                    chunkComparisonMode === "ast"
                      ? "bg-gradient-to-r from-sky-500 to-emerald-500 text-white shadow-xs"
                      : "opacity-70 hover:opacity-100"
                  )}
                >
                  Tree-Sitter AST (Ours)
                </button>
                <button
                  type="button"
                  onClick={() => setChunkComparisonMode("naive")}
                  className={cn(
                    "rounded-full px-3 py-1 font-semibold uppercase transition-all cursor-pointer",
                    chunkComparisonMode === "naive"
                      ? "bg-red-600 text-white shadow-xs"
                      : "opacity-70 hover:opacity-100"
                  )}
                >
                  Naive 500-Char Split
                </button>
              </div>
            </div>

            <div className="p-5 sm:p-6">
              {chunkComparisonMode === "ast" ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase text-emerald-700 dark:text-emerald-300">
                        <CheckCircle2 className="h-3 w-3" />
                        SYNTAX TREE PRESERVED // 100% CONTEXT INTEGRITY
                      </span>
                      <h3 className="mt-2 font-display text-xl font-bold">
                        Complete Method + Parent Class Header + 1-Hop Call Edges
                      </h3>
                    </div>
                  </div>

                  <div className="rounded-xl border border-sky-500/30 bg-[#051426] p-4 font-mono text-xs text-sky-100">
                    <div className="mb-2 flex items-center justify-between border-b border-sky-400/20 pb-2 text-[10px] text-emerald-300">
                      <span>
                        AST_NODE // class VectorStore → def upsert_atomic() [L112-L148]
                      </span>
                      <span>CALLERS: sync_delta() · CALLEES: embed_batch()</span>
                    </div>
                    <pre className="overflow-x-auto text-[11.5px] leading-relaxed">
                      <code>{`# [PARENT SCOPE]: class VectorStore(BaseStore) — Manages 1024-d Qdrant/PG index
# [1-HOP EDGES]: Called by IncrementalSyncEngine.sync_delta | Calls NemotronClient.embed
def upsert_atomic(self, repo_id: str, symbols: list[ASTSymbol]) -> UpsertReceipt:
    vectors = self.embedder.embed_batch([s.enriched_text for s in symbols])
    with self.db.transaction() as tx:
        tx.replace_file_Purchase_spans(repo_id, symbols, vectors)
    return UpsertReceipt(count=len(symbols), status="COMMITTED")`}</code>
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase text-red-600 dark:text-red-400">
                      <AlertCircle className="h-3 w-3" />
                      BROKEN SYNTAX BOUNDARY // ORPHANED BODY
                    </span>
                    <h3 className="mt-2 font-display text-xl font-bold">
                      Arbitrary Window Slices Functions in Half & Loses Class Scope
                    </h3>
                  </div>

                  <div className="rounded-xl border border-red-500/40 bg-[#1a0b12] p-4 font-mono text-xs text-red-200">
                    <div className="mb-2 flex items-center justify-between border-b border-red-400/20 pb-2 text-[10px] text-red-300">
                      <span>CHUNK #042 // CHARS 20,500–21,000 (MISSING SIGNATURE!)</span>
                      <span>PARENT CLASS: UNKNOWN</span>
                    </div>
                    <pre className="overflow-x-auto text-[11.5px] leading-relaxed opacity-85">
                      <code>{`..._batch([s.enriched_text for s in symbols])
    with self.db.transaction() as tx:
        tx.replace_file_spans(repo_id, symbols, vectors)
    return UpsertReceipt(count=len(symbols), status="COMMITTED")

def _internal_helper(self, x):
    # <-- Sliced mid-loop! LLM has no idea what 'self' or 'symbols' belong to...`}</code>
                    </pre>
                  </div>
                </div>
              )}
            </div>

            <div
              className={cn(
                "flex items-center justify-between border-t px-5 py-3 font-mono text-[10.5px]",
                isDay
                  ? "border-sky-700/15 bg-sky-50/60 text-slate-600"
                  : "border-cyan-400/15 bg-slate-950/50 text-cyan-200/70"
              )}
            >
              <span>PARSER ENGINE: TREE-SITTER CST</span>
              <span>SUPPORTED: PYTHON · TYPESCRIPT · JAVASCRIPT</span>
            </div>
          </div>

          {/* Right 5 Columns: Interactive Incremental SHA-256 Merkle Sync Simulator */}
          <div
            id="merkle-sync"
            className={cn(
              "flex flex-col justify-between overflow-hidden rounded-2xl lg:col-span-5 scroll-mt-24",
              isDay ? "aero-glass-panel-day" : "aero-glass-panel-night"
            )}
          >
            <div
              className={cn(
                "flex items-center justify-between gap-2 px-5 py-3.5",
                isDay ? "aero-titlebar-day" : "aero-titlebar-night"
              )}
            >
              <div className="flex items-center gap-2 font-mono text-[11px] font-bold uppercase tracking-wider">
                <RefreshCw
                  className={cn(
                    "h-3.5 w-3.5 text-sky-600 dark:text-cyan-300",
                    syncSimulated && "rotate-180 transition-transform duration-500"
                  )}
                />
                <span>SHA-256 MERKLE DELTA SYNC</span>
              </div>

              <button
                type="button"
                onClick={() => setSyncSimulated((s) => !s)}
                className="aero-gel-cta rounded-full px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-wider cursor-pointer"
              >
                <span className="relative z-10">
                  {syncSimulated ? "Reset Manifest" : "Simulate Git Push"}
                </span>
              </button>
            </div>

            <div className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-display text-sm font-bold">
                  {syncSimulated
                    ? "Delta Detected: Only 3 Mutated Files Re-Indexed!"
                    : "Baseline Manifest: 5 Tracked Modules"}
                </span>
                <span className="font-mono text-[10.5px] font-semibold text-emerald-600 dark:text-emerald-400">
                  {syncSimulated ? "WALL TIME: 181ms" : "100% IN SYNC"}
                </span>
              </div>

              <div
                className={cn(
                  "divide-y overflow-hidden rounded-xl border font-mono text-[11px]",
                  isDay
                    ? "divide-sky-700/15 border-sky-700/20 bg-white/80"
                    : "divide-cyan-400/15 border-cyan-400/20 bg-[#041224]/90"
                )}
              >
                {syncFiles.map((file) => {
                  const isReindexed = file.status.includes("RE-INDEXED");
                  return (
                    <div
                      key={file.path}
                      className="flex items-center justify-between gap-2 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <div className="truncate font-semibold">{file.path}</div>
                        <div className="text-[10px] opacity-60">
                          SHA256: {file.hash} · {file.lines} LOC
                        </div>
                      </div>
                      <span
                        className={cn(
                          "shrink-0 rounded px-2 py-0.5 text-[9.5px] font-bold uppercase",
                          isReindexed
                            ? "bg-gradient-to-r from-sky-500 to-emerald-500 text-white"
                            : isDay
                            ? "bg-sky-100 text-sky-900"
                            : "bg-cyan-950 text-cyan-300"
                        )}
                      >
                        {file.status}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div
              className={cn(
                "flex items-center justify-between border-t px-5 py-3 font-mono text-[10.5px]",
                isDay
                  ? "border-sky-700/15 bg-sky-50/60 text-slate-600"
                  : "border-cyan-400/15 bg-slate-950/50 text-cyan-200/70"
              )}
            >
              <span>ZERO-DOWNTIME ATOMIC SWAP</span>
              <span>NO FULL RE-EMBEDDING</span>
            </div>
          </div>
        </section>

        {/* ==================================================================
            04 // LOWER ATMOSPHERIC HORIZON CTA MONOLITH
            ================================================================== */}
        <section className="mt-16">
          <div
            className={cn(
              "relative overflow-hidden rounded-3xl p-8 sm:p-12",
              isDay ? "aero-glass-panel-day" : "aero-glass-panel-night"
            )}
          >
            {/* Decorative Refractive Sphere in Corner */}
            <div
              aria-hidden="true"
              className="aero-hydro-orb pointer-events-none absolute -right-12 -bottom-12 h-56 w-56 opacity-55"
            />

            <div className="relative z-10 grid grid-cols-1 items-center gap-8 lg:grid-cols-12">
              <div className="lg:col-span-8">
                <div
                  className={cn(
                    "mb-3 inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-widest",
                    isDay
                      ? "border-sky-600/30 bg-white/80 text-sky-800"
                      : "border-cyan-400/30 bg-cyan-950/80 text-cyan-200"
                  )}
                >
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                  <span>READY FOR DEPLOYMENT // OAUTH 2.0 PKCE</span>
                </div>

                <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
                  Mount your repository into the{" "}
                  <span
                    className={cn(
                      "font-serif font-normal italic",
                      isDay ? "text-sky-600" : "text-cyan-300"
                    )}
                  >
                    hydro-optical
                  </span>{" "}
                  workspace.
                </h2>

                <p
                  className={cn(
                    "mt-3 max-w-2xl text-sm sm:text-base leading-relaxed",
                    isDay ? "text-slate-600" : "text-cyan-100/75"
                  )}
                >
                  Connect public GitHub repositories or index your local
                  filesystem directory. Interrogate module topology, trace
                  request execution paths, and audit domain models with
                  line-accurate proof.
                </p>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row lg:col-span-4 lg:flex-col lg:items-end">
                <button
                  type="button"
                  onClick={user ? onEnterWorkspace : onGoogleSignIn}
                  disabled={isAuthenticating}
                  className="aero-gel-cta inline-flex w-full items-center justify-center gap-3 rounded-2xl px-6 py-4 font-display text-sm font-bold tracking-tight text-white cursor-pointer sm:w-auto lg:w-full"
                >
                  <span className="relative z-10">
                    {user
                      ? "Enter Workspace Console"
                      : isAuthenticating
                      ? "Redirecting to Google..."
                      : "Sign In with Google & Launch"}
                  </span>
                  <ArrowRight className="relative z-10 h-4 w-4" />
                </button>

                <button
                  type="button"
                  onClick={onEnterWorkspace}
                  className={cn(
                    "inline-flex w-full items-center justify-center gap-2 rounded-2xl px-6 py-3.5 font-mono text-xs font-semibold uppercase tracking-wider cursor-pointer sm:w-auto lg:w-full",
                    isDay ? "aero-acrylic-btn-day" : "aero-acrylic-btn-night"
                  )}
                >
                  <span>Open Workspace View</span>
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* ==================================================================
            UTILITARIAN SPECIFICATION FOOTER PLATE
            ================================================================== */}
        <footer
          className={cn(
            "mt-14 flex flex-col items-start justify-between gap-4 border-t pt-6 font-mono text-[10.5px] uppercase tracking-wider sm:flex-row sm:items-center",
            isDay
              ? "border-sky-700/20 text-slate-600"
              : "border-cyan-400/20 text-cyan-200/60"
          )}
        >
          <div className="flex items-center gap-3">
            <span className="font-bold">CODEBASE COPILOT // AERO-UTILITARIAN EDITION</span>
            <span>·</span>
            <span>REV 2.4.0</span>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <span>TREE-SITTER AST</span>
            <span>·</span>
            <span>1024-D NEMOTRON</span>
            <span>·</span>
            <span>HYBRID RRF + RERANKER</span>
          </div>
        </footer>
      </main>
    </div>
  );
}
