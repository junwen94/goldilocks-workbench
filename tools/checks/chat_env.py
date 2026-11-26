"""The chat environment holds no heavy or agent-only package (D1, D35; AGENTS.md, rule 4).

Run with the interpreter of an environment made by `uv sync --locked --package goldilocks-chat --no-dev`;
tools/check.sh makes one in a temporary folder. Fails if any forbidden distribution is installed or any forbidden
module can be imported, and also if goldilocks_chat itself cannot be imported, so that it cannot pass by running in
the wrong environment.
Usage: <chat environment>/bin/python tools/checks/chat_env.py
"""

import importlib.util
import re
import sys
from importlib.metadata import distributions

# Distribution names (normalised as in PEP 503) and the top-level modules they install.
FORBIDDEN_DISTRIBUTIONS = {
    "goldilocks-agent": "agent code",
    "deepagents": "Deep Agents",
    "aiida-core": "AiiDA",
    "aiida-mlip": "MLIP",
    "janus-core": "MLIP",
    "mace-torch": "MLIP",
    "torch": "MLIP",
}
FORBIDDEN_MODULES = {
    "goldilocks_agent": "agent code",
    "deepagents": "Deep Agents",
    "aiida": "AiiDA",
    "aiida_mlip": "MLIP",
    "janus_core": "MLIP",
    "mace": "MLIP",
    "torch": "MLIP",
}
FORBIDDEN_DISTRIBUTION_PREFIXES = {"aiida-": "an AiiDA plugin"}
REQUIRED_MODULES = ("goldilocks_chat", "goldilocks_workbench")


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def problems() -> list[str]:
    found = []
    for module in REQUIRED_MODULES:
        if importlib.util.find_spec(module) is None:
            found.append(f"{module} cannot be imported: this is not the chat environment")
    for dist in distributions():
        name = normalise(dist.metadata["Name"] or "")
        if name in FORBIDDEN_DISTRIBUTIONS:
            found.append(f"distribution {name} is installed ({FORBIDDEN_DISTRIBUTIONS[name]})")
            continue
        for prefix, kind in FORBIDDEN_DISTRIBUTION_PREFIXES.items():
            if name.startswith(prefix):
                found.append(f"distribution {name} is installed ({kind})")
    for module, kind in FORBIDDEN_MODULES.items():
        if importlib.util.find_spec(module) is not None:
            found.append(f"module {module} can be imported ({kind})")
    return sorted(set(found))


def main() -> int:
    found = problems()
    for line in found:
        print(f"  {line}")
    if found:
        print("chat-env: the chat environment has packages that only goldilocks-agent may have")
        return 1
    print("chat-env: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
