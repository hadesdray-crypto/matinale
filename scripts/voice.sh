#!/usr/bin/env bash
# Matinale des Sciences : installe (une fois, puis gardé en cache) la voix française gratuite et hors ligne.
# À « sourcer » : définit TTS (moteur sherpa-onnx) et VOICE_DIR (voix Piper fr_FR-siwis-medium), et VOICE_OK=1 si tout est prêt.
TOOLS="${MATINALE_TOOLS:-${RUNNER_TEMP:-/tmp}/matinale-outils}"
SHERPA_VERSION="v1.12.14"
VOICE="vits-piper-fr_FR-siwis-medium"
RELEASES="https://github.com/k2-fsa/sherpa-onnx/releases/download"
VOICE_OK=0
if ! command -v ffmpeg >/dev/null 2>&1; then
  (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg) >/dev/null 2>&1 || true
fi
mkdir -p "$TOOLS/sherpa/bin"
TTS="$TOOLS/sherpa/bin/sherpa-onnx-offline-tts"
VOICE_DIR="$TOOLS/$VOICE"
if [ ! -x "$TTS" ]; then
  curl -fsSL --retry 3 -o "$TOOLS/sherpa.tar.bz2" "$RELEASES/$SHERPA_VERSION/sherpa-onnx-$SHERPA_VERSION-linux-x64-static.tar.bz2" \
    && tar xjf "$TOOLS/sherpa.tar.bz2" -C "$TOOLS/sherpa" --strip-components=1 "sherpa-onnx-$SHERPA_VERSION-linux-x64-static/bin/sherpa-onnx-offline-tts" \
    || echo "Téléchargement du moteur de voix impossible."
  rm -f "$TOOLS/sherpa.tar.bz2"
fi
if [ ! -f "$VOICE_DIR/tokens.txt" ]; then
  curl -fsSL --retry 3 -o "$TOOLS/voice.tar.bz2" "$RELEASES/tts-models/$VOICE.tar.bz2" \
    && tar xjf "$TOOLS/voice.tar.bz2" -C "$TOOLS" \
    || echo "Téléchargement de la voix impossible."
  rm -f "$TOOLS/voice.tar.bz2"
fi
if [ -x "$TTS" ] && [ -f "$VOICE_DIR/tokens.txt" ] && command -v ffmpeg >/dev/null 2>&1; then VOICE_OK=1; fi
