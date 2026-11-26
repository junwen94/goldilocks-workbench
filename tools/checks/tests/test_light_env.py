"""Tests of tools/checks/light_env.py.

The passing cases on the real chat and Ada environments run in tools/check.sh, which builds those environments.
Here the script runs on stand-in environments: Python without site-packages (-S) and a temporary folder on
PYTHONPATH with empty modules and distribution metadata.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "light_env.py"
FORMS = ["chat", "ada"]
OTHER = {"chat": "ada", "ada": "chat"}


def run(*args: str, flags: tuple[str, ...] = (), path: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the script; it writes nothing to stderr, so anything there is a crash, which would also exit 1."""
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    if path is not None:
        env["PYTHONPATH"] = str(path)
    command = [sys.executable, *flags, str(SCRIPT), *args]
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


def light_like(root: Path, form: str) -> Path:
    """A stand-in for a light form's environment: its package, the shared package and nothing else."""
    module(root, f"goldilocks_{form}")
    module(root, "goldilocks_workbench")
    distribution(root, f"goldilocks-{form}")
    distribution(root, "goldilocks-workbench")
    return root


@pytest.mark.parametrize("args", [(), ("agent",), ("chat", "ada")])
def test_a_missing_or_unknown_form_is_a_usage_error(args: tuple[str, ...]) -> None:
    result = run(*args)
    assert result.returncode == 2
    assert result.stdout == "usage: light_env.py chat|ada\n"


@pytest.mark.parametrize("form", FORMS)
def test_the_full_workspace_environment_fails(form: str) -> None:
    result = run(form)
    assert result.returncode == 1
    names = ("aiida-core", "deepagents", "janus-core", "aiida-mlip", "goldilocks-agent", f"goldilocks-{OTHER[form]}")
    for name in names:
        assert f"distribution {name} is installed" in result.stdout


@pytest.mark.parametrize("form", FORMS)
def test_an_environment_without_the_form_fails(form: str) -> None:
    result = run(form, flags=("-S",))
    assert result.returncode == 1
    assert f"goldilocks_{form} cannot be imported: this is not the {form} environment" in result.stdout


@pytest.mark.parametrize("form", FORMS)
def test_the_other_light_forms_environment_fails(tmp_path: Path, form: str) -> None:
    result = run(form, flags=("-S",), path=light_like(tmp_path, OTHER[form]))
    assert result.returncode == 1
    assert f"goldilocks_{form} cannot be imported" in result.stdout


@pytest.mark.parametrize("form", FORMS)
def test_an_environment_with_only_the_light_packages_passes(tmp_path: Path, form: str) -> None:
    result = run(form, flags=("-S",), path=light_like(tmp_path, form))
    assert result.returncode == 0, result.stdout
    assert result.stdout == f"light-env {form}: ok\n"


FORBIDDEN_DISTRIBUTIONS = ["deepagents", "aiida-core", "aiida-pseudo", "Janus_Core", "torch", "goldilocks-agent"]


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("name", FORBIDDEN_DISTRIBUTIONS)
def test_a_forbidden_distribution_fails(tmp_path: Path, form: str, name: str) -> None:
    root = light_like(tmp_path, form)
    distribution(root, name)
    assert run(form, flags=("-S",), path=root).returncode == 1


@pytest.mark.parametrize("form", FORMS)
def test_the_other_light_form_as_a_distribution_fails(tmp_path: Path, form: str) -> None:
    root = light_like(tmp_path, form)
    distribution(root, f"goldilocks-{OTHER[form]}")
    result = run(form, flags=("-S",), path=root)
    assert result.returncode == 1
    assert f"distribution goldilocks-{OTHER[form]} is installed" in result.stdout


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("name", ["deepagents", "aiida", "janus_core", "mace", "torch", "goldilocks_agent"])
def test_an_importable_forbidden_module_fails(tmp_path: Path, form: str, name: str) -> None:
    root = light_like(tmp_path, form)
    module(root, name)
    result = run(form, flags=("-S",), path=root)
    assert result.returncode == 1
    assert f"module {name} can be imported" in result.stdout


@pytest.mark.parametrize("form", FORMS)
def test_the_other_light_form_as_a_module_fails(tmp_path: Path, form: str) -> None:
    root = light_like(tmp_path, form)
    module(root, f"goldilocks_{OTHER[form]}")
    result = run(form, flags=("-S",), path=root)
    assert result.returncode == 1
    assert f"module goldilocks_{OTHER[form]} can be imported (goldilocks-{OTHER[form]}, another form)" in result.stdout
