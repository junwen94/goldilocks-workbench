"""Import boundary between the shared part and the forms (D1; AGENTS.md, rules 4 and 7).

Reads every Python file under packages/<package>/src and packages/<package>/tests without running it, and fails on:
- goldilocks_workbench or goldilocks_chat importing goldilocks_agent, Deep Agents, AiiDA (or an AiiDA plugin) or
  an MLIP package; goldilocks-chat depends on goldilocks_workbench, so both must stay light;
- a package importing a form it does not depend on (goldilocks_chat from goldilocks_workbench or goldilocks_agent);
- any package importing goldilocks-dft, which is reached over HTTP only (rule 7);
- a package folder that has no rule here, so that a new package cannot pass unchecked.
Imports by name in `__import__("x")` and `importlib.import_module("x")` count too.
Usage: python tools/checks/import_boundary.py [repo-root]
"""

import ast
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
RULES: dict[str, tuple[str, dict[str, str]]] = {
    "workbench": ("goldilocks_workbench", {**HEAVY, "goldilocks_chat": NOT_A_DEPENDENCY, **EVERYWHERE}),
    "chat": ("goldilocks_chat", {**HEAVY, **EVERYWHERE}),
    "agent": ("goldilocks_agent", {"goldilocks_chat": NOT_A_DEPENDENCY, **EVERYWHERE}),
}
LIGHT = {"workbench", "chat"}


def imported_names(tree: ast.AST) -> list[tuple[int, str]]:
    """Every absolute import in the tree, as (line, dotted name)."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            first = node.args[0]
            if name in ("__import__", "import_module") and isinstance(first, ast.Constant):
                if isinstance(first.value, str):
                    found.append((node.lineno, first.value))
    return found


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
    for package in sorted(p for p in (root / "packages").glob("*") if p.is_dir()):
        folder = package.name
        if folder not in RULES:
            found.append(f"packages/{folder}: no import rule in tools/checks/import_boundary.py; add one")
            continue
        module = RULES[folder][0]
        for path in sorted([*package.glob("src/**/*.py"), *package.glob("tests/**/*.py")]):
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
