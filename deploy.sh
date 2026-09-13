#!/usr/bin/env bash
# Reconstruieşte imaginea şi reporneşte serviciul.
#
# Versiunea service worker-ului se calculează din conţinutul lui web/ şi se
# ştampilează în sw.js înainte de build: fără asta telefoanele ar servi la
# nesfârşit versiunea din cache, iar o corectură „implementată" n-ar ajunge
# niciodată la ele.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

V="$(find web -type f -exec sha256sum {} + | sort -k2 | sha256sum | cut -c1-12)"
sed -i -E "s/faceslice-([0-9a-f]{12}|__BUILD_VERSION__)/faceslice-$V/" web/sw.js
echo "versiune web: $V"

podman build -t faceslice:latest -f deploy/Containerfile .
systemctl --user restart faceslice

for _ in $(seq 1 30); do
  sleep 1
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "faceslice pornit, sănătate confirmată"; exit 0
  fi
done
echo "imaginea s-a construit, dar serviciul nu răspunde la /api/health" >&2
exit 1
