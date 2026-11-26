# S10: the Ada platform

The spike of ada D2.3, defined in the Ada plan ([`plan.md`](../../changes/2026-11-26-ada/plan.md), "S10"). It gates
A4 (the `slurm` module) and A5 (Ada on a VM). It needs an Ada login, so the owner runs it.

## Running it

On an Ada VM, with the script copied there (it needs bash only; for example
`curl -fsSLO https://raw.githubusercontent.com/junwen94/goldilocks-workbench/main/spikes/S10/ada_vm_facts.sh`):

```
bash ada_vm_facts.sh --ssh-host <alias> --work-area <path> --model-url <url> --dft-url <url> > s10.txt
```

Every option is optional:

- `--ssh-host`: the name this VM's own SSH configuration gives a SCARF login node. The script tries it in batch
  mode, so it never asks for a password. Leave it out if the Slurm commands work on the VM itself.
- `--work-area`: your SCARF work area, if it may be mounted on the VM.
- `--model-url`, `--dft-url`: a model endpoint and a goldilocks-dft service that Ada might use.
- `--no-network`: skips the HTTPS checks.

It runs only read-only commands on SCARF (`true`, `printenv SHELL`, `sbatch --version`, `sinfo --version`,
`scontrol show config`, `sacct`), and it takes a few seconds.

## What it prints

Generic facts and exit codes, under the plan's five items. It reads nothing under `~/.ssh`, and it prints no host
name, account, path or URL. Its output also passes through a filter that replaces your user name, the VM's host
name, your home folder and every value given in the options with placeholders such as `<user>` and `<ssh-host>`.
In the HTTP checks, any status other than `000` means the service answered; 401 from GHCR is expected without a
login.

## Sending it back

1. Read `s10.txt` before sending it. It should hold no host names, accounts, paths or URLs, only placeholders.
2. Answer the questions in its last section.
3. Paste the output and your answers into the conversation.

Claude then writes the result as `changes/2026-11-26-ada/spikes/S10-ada-platform.md`, with generic facts only.
Anything private, such as host names or the work-area path, goes to ddmms/goldilocks (`AGENTS.md`, rule 8).

## Tests

`test_ada_vm_facts.py` runs the script on stand-in `ssh`, Slurm and `uname` commands. It checks both routes (the
VM's own Slurm, and SSH), that only read-only commands reach SCARF, and that no private value is printed. The check
runs it with the other tests.
