"""Fetches S3's input bundles from goldilocks-core over HTTP (workbench plan, "S3"; AGENTS.md rule 7).

goldilocks-core 0.3.3, the predecessor's pin (`src/goldilocks_agent/core_pin.json@ea757c7`, stfc/goldilocks-agent),
runs from PyPI in its own environment through uvx, as the predecessor's `src/goldilocks_agent/core_server.py@ea757c7`
runs it; nothing of it is imported here. Every bundle comes from `POST /run` with `respond_with: archive`.

Its HTTP API serves no example structures, so the three structures are the ones bundled with the package, read from the
folder its CLI prints (`goldilocks examples path`). That CLI call and that read are outside rule 7's "over HTTP only";
the owner decides whether to accept them.

Usage: uv run python spikes/S3/s3_core.py [--out DIR]
Writes DIR/<case>.zip, DIR/<case>/ (extracted) and DIR/cases.json. Imports no AiiDA.
"""

import argparse
import hashlib
import io
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import s3_env as e

CORE = "goldilocks-core[http]==0.3.3"
# (name, structure, task, overrides). The overrides are test values for the hand-over, chosen to differ from
# goldilocks-core's defaults so that non-default values are checked too (the plan's round-trip test); they are not
# physics recommendations. si_maxstep1 is the caching experiment's deliberate failure: one SCF step cannot converge.
CASES: list[tuple[str, str, str, dict[str, Any]]] = [
    ("si_scf", "Si.cif", "scf_single_point", {}),
    (
        "si_nondefault",
        "Si.cif",
        "scf_single_point",
        {
            "ecutwfc_ry": 60.0,
            "k_grid": [5, 5, 5],
            "shift": [1, 1, 1],
            "occupations": "smearing",
            "smearing_type": "mp",
            "degauss": 0.02,
            "mixing_beta": 0.3,
            "conv_thr": 1e-10,
            "electron_maxstep": 120,
            "walltime_h": 12,
        },
    ),
    ("si_vcrelax", "Si.cif", "vc-relax", {}),
    ("si_band", "Si.cif", "band", {}),
    ("si_dos", "Si.cif", "dos", {}),
    ("si_phonon", "Si.cif", "phonon", {}),
    ("pt_scf", "Pt_fcc.cif", "scf_single_point", {}),
    ("fe_scf", "Fe_bcc.cif", "scf_single_point", {}),
    ("fe_afm1", "Fe_bcc.cif", "scf_single_point", {"magnetic_ordering": "afm-1"}),
    ("fe_u", "Fe_bcc.cif", "scf_single_point", {"u_by_element": {"Fe": 3.0}, "hubbard_needs_correlation": True}),
    ("si_maxstep1", "Si.cif", "scf_single_point", {"electron_maxstep": 1}),
]


def uvx(*args: str) -> list[str]:
    return ["uvx", "--from", CORE, "goldilocks", *args]


def examples_folder() -> Path:
    result = subprocess.run(uvx("examples", "path"), capture_output=True, text=True, check=True, timeout=600)
    return Path(result.stdout.strip().splitlines()[-1])


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def request(port: int, path: str, body: dict[str, Any] | None = None, timeout: float = 600) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return int(response.status), bytes(response.read())
    except urllib.error.HTTPError as error:
        return int(error.code), bytes(error.read())


def wait_ready(port: int, server: subprocess.Popen[bytes], timeout: float = 600) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("goldilocks-core exited before it was ready")
        try:
            if request(port, "/ready", timeout=5)[0] == 200:
                return
        except OSError:
            pass
        time.sleep(1)
    raise TimeoutError(f"goldilocks-core was not ready within {timeout} s")


def fetch(out: Path) -> list[dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    structures = examples_folder()
    port = free_port()
    log = (out / "core.log").open("w")
    server = subprocess.Popen(uvx("serve", "http", "--host", "127.0.0.1", "--port", str(port)), stdout=log, stderr=log)
    cases = []
    try:
        wait_ready(port, server)
        for name, structure, task, overrides in CASES:
            body = {
                "structure_content": (structures / structure).read_text(),
                "structure_name": structure.removesuffix(".cif"),
                "structure_format": "cif",
                "task": task,
                "overrides": overrides,
                "respond_with": "archive",
            }
            status, data = request(port, "/run", body)
            entry: dict[str, Any] = {"case": name, "structure": structure, "task": task, "overrides": overrides}
            if status != 200:
                cases.append({**entry, "status": status, "error": data[:2000].decode(errors="replace")})
                continue
            (out / f"{name}.zip").write_bytes(data)
            zipfile.ZipFile(io.BytesIO(data)).extractall(out / name)
            manifest = json.loads((out / name / "goldilocks.json").read_text())
            cases.append(
                {
                    **entry,
                    "status": status,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "core_version": manifest["request"]["core_version"],
                    "steps": manifest["steps"],
                }
            )
    finally:
        server.terminate()
        try:
            server.wait(30)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()
    (out / "cases.json").write_text(json.dumps(cases, indent=1))
    return cases


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=e.ROOT / "bundles")
    args = parser.parse_args(argv)
    for case in fetch(args.out):
        print(case["case"], case["status"], case.get("core_version", case.get("error", ""))[:200])
    print(f"bundles: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
