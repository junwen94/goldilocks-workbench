"""A light form's environment holds no heavy or agent-only package, nor the other light form (D1, D35; ada D8;
AGENTS.md, rule 4).

Run with the interpreter of an environment made by `uv sync --locked --package goldilocks-<form> --no-dev`;
tools/check.sh makes one per light form in a temporary folder. Fails if any forbidden distribution is installed or
any forbidden module can be imported, and also if the form's own package or goldilocks_workbench cannot be imported,
so that it cannot pass by running in the wrong environment.
Usage: <form environment>/bin/python tools/checks/light_env.py chat|ada
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
# Each light form, with the other light form, which it must not carry (ada D8).
FORMS = {"chat": "ada", "ada": "chat"}


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def problems(form: str) -> list[str]:
    other = FORMS[form]
    forbidden_distributions = {**FORBIDDEN_DISTRIBUTIONS, f"goldilocks-{other}": f"goldilocks-{other}, another form"}
    forbidden_modules = {**FORBIDDEN_MODULES, f"goldilocks_{other}": f"goldilocks-{other}, another form"}
    found = []
    for module in (f"goldilocks_{form}", "goldilocks_workbench"):
        if importlib.util.find_spec(module) is None:
            found.append(f"{module} cannot be imported: this is not the {form} environment")
    for dist in distributions():
        name = normalise(dist.metadata["Name"] or "")
        if name in forbidden_distributions:
            found.append(f"distribution {name} is installed ({forbidden_distributions[name]})")
            continue
        for prefix, kind in FORBIDDEN_DISTRIBUTION_PREFIXES.items():
            if name.startswith(prefix):
                found.append(f"distribution {name} is installed ({kind})")
    for module, kind in forbidden_modules.items():
        if importlib.util.find_spec(module) is not None:
            found.append(f"module {module} can be imported ({kind})")
    return sorted(set(found))


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in FORMS:
        print(f"usage: light_env.py {'|'.join(FORMS)}")
        return 2
    form = argv[1]
    found = problems(form)
    for line in found:
        print(f"  {line}")
    if found:
        print(f"light-env {form}: the {form} environment has packages that a light form may not have")
        return 1
    print(f"light-env {form}: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
