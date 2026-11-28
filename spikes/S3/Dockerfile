# S3 in a Linux container (workbench plan, "S3 submission key through aiida-quantumespresso"): goldilocks-agent's
# locked environment on Debian with Python 3.12 and Debian's Quantum ESPRESSO, so that the caching experiment has a
# real pw.x. Build from the repository root: bash spikes/S3/run_container.sh
FROM python:3.12-slim
# gcc and libc6-dev build pycifrw, and procps gives AiiDA's core.direct scheduler `ps` (S2 found both). Debian's
# quantum-espresso package is the only pw.x here; its version is recorded with the results.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev procps quantum-espresso \
    && rm -rf /var/lib/apt/lists/*
# pw.x is an Open MPI program run without mpirun (one process); Open MPI refuses root unless told.
ENV OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 OMP_NUM_THREADS=1
RUN pip install --no-cache-dir "uv>=0.12.9,<0.14"
WORKDIR /repo
COPY pyproject.toml uv.lock .python-version ./
COPY packages packages
RUN uv sync --locked --all-packages --python /usr/local/bin/python3.12
COPY spikes/S3 spikes/S3
ENV PATH="/repo/.venv/bin:${PATH}" GOLDILOCKS_SPIKES_CACHE=/tmp/goldilocks-spikes
CMD ["python", "spikes/S3/s3_experiments.py", "--bundles", "/bundles", "--out", "/out/linux.jsonl"]
