import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.imports import (
    build_dependency, extract_import_specs, find_cycles, is_entry_file, load_alias_configs,
    load_path_aliases, resolve_import,
)
from facts.walk import walk_project


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


class AliasConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=""):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def dep(self):
        files, _ = walk_project(self.root)
        return build_dependency(files, self.root)

    def edges(self):
        return {(e["from"], e["to"]) for e in self.dep()["edges"]}

    def test_nested_config_aliases_apply_to_its_directory_only(self):
        self.write("apps/web/tsconfig.json", '{"compilerOptions": {"paths": {"@/*": ["./src/*"]}}}')
        self.write("apps/web/src/lib/x.ts", "export const x = 1;\n")
        self.write("apps/web/src/page.tsx", "import { x } from '@/lib/x';\n")
        self.write("apps/api/src/lib/x.ts", "export const x = 1;\n")
        self.write("apps/api/src/main.ts", "import { x } from '@/lib/x';\n")
        self.assertEqual(load_alias_configs(self.root), [("apps/web", {"@/": "apps/web/src/"}, None)])
        self.assertEqual(load_path_aliases(self.root), {})
        dep = self.dep()
        self.assertEqual(dep["edges"], [{"from": "apps/web/src/page.tsx", "to": "apps/web/src/lib/x.ts"}])
        self.assertEqual(dep["unresolved_imports"], 1)

    def test_references_and_extends_are_followed(self):
        self.write("tsconfig.json", '{"files": [], "references": [{"path": "./tsconfig.app.json"}, {"path": "./missing"}]}')
        self.write("tsconfig.app.json", '{"extends": "./tsconfig.base.json", "compilerOptions": {"paths": {"~/*": ["src/*"]}}}')
        self.write("tsconfig.base.json", '{"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["lib/*"]}}}')
        self.write("src/a.ts", "import { b } from '~/b';\n")
        self.write("src/b.ts", "export const b = 1;\n")
        self.assertEqual(load_alias_configs(self.root), [("", {"~/": "src/"}, ".")])
        self.assertIn(("src/a.ts", "src/b.ts"), self.edges())

    def test_extends_cycle_is_bounded(self):
        self.write("tsconfig.json", '{"extends": "./a.json", "compilerOptions": {"paths": {"@/*": ["src/*"]}}}')
        self.write("a.json", '{"extends": "./tsconfig.json"}')
        self.assertEqual(load_path_aliases(self.root), {"@/": "src/"})

    def test_base_url_without_paths_resolves_bare_imports(self):
        self.write("tsconfig.json", '{"compilerOptions": {"baseUrl": "src"}}')
        self.write("src/components/Button.tsx", "export const Button = 1;\n")
        self.write("src/app/page.tsx", "import { Button } from 'components/Button';\nimport React from 'react';\n")
        dep = self.dep()
        self.assertEqual(dep["edges"], [{"from": "src/app/page.tsx", "to": "src/components/Button.tsx"}])
        self.assertEqual(dep["unresolved_imports"], 0)

    def test_star_alias_is_ignored(self):
        self.write("tsconfig.json", '{"compilerOptions": {"paths": {"*": ["./vendor/*"], "@/*": ["./src/*"]}}}')
        self.assertEqual(load_path_aliases(self.root), {"@/": "src/"})

    def test_wrong_types_are_ignored_without_error(self):
        self.write("tsconfig.json", '{"compilerOptions": {"paths": [["@/*", "src/*"]], "baseUrl": 3}, "extends": 5, "references": "x"}')
        self.write("web/tsconfig.json", '{"compilerOptions": {"paths": {"@/*": "src/*", "~/*": []}}}')
        self.write("api/tsconfig.json", '{"compilerOptions": []}')
        self.write("cli/jsconfig.json", '[]')
        self.assertEqual(load_alias_configs(self.root), [
            ("", {}, None), ("api", {}, None), ("cli", {}, None), ("web", {}, None),
        ])

    def test_unmatched_local_looking_bare_imports_are_counted(self):
        self.write("src/lib/x.ts", "export const x = 1;\n")
        self.write("src/app/page.tsx",
                   "import a from '@/nope';\nimport b from '~/nope';\nimport c from '#nope';\n"
                   "import d from 'lib/nope';\nimport e from 'src/nope';\nimport f from 'lodash';\n"
                   "import g from '@scope/pkg';\n")
        self.assertEqual(self.dep()["unresolved_imports"], 5)


class ResolveJsTests(unittest.TestCase):
    known = {"src/a.ts", "src/b/index.tsx", "src/c.js", "src/lib/x.ts"}

    def test_relative_with_extension_guessing(self):
        self.assertEqual(resolve_import("./a", "src/main.ts", "typescript", self.known, {}, []), "src/a.ts")
        self.assertEqual(resolve_import("./b", "src/main.ts", "typescript", self.known, {}, []), "src/b/index.tsx")
        self.assertEqual(resolve_import("../c.js", "src/lib/x.ts", "typescript", self.known, {}, []), "src/c.js")

    def test_js_extension_mapped_to_ts(self):
        self.assertEqual(resolve_import("./a.js", "src/main.ts", "typescript", self.known, {}, []), "src/a.ts")

    def test_alias(self):
        self.assertEqual(resolve_import("@/lib/x", "src/app/page.tsx", "typescript", self.known, {"@/": "src/"}, []), "src/lib/x.ts")

    def test_third_party_and_missing(self):
        self.assertIsNone(resolve_import("react", "src/main.ts", "typescript", self.known, {}, []))
        self.assertIsNone(resolve_import("./nope", "src/main.ts", "typescript", self.known, {}, []))


class ResolvePyTests(unittest.TestCase):
    known = {"main.py", "utils.py", "app/__init__.py", "app/models.py", "app/api/routes.py", "src/pkg/__init__.py", "src/pkg/core.py"}
    roots = ["", "src"]

    def test_relative(self):
        self.assertEqual(resolve_import(".models", "app/api/routes.py", "python", self.known, {}, self.roots), None)
        self.assertEqual(resolve_import("..models", "app/api/routes.py", "python", self.known, {}, self.roots), "app/models.py")
        self.assertEqual(resolve_import(".", "app/models.py", "python", self.known, {}, self.roots), "app/__init__.py")

    def test_absolute_from_roots_and_script_dir(self):
        self.assertEqual(resolve_import("app.models", "main.py", "python", self.known, {}, self.roots), "app/models.py")
        self.assertEqual(resolve_import("app", "main.py", "python", self.known, {}, self.roots), "app/__init__.py")
        self.assertEqual(resolve_import("pkg.core", "main.py", "python", self.known, {}, self.roots), "src/pkg/core.py")
        self.assertEqual(resolve_import("utils", "main.py", "python", self.known, {}, self.roots), "utils.py")

    def test_from_import_falls_back_to_package_or_module(self):
        self.assertEqual(resolve_import("app.helper_fn", "main.py", "python", self.known, {}, self.roots), "app/__init__.py")
        self.assertEqual(resolve_import("app.models.Thing", "main.py", "python", self.known, {}, self.roots), "app/models.py")
        self.assertEqual(resolve_import(".name_in_init", "app/models.py", "python", self.known, {}, self.roots), "app/__init__.py")
        self.assertIsNone(resolve_import("app.nope.x", "main.py", "python", self.known, {}, self.roots))

    def test_stdlib_is_unresolved(self):
        self.assertIsNone(resolve_import("os.path", "main.py", "python", self.known, {}, self.roots))
        self.assertIsNone(resolve_import("os", "main.py", "python", self.known, {}, self.roots))


class CycleTests(unittest.TestCase):
    def test_two_node_cycle(self):
        graph = {"a": {"b"}, "b": {"a", "c"}, "c": set()}
        self.assertEqual(find_cycles(graph), [["a", "b", "a"]])

    def test_three_node_cycle_and_no_self_loops(self):
        graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"d"}}
        self.assertEqual(find_cycles(graph), [["a", "b", "c", "a"]])

    def test_acyclic(self):
        self.assertEqual(find_cycles({"a": {"b"}, "b": set()}), [])


class EntryFileTests(unittest.TestCase):
    def test_entries(self):
        for path in ["src/app/page.tsx", "src/index.ts", "main.py", "manage.py",
                     "pkg/__init__.py", "next.config.js", "src/types.d.ts",
                     "tests/test_a.py", "top-level.ts", "src/app/api/x/route.ts"]:
            self.assertTrue(is_entry_file(path), path)

    def test_non_entries(self):
        for path in ["src/lib/utils.ts", "app/models.py", "src/components/Button.tsx"]:
            self.assertFalse(is_entry_file(path), path)


class BuildDependencyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=""):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_graph_cycles_orphans_and_unresolved(self):
        self.write("src/server.js", "const r = require('./routes');\nrequire('express');\n")
        self.write("src/routes.js", "const h = require('./handlers');\n")
        self.write("src/handlers.js", "const r = require('./routes');\nrequire('./missing');\n")
        self.write("src/legacy.js", "module.exports = 1;\n")
        files, _ = walk_project(self.root)
        dep = build_dependency(files, self.root)
        self.assertEqual(dep["edges"], [
            {"from": "src/handlers.js", "to": "src/routes.js"},
            {"from": "src/routes.js", "to": "src/handlers.js"},
            {"from": "src/server.js", "to": "src/routes.js"},
        ])
        self.assertEqual(dep["most_imported"][0], {"path": "src/routes.js", "imported_by": 2})
        self.assertEqual(dep["cycles"], [["src/handlers.js", "src/routes.js", "src/handlers.js"]])
        self.assertEqual(dep["orphans"], ["src/legacy.js"])
        self.assertEqual(dep["unresolved_imports"], 1)

    def test_edges_are_last_and_counted(self):
        self.write("a.ts", "import './b';\n")
        self.write("b.ts", "")
        dep = build_dependency(walk_project(self.root)[0], self.root)
        self.assertEqual(list(dep)[-1], "edges")
        self.assertEqual(list(dep)[0], "edge_count")
        self.assertEqual(dep["edge_count"], 1)

    def test_dotted_module_name_resolves_before_asset_check(self):
        self.write("src/users.service.ts", "export const s = 1;\n")
        self.write("src/users.controller.ts", "import { s } from './users.service';\n")
        dep = build_dependency(walk_project(self.root)[0], self.root)
        self.assertEqual(dep["edges"], [{"from": "src/users.controller.ts", "to": "src/users.service.ts"}])
        self.assertEqual(dep["unresolved_imports"], 0)

    def test_asset_imports_are_not_unresolved(self):
        self.write("tsconfig.json", '{"compilerOptions": {"paths": {"@/*": ["./src/*"]}}}')
        self.write("src/app/layout.tsx",
                   "import './globals.css';\nimport logo from './logo.svg';\n"
                   "import data from '@/data/x.json';\nimport { r } from './real';\n")
        self.write("src/app/real.ts", "export const r = 1;\n")
        dep = build_dependency(walk_project(self.root)[0], self.root)
        self.assertEqual(dep["edges"], [{"from": "src/app/layout.tsx", "to": "src/app/real.ts"}])
        self.assertEqual(dep["unresolved_imports"], 0)

    def test_test_file_importers_do_not_count_in_most_imported(self):
        self.write("src/a.ts", "export const a = 1;\n")
        self.write("src/b.ts", "import { a } from './a';\n")
        self.write("src/a.test.ts", "import { a } from './a';\n")
        dep = build_dependency(walk_project(self.root)[0], self.root)
        self.assertEqual(dep["most_imported"], [{"path": "src/a.ts", "imported_by": 1}])
        self.assertIn({"from": "src/a.test.ts", "to": "src/a.ts"}, dep["edges"])

    def test_main_guard_scripts_are_entries(self):
        self.write("tools/report.py", 'def run():\n    pass\n\nif __name__ == "__main__":\n    run()\n')
        self.write("tools/unused.py", "x = 1\n")
        dep = build_dependency(walk_project(self.root)[0], self.root)
        self.assertEqual(dep["orphans"], ["tools/unused.py"])

    def test_package_json_main_and_bin_are_entries(self):
        self.write("package.json", '{"main": "./lib/lib.js", "bin": {"tool": "./bin/tool.js"}}')
        self.write("lib/lib.js", "module.exports = 1;\n")
        self.write("bin/tool.js", "console.log(1);\n")
        self.write("lib/unused.js", "module.exports = 2;\n")
        dep = build_dependency(walk_project(self.root)[0], self.root)
        self.assertEqual(dep["orphans"], ["lib/unused.js"])

    def test_python_absolute_unresolved_only_counted_when_local_looking(self):
        self.write("app/__init__.py", "")
        self.write("app/a.py", "import os\nfrom app.nope import x\nfrom app import b\n")
        self.write("app/b.py", "")
        files, _ = walk_project(self.root)
        dep = build_dependency(files, self.root)
        self.assertEqual(dep["edges"], [{"from": "app/a.py", "to": "app/b.py"}])
        self.assertEqual(dep["unresolved_imports"], 1)


if __name__ == "__main__":
    unittest.main()
