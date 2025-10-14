# normalize_usernames.py
# -*- coding: utf-8 -*-
import argparse
import sqlite3
from pathlib import Path

def fetch_users(conn):
    conn.row_factory = sqlite3.Row
    return conn.execute("SELECT id, username FROM user").fetchall()

def normalize(name: str) -> str:
    if name is None:
        return ""
    return name.strip().lower()

def main():
    ap = argparse.ArgumentParser(description="Mettre tous les usernames en minuscules.")
    ap.add_argument("--db", required=True, type=Path, help="Chemin vers la base SQLite (ex.: data/gala.db)")
    ap.add_argument("--dry-run", action="store_true", help="Ne rien écrire, montrer seulement ce qui changerait")
    ap.add_argument("--suffix", action="store_true", help="Résoudre automatiquement les collisions en ajoutant -2, -3, ...")
    args = ap.parse_args()

    if not args.db.exists():
        raise SystemExit(f"DB introuvable: {args.db}")

    with sqlite3.connect(str(args.db)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        rows = fetch_users(conn)

        # Pré-calcul des nouveaux usernames et détection collisions
        desired = {}  # id -> new_username
        counts = {}   # new_username -> number of occurrences
        for r in rows:
            newu = normalize(r["username"])
            desired[r["id"]] = newu
            counts[newu] = counts.get(newu, 0) + 1

        # Collisions à régler?
        collisions = {u for u, n in counts.items() if n > 1}
        if collisions and not args.suffix:
            print("⚠️  Collisions détectées après mise en minuscule :")
            for u in sorted(collisions):
                ids = [r["id"] for r in rows if desired[r["id"]] == u]
                print(f" - '{u}': ids {ids}")
            print("\nAucune modification effectuée. Relancez avec --suffix pour résoudre automatiquement (username-2, -3, ...).")
            return

        # Si --suffix, génère des suffixes uniques
        if collisions and args.suffix:
            used = set()
            # commence avec les existants déjà normalisés pour éviter doublons
            for uid, u in desired.items():
                if counts[u] == 1:
                    used.add(u)
            # assigne des suffixes pour les doublons
            for u in collisions:
                same = [r for r in rows if desired[r["id"]] == u]
                # garder le premier tel quel si libre, suffixer les suivants
                num = 1
                for r in sorted(same, key=lambda x: x["id"]):
                    cand = u if num == 1 and u not in used else None
                    if cand is None:
                        k = 2
                        while True:
                            cand_try = f"{u}-{k}"
                            if cand_try not in used:
                                cand = cand_try
                                break
                            k += 1
                    desired[r["id"]] = cand
                    used.add(cand)
                    num += 1

        # Affichage des changements
        changes = [(r["id"], r["username"], desired[r["id"]]) for r in rows if r["username"] != desired[r["id"]]]
        if not changes:
            print("Aucun changement nécessaire : tous les usernames sont déjà en minuscules.")
            return

        print("Modifications prévues :")
        for uid, old, new in changes:
            print(f" - id {uid}: '{old}' -> '{new}'")

        if args.dry_run:
            print("\n(dry-run) Aucune écriture effectuée.")
            return

        # Appliquer
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE;")
        try:
            for uid, _, new in changes:
                cur.execute("UPDATE user SET username=? WHERE id=?", (new, uid))
            conn.commit()
            print(f"\n✅ Terminé. {len(changes)} username(s) mis à jour.")
        except Exception as e:
            conn.rollback()
            raise

if __name__ == "__main__":
    main()
