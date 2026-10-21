# Matinale des Sciences — version gratuite, sans Claude et sans compte

Ce paquet contient toute l'application : le site, la préparation automatique de chaque matin, l'audio et le mode d'emploi.
Une fois installé sur ton GitHub, tout tourne tout seul et gratuitement : pas d'abonnement, pas de compte pour lire.

**Ce que tu obtiens**

- Ton site à toi : `https://hadesdray-crypto.github.io/matinale/` (si le dépôt s'appelle `matinale`).
- Une icône sur ton téléphone : la Matinale s'ouvre comme une application, en plein écran, même sans réseau (dernière édition gardée).
- Une nouvelle édition chaque matin vers 5 h (heure de Paris), préparée automatiquement par GitHub.
- L'audio du jour avec une voix française (il continue écran éteint), les vidéos des chaînes francophones, l'archive des éditions.
- Deux niveaux de qualité :
  - **sans clé** : chaque fiche reprend le titre et le résumé publiés par la source, avec le lien vers l'article. Le niveau de preuve est affiché « Non évalué » ;
  - **avec la clé Gemini gratuite** (Google AI Studio) : résumés en français, niveau de preuve proposé, vidéos liées aux fiches, sources en anglais traduites. Une phrase de l'IA qui contient un chiffre absent de l'article est retirée automatiquement.

Les liens viennent toujours des flux des sources elles-mêmes (jamais inventés), et chaque lien est vérifié le matin même : un lien mort est écarté.

---

## Installation depuis ton téléphone Android (environ 10 minutes, une seule fois)

Fais tout dans **Chrome**, connecté à ton compte GitHub `hadesdray-crypto`.

**Étape 1 — Créer le dépôt**
1. Ouvre `https://github.com/new`.
2. *Repository name* : `matinale`.
3. Choisis **Public** (obligatoire pour que ce soit gratuit).
4. Coche **Add a README file**.
5. Touche **Create repository**.

**Étape 2 — Autoriser la publication du site**
1. Dans le dépôt : **Settings** (menu ⋯ si besoin) → **Pages**.
2. Sous *Build and deployment*, *Source* : choisis **GitHub Actions**.

**Étape 3 (facultative, recommandée) — La clé Gemini gratuite**
1. Ouvre `https://aistudio.google.com/apikey` → **Create API key** → copie la clé.
2. Dans le dépôt : **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
3. *Name* : `GEMINI_API_KEY` ; *Secret* : colle la clé → **Add secret**.

La clé ne se colle **que** là : jamais dans un fichier, jamais dans une conversation.
Sans clé, la Matinale fonctionne quand même (version sans IA). Tu peux l'ajouter plus tard.

**Étape 4 — Créer le fichier d'automatisation**
1. Onglet **Code** → **Add file** → **Create new file**.
2. Nom du fichier : `.github/workflows/matinale.yml` (tape-le tel quel, avec les barres `/`).
3. Colle exactement le texte de la section « Fichier d'automatisation » plus bas.
4. Touche **Commit changes…** puis **Commit changes**.

**Étape 5 — Envoyer le paquet**
1. Onglet **Code** → **Add file** → **Upload files**.
2. Choisis le fichier **`matinale.zip`** tel quel (ne le décompresse pas).
3. Touche **Commit changes**.

L'installation démarre toute seule : onglet **Actions**, un rond jaune tourne, puis une coche verte après 3 à 6 minutes.

**Étape 6 — Mettre l'icône sur ton téléphone**
1. Ouvre `https://hadesdray-crypto.github.io/matinale/` dans Chrome.
2. Touche **Installer** sur le bandeau de la Matinale (ou menu ⋮ → **Installer l'application**).

C'est fini : chaque matin, l'édition se met à jour toute seule.

### Si quelque chose coince
- **Rien ne démarre après l'étape 5** : onglet **Actions** → **Matinale des Sciences** → **Run workflow** → **Run workflow**.
- **Croix rouge sur « publication »** : l'étape 2 n'a pas été faite. Fais-la, puis ouvre le passage en rouge et touche **Re-run all jobs**.
- **Message « Le paquet est absent »** : le fichier `matinale.zip` n'a pas été envoyé à la racine du dépôt. Refais l'étape 5.
- **Pour voir ce qui s'est passé un matin** : onglet **Actions** → le passage du jour → résumé (nombre de fiches, sources lues, mode).

### Mettre à jour plus tard
Pour installer une nouvelle version du paquet, refais seulement l'étape 5 avec le nouveau `matinale.zip` : tes éditions et ton archive sont conservées.

---

## Fichier d'automatisation (à coller à l'étape 4)

```yaml
# Matinale des Sciences : prépare l'édition chaque matin et publie le site sur GitHub Pages.
# Se lance tout seul chaque matin, dès qu'un fichier .zip est envoyé à la racine du dépôt,
# ou à la main : onglet Actions > Matinale des Sciences > Run workflow.
name: Matinale des Sciences

on:
  schedule:
    - cron: "17 3 * * *"   # 3 h 17 UTC, soit 5 h 17 à Paris en été et 4 h 17 en hiver
  workflow_dispatch:
  push:
    paths:
      - "*.zip"

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: matinale
  cancel-in-progress: false

jobs:
  edition:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v5

      - name: Installer le paquet envoyé (fichier .zip)
        run: |
          for z in *.zip; do
            [ -f "$z" ] || continue
            echo "Installation de $z"
            if [ -f site/data/latest.json ]; then
              unzip -o -q "$z" -x '.github/*' 'site/data/*' 'site/audio/*'
            else
              unzip -o -q "$z" -x '.github/*'
            fi
            git rm -q --cached "$z" 2>/dev/null || true
            rm -f "$z"
          done
          test -f scripts/run.sh || { echo "::error::Le paquet est absent : envoie le fichier matinale.zip à la racine du dépôt."; exit 1; }

      - name: Garder les outils audio d'un jour sur l'autre
        uses: actions/cache@v4
        with:
          path: ${{ runner.temp }}/matinale-outils
          key: matinale-voix-sherpa-v1.12.14-siwis

      - name: Préparer l'édition du jour, l'audio et l'archive
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: bash scripts/run.sh

      - uses: actions/upload-pages-artifact@v4
        with:
          path: site

  publication:
    needs: edition
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - id: deploy
        uses: actions/deploy-pages@v4
```

---

## Note technique (pour Claude ou toute autre IA à qui ce paquet est confié)

**Objectif de l'utilisateur** : une Matinale des Sciences en français, sérieuse, sans erreur, avec uniquement des liens vérifiés,
qui fonctionne toute seule chaque matin, gratuitement, sans compte Claude ni abonnement. Il veut que tout « marche directement » :
quand un chemin échoue, l'autre prend le relais automatiquement, et **aucun message ne doit l'envoyer ailleurs** (seulement « Réessayer »).
Il installe depuis un téléphone Android. Compte GitHub : `hadesdray-crypto`, dépôt prévu : `matinale` (public).

**Installation** : si tu peux pousser sur GitHub (git), pousse tous les fichiers du paquet tels quels, y compris
`.github/workflows/matinale.yml` (le zip devient inutile), puis fais régler *Settings → Pages → Source : GitHub Actions* et,
s'il le souhaite, le secret `GEMINI_API_KEY`. Sinon, guide-le étape par étape avec la section « Installation » ci-dessus.
Ne demande jamais la clé Gemini dans la conversation.

**Organisation**
- `site/` : le site statique publié sur GitHub Pages. `index.html` (application complète, un seul fichier), `sw.js` (hors ligne :
  dès la première ouverture, garde la page, les polices, la dernière édition et les 7 précédentes ; réseau d'abord mais 2,5 à 3 s
  au plus, sinon la copie du téléphone ; l'audio n'est pas gardé, la voix du téléphone prend le relais), `fonts/` (Syne, Spectral,
  DM Mono rangées avec l'appli, licence SIL OFL : aucune ressource externe au démarrage), `manifest.webmanifest` et `icons/` (installation comme application), `data/latest.json` (édition du jour + annuaire + archive),
  `data/editions/AAAA-MM-JJ.json` (anciennes éditions), `data/archive.json`, `audio/` (préparé chaque matin, non versionné).
- `scripts/build.py` : prépare l'édition (bibliothèque standard Python uniquement). Flux RSS/Atom de `scripts/sources.json`
  (plan B : découverte automatique du flux sur la page d'accueil), tri, doublons, catégories, vidéos YouTube des chaînes de
  `scripts/francophonie.json`, Gemini facultatif (modèles essayés dans l'ordre : `gemini-flash-latest`, `gemini-2.5-flash`,
  puis les versions *lite* ; variable `GEMINI_MODEL` pour en imposer un), vérification des liens, écriture de `site/data/`.
  Si moins de 3 fiches vérifiées : l'édition précédente reste en ligne. Une édition du jour rédigée à la main (sans champ
  `generator`) n'est jamais écrasée sans `--force`.
- `scripts/make_audio.py` : audio `flash.mp3` + `full.mp3` + `audio.json` (chapitres horodatés), voix Piper `fr_FR-siwis-medium`
  via sherpa-onnx v1.12.14 (téléchargés depuis les versions GitHub de k2-fsa/sherpa-onnx, mis en cache par le workflow) et ffmpeg.
- `scripts/run.sh` : enchaîne édition → audio → sauvegarde (commit des données, ce qui garde aussi le workflow planifié actif).
- `.github/workflows/matinale.yml` : chaque jour à 3 h 17 UTC, à l'envoi d'un `.zip` à la racine (installé puis supprimé ; les données
  existantes sont conservées), ou à la main. Publie `site/` avec `actions/upload-pages-artifact` + `actions/deploy-pages`.
- `.github/workflows/mise-en-ligne.yml` : quand le code du site change (tout `site/` sauf `site/data/`), republie le site sans
  refaire l'édition du jour, en reprenant l'audio du jour déjà en ligne.

**Format d'une édition** (`data/latest.json` → `edition`) : `date`, `number`, `title`, `intro`, `period`, `top`, `items[]`,
`categories{cat: {summary}}`, `podcast{intro, outro, flashIntro, flashOutro, franco}`, `francophonie{intro, highlights[], videos[]}`,
`updatedAt`, `generator` (`rss` | `gemini` ; absent = rédigée à la main). Une fiche : `id`, `cat` (espace, sante, cerveau, physique,
terre, vivant, archeo, tech), `date`, `title`, `dek`, `body[]`, `why`, `evidence{level 0-4, type, status, reviewed, note}`,
`sources[{kind: officiel|presse|etude, label, url}]`, `videos[{url, title, by, date, kind, lang, platform, note}]`, `sure[]`,
`unsure[]`, `flash`, `audio` (facultatif), `health`, `videoQuery`.
Niveaux de preuve : 4 Établi · 3 Solide · 2 Préliminaire · 1 Hypothèse · 0 Non évalué.

**Essayer en local** : `python3 scripts/build.py --site site --no-ai` puis `python3 -m http.server -d site 8000`
et ouvrir `http://localhost:8000/`.

**Plus tard (Play Store)** : le site est une application web installable ; elle peut être emballée pour le Play Store
(Trusted Web Activity, par exemple avec PWABuilder ou Bubblewrap).
