import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.signals import classify_name, layer_mixing, layer_signals, naming_styles, repeated_function_names, similar_filenames
from facts.walk import SourceFile


def sf(path, text, language="typescript"):
    f = SourceFile(path, Path("/nonexistent") / path, language, text.count("\n"))
    f._text = text
    return f


class LayerSignalTests(unittest.TestCase):
    def test_react_component_with_fetch_and_sql(self):
        text = """
export default function Page() {
  const [rows, setRows] = useState([]);
  useEffect(() => { fetch('/api'); }, []);
  const q = "SELECT * FROM users";
  return <Layout>{rows}</Layout>;
}
"""
        categories, labels = layer_signals(text)
        self.assertEqual(categories, ["ui", "network", "data"])
        self.assertEqual(labels, ["jsx", "useState", "useEffect", "fetch(", "SELECT"])

    def test_python_requests_and_sqlite(self):
        text = "import sqlite3\nimport requests\nr = requests.get(url)\n"
        categories, labels = layer_signals(text)
        self.assertEqual(categories, ["network", "data"])
        self.assertEqual(labels, ["requests.", "sqlite3"])

    def test_pure_logic_has_no_signals(self):
        self.assertEqual(layer_signals("def add(a, b):\n    return a + b\n"), ([], []))

    def test_returned_html_tag_is_ui(self):
        categories, _ = layer_signals("return <div/>;\n")
        self.assertEqual(categories, ["ui"])

    def test_typescript_generics_are_not_ui(self):
        text = "export async function load(): Promise<Array<string>> {\n  const r = await fetch('/x');\n  return r.json();\n}\n"
        self.assertEqual(layer_signals(text), (["network"], ["fetch("]))


class LayerMixingTests(unittest.TestCase):
    def test_reports_only_files_with_two_or_more_categories(self):
        files = [
            sf("src/page.tsx", "useState(); fetch('/x');\n"),
            sf("src/pure.ts", "export const a = 1;\n"),
            sf("src/db.ts", "prisma.user.findMany();\n"),
            sf("src/page.test.tsx", "useState(); fetch('/x');\n"),
        ]
        self.assertEqual(layer_mixing(files), [
            {"path": "src/page.tsx", "categories": ["ui", "network"], "signals": ["useState", "fetch("]},
        ])


class SimilarFilenameTests(unittest.TestCase):
    def test_groups_utils_synonyms_and_numbered_copies(self):
        files = [
            sf("src/utils.ts", ""), sf("src/utils2.ts", ""), sf("src/lib/helpers.ts", ""),
            sf("src/api/client.ts", ""), sf("src/api/client-v2.ts", ""),
            sf("src/app/page.tsx", ""), sf("src/app/about/page.tsx", ""),
            sf("src/unique.ts", ""),
        ]
        self.assertEqual(similar_filenames(files), [
            ["src/api/client-v2.ts", "src/api/client.ts"],
            ["src/lib/helpers.ts", "src/utils.ts", "src/utils2.ts"],
        ])


class RepeatedFunctionTests(unittest.TestCase):
    def test_names_in_three_or_more_files(self):
        files = [
            sf("a.ts", "export function formatDate(d) {}\nconst x = () => 1;\n"),
            sf("b.ts", "const formatDate = (d) => d;\n"),
            sf("c.py", "def formatDate(d):\n    pass\ndef main():\n    pass\n", "python"),
            sf("d.py", "async def formatDate(d):\n    pass\ndef main():\n    pass\n", "python"),
            sf("e.py", "def main():\n    pass\n", "python"),
            sf("f.test.ts", "function formatDate() {}\n"),
        ]
        self.assertEqual(repeated_function_names(files), [
            {"name": "formatDate", "files": ["a.ts", "b.ts", "c.py", "d.py"]},
        ])


class NamingTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(classify_name("user_service"), "snake_case")
        self.assertEqual(classify_name("user-service"), "kebab-case")
        self.assertEqual(classify_name("userService"), "camelCase")
        self.assertEqual(classify_name("UserService"), "PascalCase")
        self.assertEqual(classify_name("User_Service"), "mixed")
        self.assertIsNone(classify_name("utils"))
        self.assertIsNone(classify_name("__init__"))

    def test_counts_files_and_dirs(self):
        files = [
            sf("src/components/TodoList.tsx", ""),
            sf("src/components/todo-item.tsx", ""),
            sf("src/lib/date_utils.ts", ""),
            sf("src/my-feature/index.ts", ""),
        ]
        self.assertEqual(naming_styles(files), {
            "file_case_styles": {"PascalCase": 1, "kebab-case": 1, "snake_case": 1},
            "dir_case_styles": {"kebab-case": 1},
        })


if __name__ == "__main__":
    unittest.main()
