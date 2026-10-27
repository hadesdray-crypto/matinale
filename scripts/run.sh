#!/usr/bin/env bash
# Matinale des Sciences : la préparation de chaque matin (lancée par .github/workflows/matinale.yml).
# Chaque étape a son plan B : si l'une échoue, la page garde ce qui marche et la suite continue.
set -u
cd "$(dirname "$0")/.."

echo "::group::Édition du jour"
python3 -c "import PIL" 2>/dev/null || pip install -q --break-system-packages pillow >/dev/null 2>&1 || true   # réduit les images (facultatif)
python3 scripts/build.py --site site ${MATINALE_FORCE:+--force} > >(tee site/data/build-log.txt) 2>&1 || echo "::warning::L'édition n'a pas pu être mise à jour : la précédente reste en ligne."
echo "::endgroup::"
echo "::group::Politique & monde"
mkdir -p site/data/politique
python3 scripts/politique.py --site site > >(tee site/data/politique/build-log.txt) 2>&1 || echo "::warning::Rubrique Politique & monde non mise à jour : la précédente reste en ligne."
echo "::endgroup::"
# La clé Gemini ne sert qu'à l'édition : les outils audio téléchargés ensuite ne la voient pas.
unset GEMINI_API_KEY

echo "::group::Enregistrement audio (voix française gratuite, hors ligne)"
audio_ok=0
. scripts/voice.sh
if [ "$VOICE_OK" = 1 ]; then
  python3 scripts/make_audio.py --edition site/data/latest.json --tts "$TTS" --voice "$VOICE_DIR" --out site/audio && audio_ok=1
  if [ -f site/data/politique/latest.json ]; then
    python3 scripts/make_audio.py --edition site/data/politique/latest.json --tts "$TTS" --voice "$VOICE_DIR" --out site/audio/politique --prefix audio/politique --modes flash \
      || { rm -f site/audio/politique/audio.json; echo "::warning::Audio Politique & monde non préparé : la voix du téléphone le lira."; }
  fi
  # Audio des notions « Comprendre » : fabriqué seulement pour une notion nouvelle ou modifiée (sinon rien à faire).
  python3 scripts/notions_audio.py --bases site/data/bases.json --tts "$TTS" --voice "$VOICE_DIR" --out site/audio/notions \
    || echo "::warning::Audio des notions non mis à jour : la voix du téléphone les lira."
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
