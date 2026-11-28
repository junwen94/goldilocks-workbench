#!/bin/bash
# Builds S3's Linux image and runs its experiments in it, on the bundles s3_core.py fetched on the host (goldilocks-core
# is not installed in the image). Results go to a folder outside the repository.
# Usage: bash spikes/S3/run_container.sh [bundles folder] [results folder] [experiments, comma-separated]
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
bundles="${1:-$HOME/.cache/goldilocks-spikes/s3/bundles}"
out="${2:-$HOME/.cache/goldilocks-spikes/s3/results/linux-$(date +%Y%m%d-%H%M%S)}"
only="${3:-key,kills,tasks,roundtrip,handlers,caching}"
mkdir -p "$out"
docker build -t goldilocks-s3 -f "$root/spikes/S3/Dockerfile" "$root"
docker run --rm -v "$bundles":/bundles:ro -v "$out":/out goldilocks-s3 \
  python spikes/S3/s3_experiments.py --bundles /bundles --out /out/linux.jsonl --only "$only"
echo "results: $out/linux.jsonl"
