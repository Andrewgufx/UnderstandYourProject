import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.signals import layer_mixing, layer_signals
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


if __name__ == "__main__":
    unittest.main()
