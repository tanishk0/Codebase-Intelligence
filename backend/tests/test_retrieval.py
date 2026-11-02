from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.chunker import CodeChunk, TreeSitterChunker, build_search_text, split_identifier_tokens
from ingestion.dependency import DependencyAnalyzer
from ingestion.loader import LoadedFile
from ingestion.summarizer import RepoSummarizer, build_file_outline
from ingestion.vector_store import SupabaseVectorStore
from retrieval.chat_engine import ConversationalRAGEngine
from retrieval.query_router import QueryPlan, QueryRewriteError, QueryRouter
from retrieval.reranker import CodeReranker, ContextAssembler, NvidiaCrossEncoderReranker, RerankerServiceError
from retrieval.retriever import CodebaseRetriever


class TestIdentifierSplittingAndChunkSymbols(unittest.TestCase):
    def test_split_identifier_tokens_handles_camel_and_snake(self) -> None:
        tokens = split_identifier_tokens("def getUserById(user_repo_id): return TreeSitterChunker")
        self.assertIn("get user by id", tokens)
        self.assertIn("user repo id", tokens)
        self.assertIn("tree sitter chunker", tokens)

    def test_chunker_extracts_symbol_names_and_splits_oversized_functions(self) -> None:
        chunker = TreeSitterChunker(max_class_lines=10, max_function_lines=6, fallback_overlap_lines=2)
        py_code = "\n".join(
            [
                "def long_worker(x: int) -> int:",
                "    step1 = x + 1",
                "    step2 = step1 + 1",
                "    step3 = step2 + 1",
                "    step4 = step3 + 1",
                "    step5 = step4 + 1",
                "    step6 = step5 + 1",
                "    return step6",
            ]
        )
        loaded = LoadedFile("src/worker.py", py_code, ".py", len(py_code))
        chunks = chunker.chunk_file(loaded)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].symbol_name, "long_worker")
        self.assertEqual(chunks[1].symbol_name, "long_worker")
        self.assertIn("# Function: def long_worker(x: int) -> int: (continued)", chunks[1].content)

        search_txt = build_search_text(chunks[0])
        self.assertIn("long worker", search_txt)


class TestSummarizer(unittest.TestCase):
    def test_build_file_outline_and_summary_chunks(self) -> None:
        chunks = [
            CodeChunk("src/auth.py", "# File: src/auth.py\nimport jwt", 1, 1, "module_preamble"),
            CodeChunk(
                "src/auth.py",
                '# File: src/auth.py\n# Class: AuthService (Header)\nclass AuthService:\n    """Handles JWT auth."""',
                3,
                5,
                "class_header",
                parent_class="AuthService",
                symbol_name="AuthService",
            ),
            CodeChunk(
                "src/auth.py",
                "# File: src/auth.py\n# Class: AuthService\ndef verify_token(self, token: str): return True",
                7,
                8,
                "method",
                parent_class="AuthService",
                symbol_name="verify_token",
            ),
        ]
        outline = build_file_outline("src/auth.py", chunks)
        self.assertIn("AuthService", outline)
        self.assertIn("verify_token", outline)

        summarizer = RepoSummarizer()
        summary_chunks = summarizer.build_file_summary_chunks(chunks, use_llm=False)
        self.assertEqual(len(summary_chunks), 1)
        self.assertEqual(summary_chunks[0].node_type, "file_summary")
        self.assertEqual(summary_chunks[0].symbol_name, "auth.py")

        repo_summary = summarizer.build_repo_summary("https://github.com/org/repo", summary_chunks, use_llm=False)
        self.assertIn("src/auth.py", repo_summary)


class TestQueryRouter(unittest.TestCase):
    def test_extracts_hints_for_unified_hybrid_search(self) -> None:
        router = QueryRouter()

        p_sym = router.plan("where is `RepoCloner` defined?")
        self.assertTrue(p_sym.needs_retrieval)
        self.assertEqual(p_sym.target_symbol, "RepoCloner")

        p_file = router.plan("how does chunker.py handle decorators?")
        self.assertTrue(p_file.needs_retrieval)
        self.assertEqual(p_file.target_file, "chunker.py")

        p_meta = router.plan("summarize that in bullet points", history=[{"role": "assistant", "content": "..."}])
        self.assertFalse(p_meta.needs_retrieval)

    def test_condenses_followup_with_llm(self) -> None:
        mock_llm = MagicMock()
        mock_llm.complete_json.return_value = {
            "needs_retrieval": True,
            "standalone_query": "Why does `TreeSitterChunker.chunk_python` mark the class span as covered?",
        }
        router = QueryRouter(llm_client=mock_llm)
        history = [
            {"role": "user", "content": "How does TreeSitterChunker.chunk_python split large classes?"},
            {"role": "assistant", "content": "It emits a class_header and marks all class lines in covered_lines."},
        ]
        plan = router.plan("why does it do that?", history=history)
        self.assertTrue(plan.needs_retrieval)
        self.assertIn("TreeSitterChunker", plan.standalone_query)

    def test_followup_rewrite_failure_is_reported(self) -> None:
        mock_llm = MagicMock()
        mock_llm.complete_json.side_effect = RuntimeError("service unavailable")

        with self.assertRaisesRegex(QueryRewriteError, "AI service is unavailable"):
            QueryRouter(llm_client=mock_llm).plan(
                "why does it do that?",
                history=[{"role": "assistant", "content": "It chunks large classes."}],
            )


class TestRerankerAndContextAssembler(unittest.TestCase):
    def test_cross_encoder_uses_model_scores_for_final_order(self) -> None:
        client = MagicMock()
        client.__enter__.return_value.post.return_value.status_code = 200
        client.__enter__.return_value.post.return_value.json.return_value = {
            "rankings": [
                {"index": 1, "logit": 2.0},
                {"index": 0, "logit": 0.5},
            ]
        }
        with patch("retrieval.reranker.httpx.Client", return_value=client):
            ranked = NvidiaCrossEncoderReranker(api_key="key").rerank(
                "where is the handler?",
                [
                    {"id": 1, "file_path": "a.py", "content": "def unrelated(): pass"},
                    {"id": 2, "file_path": "b.py", "content": "def handler(): pass"},
                ],
                top_k=1,
            )
        self.assertEqual(ranked[0]["id"], 2)
        self.assertEqual(ranked[0]["model_rerank_score"], 2.0)

    def test_cross_encoder_failure_does_not_fall_back_to_heuristics(self) -> None:
        client = MagicMock()
        client.__enter__.return_value.post.return_value.status_code = 503
        with patch("retrieval.reranker.httpx.Client", return_value=client):
            with self.assertRaises(RerankerServiceError):
                NvidiaCrossEncoderReranker(api_key="key").rerank(
                    "query", [{"id": 1, "content": "code"}], top_k=1
                )

    def test_reranker_boosts_symbol_and_caps_per_file(self) -> None:
        reranker = CodeReranker(top_k=5, max_chunks_per_file=2)
        plan = QueryPlan(
            original_query="where is validate_github_url?",
            standalone_query="where is validate_github_url?",
            target_symbol="validate_github_url",
        )
        candidates = [
            {
                "id": 1,
                "file_path": "tests/test_git.py",
                "start_line": 1,
                "end_line": 10,
                "node_type": "function",
                "symbol_name": "test_validate",
                "content": "validate_github_url()",
                "similarity": 0.80,
            },
            {
                "id": 2,
                "file_path": "ingestion/git_clone.py",
                "start_line": 8,
                "end_line": 16,
                "node_type": "function",
                "symbol_name": "validate_github_url",
                "content": "def validate_github_url(url: str):",
                "similarity": 0.72,
            },
        ]
        ranked = reranker.rerank(candidates, plan)
        # Exact symbol match in non-test file must outrank the test file
        self.assertEqual(ranked[0]["id"], 2)

    def test_context_assembler_merges_overlapping_chunks_and_attaches_headers(self) -> None:
        assembler = ContextAssembler(token_budget=2000)
        primary = [
            {
                "id": 10,
                "file_path": "README.md",
                "start_line": 1,
                "end_line": 4,
                "node_type": "text",
                "content": "# File: README.md\nline 1\nline 2\nline 3\nline 4",
                "rerank_score": 0.8,
            },
            {
                "id": 11,
                "file_path": "README.md",
                "start_line": 3,
                "end_line": 6,
                "node_type": "text",
                "content": "# File: README.md\nline 3\nline 4\nline 5\nline 6",
                "rerank_score": 0.75,
            },
        ]
        neighbors = [
            {
                "id": 99,
                "file_path": "src/service.py",
                "start_line": 1,
                "end_line": 5,
                "node_type": "class_header",
                "parent_class": "Service",
                "content": "# File: src/service.py\nclass Service:",
            }
        ]
        assembled = assembler.assemble(primary, neighbor_chunks=neighbors)
        readme_chunks = [c for c in assembled if c["file_path"] == "README.md"]
        self.assertEqual(len(readme_chunks), 1)
        self.assertEqual(readme_chunks[0]["start_line"], 1)
        self.assertEqual(readme_chunks[0]["end_line"], 6)
        self.assertEqual(readme_chunks[0]["content"].count("line 3"), 1)

    def test_context_assembler_does_not_merge_adjacent_symbols(self) -> None:
        chunks = [
            {
                "file_path": "src/service.py", "start_line": 1, "end_line": 3,
                "node_type": "method", "parent_class": "Service", "symbol_name": "first",
                "content": "# File: src/service.py\n# Class: Service\ndef first(self):\n    pass",
                "rerank_score": 0.9,
            },
            {
                "file_path": "src/service.py", "start_line": 5, "end_line": 6,
                "node_type": "function", "parent_class": "", "symbol_name": "second",
                "content": "# File: src/service.py\ndef second():\n    pass",
                "rerank_score": 0.8,
            },
        ]
        self.assertEqual(len(ContextAssembler.merge_adjacent_chunks(chunks)), 2)

    def test_context_assembler_enforces_budget_for_first_chunk(self) -> None:
        assembler = ContextAssembler(token_budget=2)
        chunks = [{"file_path": "src/large.py", "content": "x" * 20, "rerank_score": 1.0}]
        self.assertEqual(assembler.assemble(chunks), [])


class TestConversationalRAGFlow(unittest.TestCase):
    def test_multi_turn_rag_carries_over_previous_chunks_and_rewrites_followup(self) -> None:
        mock_store = MagicMock()
        mock_store.get_repository.return_value = {
            "id": "repo-1",
            "active_run_id": "run-1",
            "repo_summary": "Codebase Copilot backend.",
        }
        mock_store.hybrid_search.return_value = [
            {
                "id": 42,
                "file_path": "ingestion/chunker.py",
                "start_line": 150,
                "end_line": 192,
                "node_type": "method",
                "parent_class": "TreeSitterChunker",
                "symbol_name": "chunk_python",
                "content": "# File: ingestion/chunker.py\ndef chunk_python(self, file): ...",
                "similarity": 0.82,
                "rrf_score": 0.03,
            }
        ]
        mock_store.fetch_chunks_by_ids.return_value = [
            {
                "id": 41,
                "file_path": "ingestion/chunker.py",
                "start_line": 42,
                "end_line": 50,
                "node_type": "class_header",
                "parent_class": "TreeSitterChunker",
                "symbol_name": "TreeSitterChunker",
                "content": "# File: ingestion/chunker.py\nclass TreeSitterChunker:",
            }
        ]
        mock_store.fetch_context_neighbors.return_value = []

        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1, 0.2]

        mock_llm = MagicMock()
        mock_llm.complete_json.return_value = {
            "needs_retrieval": True,
            "standalone_query": "How does TreeSitterChunker.chunk_python handle decorated classes?",
        }
        mock_llm.complete.return_value = (
            "It unwraps `decorated_definition` in `[ingestion/chunker.py:L150-L192]`."
        )
        mock_model_reranker = MagicMock()
        mock_model_reranker.rerank.side_effect = lambda _query, chunks, top_k: chunks[:top_k]

        retriever = CodebaseRetriever(
            vector_store=mock_store,
            embedder=mock_embedder,
            llm_client=mock_llm,
            model_reranker=mock_model_reranker,
        )
        engine = ConversationalRAGEngine(retriever=retriever, llm_client=mock_llm, vector_store=mock_store)

        history = [
            {"role": "user", "content": "Tell me about TreeSitterChunker"},
            {"role": "assistant", "content": "It chunks ASTs.", "cited_chunk_ids": [41]},
        ]
        turn = engine.ask("how does it handle decorated classes?", repo_id="repo-1", history=history)

        self.assertIn("ingestion/chunker.py:L150-L192", turn.answer)
        self.assertIn(42, turn.cited_chunk_ids)
        mock_store.fetch_chunks_by_ids.assert_called_once_with("repo-1", [41])


class TestDependencyAnalyzer(unittest.TestCase):
    def test_python_import_alias_resolves_to_exported_symbol(self) -> None:
        files = [
            LoadedFile("pkg/lib.py", "def actual():\n    pass\n", ".py", 20),
            LoadedFile(
                "pkg/main.py",
                "from .lib import actual as alias\n\ndef caller():\n    alias()\n",
                ".py",
                60,
            ),
        ]
        chunks = TreeSitterChunker().chunk_all(files)
        DependencyAnalyzer().analyze(chunks, files=files)

        caller = next(c for c in chunks if c.symbol_name == "caller")
        target = next(c for c in chunks if c.symbol_name == "actual")
        self.assertEqual(caller.calls, ["actual"])
        self.assertEqual(target.called_by, ["caller"])

    def test_python_imports_inheritance_and_call_graph_disambiguation(self) -> None:
        chunker = TreeSitterChunker(max_class_lines=5)
        analyzer = DependencyAnalyzer()

        files = [
            LoadedFile(
                "backend/core/base.py",
                "\n".join(
                    [
                        "class BaseService:",
                        "    def audit_log(self, msg: str) -> None:",
                        "        pass",
                        "",
                        "    def ping(self) -> str:",
                        "        return 'ok'",
                    ]
                ),
                ".py",
                120,
            ),
            LoadedFile(
                "backend/utils/crypto.py",
                "\n".join(
                    [
                        "def verify_signature(payload: str) -> bool:",
                        "    return len(payload) > 0",
                        "",
                        "def common_helper() -> int:",
                        "    return 1",
                    ]
                ),
                ".py",
                110,
            ),
            LoadedFile(
                "backend/other/ambiguous.py",
                "\n".join(
                    [
                        "def common_helper() -> int:",
                        "    return 2",
                        "",
                        "def unique_repo_func() -> str:",
                        "    return 'unique'",
                    ]
                ),
                ".py",
                110,
            ),
            LoadedFile(
                "backend/services/auth.py",
                "\n".join(
                    [
                        "from core.base import BaseService",
                        "from ..utils.crypto import verify_signature",
                        "",
                        "class AuthService(BaseService):",
                        "    def login(self, token: str) -> bool:",
                        "        self.audit_log(token)",
                        "        ok = verify_signature(token)",
                        "        unique_repo_func()",
                        "        common_helper()",
                        "        return ok",
                    ]
                ),
                ".py",
                260,
            ),
        ]

        chunks = chunker.chunk_all(files)
        analyzer.analyze(chunks, files=files)
        # Re-running analyze() must be idempotent
        analyzer.analyze(chunks, files=files)

        by_sym = {(c.file_path, c.node_type, c.symbol_name): c for c in chunks}
        login_chunk = by_sym[("backend/services/auth.py", "method", "login")]
        verify_chunk = by_sym[("backend/utils/crypto.py", "function", "verify_signature")]
        audit_chunk = by_sym[("backend/core/base.py", "method", "audit_log")]

        # 1. File-level imports & reverse imported_by
        self.assertEqual(
            login_chunk.imports,
            ["backend/core/base.py", "backend/utils/crypto.py"],
        )
        self.assertIn("backend/services/auth.py", verify_chunk.imported_by)
        self.assertIn("backend/services/auth.py", audit_chunk.imported_by)

        # 2. Class inheritance
        self.assertEqual(login_chunk.inherits_from, ["BaseService"])

        # 3. Call graph disambiguation:
        # - `audit_log` resolved via inherited method on BaseService
        # - `verify_signature` resolved via imported file `backend/utils/crypto.py`
        # - `unique_repo_func` resolved via repo-wide unique fallback
        # - `common_helper` resolved to `backend/utils/crypto.py` (imported) and NOT `backend/other/ambiguous.py`
        self.assertEqual(
            login_chunk.calls,
            ["audit_log", "verify_signature", "unique_repo_func", "common_helper"],
        )
        self.assertIn("AuthService.login", verify_chunk.called_by)
        self.assertIn("AuthService.login", audit_chunk.called_by)

        ambiguous_other = by_sym[("backend/other/ambiguous.py", "function", "common_helper")]
        self.assertEqual(ambiguous_other.called_by, [])

        # 4. Injected headers on chunk.content
        self.assertIn("# Inherits from: BaseService", login_chunk.content)
        self.assertIn("# Calls: audit_log, verify_signature", login_chunk.content)
        self.assertIn("# Called by: AuthService.login", verify_chunk.content)

    def test_typescript_alias_and_barrel_resolution(self) -> None:
        chunker = TreeSitterChunker(max_class_lines=5)
        analyzer = DependencyAnalyzer()

        files = [
            LoadedFile(
                "src/api/index.ts",
                "export function fetchJson(url: string) {\n    return url;\n}\n",
                ".ts",
                60,
            ),
            LoadedFile(
                "src/services/user.ts",
                "\n".join(
                    [
                        "import { fetchJson } from '@/api';",
                        "",
                        "export class UserService extends BaseClient {",
                        "    loadUser(id: string) {",
                        "        return fetchJson(id);",
                        "    }",
                        "    reset() {",
                        "        return null;",
                        "    }",
                        "}",
                    ]
                ),
                ".ts",
                200,
            ),
        ]

        chunks = chunker.chunk_all(files)
        analyzer.analyze(chunks, files=files)

        load_user = next(c for c in chunks if c.symbol_name == "loadUser")
        fetch_json = next(c for c in chunks if c.symbol_name == "fetchJson")

        self.assertEqual(load_user.imports, ["src/api/index.ts"])
        self.assertEqual(fetch_json.imported_by, ["src/services/user.ts"])
        self.assertEqual(load_user.inherits_from, ["BaseClient"])
        self.assertEqual(load_user.calls, ["fetchJson"])
        self.assertEqual(fetch_json.called_by, ["UserService.loadUser"])

    def test_one_hop_dependency_expansion_capped_at_four(self) -> None:
        primary_chunks = [
            {
                "id": 1,
                "file_path": "backend/services/auth.py",
                "start_line": 10,
                "end_line": 20,
                "node_type": "method",
                "parent_class": "AuthService",
                "symbol_name": "login",
                "calls": ["verify_signature", "decode_jwt"],
                "called_by": [
                    "Router.post_login", "Router.post_logout", "Router.post_refresh",
                    "Router.post_revoke", "Router.post_status",
                ],
                "inherits_from": ["BaseService"],
                "content": "# File: backend/services/auth.py\ndef login(self, token): ...",
                "rerank_score": 0.92,
            }
        ]
        dep_symbols = CodebaseRetriever._extract_dependency_symbols(primary_chunks, max_primary=3)
        self.assertEqual(
            dep_symbols[:5],
            ["Router.post_login", "Router.post_logout", "Router.post_refresh", "Router.post_revoke", "Router.post_status"],
        )

        # Verify SupabaseVectorStore.fetch_context_neighbors caps 1-hop dependency chunks at 4
        mock_client = MagicMock()
        repo_table = MagicMock()
        chunks_table = MagicMock()
        mock_client.table.side_effect = lambda name: repo_table if name == "repositories" else chunks_table
        repo_table.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "repo-1", "active_run_id": "run-1"}
        ]

        # First query: module_preamble / class_header; Second query: dependency symbols
        preamble_exec = MagicMock()
        preamble_exec.data = []
        dep_exec = MagicMock()
        dep_exec.data = [
            {
                "id": 100 + i,
                "file_path": f"backend/utils/dep_{i}.py",
                "start_line": 1,
                "end_line": 5,
                "node_type": "function",
                "parent_class": "Router",
                "symbol_name": sym,
                "content": f"def {sym}(): pass",
            }
            for i, sym in enumerate(["post_login", "post_logout", "post_refresh", "post_revoke", "post_status"])
        ]
        (
            chunks_table.select.return_value.eq.return_value.eq.return_value.in_.return_value.in_.return_value.execute
        ).side_effect = [preamble_exec, dep_exec]

        store = SupabaseVectorStore(client=mock_client)
        neighbors = store.fetch_context_neighbors(
            repo_id="repo-1",
            file_paths=["backend/services/auth.py"],
            parent_classes=["AuthService"],
            dependency_symbols=dep_symbols,
            max_dependency_chunks=4,
        )
        dep_neighbors = [n for n in neighbors if n.get("is_dependency_neighbor")]
        self.assertEqual(len(dep_neighbors), 4)
        self.assertEqual(
            [n["symbol_name"] for n in dep_neighbors],
            ["post_login", "post_logout", "post_refresh", "post_revoke"],
        )


if __name__ == "__main__":
    unittest.main()

