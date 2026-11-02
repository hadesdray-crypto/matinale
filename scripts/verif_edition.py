"""Matinale : contrôle de l'édition du jour (lancé par .github/workflows/matinale.yml).
  python3 scripts/verif_edition.py            : code retour 0 si l'édition du jour est complète, 1 sinon.
  python3 scripts/verif_edition.py --alerte   : si elle est incomplète, ouvre un signalement GitHub (prévient par e-mail).
Ne bloque jamais la mise en ligne : c'est un contrôle."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edition_sante  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', default='site')
    ap.add_argument('--alerte', action='store_true')
    a = ap.parse_args()
    ok, n, s, msg = edition_sante.etat(a.site)
    print(('OK : ' if ok else 'ALERTE : ') + msg)
    if not ok and a.alerte:
        from liens import signaler
        today = edition_sante.aujourdhui()
        signaler(f"Matinale : l'édition du {today} est incomplète ({n} fiches)",
                 f"{msg}\n\nLe programme a essayé plusieurs fois ce matin (plusieurs modèles Gemini gratuits, demandes par petits lots, "
                 "fiches de secours sans IA) sans atteindre le minimum. Regarde le journal du dernier lancement dans l'onglet Actions "
                 "du dépôt, puis relance « Matinale des Sciences » (Run workflow).")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
