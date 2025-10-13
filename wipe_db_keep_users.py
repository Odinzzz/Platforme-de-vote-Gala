# -*- coding: utf-8 -*-
"""
Wipe (nettoyage) des données Gala tout en conservant les utilisateurs/roles.

Par défaut, on conserve aussi les compagnies et les catégories pour éviter
une perte de données non voulue. Vous pouvez forcer leur suppression avec
les options correspondantes.

Exemples
--------
# Conserver users/roles/personnes/juge, ET garder compagnies & catégories
python wipe_db_keep_users.py --db data/gala.db

# Conserver users/roles/personnes/juge, mais supprimer compagnies et catégories
python wipe_db_keep_users.py --db data/gala.db --drop-companies --drop-categories

# Mode simulation
python wipe_db_keep_users.py --db data/gala.db --dry-run
"""
from __future__ import annotations
import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, List

# Tables user à CONSERVER absolument
KEEP_TABLES = {"role", "personne", "user", "juge"}

# Tables effaçables (ordre respectant les FK)
LEAF_FIRST_ORDER = [
    "note",                    # FK -> juge, participant, question
    "reponse_participant",    # FK -> participant, question
    "juge_gala_submission",   # FK -> juge, gala
    "gala_lock",              # FK -> gala, user
    "juge_gala_categorie",    # FK -> juge, gala_categorie
    "participant",            # FK -> compagnie, gala_categorie, segment
    "question",               # FK -> gala_categorie
    "segment",                # FK -> gala_categorie
    "gala_categorie",         # FK -> gala, categorie
    # "compagnie",            # (optionnel)
    # "categorie",            # (optionnel)
    # "gala",                 # (optionnel)
]


def wipe(conn: sqlite3.Connection, drop_companies: bool, drop_categories: bool, drop_galas: bool, dry_run: bool) -> None:
    # Construire la liste finale à supprimer dans l'ordre
    to_wipe: List[str] = list(LEAF_FIRST_ORDER)
    if drop_companies and "compagnie" not in to_wipe:
        to_wipe.append("compagnie")
    if drop_categories and "categorie" not in to_wipe:
        to_wipe.append("categorie")
    if drop_galas and "gala" not in to_wipe:
        to_wipe.append("gala")

    # Sanity: ne jamais inclure les tables à garder
    for t in to_wipe:
        if t in KEEP_TABLES:
            raise RuntimeError(f"Sélection invalide: tentative d'effacer {t} qui est protégé.")

    print("Tables ciblées (dans l'ordre):", to_wipe)

    conn.execute("PRAGMA foreign_keys = ON;")
    if dry_run:
        print("[DRY-RUN] Aucune modification écrite.")
        return

    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE;")
    try:
        for table in to_wipe:
            cur.execute(f"DELETE FROM {table};")
        # Reset des autoincrements pour les tables supprimées
        for table in to_wipe:
            cur.execute("DELETE FROM sqlite_sequence WHERE name=?;", (table,))
        conn.commit()
        print("✅ Wipe terminé.")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--drop-companies", action="store_true", help="Supprimer aussi la table compagnie")
    ap.add_argument("--drop-categories", action="store_true", help="Supprimer aussi la table categorie")
    ap.add_argument("--drop-galas", action="store_true", help="Supprimer aussi la table gala")
    ap.add_argument("--dry-run", action="store_true", help="Simulation sans écrire")
    args = ap.parse_args()

    if not args.db.exists():
        raise SystemExit(f"DB introuvable: {args.db}")

    with sqlite3.connect(str(args.db)) as conn:
        wipe(
            conn,
            drop_companies=args.drop_companies,
            drop_categories=args.drop_categories,
            drop_galas=args.drop_galas,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
