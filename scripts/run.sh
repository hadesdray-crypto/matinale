#!/usr/bin/env bash
# Matinale des Sciences : la préparation de chaque matin (lancée par .github/workflows/matinale.yml).
# Chaque étape a son plan B : si l'une échoue, la page garde ce qui marche et la suite continue.
set -u
cd "$(dirname "$0")/.."
TOOLS="${MATINALE_TOOLS:-${RUNNER_TEMP:-/tmp}/matinale-outils}"
SHERPA_VERSION="v1.12.14"
VOICE="vits-piper-fr_FR-siwis-medium"
RELEASES="https://github.com/k2-fsa/sherpa-onnx/releases/download"

echo "::group::Édition du jour"
python3 scripts/build.py --site site ${MATINALE_FORCE:+--force} > >(tee site/data/build-log.txt) 2>&1 || echo "::warning::L'édition n'a pas pu être mise à jour : la précédente reste en ligne."
echo "::endgroup::"

echo "::group::Enregistrement audio (voix française gratuite, hors ligne)"
audio_ok=0
if ! command -v ffmpeg >/dev/null 2>&1; then
  (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg) >/dev/null 2>&1 || true
fi
mkdir -p "$TOOLS/sherpa/bin"
TTS="$TOOLS/sherpa/bin/sherpa-onnx-offline-tts"
if [ ! -x "$TTS" ]; then
  curl -fsSL --retry 3 -o "$TOOLS/sherpa.tar.bz2" "$RELEASES/$SHERPA_VERSION/sherpa-onnx-$SHERPA_VERSION-linux-x64-static.tar.bz2" \
    && tar xjf "$TOOLS/sherpa.tar.bz2" -C "$TOOLS/sherpa" --strip-components=1 "sherpa-onnx-$SHERPA_VERSION-linux-x64-static/bin/sherpa-onnx-offline-tts" \
    || echo "Téléchargement du moteur de voix impossible."
  rm -f "$TOOLS/sherpa.tar.bz2"
fi
if [ ! -f "$TOOLS/$VOICE/tokens.txt" ]; then
  curl -fsSL --retry 3 -o "$TOOLS/voice.tar.bz2" "$RELEASES/tts-models/$VOICE.tar.bz2" \
    && tar xjf "$TOOLS/voice.tar.bz2" -C "$TOOLS" \
    || echo "Téléchargement de la voix impossible."
  rm -f "$TOOLS/voice.tar.bz2"
fi
if [ -x "$TTS" ] && [ -f "$TOOLS/$VOICE/tokens.txt" ] && command -v ffmpeg >/dev/null 2>&1; then
  python3 scripts/make_audio.py --edition site/data/latest.json --tts "$TTS" --voice "$TOOLS/$VOICE" --out site/audio && audio_ok=1
fi
if [ "$audio_ok" != 1 ]; then
  rm -f site/audio/audio.json
  echo "::warning::Audio non préparé aujourd'hui : la page lira l'édition avec la voix du téléphone."
fi
echo "::endgroup::"

if [ -n "${GITHUB_ACTIONS:-}" ]; then
  echo "::group::Sauvegarde de l'édition dans le dépôt"
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add -A
  if git diff --cached --quiet; then
    echo "Rien de nouveau à sauvegarder."
  else
    git commit -q -m "Édition du $(TZ=Europe/Paris date +%F)" && git push -q || echo "::warning::Sauvegarde impossible : le site est quand même publié."
  fi
  echo "::endgroup::"
fi
exit 0
