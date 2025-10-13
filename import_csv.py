# -*- coding: utf-8 -*-
"""
Importe un CSV de candidatures dans la base SQLite (schéma Gala CCEP).

Usage:
    python import_csv.py --csv donnees.csv --gala "Soirée Distinction" --annee 2025 \
        --lieu "Portneuf" --date "2025-11-15" [--db data/gala.db]

Fonctions clés :
- Crée la base si absente via init_db.py (si exposé).
- Assure gala, catégories, liaisons gala_categorie, questions (idempotent).
- Crée/MAJ les compagnies et crée 1 participant par catégorie choisie.
- Insère les réponses aux questions par catégorie **et** aux 2 questions « générales ».
- Tolère des variantes d'orthographe (accents/typos) pour les catégories.

Notes :
- Les catégories de participation peuvent venir d'un champ JSON unique (liste) OU
  de deux colonnes (q18 et q26/historique Google Forms).
- Catégories importées :
  Contribution au développement économique et régional, Contribution à la Vitalité locale,
  Développement durable et engagement environnemental, Entrepreneuriat collectif, Innovation,
  Jeune entreprise, Rayonnement de Portneuf à l’extérieur de la région, Repreneuriat,
  RH – Meilleures pratiques
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import unicodedata

# =========================================
#  DB bootstrap
# =========================================
try:
    # Votre init_db.py doit idéalement exposer init_database() et DB_FILE
    from init_db import init_database, DB_FILE as DEFAULT_DB  # type: ignore
except Exception:
    init_database = None  # type: ignore
    DEFAULT_DB = Path("data")/"gala.db"  # fallback

# =========================================
#  Helpers de normalisation
# =========================================

def norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).strip()
    s = re.sub(r"\s+", " ", s)
    return s

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def keyify(s: str) -> str:
    return strip_accents(norm(s)).lower()

# =========================================
#  Catégories ciblées & questions (doivent correspondre aux en-têtes CSV)
# =========================================
TARGET_CATEGORIES = [
    "Contribution au développement économique et régional",
    "Contribution à la Vitalité locale",
    "Développement durable et engagement environnemental",
    "Entrepreneuriat collectif",
    "Innovation",
    "Jeune entreprise",
    "Rayonnement de Portneuf à l’extérieur de la région",
    "Repreneuriat",
    "RH – Meilleures pratiques",
]

# Alias tolérants (orthographes/abréviations usuelles) → nom canonique
# Comparaison faite en minuscule sans accents
CATEGORY_ALIASES: Dict[str, str] = {
    # Repreneuriat
    "reprenariat": "Repreneuriat",
    "repreneuriat": "Repreneuriat",
    "repreunariat": "Repreneuriat",
    # Rayonnement
    "rayonnement hors region": "Rayonnement de Portneuf à l’extérieur de la région",
    "rayonnement de portneuf a l'exterieur de la region": "Rayonnement de Portneuf à l’extérieur de la région",
    "rayonnement de portneuf a l exterieur de la region": "Rayonnement de Portneuf à l’extérieur de la région",
    # Développement durable
    "developpement durable": "Développement durable et engagement environnemental",
    "developpement durable et engagement environnemental": "Développement durable et engagement environnemental",
    # Vitalité locale
    "contribution a la vitalite locale": "Contribution à la Vitalité locale",
    # Développement éco & régional
    "contribution au developpement economique et regional": "Contribution au développement économique et régional",
}

CATEGORY_QUESTIONS: Dict[str, List[str]] = {
    "RH – Meilleures pratiques": [
        "Quelles sont les principales stratégies mises en place pour améliorer la gestion des ressources humaines dans votre organisation?",
        "Comment favorisez-vous la conciliation travail-vie personnelle pour vos employés?",
        "Avez-vous intégré des saines habitudes de vie dans votre milieu de travail? Si oui, lesquelles?",
        "Comment gérez-vous le recrutement et la rétention de votre personnel?",
        "Votre entreprise emploie-t-elle des travailleurs immigrants? Quels défis et opportunités cela représente-t-il pour vous?",
        "Avez-vous mis en place des initiatives pour contribuer à la pénurie de logements dans la région?",
        "Réalisez-vous des sondages ou des consultations auprès de vos employés? Comment ces résultats influencent-ils vos décisions en RH?",
    ],
    "Jeune entreprise": [
        "Comment est née votre entreprise?",
        "Quels défis majeurs avez-vous rencontrés et comment les avez-vous surmontés?",
        "Quels sont vos projets à court et long terme pour assurer la pérennité de votre entreprise?",
        "Décrivez les mécanismes de transfert ou d'acquisition de connaissances mis en place.",
    ],
    "Contribution à la Vitalité locale": [
        "De quelle façon votre entreprise ou initiative contribue-t-elle au dynamisme de la communauté?",
        "Avez-vous des partenariats locaux qui renforcent votre impact?",
        "Quels sont les retombées économiques, sociales ou culturelles de votre projet?",
        "Comment votre initiative répond-elle aux besoins spécifiques des citoyens de Portneuf?",
        "Avez-vous mis en place des projets qui encouragent l’engagement citoyen?",
    ],
    "Développement durable et engagement environnemental": [
        "Quelles actions concrètes votre entreprise a-t-elle mises en place pour réduire son empreinte écologique?",
        "Comment intégrez-vous les principes du développement durable dans votre gestion quotidienne?",
        "Avez-vous développé des produits ou services innovants en matière d’environnement?",
        "Comment votre entreprise sensibilise-t-elle ses employés et sa clientèle aux enjeux environnementaux?",
        "Avez-vous des certifications ou des reconnaissances en matière de développement durable?",
    ],
    "Contribution au développement économique et régional": [
        "Comment votre entreprise ou organisme contribue-t-il à la croissance économique de Portneuf?",
        "En quoi votre projet améliore-t-il la qualité de vie des citoyens?",
        "Avez-vous créé ou maintenu des emplois dans la région? Si oui, combien? Expliquez au besoin.",
        "Comment mettez-vous en valeur l’expertise locale dans vos activités?",
        "Avez-vous contribué au développement de créneaux spécifiques qui renforcent l’économie régionale?",
    ],
    "Entrepreneuriat collectif": [
        "Quelle est la mission de votre entreprise ou organisme d’économie sociale?",
        "Comment votre modèle de gestion participatif influence-t-il votre prise de décision?",
        "Quels sont les impacts économiques et sociaux de votre initiative sur la communauté?",
        "Comment assurez-vous la pérennité de votre projet tout en respectant vos valeurs collectives?",
        "Quelles collaborations avez-vous établies pour maximiser votre impact dans la région?",
    ],
    "Rayonnement de Portneuf à l’extérieur de la région": [
        "Comment votre entreprise ou organisation contribue-t-elle au rayonnement de Portneuf hors de la région?",
        "Quels marchés ou réseaux avez-vous réussi à atteindre au-delà de la région?",
        "Avez-vous reçu des distinctions ou des reconnaissances à l’échelle provinciale, nationale ou internationale?",
        "Comment votre projet met-il en valeur l’expertise et le savoir-faire de Portneuf?",
        "Quels sont vos objectifs pour continuer à faire briller la région à plus grande échelle?",
    ],
    "Innovation": [
        "Quel problème ou besoin avez-vous identifié sur le marché et comment votre innovation y répond-elle?",
        "Quelle est l’origine de votre projet innovant?",
        "En quoi votre innovation est-elle unique ou différente des solutions existantes?",
        "Quels ont été les défis techniques, financiers ou humains dans le développement de votre innovation?",
        "Quels sont les impacts concrets de votre innovation sur votre entreprise, votre secteur ou votre clientèle?",
    ],
    "Repreneuriat": [
        "Comment avez-vous relevé le défi du repreneuriat?",
        "Quels défis majeurs avez-vous rencontrés et comment les avez-vous surmontés?2",
        "Décrivez les mécanismes de transfert ou d'acquisition de connaissances mis en place.2",
    ],
}

# === Questions générales (narratif commun, hors catégorie spécifique) ===
GENERAL_CATEGORY_NAME = "Narratif (général)"
GENERAL_QUESTIONS = [
    "En lien avec la catégorie choisie, décrivez nous, en quelques phrases, le(s) projet(s) pour lesquels vous déposez une candidature. Nous souhaitons ici une description du projet : l’origine, le bes...",
    "Toujours en lien avec la catégorie choisie, présentez nous, en quelques phrases, les éléments qui distinguent votre projet des autres. Nous souhaitons ici que vous mettiez en valeur votre réussite...",
]

# Colonnes contextuelles → compagnie
COMPANY_FIELD_MAP = {
    "Nom de l'entreprise ou organisme": "nom",
    "Secteur d'activité de l'entreprise": "secteur",
    "Nombres d'employés?": "nombre_employes",
    "Adresse complète dans le comté de Portneuf": "adresse",
    "Numéro de téléphone de la personne responsable du dossier": "telephone",
    "Courriel de la personne responsable du dossier": "courriel",
    "Nom de la personne responsable du dossier": "responsable_nom",
    "Numéro d'entreprise (NEQ)": "neq",
}

# Colonnes possibles pour les catégories choisies
CATEGORY_COLUMNS_CANDIDATES = [
    # champ combiné (liste JSON en une colonne)
    "catégories",
    "categories",
    # colonnes historiques (Google Forms)
    "Dans quelle catégorie votre entreprise se démarquera en lien avec le ou les projets réalisés ?MAXIMUM 2 choix au total, mais commençons par le premier",
    "Voulez-vous déposer votre candidature dans une autre catégorie?Maximum deux catégories par entreprise",
]

# =========================================
#  SQL helpers (idempotents)
# =========================================

def ensure_gala(conn: sqlite3.Connection, nom: str, annee: int, lieu: Optional[str], date_gala: Optional[str]) -> int:
    cur = conn.execute("SELECT id FROM gala WHERE nom=? AND annee=?", (nom, annee))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO gala(nom, annee, lieu, date_gala) VALUES (?,?,?,?)", (nom, annee, lieu, date_gala))
    return cur.lastrowid

def ensure_categorie(conn: sqlite3.Connection, nom: str, description: Optional[str] = None) -> int:
    cur = conn.execute("SELECT id FROM categorie WHERE nom=?", (nom,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO categorie(nom, description) VALUES(?, ?)", (nom, description))
    return cur.lastrowid

def ensure_gala_categorie(conn: sqlite3.Connection, gala_id: int, categorie_id: int) -> int:
    cur = conn.execute("SELECT id FROM gala_categorie WHERE gala_id=? AND categorie_id=?", (gala_id, categorie_id))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO gala_categorie(gala_id, categorie_id, actif) VALUES(?,?,1)", (gala_id, categorie_id))
    return cur.lastrowid

def ensure_question(conn: sqlite3.Connection, gala_categorie_id: int, texte: str, ponderation: float = 1.0) -> int:
    cur = conn.execute(
        "SELECT id FROM question WHERE gala_categorie_id=? AND texte=?",
        (gala_categorie_id, texte),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO question(gala_categorie_id, texte, ponderation) VALUES(?,?,?)",
        (gala_categorie_id, texte, ponderation),
    )
    return cur.lastrowid

def ensure_compagnie(conn: sqlite3.Connection, data: Dict[str, str]) -> int:
    # clé d'unicité pragmatique: nom + courriel (ajuste si besoin)
    cur = conn.execute(
        "SELECT id FROM compagnie WHERE nom=? AND COALESCE(courriel,'')=COALESCE(?, '')",
        (data.get("nom"), data.get("courriel")),
    )
    row = cur.fetchone()
    if row:
        # Mise à jour légère
        conn.execute(
            "UPDATE compagnie SET secteur=?, nombre_employes=?, adresse=?, telephone=?, responsable_nom=?, neq=? WHERE id=?",
            (
                data.get("secteur"),
                data.get("nombre_employes"),
                data.get("adresse"),
                data.get("telephone"),
                data.get("responsable_nom"),
                data.get("neq"),
                row[0],
            ),
        )
        return row[0]
    cur = conn.execute(
        """
        INSERT INTO compagnie(nom, secteur, nombre_employes, adresse, telephone, courriel, responsable_nom, neq)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            data.get("nom"),
            data.get("secteur"),
            data.get("nombre_employes"),
            data.get("adresse"),
            data.get("telephone"),
            data.get("courriel"),
            data.get("responsable_nom"),
            data.get("neq"),
        ),
    )
    return cur.lastrowid

def ensure_participant(conn: sqlite3.Connection, compagnie_id: int, gala_categorie_id: int) -> int:
    cur = conn.execute(
        "SELECT id FROM participant WHERE compagnie_id=? AND gala_categorie_id=?",
        (compagnie_id, gala_categorie_id),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO participant(compagnie_id, gala_categorie_id) VALUES(?,?)",
        (compagnie_id, gala_categorie_id),
    )
    return cur.lastrowid

def upsert_reponse(conn: sqlite3.Connection, participant_id: int, question_id: int, contenu: str) -> None:
    # UNIQUE(participant_id, question_id)
    cur = conn.execute(
        "SELECT id FROM reponse_participant WHERE participant_id=? AND question_id=?",
        (participant_id, question_id),
    )
    row = cur.fetchone()
    if row:
        conn.execute(
            "UPDATE reponse_participant SET contenu=? WHERE id=?",
            (contenu, row[0]),
        )
    else:
        conn.execute(
            "INSERT INTO reponse_participant(participant_id, question_id, contenu) VALUES(?,?,?)",
            (participant_id, question_id, contenu),
        )

# =========================================
#  Lecture CSV & détection des colonnes catégorie
# =========================================

def detect_category_columns(headers: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """Retourne (col_combined, col_first_or_none). Si col_combined est présent, on l'utilise.
    Sinon, on tentera (q18, q26) si disponibles.
    """
    # 1) champ combiné type liste JSON
    for h in headers:
        hl = h.lower()
        if ("catégorie" in hl or "categorie" in hl) and ("max" in hl or "autre" in hl or "liste" in hl or "[" in hl):
            return (h, None)

    # 2) colonnes historiques
    q18 = None
    q26 = None
    for h in headers:
        if h.startswith("Dans quelle catégorie votre entreprise se démarquera"):
            q18 = h
        if h.startswith("Voulez-vous déposer votre candidature dans une autre catégorie"):
            q26 = h
    return (None, q18) if (q18 or q26) else (None, None)

def parse_categories(row: Dict[str, str], col_combined: Optional[str], col_first: Optional[str], headers: List[str]) -> List[str]:
    cats: List[str] = []
    if col_combined and row.get(col_combined):
        raw = row[col_combined].strip()
        try:
            cats = json.loads(raw)
            if not isinstance(cats, list):
                cats = [str(raw)]
        except Exception:
            # fallback: séparé par ; ou ,
            cats = [c.strip() for c in re.split(r"[;,]", raw) if c.strip()]
    else:
        # Deux champs potentiels (premier + autre)
        vals: List[str] = []
        if col_first and row.get(col_first):
            vals.append(row[col_first])
        for h in headers:
            if h.lower().startswith("voulez-vous déposer votre candidature dans une autre catégorie") and row.get(h):
                vals.append(row[h])
        cats = [norm(v) for v in vals if norm(v)]

    # Normalisation + alias → nom canonique
    canon_keys = {keyify(t): t for t in TARGET_CATEGORIES}
    resolved: List[str] = []
    for c in cats:
        k = keyify(c)
        if k in CATEGORY_ALIASES:
            resolved.append(CATEGORY_ALIASES[k])
            continue
        if k in canon_keys:
            resolved.append(canon_keys[k])
            continue
        hit = next((canon_keys[ck] for ck in canon_keys.keys() if k.startswith(ck[:30])), None)
        if hit:
            resolved.append(hit)
            continue

    # Filtrer aux seules catégories autorisées + dédoublonner
    seen = set()
    result: List[str] = []
    for c in resolved:
        if c in TARGET_CATEGORIES and c not in seen:
            seen.add(c)
            result.append(c)
    return result

# =========================================
#  Import principal
# =========================================

def import_csv(db_path: Path, csv_path: Path, gala_nom: str, annee: int, lieu: Optional[str], date_gala: Optional[str]) -> None:
    if not db_path.exists():
        if init_database:
            print("🛠️  DB absente → création via init_db.init_database() …")
            init_database()
        else:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            raise FileNotFoundError(f"Base inexistante et init_db.py introuvable. Crée d'abord {db_path}.")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        gala_id = ensure_gala(conn, gala_nom, annee, lieu, date_gala)

        # 1) Préparer catégories & questions spécifiques (idempotent)
        cat_name_to_gc_id: Dict[str, int] = {}
        for cat_name in TARGET_CATEGORIES:
            cat_id = ensure_categorie(conn, cat_name)
            gc_id = ensure_gala_categorie(conn, gala_id, cat_id)
            cat_name_to_gc_id[cat_name] = gc_id
            for qtxt in CATEGORY_QUESTIONS.get(cat_name, []):
                ensure_question(conn, gc_id, qtxt)

        # 2) Catégorie « Narratif (général) » (toujours créée)
        cat_gen_id = ensure_categorie(conn, GENERAL_CATEGORY_NAME)
        gc_gen_id = ensure_gala_categorie(conn, gala_id, cat_gen_id)
        for qtxt in GENERAL_QUESTIONS:
            ensure_question(conn, gc_gen_id, qtxt)

        conn.commit()

        # 3) Charger CSV & importer lignes
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            if not headers:
                raise RuntimeError("CSV sans en-têtes détectés.")

            col_combined, col_first = detect_category_columns(headers)
            print(f"➡️  Détection colonnes catégories: combined={col_combined!r}, first={col_first!r}")

            inserted_participants = 0
            inserted_compagnies = 0
            inserted_reponses = 0

            for row in reader:
                # 3.1 Compagnie
                comp_payload: Dict[str, str] = {}
                for csv_col, db_field in COMPANY_FIELD_MAP.items():
                    if csv_col in row and row[csv_col]:
                        comp_payload[db_field] = norm(row[csv_col])
                if not comp_payload.get("nom"):
                    continue  # ignore les lignes sans nom
                compagnie_id = ensure_compagnie(conn, comp_payload)
                if compagnie_id:
                    inserted_compagnies += 1

                # 3.2 Participant « narratif général » (un par compagnie/gala)
                p_general_id = ensure_participant(conn, compagnie_id, gc_gen_id)
                # Insérer les 2 réponses générales si colonnes présentes (tolérance entêtes tronquées → préfixes)
                for qtxt in GENERAL_QUESTIONS:
                    # correspondance stricte ou par préfixe 60 car.
                    match_col = next((h for h in headers if h == qtxt or keyify(h).startswith(keyify(qtxt)[:60])), None)
                    if match_col and row.get(match_col):
                        cur = conn.execute(
                            "SELECT id FROM question WHERE gala_categorie_id=? AND texte=?",
                            (gc_gen_id, qtxt),
                        )
                        qr = cur.fetchone()
                        qid = qr[0] if qr else ensure_question(conn, gc_gen_id, qtxt)
                        upsert_reponse(conn, p_general_id, qid, row[match_col])
                        inserted_reponses += 1

                # 3.3 Catégories de participation
                cats = parse_categories(row, col_combined, col_first, headers)
                if not cats:
                    continue

                for cat in cats:
                    gc_id = cat_name_to_gc_id.get(cat)
                    if not gc_id:
                        continue  # hors scope
                    participant_id = ensure_participant(conn, compagnie_id, gc_id)
                    inserted_participants += 1

                    # 3.4 Réponses par question de la catégorie
                    for qtxt in CATEGORY_QUESTIONS.get(cat, []):
                        # match strict ou préfixe (entêtes tronquées)
                        match_col = next((h for h in headers if h == qtxt or keyify(h).startswith(keyify(qtxt)[:60])), None)
                        if match_col and row.get(match_col) not in (None, ""):
                            cur = conn.execute(
                                "SELECT id FROM question WHERE gala_categorie_id=? AND texte=?",
                                (gc_id, qtxt),
                            )
                            qr = cur.fetchone()
                            qid = qr[0] if qr else ensure_question(conn, gc_id, qtxt)
                            upsert_reponse(conn, participant_id, qid, row[match_col])
                            inserted_reponses += 1

            conn.commit()
            print(
                f"✅ Import terminé — compagnies:{inserted_compagnies} participants:{inserted_participants} réponses:{inserted_reponses}"
            )

    finally:
        conn.close()

# =========================================
#  CLI
# =========================================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--gala", required=True)
    ap.add_argument("--annee", type=int, required=True)
    ap.add_argument("--lieu")
    ap.add_argument("--date")
    args = ap.parse_args()

    # Crée le dossier du DB si besoin
    if args.db and args.db.parent:
        args.db.parent.mkdir(parents=True, exist_ok=True)

    import_csv(args.db, args.csv, args.gala, args.annee, args.lieu, args.date)

if __name__ == "__main__":
    main()
