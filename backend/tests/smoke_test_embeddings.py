from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.chunker import CodeChunk, TreeSitterChunker
from ingestion.embedder import NvidiaEmbedder
from ingestion.loader import load_repository_files
from ingestion.vector_store import SupabaseVectorStore


def run_embeddings_smoke_test() -> None:
    print("1. Chunking local backend repository...")
    files = load_repository_files(BACKEND_DIR)
    chunks: list[CodeChunk] = TreeSitterChunker().chunk_all(files)
    sample_chunks = chunks[:5]
    print(f"   Selected {len(sample_chunks)} sample chunks out of {len(chunks)} total chunks.")

    print("2. Connecting to Supabase Vector Store...")
    store = SupabaseVectorStore()  # Raises early if SUPABASE_KEY is a publishable/anon key
    embedder = NvidiaEmbedder()

    print("3. Embedding (NVIDIA NIM) + indexing (Supabase) under a new run...")
    repo_id = store.index_chunks(
        repo_url="https://github.com/local/codebase-copilot-smoke-test",
        chunks=sample_chunks,
        embedder=embedder,
    )
    print(f"   Indexed {len(sample_chunks)} chunks under repo_id={repo_id}.")

    query = "How does the Tree-sitter Python AST chunker split large classes?"
    matches = store.query(query, repo_id=repo_id, embedder=embedder, match_count=3)
    print(f"   Top {len(matches)} hybrid search matches for: '{query}'")
    for idx, match in enumerate(matches, start=1):
        print(
            f"     #{idx} [rrf={match.get('rrf_score', 0.0):.4f}, sim={match['similarity']:.3f}] {match['file_path']} "
            f"(L{match['start_line']}-L{match['end_line']}, {match['node_type']})"
        )


if __name__ == "__main__":
    try:
        run_embeddings_smoke_test()
    except Exception as exc:
        print(
            f"\n[Error] {exc}\n"
            "-> Checklist: (1) SUPABASE_KEY is the secret key (sb_secret_...), "
            "(2) backend/supabase_schema.sql has been run in the Supabase SQL Editor."
        )
        sys.exit(1)
