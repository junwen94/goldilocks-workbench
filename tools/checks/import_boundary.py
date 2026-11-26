"""Import boundary between the shared part and the forms (D1; AGENTS.md, rules 4 and 7).

Reads every Python file under packages/<package>/ (src, tests, conftest.py, scripts, ...) without running it, skipping
hidden folders and __pycache__ at every level (packages/.mypy_cache is not a package), and fails on:
- goldilocks_workbench, goldilocks_chat or goldilocks_ada importing goldilocks_agent, Deep Agents, AiiDA (or an AiiDA
  plugin) or an MLIP package; the two light forms depend on goldilocks_workbench, so all three must stay light
  (ada D8);
- a package importing a form it does not depend on: goldilocks_chat or goldilocks_ada from any other package, so the
  light forms never import each other (ada D8);
- any package importing goldilocks-dft, which is reached over HTTP only (rule 7);
- a package folder that has no rule here, so that a new package cannot pass unchecked.
Imports by name in `__import__("x")` and `importlib.import_module("x")` count too, also under another name
(`from importlib import import_module as im`) and with the name as a keyword (`import_module(name="x")`). A name built
at run time, or code run by exec, is not seen; tools/checks/light_env.py checks what the chat and Ada environments can
import.
Usage: python tools/checks/import_boundary.py [repo-root]
"""

import ast
import os
import sys
from pathlib import Path

HEAVY = {
    "goldilocks_agent": "agent code (AGENTS.md, rule 4)",
    "deepagents": "Deep Agents (AGENTS.md, rule 4)",
    "aiida": "AiiDA (AGENTS.md, rule 4)",
    "janus_core": "an MLIP package (AGENTS.md, rule 4)",
    "mace": "an MLIP package (AGENTS.md, rule 4)",
    "torch": "an MLIP package (AGENTS.md, rule 4)",
}
NOT_A_DEPENDENCY = "a form this package does not depend on (D1)"
EVERYWHERE = {
    "goldilocks_dft": "goldilocks-dft, reached over HTTP only (AGENTS.md, rule 7)",
    "goldilocks_core": "goldilocks-dft, reached over HTTP only (AGENTS.md, rule 7)",
}
# packages/<folder> -> (module name, forbidden top-level modules with the reason)
FORMS = {"goldilocks_chat": NOT_A_DEPENDENCY, "goldilocks_ada": NOT_A_DEPENDENCY}
RULES: dict[str, tuple[str, dict[str, str]]] = {
    "workbench": ("goldilocks_workbench", {**HEAVY, **FORMS, **EVERYWHERE}),
    "chat": ("goldilocks_chat", {**HEAVY, "goldilocks_ada": NOT_A_DEPENDENCY, **EVERYWHERE}),
    "ada": ("goldilocks_ada", {**HEAVY, "goldilocks_chat": NOT_A_DEPENDENCY, **EVERYWHERE}),
    "agent": ("goldilocks_agent", {**FORMS, **EVERYWHERE}),
}
LIGHT = {"workbench", "chat", "ada"}


DYNAMIC = ("__import__", "import_module")


def dynamic_import_names(tree: ast.AST) -> set[str]:
    """Names that call __import__ or importlib.import_module in this tree, including names given with `as`."""
    names = set(DYNAMIC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in ("importlib", "builtins"):
            names |= {alias.asname or alias.name for alias in node.names if alias.name in DYNAMIC}
    return names


def module_argument(call: ast.Call) -> str | None:
    """The module name given to __import__ or import_module as a string, positionally or as `name=`."""
    first = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "name"), None)
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def imported_names(tree: ast.AST) -> list[tuple[int, str]]:
    """Every absolute import in the tree, as (line, dotted name)."""
    found = []
    dynamic = dynamic_import_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Name) and func.id in dynamic) or (
                isinstance(func, ast.Attribute) and func.attr in DYNAMIC
            ):
                name = module_argument(node)
                if name:
                    found.append((node.lineno, name))
    return found


def skipped(folder: str) -> bool:
    """Hidden folders (.venv, .mypy_cache, ...) and __pycache__, inside a package or directly under packages/."""
    return folder.startswith(".") or folder == "__pycache__"


def python_files(package: Path) -> list[Path]:
    """Every Python file in the package folder, except those in skipped folders."""
    files = []
    for folder, subfolders, names in os.walk(package):
        subfolders[:] = [d for d in subfolders if not skipped(d)]
        files += [Path(folder) / name for name in names if name.endswith(".py")]
    return sorted(files)


def reason(folder: str, top: str) -> str | None:
    forbidden = RULES[folder][1]
    if top in forbidden:
        return forbidden[top]
    if folder in LIGHT and top.startswith("aiida_"):
        return "an AiiDA plugin (AGENTS.md, rule 4)"
    return None


def problems(root: Path) -> tuple[list[str], int]:
    found = []
    count = 0
    for package in sorted(p for p in (root / "packages").glob("*") if p.is_dir() and not skipped(p.name)):
        folder = package.name
        if folder not in RULES:
            found.append(f"packages/{folder}: no import rule in tools/checks/import_boundary.py; add one")
            continue
        module = RULES[folder][0]
        for path in python_files(package):
            count += 1
            where = path.relative_to(root).as_posix()
            try:
                tree = ast.parse(path.read_bytes(), filename=where)
            except SyntaxError as error:
                found.append(f"{where}:{error.lineno}: cannot be parsed")
                continue
            for line, name in imported_names(tree):
                top = name.split(".")[0]
                why = reason(folder, top)
                if why:
                    found.append(f"{where}:{line}: {module} imports {name}: {why}")
    return found, count


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[2]
    found, count = problems(root)
    for line in found:
        print(f"  {line}")
    if found:
        print("import-boundary: imports above cross the boundary between the shared part and the forms")
        return 1
    print(f"import-boundary: ok ({count} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
