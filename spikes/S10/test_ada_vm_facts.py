"""Tests of spikes/S10/ada_vm_facts.sh, on stand-in `ssh`, Slurm and `uname` commands put first on PATH.

They check that the script answers the plan's five items through either route (the VM's own Slurm commands, or SSH),
runs only read-only commands on SCARF, and prints none of the private values it is given or finds.
"""

import getpass
import os
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "ada_vm_facts.sh"
ALIAS = "scarf-secret-alias"
SECRET_URLS = ("https://model.secret.example/v1", "http://dft.secret.example:8000")
# What the stand-ins answer, shared by the local and the remote Slurm commands.
SLURM = """
case $cmd in
  sbatch|sinfo) echo "slurm 23.11.4" ;;
  squeue) exit 0 ;;
  scontrol) printf 'ClusterName = %s\\nMinJobAge = 300 sec\\nSlurmctldHost = %s\\n' \\
    "${FAKE_CLUSTER:-scarf}" "$FAKE_CTLD" ;;
  sacct) printf '2026-01-02T00:00:00\\n2025-03-14T10:00:00\\n' ;;
  printenv) echo /bin/tcsh ;;
  true) exit "${FAKE_SSH_EXIT:-0}" ;;
  *) exit 127 ;;
esac
"""


def standin(folder: Path, name: str, body: str) -> None:
    path = folder / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    """Stand-ins for ssh (logging each remote command) and for `uname -m`, which leaks the alias to test the filter."""
    folder = tmp_path / "bin"
    folder.mkdir()
    ssh = 'if [ "$1" = -V ]; then echo "OpenSSH_9.9p1, stand-in" >&2; exit 0; fi\n'
    ssh += "while [ $# -gt 0 ]; do case $1 in --) shift; break ;; *) shift ;; esac; done\nshift\n"
    ssh += 'echo "$*" >> "$SSH_LOG"\ncmd=$1\n' + SLURM
    standin(folder, "ssh", ssh)
    real_uname = shutil.which("uname")
    assert real_uname is not None
    standin(folder, "uname", f'if [ "$1" = -m ]; then echo "arch-on-{ALIAS}"; else exec {real_uname} "$@"; fi\n')
    return folder


def local_slurm(folder: Path) -> None:
    for name in ("sbatch", "squeue", "sacct", "scancel", "sinfo", "scontrol"):
        standin(folder, name, f"cmd={name}\n" + SLURM)


def run(bin_dir: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    path = os.pathsep.join([str(bin_dir), str(Path(sys.executable).parent), "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SSH_")}
    environment.update({"PATH": path, "SSH_LOG": str(bin_dir / "ssh.log"), "FAKE_CTLD": ALIAS, **env})
    command = ["bash", str(SCRIPT), "--no-network", *args]
    result = subprocess.run(command, capture_output=True, text=True, check=False, env=environment, timeout=120)
    assert result.stderr == "", result.stderr
    return result


def private_values(tmp_path: Path) -> list[str]:
    return [ALIAS, str(tmp_path), "secret.example", getpass.getuser(), socket.gethostname(), str(Path.home())]


def test_an_unknown_option_prints_the_usage(bin_dir: Path) -> None:
    result = subprocess.run(["bash", str(SCRIPT), "--bogus"], capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert result.stdout.startswith("Usage: bash spikes/S10/ada_vm_facts.sh")


def test_the_ssh_route_answers_every_item_and_prints_nothing_private(bin_dir: Path, tmp_path: Path) -> None:
    work_area = tmp_path / "private work area"
    work_area.mkdir()
    urls = ["--model-url", SECRET_URLS[0], "--dft-url", SECRET_URLS[1]]
    result = run(bin_dir, "--ssh-host", ALIAS, "--work-area", str(work_area), *urls)
    assert result.returncode == 0, result.stdout
    out = result.stdout
    for line in (
        "== 1. One user per VM",
        "== 5. Slurm on SCARF",
        "sbatch on the VM: no",
        "ssh in batch mode (no prompt), exit code: 0",
        "remote login shell: tcsh",
        "sbatch over ssh, exit code: 0",
        "cluster name (SSH): scarf",
        "work area exists on the VM: yes",
        "route: SSH",
        "MinJobAge: 300 sec",
        "oldest job sacct shows (year-month): 2025-03",
        "architecture: arch-on-<ssh-host>",
    ):
        assert line in out
    for value in private_values(tmp_path):
        assert value not in out, value


def test_only_read_only_commands_reach_scarf(bin_dir: Path) -> None:
    run(bin_dir, "--ssh-host", ALIAS)
    sent = set((bin_dir / "ssh.log").read_text().splitlines())
    allowed = {
        "true",
        "printenv SHELL",
        "sbatch --version",
        "sinfo --version",
        "scontrol show config",
        "sacct -X -n -P -S 2015-01-01 -o Submit",
    }
    assert sent and sent <= allowed, sent - allowed


def test_the_vms_own_slurm_is_the_first_route(bin_dir: Path) -> None:
    local_slurm(bin_dir)
    result = run(bin_dir)
    out = result.stdout
    assert result.returncode == 0
    for line in ("sbatch on the VM: yes", "cluster name (VM): scarf", "squeue --me (VM), exit code: 0", "route: VM"):
        assert line in out
    assert "ssh to SCARF: not tested (no --ssh-host)" in out
    assert not (bin_dir / "ssh.log").exists()


def test_another_cluster_name_is_not_printed(bin_dir: Path) -> None:
    local_slurm(bin_dir)
    result = run(bin_dir, FAKE_CLUSTER="hidden-cluster-name")
    assert "cluster name (VM): other" in result.stdout
    assert "hidden-cluster-name" not in result.stdout


def test_a_failed_ssh_gives_its_exit_code_and_no_route(bin_dir: Path) -> None:
    result = run(bin_dir, "--ssh-host", ALIAS, FAKE_SSH_EXIT="255")
    out = result.stdout
    assert "ssh in batch mode (no prompt), exit code: 255" in out
    assert "route: none" in out
    assert "remote login shell" not in out


def test_the_script_never_names_key_files_or_prints_ssh_configuration() -> None:
    text = SCRIPT.read_text()
    for needle in (".ssh/", "id_rsa", "id_ed25519", "id_ecdsa", "ssh -G", "ssh -i", "IdentityFile", "known_hosts"):
        assert needle not in text, needle
