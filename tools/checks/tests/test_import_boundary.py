"""Tests of tools/checks/import_boundary.py, run on small package trees in a temporary folder."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "import_boundary.py"
REPO = Path(__file__).resolve().parents[3]
MODULES = {"workbench": "goldilocks_workbench", "chat": "goldilocks_chat", "agent": "goldilocks_agent"}


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), str(root)], capture_output=True, text=True, check=False)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Three empty packages, as in this repository."""
    for folder, module in MODULES.items():
        init = tmp_path / "packages" / folder / "src" / module / "__init__.py"
        init.parent.mkdir(parents=True)
        init.write_text('"""Empty."""\n')
    return tmp_path


def plant(root: Path, folder: str, code: str, name: str = "planted.py", place: str = "src") -> None:
    """Write a file into packages/<folder>/src/<module>, or into packages/<folder>/<place> ("" is the folder itself)."""
    path = root / "packages" / folder / place / (MODULES[folder] if place == "src" else "") / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)


def test_this_repository_passes() -> None:
    result = run(REPO)
    assert result.returncode == 0, result.stdout
    assert result.stdout.startswith("import-boundary: ok")


def test_empty_packages_pass(tree: Path) -> None:
    result = run(tree)
    assert result.returncode == 0, result.stdout
    assert result.stdout == "import-boundary: ok (3 files)\n"


def test_the_shared_part_importing_agent_code_fails(tree: Path) -> None:
    plant(tree, "workbench", "import goldilocks_agent\n")
    result = run(tree)
    assert result.returncode == 1
    where = "packages/workbench/src/goldilocks_workbench/planted.py:1"
    assert f"{where}: goldilocks_workbench imports goldilocks_agent: agent code" in result.stdout


@pytest.mark.parametrize("folder", ["workbench", "chat"])
@pytest.mark.parametrize(
    "code",
    [
        "from goldilocks_agent.runs import start\n",
        "import deepagents\n",
        "import aiida.orm\n",
        "from aiida_quantumespresso.workflows.pw.base import PwBaseWorkChain\n",
        "import aiida_mlip\n",
        "import janus_core\n",
        "from mace.calculators import mace_mp\n",
        "import torch\n",
        "import importlib\nimportlib.import_module('deepagents')\n",
        "__import__('aiida')\n",
        "from importlib import import_module\nimport_module('janus_core.calculations')\n",
        "from importlib import import_module as im\nim('aiida')\n",
        "import importlib as il\nil.import_module('deepagents')\n",
        "import importlib\nimportlib.import_module(name='aiida.orm')\n",
        "__import__(name='torch')\n",
        "from builtins import __import__ as imp\nimp('mace')\n",
        "def f() -> None:\n    import torch\n",
    ],
)
def test_light_packages_importing_heavy_packages_fail(tree: Path, folder: str, code: str) -> None:
    plant(tree, folder, code)
    assert run(tree).returncode == 1


def test_a_heavy_import_in_a_test_file_fails(tree: Path) -> None:
    plant(tree, "chat", "import aiida\n", name="test_planted.py", place="tests")
    result = run(tree)
    assert result.returncode == 1
    assert "packages/chat/tests/test_planted.py:1:" in result.stdout


@pytest.mark.parametrize(
    ("place", "name"), [("", "conftest.py"), ("scripts", "make_data.py"), ("docs/examples", "example.py")]
)
def test_a_heavy_import_outside_src_and_tests_fails(tree: Path, place: str, name: str) -> None:
    plant(tree, "chat", "import aiida\n", name=name, place=place)
    result = run(tree)
    assert result.returncode == 1
    assert f"packages/chat/{place + '/' if place else ''}{name}:1:" in result.stdout


@pytest.mark.parametrize("place", [".venv/lib/python3.12/site-packages", "src/goldilocks_chat/__pycache__"])
def test_hidden_folders_and_pycache_are_skipped(tree: Path, place: str) -> None:
    plant(tree, "chat", "import aiida\n", place=place)
    result = run(tree)
    assert result.returncode == 0, result.stdout
    assert result.stdout == "import-boundary: ok (3 files)\n"


def test_the_agent_may_import_heavy_packages_and_the_shared_part(tree: Path) -> None:
    plant(tree, "agent", "import aiida.orm\nimport deepagents\nimport janus_core\nimport goldilocks_workbench\n")
    assert run(tree).returncode == 0


@pytest.mark.parametrize("folder", ["workbench", "agent"])
def test_importing_a_form_that_is_not_a_dependency_fails(tree: Path, folder: str) -> None:
    plant(tree, folder, "import goldilocks_chat\n")
    assert run(tree).returncode == 1


@pytest.mark.parametrize("folder", ["workbench", "chat", "agent"])
@pytest.mark.parametrize("module", ["goldilocks_dft", "goldilocks_core.api"])
def test_importing_goldilocks_dft_fails_everywhere(tree: Path, folder: str, module: str) -> None:
    plant(tree, folder, f"import {module}\n")
    assert run(tree).returncode == 1


def test_relative_imports_and_similar_names_pass(tree: Path) -> None:
    plant(tree, "chat", "from . import planted_two\nimport aiidalab_like\nimport torchvision_like\n")
    assert run(tree).returncode == 0


def test_a_package_folder_without_a_rule_fails(tree: Path) -> None:
    (tree / "packages" / "ada" / "src" / "goldilocks_ada").mkdir(parents=True)
    result = run(tree)
    assert result.returncode == 1
    assert "packages/ada: no import rule" in result.stdout


def test_a_file_that_cannot_be_parsed_fails(tree: Path) -> None:
    plant(tree, "workbench", "def broken(:\n")
    result = run(tree)
    assert result.returncode == 1
    assert "cannot be parsed" in result.stdout
