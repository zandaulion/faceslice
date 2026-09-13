#!/usr/bin/env bash
# Reconstruieşte imaginea şi reporneşte serviciul.
#
# Versiunea se calculează din conţinutul lui web/ şi se ştampilează în două
# locuri înainte de build.
#
# În sw.js, ca numele cache-ului să se schimbe: fără asta telefoanele ar servi
# la nesfârşit versiunea din cache.
#
# Şi în adresele din index.html, din cauza CDN-ului. Cloudflare cachează .css
# şi .js dar nu şi HTML, aşa că se ajungea la combinaţia cea mai derutantă --
# marcaj nou peste stiluri vechi -- şi nicio reîncărcare n-o repara, fiindcă
# fişierul nou nici nu pleca de la CDN. O adresă care poartă versiunea e alt
# obiect pentru orice cache de pe drum, iar index.html, nefiind cachat, o cere
# imediat. Nu depinde de setările CDN-ului, la care nu avem acces de aici.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

V="$(find web -type f -exec sha256sum {} + | sort -k2 | sha256sum | cut -c1-12)"
sed -i -E "s/faceslice-([0-9a-f]{12}|__BUILD_VERSION__)/faceslice-$V/" web/sw.js
sed -i -E "s/\?v=([0-9a-f]{12}|__BUILD_VERSION__)/?v=$V/g" web/index.html
echo "versiune web: $V"

# Portul şi numele serviciului ţin de maşina pe care rulează, nu de proiect.
PORT="${FACESLICE_PORT:-8000}"
SERVICE="${FACESLICE_SERVICE:-faceslice}"

podman build -t faceslice:latest -f deploy/Containerfile .
systemctl --user restart "$SERVICE"

for _ in $(seq 1 30); do
  sleep 1
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    echo "faceslice pornit, sănătate confirmată"; exit 0
  fi
done
echo "imaginea s-a construit, dar serviciul nu răspunde la /api/health" >&2
exit 1
