"""The goldilocks-ada command (D1: one entry point per form). Its commands arrive with their milestones."""

import argparse
from importlib.metadata import version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="goldilocks-ada", description="Goldilocks Workbench, Ada form.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('goldilocks-ada')}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
