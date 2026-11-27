# S2 in a Linux container (workbench plan, "S2 AiiDA on the desktop"): goldilocks-agent's locked environment on
# Debian with Python 3.12, running S2's experiments except the laptop-sleep test. Build from the repository root:
#   bash spikes/S2/run_container.sh
FROM python:3.12-slim
# pycifrw (from aiida-core[atomic-tools]) has no wheel for Linux arm64 and Python 3.12, so it is compiled (S2 found
# this; M10's image needs a compiler in its build stage, or a prebuilt wheel). AiiDA's core.direct scheduler lists
# jobs with `ps`, which the slim image lacks: without procps every job looked finished at once and its parser failed
# with exit 320 (S2's first Linux run).
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev procps && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "uv>=0.12.9,<0.14"
WORKDIR /repo
COPY pyproject.toml uv.lock .python-version ./
COPY packages packages
RUN uv sync --locked --all-packages --python /usr/local/bin/python3.12
COPY spikes/S2 spikes/S2
ENV PATH="/repo/.venv/bin:${PATH}" GOLDILOCKS_SPIKES_CACHE=/tmp/goldilocks-spikes
CMD ["python", "spikes/S2/s2_experiments.py", "--out", "/out/linux.jsonl"]
