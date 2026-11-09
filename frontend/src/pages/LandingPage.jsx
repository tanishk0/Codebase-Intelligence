import React, { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  ArrowUpRight,
  ChevronDown,
  MessageSquare,
  Folder,
  Search,
  Clock,
  Plus,
  FileText,
  Check,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { PrimaryButton, SecondaryButton } from "@/components/ui/button";
import ArclineLogo, { ArclineIcon } from "@/components/ArclineLogo";
import hero3dDark from "../assets/hero-3d-dark.png";

// Radix UI GitHub Icon (exact SVG requested by user)
function GitHubIcon({ className = "w-4 h-4" }) {
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

// 4-Point Diamond Sparkle Icon (accent blue #5899FA / #7DB4FF)
function DiamondSparkleIcon({ className = "w-4 h-4 text-[#5899FA]" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 2L14.3 9.7L22 12L14.3 14.3L12 22L9.7 14.3L2 12L9.7 9.7L12 2Z" />
    </svg>
  );
}

// Right-pointing Paper Plane Icon matching the reference window's Send button
function SendPlaneIcon({ className = "w-3.5 h-3.5" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 8L2.5 2.5L4.8 8L2.5 13.5L14 8Z" />
      <path d="M4.8 8H9.5" />
    </svg>
  );
}

// Renders text with backtick-wrapped identifiers as styled dark-mode code pills
function FormattedAnswerText({ text }) {
  const parts = text.split(/(`[^`]+`)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("`") && part.endsWith("`")) {
          const code = part.slice(1, -1);
          return (
            <code
              key={i}
              className="mx-0.5 inline-block rounded-[4px] border border-[#283244] bg-[#1B2230] px-1.5 py-0.2 font-mono text-[11px] font-medium text-[#E5E7EB]"
            >
              {code}
            </code>
          );
        }
        return <React.Fragment key={i}>{part}</React.Fragment>;
      })}
    </>
  );
}

// Interactive Preset Scenarios for the Preview Window
const PRESET_QUERIES = [
  {
    id: "auth-flow",
    userPrompt: "How does the authentication flow work in this repo?",
    answer:
      "The auth flow uses JWT-based authentication with HTTP-only cookies. Users sign in with email and password, a JWT is issued in the `signin` controller, and the `protect` middleware verifies the token on protected routes.",
    sources: [
      {
        path: "src/controllers/auth.controller.js",
        lines: "L18–L46",
        snippet: `// src/controllers/auth.controller.js
export const signin = async (req, res) => {
  const { email, password } = req.body;
  const user = await User.findOne({ email }).select('+password');
  if (!user || !(await user.correctPassword(password, user.password))) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }
  const token = signToken(user._id);
  res.cookie('jwt', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    maxAge: 7 * 24 * 60 * 60 * 1000
  });
  res.status(200).json({ status: 'success', user: { id: user._id, email } });
};`,
      },
      {
        path: "src/middleware/protect.js",
        lines: "L1–L22",
        snippet: `// src/middleware/protect.js
import jwt from 'jsonwebtoken';

export const protect = async (req, res, next) => {
  const token = req.cookies.jwt || req.headers.authorization?.split(' ')[1];
  if (!token) {
    return res.status(401).json({ error: 'You are not logged in.' });
  }
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = await User.findById(decoded.id);
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Invalid or expired session.' });
  }
};`,
      },
    ],
  },
  {
    id: "db-schema",
    userPrompt: "Where is the database schema and model relationship defined?",
    answer:
      "Database models are orchestrated in the `models` directory with Mongoose. The `User` schema defines hashed credentials, role-based access control, and 1-to-many relationships to repositories.",
    sources: [
      {
        path: "src/models/user.model.js",
        lines: "L8–L34",
        snippet: `// src/models/user.model.js
const userSchema = new mongoose.Schema({
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true, select: false },
  role: { type: String, enum: ['admin', 'developer', 'viewer'], default: 'developer' },
  repositories: [{ type: mongoose.Schema.Types.ObjectId, ref: 'Repository' }]
}, { timestamps: true });`,
      },
      {
        path: "src/models/repository.model.js",
        lines: "L12–L28",
        snippet: `// src/models/repository.model.js
const repositorySchema = new mongoose.Schema({
  repoUrl: { type: String, required: true },
  branch: { type: String, default: 'main' },
  fileManifest: { type: Map, of: String },
  lastIndexedAt: { type: Date }
});`,
      },
    ],
  },
  {
    id: "hybrid-rag",
    userPrompt: "How are semantic embeddings and BM25 fused together?",
    answer:
      "Retrieval combines 1024-dimensional Nemotron vector search with exact token BM25 scoring via `reciprocalRankFusion`, then routes top candidates through a Cross-Encoder `rerank` stage.",
    sources: [
      {
        path: "src/retrieval/hybrid_fuser.js",
        lines: "L42–L78",
        snippet: `// src/retrieval/hybrid_fuser.js
export function reciprocalRankFusion(denseResults, bm25Results, k = 60) {
  const scores = new Map();
  const applyRank = (results) => {
    results.forEach((item, rank) => {
      const prev = scores.get(item.id) || 0;
      scores.set(item.id, prev + (1 / (k + rank + 1)));
    });
  };
  applyRank(denseResults);
  applyRank(bm25Results);
  return Array.from(scores.entries()).sort((a, b) => b[1] - a[1]);
}`,
      },
    ],
  },
];

// Framer Motion staggered entrance animation variants
const staggerContainerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.08,
    },
  },
};

const fadeUpItemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.6,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

const heroPreviewVariants = {
  hidden: { opacity: 0, y: 28, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.75,
      delay: 0.2,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

const footerStaggerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.32,
    },
  },
};

const footerStepVariants = {
  hidden: { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.5,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

export default function LandingPage({
  user,
  onEnterWorkspace,
  onGoogleSignIn,
  isAuthenticating,
  authError,
}) {
  // Navigation modal state
  const [activeNavModal, setActiveNavModal] = useState(null);

  // Interactive Window State
  const [activeTab, setActiveTab] = useState("chat");
  const [activeQueryIdx, setActiveQueryIdx] = useState(0);
  const [repoDropdownOpen, setRepoDropdownOpen] = useState(false);
  const [activeRepoName, setActiveRepoName] = useState("my-repo");
  const [sourcesOpen, setSourcesOpen] = useState(true);
  const [inspectingSource, setInspectingSource] = useState(null);
  const [customInput, setCustomInput] = useState("");

  const currentQuery = PRESET_QUERIES[activeQueryIdx];

  React.useEffect(() => {
    const root = document.documentElement;
    const prevBg = document.body.style.backgroundColor;
    const prevRootBg = root.style.backgroundColor;
    const hadDark = root.classList.contains("dark");

    document.body.style.backgroundColor = "#0B0F16";
    root.style.backgroundColor = "#0B0F16";
    root.classList.add("dark");

    return () => {
      document.body.style.backgroundColor = prevBg;
      root.style.backgroundColor = prevRootBg;
      if (!hadDark) {
        root.classList.remove("dark");
      }
    };
  }, []);

  const handleSendCustomInput = (e) => {
    e.preventDefault();
    if (!customInput.trim()) return;
    setActiveQueryIdx((prev) => (prev + 1) % PRESET_QUERIES.length);
    setCustomInput("");
  };

  return (
    <div className="landing-dark-canvas flex h-screen w-full flex-col justify-between overflow-y-auto overflow-x-hidden bg-[#0B0F16] text-[#E5E7EB]">
      {/* ====================================================================
          TOP NAVIGATION HEADER
          ==================================================================== */}
      <motion.header
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-30 mx-auto flex w-full max-w-[1340px] shrink-0 items-center justify-between px-6 pt-5 pb-3 sm:px-10 lg:px-14 lg:pt-6"
      >
        {/* Left Group: Brand Logo + Navigation Links */}
        <div className="flex items-center">
          <button
            type="button"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="flex items-center focus:outline-none cursor-pointer"
          >
            <ArclineLogo
              iconClassName="h-7 w-7"
              textClassName="font-inter text-[18px] font-semibold tracking-[-0.02em] text-white"
            />
          </button>

          {/* Navigation Links (positioned cleanly to the right of brand logo as in reference) */}
          <nav className="hidden items-center gap-8 md:ml-16 md:flex lg:ml-28 lg:gap-10">
            {[
              { id: "product", label: "Product" },
              { id: "integrations", label: "Integrations" },
              { id: "docs", label: "Docs" },
              { id: "pricing", label: "Pricing" },
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveNavModal(item.id)}
                className="font-inter text-[13.5px] font-normal text-[#D1D5DB] transition-colors hover:text-white cursor-pointer"
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Right Action Buttons */}
        <div className="flex items-center gap-5 lg:gap-6">
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="hidden items-center gap-2 font-inter text-[13.5px] font-medium text-[#E5E7EB] transition-colors hover:text-white sm:flex"
          >
            <GitHubIcon className="h-4 w-4" />
            <span>GitHub</span>
          </a>

          <PrimaryButton
            size="sm"
            withArrow
            isLoading={isAuthenticating}
            onClick={user ? onEnterWorkspace : onGoogleSignIn}
          >
            {user ? "Open Workspace" : "Get started"}
          </PrimaryButton>
        </div>
      </motion.header>

      {/* ====================================================================
          MAIN HERO SECTION (LEFT EDITORIAL COPY + RIGHT PREVIEW WINDOW)
          ==================================================================== */}
      <main className="relative z-10 mx-auto flex w-full max-w-[1340px] flex-1 flex-col justify-center px-6 py-4 sm:px-10 lg:px-14">
        {authError && (
          <div className="mb-4 rounded-lg border border-red-500/40 bg-red-950/40 p-3 text-xs text-red-200">
            {authError}
          </div>
        )}

        <div className="flex flex-col items-start justify-between gap-12 lg:flex-row lg:items-center lg:gap-8">
          {/* ================================================================
              LEFT COLUMN: EDITORIAL COPY & CALLS TO ACTION (STAGGERED FADE-IN)
              ================================================================ */}
          <motion.div
            variants={staggerContainerVariants}
            initial="hidden"
            animate="visible"
            className="relative z-20 flex w-full flex-col items-start lg:w-[40%] xl:w-[41%]"
          >
            {/* Eyebrow Label with Hairline */}
            <motion.div variants={fadeUpItemVariants} className="flex items-center gap-3.5">
              <span className="font-inter text-[11px] font-medium tracking-[0.16em] uppercase text-[#9CA3AF]">
                AI FOR CODEBASES
              </span>
              <span className="inline-block h-[1px] w-7 bg-[#243041]" />
            </motion.div>

            {/* Main Editorial Headline in Fraunces */}
            <motion.h1
              variants={fadeUpItemVariants}
              className="font-fraunces mt-5 mb-5 text-[48px] font-normal leading-[1.04] tracking-[-0.025em] text-[#F3F4F6] sm:text-[58px] lg:text-[62px] xl:text-[68px]"
            >
              Understand
              <br />
              <span className="whitespace-nowrap">your codebase,</span>
              <br />
              <span className="italic font-normal text-[#7DB4FF]">
                instantly.
              </span>
            </motion.h1>

            {/* Subtitle Description in Inter */}
            <motion.p
              variants={fadeUpItemVariants}
              className="mb-7 max-w-[400px] font-inter text-[15px] leading-[1.58] text-[#9CA3AF] lg:text-[16px]"
            >
              Ask questions about your repository and get source-grounded
              answers with file citations.
            </motion.p>

            {/* Action Buttons */}
            <motion.div
              variants={fadeUpItemVariants}
              className="flex flex-wrap items-center gap-3.5"
            >
              <PrimaryButton
                size="lg"
                withArrow
                isLoading={isAuthenticating}
                onClick={user ? onEnterWorkspace : onGoogleSignIn}
              >
                {user ? "Open Workspace" : "Get started"}
              </PrimaryButton>

              <SecondaryButton
                size="lg"
                icon={GitHubIcon}
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
              >
                View on GitHub
              </SecondaryButton>
            </motion.div>
          </motion.div>

          {/* ================================================================
              RIGHT COLUMN: 3D HERO ASSET + INTERACTIVE PREVIEW WINDOW
              ================================================================ */}
          <motion.div
            variants={heroPreviewVariants}
            initial="hidden"
            animate="visible"
            className="relative flex w-full items-center justify-center lg:w-[55.5%] lg:justify-end"
          >
            <div className="relative w-full max-w-[660px] lg:max-w-none">
              {/* Signature 3D Metallic Form — Anchored proportionally to the Window
                  so the top peak rises above the window and the bottom-left tip
                  sweeps diagonally underneath the bottom-left corner of the window */}
              <div className="pointer-events-none select-none absolute z-0 w-[172%] max-w-none left-[-41%] top-[-36%]">
                <img
                  src={hero3dDark}
                  onError={(e) => {
                    e.currentTarget.src = "/hero-3d-dark.png";
                  }}
                  alt="Signature 3D Form"
                  className="h-auto w-full object-contain"
                />
              </div>

              {/* Interactive Workspace Window Card */}
              <div className="landing-dark-window relative z-10 w-full overflow-hidden rounded-[16px] border border-[#243041] bg-[#131822]/95 backdrop-blur-md">
                {/* Window Header Bar */}
                <div className="flex h-11 items-center justify-between border-b border-[#202736] bg-[#131822] px-4">
                  <div className="flex items-center gap-2.5">
                    <ArclineIcon className="h-5 w-5" />
                    <span className="font-inter text-[13.5px] font-semibold tracking-tight text-[#F3F4F6]">
                      Arcline
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1">
                      <span className="flex h-5 min-w-[20px] items-center justify-center rounded-[4px] border border-[#263042] bg-[#1A2130] px-1 font-inter text-[10px] font-medium text-[#9CA3AF]">
                        ⌘
                      </span>
                      <span className="flex h-5 min-w-[20px] items-center justify-center rounded-[4px] border border-[#263042] bg-[#1A2130] px-1.5 font-inter text-[10px] font-medium text-[#9CA3AF]">
                        K
                      </span>
                    </div>
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#263042] font-inter text-[11px] font-medium text-[#D1D5DB]">
                      {user ? (user.name || "U")[0].toUpperCase() : "T"}
                    </div>
                  </div>
                </div>

                {/* Window Main Layout: Compact Left Sidebar (~25%) + Right Chat Area (~75%) */}
                <div className="grid min-h-[340px] grid-cols-1 divide-y divide-[#202736] sm:grid-cols-[156px_1fr] sm:divide-x sm:divide-y-0 lg:grid-cols-[164px_1fr]">
                  {/* Window Left Sidebar */}
                  <div className="flex flex-col justify-between bg-[#121721] p-3">
                    <div className="space-y-2.5">
                      {/* Repository Selector Row */}
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() => setRepoDropdownOpen((prev) => !prev)}
                          className="flex w-full items-center justify-between rounded-[7px] px-2 py-1.5 font-inter text-[12px] font-medium text-[#E5E7EB] transition-colors hover:bg-[#1A2232]/70 cursor-pointer"
                        >
                          <div className="flex items-center gap-2 truncate">
                            <GitHubIcon className="h-3.5 w-3.5 text-[#E5E7EB]" />
                            <span className="truncate">{activeRepoName}</span>
                          </div>
                          <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
                        </button>

                        {repoDropdownOpen && (
                          <div className="absolute top-full left-0 z-30 mt-1 w-full rounded-[8px] border border-[#243041] bg-[#111827] p-1 shadow-2xl">
                            {["my-repo", "arcline-core", "express-api"].map(
                              (r) => (
                                <button
                                  key={r}
                                  type="button"
                                  onClick={() => {
                                    setActiveRepoName(r);
                                    setRepoDropdownOpen(false);
                                  }}
                                  className={cn(
                                    "flex w-full items-center justify-between rounded-[5px] px-2 py-1 text-left font-inter text-[11.5px] cursor-pointer",
                                    activeRepoName === r
                                      ? "bg-[#1A2232] font-medium text-white"
                                      : "text-[#9CA3AF] hover:bg-[#1A2232]/60 hover:text-white"
                                  )}
                                >
                                  <span>{r}</span>
                                  {activeRepoName === r && (
                                    <Check className="h-3 w-3 text-[#7DB4FF]" />
                                  )}
                                </button>
                              )
                            )}
                          </div>
                        )}
                      </div>

                      {/* Window Navigation Items */}
                      <nav className="space-y-0.5">
                        {[
                          { id: "chat", label: "Chat", icon: MessageSquare },
                          { id: "files", label: "Files", icon: Folder },
                          { id: "search", label: "Search", icon: Search },
                          { id: "history", label: "History", icon: Clock },
                        ].map((item) => {
                          const Icon = item.icon;
                          const isCurrent = activeTab === item.id;
                          return (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => setActiveTab(item.id)}
                              className={cn(
                                "flex w-full items-center gap-2.5 rounded-[7px] px-2.5 py-1.5 font-inter text-[12px] transition-colors cursor-pointer",
                                isCurrent
                                  ? "bg-[#222B3B] font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
                                  : "text-[#9CA3AF] hover:bg-[#1A2232]/50 hover:text-[#E5E7EB]"
                              )}
                            >
                              <Icon className="h-3.5 w-3.5 opacity-85" />
                              <span>{item.label}</span>
                            </button>
                          );
                        })}
                      </nav>
                    </div>

                    {/* Add Repository Action at Bottom of Sidebar */}
                    <div className="pt-2">
                      <button
                        type="button"
                        onClick={onEnterWorkspace}
                        className="flex items-center gap-2 px-2 py-1 font-inter text-[11.5px] font-normal text-[#9CA3AF] transition-colors hover:text-[#E5E7EB] cursor-pointer"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        <span>Add repository</span>
                      </button>
                    </div>
                  </div>

                  {/* Window Right Area (Chat / Content View) */}
                  <div className="flex flex-col justify-between bg-[#131822] p-4">
                    {activeTab === "chat" && (
                      <div className="flex h-full flex-col justify-between">
                        <div className="space-y-3">
                          {/* User Message Bubble (Right-Aligned) */}
                          <div className="flex justify-end">
                            <div className="rounded-[10px] border border-[#2B3548]/80 bg-[#222938] px-3.5 py-2 font-inter text-[12px] text-[#E5E7EB]">
                              {currentQuery.userPrompt}
                            </div>
                          </div>

                          {/* Assistant Response + Sources Outer Container Card */}
                          <div className="rounded-[12px] border border-[#1E2634] bg-[#10141D]/80 p-3.5">
                            <div className="flex items-start gap-2.5">
                              <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
                                <DiamondSparkleIcon className="h-4 w-4 text-[#5899FA]" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="font-inter text-[12px] leading-[1.6] text-[#D1D5DB]">
                                  <FormattedAnswerText
                                    text={currentQuery.answer}
                                  />
                                </p>

                                {/* Sources Disclosure */}
                                <div className="mt-3">
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setSourcesOpen((prev) => !prev)
                                    }
                                    className="flex items-center gap-1.5 font-inter text-[11px] font-medium text-[#9CA3AF] transition-colors hover:text-white cursor-pointer"
                                  >
                                    <span>
                                      • Sources ({currentQuery.sources.length})
                                    </span>
                                    <ChevronDown
                                      className={cn(
                                        "h-3 w-3 transition-transform",
                                        sourcesOpen && "rotate-180"
                                      )}
                                    />
                                  </button>

                                  {sourcesOpen && (
                                    <div className="mt-2 space-y-1.5">
                                      {currentQuery.sources.map((src) => (
                                        <div
                                          key={src.path}
                                          onClick={() =>
                                            setInspectingSource(src)
                                          }
                                          className="group flex items-center justify-between rounded-[8px] border border-[#202837] bg-[#141923] px-3 py-1.5 text-[11.5px] transition-colors hover:border-[#2E3A4F] hover:bg-[#1A2130] cursor-pointer"
                                        >
                                          <div className="flex items-center gap-2 truncate pr-2">
                                            <FileText className="h-3.5 w-3.5 shrink-0 text-[#9CA3AF]" />
                                            <span className="truncate font-inter text-[#D1D5DB] group-hover:text-white">
                                              {src.path}
                                            </span>
                                          </div>
                                          <div className="flex shrink-0 items-center gap-2">
                                            <span className="rounded-[4px] bg-[#1F2735] px-1.5 py-0.5 font-mono text-[10px] text-[#9CA3AF]">
                                              {src.lines}
                                            </span>
                                            <ArrowUpRight className="h-3.5 w-3.5 text-[#9CA3AF] transition-colors group-hover:text-white" />
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Interactive Bottom Query Input */}
                        <form
                          onSubmit={handleSendCustomInput}
                          className="relative mt-3"
                        >
                          <input
                            type="text"
                            value={customInput}
                            onChange={(e) => setCustomInput(e.target.value)}
                            placeholder="Ask about your codebase..."
                            className="w-full rounded-[10px] border border-[#222B3A] bg-[#171C28] py-2.5 pr-10 pl-3.5 font-inter text-[12px] text-[#E5E7EB] placeholder:text-[#6B7280] transition-colors focus:border-[#7DB4FF] focus:outline-none"
                          />
                          <button
                            type="submit"
                            aria-label="Send query"
                            className="absolute right-1.5 top-1/2 -translate-y-1/2 flex h-7 w-7 items-center justify-center rounded-[7px] bg-[#E5E7EB] text-[#0B0F16] transition-colors hover:bg-white cursor-pointer"
                          >
                            <SendPlaneIcon className="h-3.5 w-3.5" />
                          </button>
                        </form>
                      </div>
                    )}

                    {/* Files Tab View */}
                    {activeTab === "files" && (
                      <div className="flex h-full flex-col justify-between font-inter text-[12px]">
                        <div>
                          <div className="mb-2 font-medium text-[#9CA3AF]">
                            Repository Explorer // {activeRepoName}
                          </div>
                          <div className="space-y-1 rounded-[10px] border border-[#243041] bg-[#0E1420]/60 p-2">
                            {[
                              "src/controllers/auth.controller.js",
                              "src/middleware/protect.js",
                              "src/models/user.model.js",
                              "src/routes/api.router.js",
                              "src/retrieval/hybrid_fuser.js",
                            ].map((f) => (
                              <div
                                key={f}
                                onClick={() =>
                                  setInspectingSource(
                                    PRESET_QUERIES[0].sources[0]
                                  )
                                }
                                className="flex items-center gap-2 rounded-[6px] px-2 py-1.5 text-[#E5E7EB] transition-colors hover:bg-[#1A2232] cursor-pointer"
                              >
                                <FileText className="h-3.5 w-3.5 text-[#9CA3AF]" />
                                <span>{f}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setActiveTab("chat")}
                          className="pt-4 text-left text-[11.5px] font-medium text-[#7DB4FF] hover:underline cursor-pointer"
                        >
                          ← Back to Chat Q&A
                        </button>
                      </div>
                    )}

                    {/* Search Tab View */}
                    {activeTab === "search" && (
                      <div className="flex h-full flex-col justify-between font-inter text-[12px]">
                        <div>
                          <div className="mb-2 font-medium text-[#9CA3AF]">
                            Exact Identifier & Symbol Search (BM25)
                          </div>
                          <div className="space-y-2 rounded-[10px] border border-[#243041] bg-[#0E1420]/60 p-3">
                            <div className="font-mono text-[11px] text-[#9CA3AF]">
                              Matched 2 symbols for `protect`:
                            </div>
                            <div className="space-y-1.5 text-[11.5px]">
                              <div className="rounded border border-[#243041] bg-[#1A2232] p-2">
                                <span className="font-semibold text-white">
                                  protect()
                                </span>{" "}
                                — src/middleware/protect.js:L1
                              </div>
                              <div className="rounded border border-[#243041] bg-[#1A2232] p-2">
                                <span className="font-semibold text-white">
                                  signin()
                                </span>{" "}
                                — src/controllers/auth.controller.js:L18
                              </div>
                            </div>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setActiveTab("chat")}
                          className="pt-4 text-left text-[11.5px] font-medium text-[#7DB4FF] hover:underline cursor-pointer"
                        >
                          ← Back to Chat Q&A
                        </button>
                      </div>
                    )}

                    {/* History Tab View */}
                    {activeTab === "history" && (
                      <div className="flex h-full flex-col justify-between font-inter text-[12px]">
                        <div>
                          <div className="mb-2 font-medium text-[#9CA3AF]">
                            Saved Conversation Threads
                          </div>
                          <div className="space-y-1.5">
                            {PRESET_QUERIES.map((q, idx) => (
                              <button
                                key={q.id}
                                type="button"
                                onClick={() => {
                                  setActiveQueryIdx(idx);
                                  setActiveTab("chat");
                                }}
                                className="w-full rounded-[8px] border border-[#243041] p-2 text-left transition-colors hover:bg-[#1A2232] cursor-pointer"
                              >
                                <div className="truncate font-medium text-[#E5E7EB]">
                                  {q.userPrompt}
                                </div>
                                <div className="text-[11px] text-[#9CA3AF]">
                                  {q.sources.length} citations · Grounded
                                </div>
                              </button>
                            ))}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setActiveTab("chat")}
                          className="pt-4 text-left text-[11.5px] font-medium text-[#7DB4FF] hover:underline cursor-pointer"
                        >
                          ← Back to Chat Q&A
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </main>

      {/* ====================================================================
          BOTTOM PROCESS STRIP (01 — 02 — 03 WITH HORIZONTAL CONNECTORS)
          ==================================================================== */}
      <motion.footer
        variants={footerStaggerVariants}
        initial="hidden"
        animate="visible"
        className="relative z-20 mx-auto w-full max-w-[1340px] shrink-0 px-6 pt-4 pb-7 sm:px-10 lg:px-14 lg:pb-9"
      >
        <div className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-center lg:px-4">
          {/* Step 01 */}
          <motion.div variants={footerStepVariants} className="flex items-center gap-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#222B3A] bg-[#151B26] font-inter text-[12.5px] font-medium text-[#D1D5DB]">
              01
            </span>
            <div>
              <h2 className="font-inter text-[14.5px] font-semibold tracking-tight text-white">
                Connect repository
              </h2>
              <p className="mt-0.5 font-inter text-[13px] text-[#9CA3AF]">
                Link your codebase in seconds.
              </p>
            </div>
          </motion.div>

          {/* Connector Line 1 */}
          <motion.div
            variants={footerStepVariants}
            className="hidden h-[1px] w-16 bg-[#222B3A] md:block lg:w-24"
          />

          {/* Step 02 */}
          <motion.div variants={footerStepVariants} className="flex items-center gap-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#222B3A] bg-[#151B26] font-inter text-[12.5px] font-medium text-[#D1D5DB]">
              02
            </span>
            <div>
              <h2 className="font-inter text-[14.5px] font-semibold tracking-tight text-white">
                Ask questions
              </h2>
              <p className="mt-0.5 font-inter text-[13px] text-[#9CA3AF]">
                In natural language.
              </p>
            </div>
          </motion.div>

          {/* Connector Line 2 */}
          <motion.div
            variants={footerStepVariants}
            className="hidden h-[1px] w-16 bg-[#222B3A] md:block lg:w-24"
          />

          {/* Step 03 */}
          <motion.div variants={footerStepVariants} className="flex items-center gap-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#222B3A] bg-[#151B26] font-inter text-[12.5px] font-medium text-[#D1D5DB]">
              03
            </span>
            <div>
              <h2 className="font-inter text-[14.5px] font-semibold tracking-tight text-white">
                Explore cited answers
              </h2>
              <p className="mt-0.5 font-inter text-[13px] text-[#9CA3AF]">
                With exact file references.
              </p>
            </div>
          </motion.div>
        </div>
      </motion.footer>

      {/* ====================================================================
          CITATION CODE INSPECTOR MODAL (DARK THEME)
          ==================================================================== */}
      <AnimatePresence>
        {inspectingSource && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              className="relative w-full max-w-2xl rounded-[16px] border border-[#243041] bg-[#111827] p-6 shadow-2xl"
            >
              <div className="mb-4 flex items-center justify-between border-b border-[#243041] pb-4">
                <div className="flex items-center gap-2.5">
                  <FileText className="h-4 w-4 text-[#7DB4FF]" />
                  <span className="font-inter text-[14px] font-semibold text-white">
                    {inspectingSource.path}
                  </span>
                  <span className="rounded border border-[#243041] bg-[#1A2232] px-2 py-0.5 font-mono text-[11px] text-[#9CA3AF]">
                    {inspectingSource.lines}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setInspectingSource(null)}
                  className="rounded p-1 text-[#9CA3AF] hover:bg-[#1A2232] hover:text-white cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="landing-dark-code-scroll overflow-x-auto rounded-[10px] border border-[#243041] bg-[#0B0F16] p-4 font-mono text-[12px] leading-relaxed text-[#E5E7EB]">
                <pre>{inspectingSource.snippet}</pre>
              </div>

              <div className="mt-4 flex justify-end">
                <PrimaryButton
                  size="sm"
                  onClick={() => setInspectingSource(null)}
                >
                  Done
                </PrimaryButton>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ====================================================================
          TOP NAV CONTENT OVERLAY MODALS (DARK THEME)
          ==================================================================== */}
      <AnimatePresence>
        {activeNavModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="relative w-full max-w-lg rounded-[20px] border border-[#243041] bg-[#111827] p-6 shadow-2xl"
            >
              <div className="mb-4 flex items-center justify-between border-b border-[#243041] pb-3">
                <div className="font-inter text-[15px] font-semibold capitalize text-white">
                  {activeNavModal}
                </div>
                <button
                  type="button"
                  onClick={() => setActiveNavModal(null)}
                  className="rounded p-1 text-[#9CA3AF] hover:text-white cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {activeNavModal === "product" && (
                <div className="space-y-3 font-inter text-[13.5px] text-[#9CA3AF]">
                  <p>
                    <strong className="text-white">Arcline</strong>{" "}
                    indexes entire code repositories using AST symbol extraction,
                    combining 1024-dimensional semantic vectors with exact-token
                    BM25 lexical search.
                  </p>
                  <p>
                    Every architectural explanation is grounded in line-accurate
                    source spans with verified references.
                  </p>
                </div>
              )}

              {activeNavModal === "integrations" && (
                <div className="space-y-3 font-inter text-[13.5px] text-[#9CA3AF]">
                  <p>
                    Native integrations for{" "}
                    <strong className="text-white">GitHub</strong>,{" "}
                    <strong className="text-white">GitLab</strong>, and{" "}
                    <strong className="text-white">Local Workspaces</strong>.
                  </p>
                  <p>
                    Zero-downtime incremental sync with SHA-256 Merkle tree
                    diffing.
                  </p>
                </div>
              )}

              {activeNavModal === "docs" && (
                <div className="space-y-3 font-inter text-[13.5px] text-[#9CA3AF]">
                  <p>
                    Read our full documentation on Tree-sitter query extraction,
                    hybrid RRF algorithms, and OAuth 2.0 PKCE authentication.
                  </p>
                </div>
              )}

              {activeNavModal === "pricing" && (
                <div className="space-y-3 font-inter text-[13.5px] text-[#9CA3AF]">
                  <p>
                    <strong className="text-white">Community Edition</strong> is
                    100% free and open-source for personal repositories.
                  </p>
                  <p>
                    Team & Enterprise tiers include private VPC vector stores
                    and organization-wide RBAC.
                  </p>
                </div>
              )}

              <div className="mt-6 flex justify-end">
                <PrimaryButton
                  size="sm"
                  onClick={() => setActiveNavModal(null)}
                >
                  Close
                </PrimaryButton>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
