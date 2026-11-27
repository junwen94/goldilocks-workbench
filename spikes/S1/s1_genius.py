"""GENIUS's 295 request strings for S1b, fetched at run time and never committed (workbench plan, S1).

GENIUS is KIT-Workflows/agentic-workflow-framework (MIT; Soleymanibrojeni et al. 2026, Communications Materials,
doi:10.1038/s43246-026-01167-0). Its repository ships the results of a 295-request benchmark; independent
researchers wrote the requests. Only the request strings are taken, with each record's formula and database, from a
pinned commit; a sha256 over them checks that the same strings come back.

`label` is the keyword rule that gives each request its expected goldilocks-dft task (owner, 2026-11-26). A request
the rule cannot place gets None, is left out of the score, and is counted.
Usage: uv run python spikes/S1/s1_genius.py [--cache DIR]   (fetches, checks, prints the labels' counts)
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

REPOSITORY = "KIT-Workflows/agentic-workflow-framework"
COMMIT = "83e32acd1c322f800b3ea238c6e9ec07f734ac66"
COUNT = 295
FOLDER = "total results/concat_json"
# sha256 of the requests as `digest` joins them, from the first fetch (2026-11-27).
REQUESTS_SHA256 = "0d3a0e061d0c408da5f026a47ff79272b64245141ca8becac0582c63ac7eb4a7"


@dataclass(frozen=True)
class Request:
    record: int
    request: str
    formula: str
    database: str


def default_cache() -> Path:
    root = Path(os.environ.get("GOLDILOCKS_SPIKES_CACHE", Path.home() / ".cache" / "goldilocks-spikes"))
    return root / "genius" / COMMIT[:7]


def url(record: int) -> str:
    path = urllib.parse.quote(f"{FOLDER}/qe_result_{record}.json")
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/{path}"


def extract(record: int, document: object) -> Request:
    first = document[0] if isinstance(document, list) else document
    if not isinstance(first, dict):
        raise ValueError(f"record {record}: unexpected layout")
    analysis = first.get("analysis_dict") or {}
    return Request(
        record,
        str(first["calculation_description"]),
        str(analysis.get("formula", "")),
        str(analysis.get("database", "")),
    )


def digest(requests: Sequence[Request]) -> str:
    text = "\n".join(f"{r.record}\t{r.request}" for r in sorted(requests, key=lambda r: r.record))
    return hashlib.sha256(text.encode()).hexdigest()


def records() -> list[int]:
    """The record numbers at the pinned commit (0 to 440, with gaps), from GitHub's tree of that commit."""
    tree_url = f"https://api.github.com/repos/{REPOSITORY}/git/trees/{COMMIT}?recursive=1"
    with urllib.request.urlopen(tree_url, timeout=60) as response:
        tree = json.load(response)
    pattern = re.compile(re.escape(FOLDER) + r"/qe_result_(\d+)\.json$")
    found = sorted(int(m.group(1)) for item in tree.get("tree", []) if (m := pattern.match(item.get("path", ""))))
    if len(found) != COUNT or tree.get("truncated"):
        raise ValueError(f"expected {COUNT} records at {COMMIT[:7]}, found {len(found)}")
    return found


def fetch(cache: Path) -> Path:
    """Downloads each record once, keeps only its Request, and writes them all to `cache/requests.jsonl`."""
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "requests.jsonl"
    if target.exists():
        return target
    requests = []
    for record in records():
        with urllib.request.urlopen(url(record), timeout=120) as response:
            requests.append(extract(record, json.load(response)))
        print(f"fetched {len(requests)}/{COUNT}", end="\r", flush=True, file=sys.stderr)
    partial = target.with_suffix(".partial")
    partial.write_text("".join(json.dumps(asdict(r)) + "\n" for r in requests))
    partial.rename(target)
    return target


def load(cache: Path | None = None) -> list[Request]:
    """The 295 requests, fetched if needed, checked against REQUESTS_SHA256."""
    path = fetch(cache or default_cache())
    requests = [Request(**json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
    found = digest(requests)
    if len(requests) != COUNT or (REQUESTS_SHA256 and found != REQUESTS_SHA256):
        raise ValueError(f"GENIUS requests changed: {len(requests)} requests, sha256 {found}")
    return requests


# The rule, written by Claude after reading a sample of the requests (2026-11-27). Phrases are matched in order, on
# the lower-cased request; the first that matches decides. "relaxation" means relax or vc-relax, either accepted:
# most requests ask for a "geometry optimization" without saying whether the cell may move.
STUDY = "study"  # several calculations that vary a setting: left out of the score, like an unlabelled request
RULES: list[tuple[str, str]] = [
    (
        r"\bvary(ing)?\b|\bfrom [\d.]+ (ry )?to [\d.]+|\bsteps? of\b|different (constrain|value)|for each step"
        r"|\bcompar(e|ing)\b|the following [\w\s-]{0,30}(functionals|corrections)",
        STUDY,
    ),
    (r"without changing the (lattice|cell)|fixed (cell|lattice)|atomic positions only", "relax"),
    (r"vc-relax|variable[- ]cell|cell_dofree|lattice (constant|parameter|vector)s?|\bvolume\b", "vc-relax"),
    (
        r"relax|geometry (optimi[sz]|refine)|structural optimi[sz]|optimi[sz]e .{0,40}(geometry|structure)|minimi[sz]",
        "relaxation",
    ),
    (
        r"single[- ](shot|point)|total magneti[sz]ation|total energy|self-consistent field calculation",
        "scf_single_point",
    ),
]
# The tools a step-1 pick must include for each label: one from each group (s1_catalogue's tool IDs).
CALCULATION = {
    "scf_single_point": {"aiida.scf"},
    "relax": {"aiida.relax"},
    "vc-relax": {"aiida.vc_relax"},
    "relaxation": {"aiida.relax", "aiida.vc_relax"},
}


def label(request: str) -> str | None:
    """The request's expected task, or None if the rule cannot place it or it is a study of several calculations."""
    text = request.lower()
    for pattern, task in RULES:
        if re.search(pattern, text):
            return None if task == STUDY else task
    return None


def rule_of(request: str) -> str:
    """Which rule placed the request: its label, "study", or "unlabelled"."""
    text = request.lower()
    return next((task for pattern, task in RULES if re.search(pattern, text)), "unlabelled")


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=default_cache())
    args = parser.parse_args(argv)
    requests = load(args.cache)
    print(f"{len(requests)} requests, sha256 {digest(requests)}")
    counts = Counter(rule_of(r.request) for r in requests)
    for task, n in counts.most_common():
        print(f"{task}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
