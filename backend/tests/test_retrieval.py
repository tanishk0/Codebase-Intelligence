from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.chunker import CodeChunk, TreeSitterChunker, build_search_text, split_identifier_tokens
from ingestion.loader import LoadedFile
from ingestion.summarizer import RepoSummarizer, build_file_outline
from retrieval.chat_engine import ConversationalRAGEngine
from retrieval.query_router import QueryPlan, QueryRouter
from retrieval.reranker import CodeReranker, ContextAssembler
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


class TestRerankerAndContextAssembler(unittest.TestCase):
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

        retriever = CodebaseRetriever(
            vector_store=mock_store,
            embedder=mock_embedder,
            llm_client=mock_llm,
        )
        engine = ConversationalRAGEngine(retriever=retriever, llm_client=mock_llm, vector_store=mock_store)

        history = [
            {"role": "user", "content": "Tell me about TreeSitterChunker"},
            {"role": "assistant", "content": "It chunks ASTs.", "cited_chunk_ids": [41]},
        ]
        turn = engine.ask("how does it handle decorated classes?", repo_id="repo-1", history=history)

        self.assertIn("ingestion/chunker.py:L150-L192", turn.answer)
        self.assertIn(42, turn.cited_chunk_ids)
        mock_store.fetch_chunks_by_ids.assert_called_once_with([41])


if __name__ == "__main__":
    unittest.main()

