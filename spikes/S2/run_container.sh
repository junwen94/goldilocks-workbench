#!/bin/bash
# Builds S2's Linux image and runs its experiments in it (not the laptop-sleep test). Results go to a folder outside
# the repository. Usage: bash spikes/S2/run_container.sh [results folder]
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
out="${1:-$HOME/.cache/goldilocks-spikes/s2/results/linux-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$out"
docker build -t goldilocks-s2 -f "$root/spikes/S2/Dockerfile" "$root"
docker run --rm -v "$out":/out goldilocks-s2
echo "results: $out/linux.jsonl"
