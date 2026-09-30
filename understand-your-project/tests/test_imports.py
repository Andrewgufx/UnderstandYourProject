import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.imports import extract_import_specs, load_path_aliases


class ExtractJsTests(unittest.TestCase):
    def test_all_import_forms(self):
        text = """
import React from 'react';
import { a } from "./a";
import * as ns from './ns.js';
import './side-effect';
export { b } from './b';
export * from "./all";
const c = require('./c');
const d = await import('./d');
"""
        self.assertEqual(
            extract_import_specs(text, "typescript"),
            ["react", "./a", "./ns.js", "./side-effect", "./b", "./all", "./c", "./d"],
        )

    def test_type_only_import(self):
        text = "import type { T } from './types';\n"
        self.assertEqual(extract_import_specs(text, "typescript"), ["./types"])


class ExtractPyTests(unittest.TestCase):
    def test_all_import_forms(self):
        text = """
import os
import a.b, c as d
from . import x, y
from .. import z
from .sub.mod import thing
from pkg.mod import thing as other
    from indented import q
"""
        self.assertEqual(
            extract_import_specs(text, "python"),
            ["os", "a.b", "c", ".x", ".y", "..z", ".sub.mod.thing", "pkg.mod.thing", "indented.q"],
        )

    def test_parenthesized_and_star_imports_keep_the_module(self):
        text = "from pkg.mod import (\n    a,\n    b,\n)\nfrom other import *\n"
        self.assertEqual(extract_import_specs(text, "python"), ["pkg.mod", "other"])

    def test_ignores_strings_that_look_like_imports(self):
        text = 'msg = "from x import y"\n'
        self.assertEqual(extract_import_specs(text, "python"), [])


class AliasTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_tsconfig_paths_with_comments_and_trailing_commas(self):
        (self.root / "tsconfig.json").write_text("""{
  // comment
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@components/*": ["src/components/*"],
    },
  },
}""")
        self.assertEqual(load_path_aliases(self.root), {"@/": "src/", "@components/": "src/components/"})

    def test_base_url_is_prepended(self):
        (self.root / "jsconfig.json").write_text(
            '{"compilerOptions": {"baseUrl": "src", "paths": {"~/*": ["lib/*"]}}}')
        self.assertEqual(load_path_aliases(self.root), {"~/": "src/lib/"})

    def test_missing_or_invalid_config(self):
        self.assertEqual(load_path_aliases(self.root), {})
        (self.root / "tsconfig.json").write_text("not json at all {{{")
        self.assertEqual(load_path_aliases(self.root), {})

    def test_alias_key_glob_is_not_treated_as_comment(self):
        (self.root / "tsconfig.json").write_text(
            '{"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"]}},\n'
            ' "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"], // trailing\n'
            ' "exclude": ["node_modules"]}')
        self.assertEqual(load_path_aliases(self.root), {"@/": "src/"})


if __name__ == "__main__":
    unittest.main()
