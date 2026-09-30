import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.structure import build_tree, largest_files, scale
from facts.walk import SourceFile


def sf(path, lines, language="typescript"):
    return SourceFile(path, Path("/nonexistent") / path, language, lines)


class ScaleTests(unittest.TestCase):
    def test_counts_and_in_scope(self):
        files = [sf("a.ts", 10), sf("b.py", 5, "python")]
        result = scale(files, total_files=4)
        self.assertEqual(result, {
            "total_files": 4, "source_files": 2, "source_lines": 15,
            "lines_by_language": {"python": 5, "typescript": 10},
            "out_of_scope": False,
        })

    def test_out_of_scope_by_lines(self):
        files = [sf("a.ts", 80001)]
        self.assertTrue(scale(files, 1)["out_of_scope"])

    def test_out_of_scope_by_file_count(self):
        files = [sf("f%d.ts" % i, 1) for i in range(801)]
        self.assertTrue(scale(files, 801)["out_of_scope"])


class TreeTests(unittest.TestCase):
    def test_aggregates_per_directory_up_to_max_depth(self):
        files = [
            sf("src/app/page.tsx", 10),
            sf("src/app/api/x/route.ts", 5),
            sf("src/lib/a.ts", 3),
            sf("root.ts", 1),
        ]
        tree = build_tree(files, max_depth=3)
        self.assertEqual(tree, [
            {"path": "src", "depth": 1, "files": 3, "lines": 18},
            {"path": "src/app", "depth": 2, "files": 2, "lines": 15},
            {"path": "src/app/api", "depth": 3, "files": 1, "lines": 5},
            {"path": "src/lib", "depth": 2, "files": 1, "lines": 3},
        ])


class LargestFilesTests(unittest.TestCase):
    def test_includes_all_over_threshold_and_pads_to_minimum(self):
        files = [sf("f%02d.ts" % i, i) for i in range(20)]
        files.append(sf("big.ts", 301))
        files.append(sf("huge.py", 900, "python"))
        result = largest_files(files)
        self.assertEqual(len(result), 15)
        self.assertEqual(result[0], {"path": "huge.py", "lines": 900, "language": "python"})
        self.assertEqual(result[1]["path"], "big.ts")

    def test_more_than_minimum_when_many_large(self):
        files = [sf("f%02d.ts" % i, 400 + i) for i in range(20)]
        self.assertEqual(len(largest_files(files)), 20)


if __name__ == "__main__":
    unittest.main()
