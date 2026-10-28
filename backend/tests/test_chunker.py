from pathlib import Path
import sys
import unittest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.chunker import TreeSitterChunker
from ingestion.loader import LoadedFile


class TestTreeSitterChunker(unittest.TestCase):
    def setUp(self) -> None:
        # Use a small max_class_lines threshold so we can easily test both small and large class splitting
        self.chunker = TreeSitterChunker(max_class_lines=10)

    def test_python_chunking(self) -> None:
        py_code = """import os

GLOBAL_LIMIT = 100

class SmallClass:
    def ping(self) -> str:
        return "pong"

class LargeService:
    \"\"\"Large class that exceeds 10 lines.\"\"\"
    timeout = 30

    def first_method(self):
        x = 1
        y = 2
        return x + y

    @staticmethod
    def second_method(a, b):
        res = a * b
        return res

def standalone_helper():
    return GLOBAL_LIMIT
"""
        loaded = LoadedFile(
            file_path="src/service.py",
            content=py_code,
            extension=".py",
            size_bytes=len(py_code),
        )
        chunks = self.chunker.chunk_file(loaded)
        by_type = [(c.node_type, c.parent_class, c.start_line, c.end_line) for c in chunks]

        self.assertEqual(
            by_type,
            [
                ("module_preamble", "", 1, 3),
                ("class", "SmallClass", 5, 7),
                ("class_header", "LargeService", 9, 11),
                ("method", "LargeService", 13, 16),
                ("method", "LargeService", 18, 21),
                ("function", "", 23, 24),
            ],
        )

    def test_fallback_chunking(self) -> None:
        md_content = "\n".join(f"Line {i}" for i in range(1, 26))
        chunker = TreeSitterChunker(fallback_chunk_lines=10, fallback_overlap_lines=2)
        loaded = LoadedFile(
            file_path="README.md",
            content=md_content,
            extension=".md",
            size_bytes=len(md_content),
        )
        chunks = chunker.chunk_file(loaded)
        ranges = [(c.node_type, c.start_line, c.end_line) for c in chunks]

        self.assertEqual(
            ranges,
            [
                ("text", 1, 10),
                ("text", 9, 18),
                ("text", 17, 25),
            ],
        )


if __name__ == "__main__":
    unittest.main()

