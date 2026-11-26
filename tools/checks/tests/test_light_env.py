"""Tests of tools/checks/chat_env.py.

The passing case on the real chat environment runs in tools/check.sh, which builds that environment. Here the
script runs on stand-in environments: Python without site-packages (-S) and a temporary folder on PYTHONPATH with
empty modules and distribution metadata.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "chat_env.py"


def run(*flags: str, path: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the script; it writes nothing to stderr, so anything there is a crash, which would also exit 1."""
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    if path is not None:
        env["PYTHONPATH"] = str(path)
    command = [sys.executable, *flags, str(SCRIPT)]
    result = subprocess.run(command, capture_output=True, text=True, check=False, env=env)
    assert result.stderr == "", result.stderr
    return result


def module(root: Path, name: str) -> None:
    (root / name).mkdir(parents=True, exist_ok=True)
    (root / name / "__init__.py").write_text("")


def distribution(root: Path, name: str, version: str = "1.0") -> None:
    info = root / f"{name.replace('-', '_')}-{version}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n")


@pytest.fixture
def chat_like(tmp_path: Path) -> Path:
    """A stand-in for the chat environment: the two light packages and nothing else."""
    module(tmp_path, "goldilocks_chat")
    module(tmp_path, "goldilocks_workbench")
    distribution(tmp_path, "goldilocks-chat")
    distribution(tmp_path, "goldilocks-workbench")
    return tmp_path


def test_the_full_workspace_environment_fails() -> None:
    result = run()
    assert result.returncode == 1
    for name in ("aiida-core", "deepagents", "janus-core", "aiida-mlip", "goldilocks-agent"):
        assert f"distribution {name} is installed" in result.stdout


def test_an_environment_without_goldilocks_chat_fails() -> None:
    result = run("-S")
    assert result.returncode == 1
    assert "goldilocks_chat cannot be imported: this is not the chat environment" in result.stdout


def test_an_environment_with_only_the_light_packages_passes(chat_like: Path) -> None:
    result = run("-S", path=chat_like)
    assert result.returncode == 0, result.stdout
    assert result.stdout == "chat-env: ok\n"


FORBIDDEN_DISTRIBUTIONS = ["deepagents", "aiida-core", "aiida-pseudo", "Janus_Core", "torch", "goldilocks-agent"]


@pytest.mark.parametrize("name", FORBIDDEN_DISTRIBUTIONS)
def test_a_forbidden_distribution_fails(chat_like: Path, name: str) -> None:
    distribution(chat_like, name)
    assert run("-S", path=chat_like).returncode == 1


@pytest.mark.parametrize("name", ["deepagents", "aiida", "janus_core", "mace", "torch", "goldilocks_agent"])
def test_an_importable_forbidden_module_fails(chat_like: Path, name: str) -> None:
    module(chat_like, name)
    result = run("-S", path=chat_like)
    assert result.returncode == 1
    assert f"module {name} can be imported" in result.stdout
