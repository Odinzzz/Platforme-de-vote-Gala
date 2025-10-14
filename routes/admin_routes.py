from __future__ import annotations

from collections import defaultdict
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from flask import Blueprint, render_template, session, jsonify, request, abort

from models.db import get_db_connection

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ROLE_DISPLAY_ORDER = ["admin", "juge", "membre"]
FAVORITE_BONUS = 0.5


def _require_admin() -> None:
    user = session.get("user")
    if not user or (user.get("role") or "").lower() != "admin":
        abort(403)


@admin_bp.before_request
def ensure_admin() -> None:
    _require_admin()


@admin_bp.route("/users", methods=["GET"])
def users_page():
    return render_template("admin/users.html", user=session.get("user"))


@admin_bp.route("/participants", methods=["GET"])
def participants_page():
    return render_template("admin/participants.html", user=session.get("user"))


@admin_bp.route("/api/users", methods=["GET"])
def list_users():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT user.id, user.username, user.role_id, personne.prenom, personne.nom, role.nom AS role_nom
        FROM user
        JOIN personne ON user.personne_id = personne.id
        LEFT JOIN role ON user.role_id = role.id
        ORDER BY
            CASE LOWER(role.nom)
                WHEN 'admin' THEN 1
                WHEN 'juge' THEN 2
                WHEN 'membre' THEN 3
                ELSE 4
            END,
            personne.nom COLLATE NOCASE,
            personne.prenom COLLATE NOCASE
        """
    ).fetchall()
    conn.close()

    users_by_role: Dict[str, List[Dict[str, Any]]] = {role: [] for role in ROLE_DISPLAY_ORDER}

    for row in rows:
        role_name = (row["role_nom"] or "membre").lower()
        if role_name not in users_by_role:
            users_by_role[role_name] = []
        users_by_role[role_name].append(
            {
                "id": row["id"],
                "username": row["username"],
                "prenom": row["prenom"],
                "nom": row["nom"],
                "role": role_name,
            }
        )

    return jsonify({
        "users_by_role": users_by_role,
        "role_order": ROLE_DISPLAY_ORDER,
    })


def _fetch_user(conn, user_id: int):
    return conn.execute(
        """
        SELECT user.id, user.username, user.role_id, personne.prenom, personne.nom, personne.courriel,
               role.nom AS role_nom
        FROM user
        JOIN personne ON user.personne_id = personne.id
        LEFT JOIN role ON user.role_id = role.id
        WHERE user.id = ?
        """,
        (user_id,),
    ).fetchone()


def _build_judge_payload(conn, user_id: int) -> Dict[str, Any]:
    judge_row = conn.execute(
        "SELECT id FROM juge WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    judge_id = judge_row["id"] if judge_row else None
    assigned_ids = set()
    if judge_id:
        assigned_rows = conn.execute(
            "SELECT gala_categorie_id FROM juge_gala_categorie WHERE juge_id = ?",
            (judge_id,),
        ).fetchall()
        assigned_ids = {row["gala_categorie_id"] for row in assigned_rows}

    gala_rows = conn.execute(
        """
        SELECT gala.id AS gala_id, gala.nom AS gala_nom, gala.annee AS gala_annee,
               gala_categorie.id AS gala_categorie_id,
               categorie.nom AS categorie_nom
        FROM gala
        JOIN gala_categorie ON gala_categorie.gala_id = gala.id
        JOIN categorie ON categorie.id = gala_categorie.categorie_id
        ORDER BY gala.annee DESC, categorie.nom COLLATE NOCASE
        """
    ).fetchall()

    grouped: Dict[int, Dict[str, Any]] = {}
    for row in gala_rows:
        gala_id = row["gala_id"]
        if gala_id not in grouped:
            grouped[gala_id] = {
                "gala_id": gala_id,
                "nom": row["gala_nom"],
                "annee": row["gala_annee"],
                "categories": [],
            }
        grouped[gala_id]["categories"].append(
            {
                "id": row["gala_categorie_id"],
                "nom": row["categorie_nom"],
                "assigned": row["gala_categorie_id"] in assigned_ids,
            }
        )

    return {
        "judge_id": judge_id,
        "assigned_ids": sorted(assigned_ids),
        "galas": list(grouped.values()),
    }


@admin_bp.route("/api/users/<int:user_id>", methods=["GET"])
def user_detail(user_id: int):
    conn = get_db_connection()
    user_row = _fetch_user(conn, user_id)
    if not user_row:
        conn.close()
        abort(404)

    roles = conn.execute(
        "SELECT id, nom FROM role ORDER BY nom COLLATE NOCASE"
    ).fetchall()

    judge_payload = _build_judge_payload(conn, user_row["id"])

    conn.close()

    user_payload = {
        "id": user_row["id"],
        "username": user_row["username"],
        "prenom": user_row["prenom"],
        "nom": user_row["nom"],
        "courriel": user_row["courriel"],
        "role_id": user_row["role_id"],
        "role": user_row["role_nom"],
    }

    roles_payload = [
        {"id": row["id"], "nom": row["nom"]}
        for row in roles
    ]

    return jsonify({
        "user": user_payload,
        "roles": roles_payload,
        "judge": judge_payload,
    })


@admin_bp.route("/api/users/<int:user_id>/role", methods=["PATCH"])
def update_user_role(user_id: int):
    payload = request.get_json(silent=True) or {}
    role_id = payload.get("role_id")

    try:
        role_id_int = int(role_id)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Role invalide."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    user_row = _fetch_user(conn, user_id)
    if not user_row:
        conn.close()
        abort(404)

    role_row = cursor.execute(
        "SELECT id, nom FROM role WHERE id = ?",
        (role_id_int,),
    ).fetchone()
    if not role_row:
        conn.close()
        return jsonify({"status": "error", "message": "Role introuvable."}), 404

    new_role = (role_row["nom"] or "").lower()

    if user_row["role_id"] != role_row["id"]:
        cursor.execute(
            "UPDATE user SET role_id = ? WHERE id = ?",
            (role_row["id"], user_id),
        )

    judge_row = cursor.execute(
        "SELECT id FROM juge WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if new_role == "juge" and not judge_row:
        cursor.execute(
            "INSERT INTO juge (user_id) VALUES (?)",
            (user_id,),
        )
    elif new_role != "juge" and judge_row:
        cursor.execute(
            "DELETE FROM juge_gala_categorie WHERE juge_id = ?",
            (judge_row["id"],),
        )
        cursor.execute(
            "DELETE FROM juge WHERE id = ?",
            (judge_row["id"],),
        )

    conn.commit()

    updated_row = _fetch_user(conn, user_id)
    judge_payload = _build_judge_payload(conn, user_id)
    conn.close()

    user_payload = {
        "id": updated_row["id"],
        "username": updated_row["username"],
        "prenom": updated_row["prenom"],
        "nom": updated_row["nom"],
        "courriel": updated_row["courriel"],
        "role_id": updated_row["role_id"],
        "role": updated_row["role_nom"],
    }

    session_user = session.get("user")
    if session_user and session_user.get("id") == user_payload["id"]:
        session_user["role"] = user_payload["role"]
        session["user"] = session_user

    return jsonify({
        "status": "ok",
        "user": user_payload,
        "judge": judge_payload,
    })


@admin_bp.route("/api/users/<int:user_id>/assignments", methods=["PATCH"])
def update_judge_assignments(user_id: int):
    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("gala_categorie_ids", [])

    try:
        desired_ids = {int(value) for value in raw_ids}
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Liste d'assignations invalide."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    user_row = _fetch_user(conn, user_id)
    if not user_row:
        conn.close()
        abort(404)

    role_name = (user_row["role_nom"] or "").lower()
    if role_name != "juge":
        conn.close()
        return jsonify({"status": "error", "message": "L'utilisateur doit etre juge."}), 400

    judge_row = cursor.execute(
        "SELECT id FROM juge WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not judge_row:
        cursor.execute(
            "INSERT INTO juge (user_id) VALUES (?)",
            (user_id,),
        )
        judge_row = cursor.execute(
            "SELECT id FROM juge WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    judge_id = judge_row["id"]

    if desired_ids:
        placeholders = ",".join(["?"] * len(desired_ids))
        valid_rows = cursor.execute(
            f"SELECT id FROM gala_categorie WHERE id IN ({placeholders})",
            tuple(desired_ids),
        ).fetchall()
        valid_ids = {row["id"] for row in valid_rows}
    else:
        valid_ids = set()

    cursor.execute(
        "DELETE FROM juge_gala_categorie WHERE juge_id = ?",
        (judge_id,),
    )

    for gala_cat_id in sorted(valid_ids):
        cursor.execute(
            "INSERT INTO juge_gala_categorie (juge_id, gala_categorie_id) VALUES (?, ?)",
            (judge_id, gala_cat_id),
        )

    conn.commit()

    judge_payload = _build_judge_payload(conn, user_id)
    conn.close()

    return jsonify({
        "status": "ok",
        "judge": judge_payload,
    })


# ==============================
# Admin Gala management
# ==============================
@admin_bp.route("/galas", methods=["GET"])
def galas_page():
    return render_template("admin/galas.html", user=session.get("user"))


@admin_bp.route("/results", methods=["GET"])
def results_page():
    return render_template("admin/results.html", user=session.get("user"))


def _serialize_gala_row(row, lock_row=None, submissions_count=0) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "nom": row["nom"],
        "annee": row["annee"],
        "lieu": row["lieu"],
        "date_gala": row["date_gala"],
        "categories_count": row["categories_count"],
        "questions_count": row["questions_count"],
        "locked": lock_row is not None,
        "locked_at": lock_row["locked_at"] if lock_row else None,
        "locked_by": lock_row["locked_by"] if lock_row else None,
        "submissions_count": submissions_count,
    }


def _fetch_gala_lock_map(conn, gala_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    if not gala_ids:
        return {}
    placeholders = ",".join("?" for _ in gala_ids)
    rows = conn.execute(
        f"SELECT gala_id, locked_at, locked_by FROM gala_lock WHERE gala_id IN ({placeholders})",
        tuple(gala_ids),
    ).fetchall()
    return {row["gala_id"]: row for row in rows}


def _fetch_submission_counts(conn, gala_ids: List[int]) -> Dict[int, int]:
    if not gala_ids:
        return {}
    placeholders = ",".join("?" for _ in gala_ids)
    rows = conn.execute(
        f"SELECT gala_id, COUNT(*) AS total FROM juge_gala_submission WHERE gala_id IN ({placeholders}) GROUP BY gala_id",
        tuple(gala_ids),
    ).fetchall()
    return {row["gala_id"]: row["total"] for row in rows}


def _get_gala_lock(conn, gala_id: int):
    return conn.execute(
        "SELECT gala_id, locked_at, locked_by FROM gala_lock WHERE gala_id = ?",
        (gala_id,),
    ).fetchone()




def _ensure_gala_unlocked(conn, gala_id: int):
    if _get_gala_lock(conn, gala_id):
        conn.close()
        return jsonify({"status": "error", "message": "Ce gala est verrouille."}), 409
    return None


@admin_bp.route("/api/galas", methods=["GET"])

def list_galas_admin():

    conn = get_db_connection()

    rows = conn.execute(

        """

        SELECT g.id, g.nom, g.annee, g.lieu, g.date_gala,

               COUNT(DISTINCT gc.id) AS categories_count,

               COUNT(DISTINCT q.id) AS questions_count

        FROM gala AS g

        LEFT JOIN gala_categorie AS gc ON gc.gala_id = g.id

        LEFT JOIN question AS q ON q.gala_categorie_id = gc.id

        GROUP BY g.id

        ORDER BY g.annee DESC, g.nom COLLATE NOCASE

        """

    ).fetchall()

    gala_ids = [row["id"] for row in rows]

    lock_map = _fetch_gala_lock_map(conn, gala_ids)

    submissions_map = _fetch_submission_counts(conn, gala_ids)

    conn.close()

    payload = [_serialize_gala_row(row, lock_map.get(row["id"]), submissions_map.get(row["id"], 0)) for row in rows]

    return jsonify({"galas": payload})







@admin_bp.route("/api/galas", methods=["POST"])
def create_gala():
    payload = request.get_json(silent=True) or {}
    nom = (payload.get("nom") or "").strip()
    annee = payload.get("annee")
    lieu = (payload.get("lieu") or "").strip() or None
    date_gala = (payload.get("date_gala") or "").strip() or None

    errors = []
    if not nom:
        errors.append("Le nom est requis.")
    try:
        annee_int = int(annee)
        if annee_int < 1900:
            errors.append("Annee invalide.")
    except (TypeError, ValueError):
        errors.append("Annee invalide.")
        annee_int = None

    if errors:
        return jsonify({"status": "error", "message": " ".join(errors)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO gala (nom, annee, lieu, date_gala)
        VALUES (?, ?, ?, ?)
        """,
        (nom, annee_int, lieu, date_gala),
    )
    gala_id = cursor.lastrowid
    conn.commit()

    row = cursor.execute(
        """
        SELECT g.id, g.nom, g.annee, g.lieu, g.date_gala, 0 AS categories_count, 0 AS questions_count
        FROM gala AS g
        WHERE g.id = ?
        """,
        (gala_id,),
    ).fetchone()
    conn.close()

    return jsonify({"status": "ok", "gala": _serialize_gala_row(row)}), 201


def _fetch_gala(conn, gala_id: int):
    return conn.execute(
        """
        SELECT id, nom, annee, lieu, date_gala
        FROM gala
        WHERE id = ?
        """,
        (gala_id,),
    ).fetchone()


@admin_bp.route("/api/galas/<int:gala_id>", methods=["GET"])
def gala_detail(gala_id: int):
    conn = get_db_connection()
    gala_row = _fetch_gala(conn, gala_id)
    if not gala_row:
        conn.close()
        abort(404)

    categories = conn.execute(
        """
        SELECT gc.id AS gala_categorie_id, gc.categorie_id, gc.ordre_affichage, gc.actif,
               c.nom AS categorie_nom,
               COUNT(q.id) AS questions_count
        FROM gala_categorie AS gc
        JOIN categorie AS c ON c.id = gc.categorie_id
        LEFT JOIN question AS q ON q.gala_categorie_id = gc.id
        WHERE gc.gala_id = ?
        GROUP BY gc.id
        ORDER BY gc.ordre_affichage ASC, c.nom COLLATE NOCASE
        """,
        (gala_id,),
    ).fetchall()

    available_categories = conn.execute(
        """
        SELECT c.id, c.nom
        FROM categorie AS c
        WHERE c.id NOT IN (
            SELECT categorie_id FROM gala_categorie WHERE gala_id = ?
        )
        ORDER BY c.nom COLLATE NOCASE
        """,
        (gala_id,),
    ).fetchall()

    lock_row = _get_gala_lock(conn, gala_id)
    submissions_count = conn.execute(
        "SELECT COUNT(*) AS total FROM juge_gala_submission WHERE gala_id = ?",
        (gala_id,),
    ).fetchone()["total"]
    conn.close()

    total_questions = sum((row["questions_count"] or 0) for row in categories)
    summary_row = {
        "id": gala_row["id"],
        "nom": gala_row["nom"],
        "annee": gala_row["annee"],
        "lieu": gala_row["lieu"],
        "date_gala": gala_row["date_gala"],
        "categories_count": len(categories),
        "questions_count": total_questions,
    }
    gala_payload = _serialize_gala_row(summary_row, lock_row, submissions_count)

    categories_payload = [
        {
            "id": row["gala_categorie_id"],
            "categorie_id": row["categorie_id"],
            "nom": row["categorie_nom"],
            "ordre_affichage": row["ordre_affichage"],
            "actif": row["actif"],
            "questions_count": row["questions_count"],
        }
        for row in categories
    ]
    available_payload = [
        {"id": row["id"], "nom": row["nom"]}
        for row in available_categories
    ]

    return jsonify({
        "gala": gala_payload,
        "categories": categories_payload,
        "available_categories": available_payload,
    })


@admin_bp.route("/api/galas/<int:gala_id>", methods=["PATCH"])
def update_gala(gala_id: int):
    payload = request.get_json(silent=True) or {}
    nom = payload.get("nom")
    annee = payload.get("annee")
    lieu = payload.get("lieu")
    date_gala = payload.get("date_gala")

    conn = get_db_connection()
    gala_row = _fetch_gala(conn, gala_id)
    if not gala_row:
        conn.close()
        abort(404)

    locked_response = _ensure_gala_unlocked(conn, gala_id)
    if locked_response:
        return locked_response


    fields = []
    values = []

    if nom is not None:
        nom_value = nom.strip()
        if not nom_value:
            conn.close()
            return jsonify({"status": "error", "message": "Le nom est requis."}), 400
        fields.append("nom = ?")
        values.append(nom_value)

    if annee is not None:
        try:
            annee_int = int(annee)
            if annee_int < 1900:
                raise ValueError
        except (TypeError, ValueError):
            conn.close()
            return jsonify({"status": "error", "message": "Annee invalide."}), 400
        fields.append("annee = ?")
        values.append(annee_int)

    if lieu is not None:
        fields.append("lieu = ?")
        values.append(lieu.strip() or None)

    if date_gala is not None:
        fields.append("date_gala = ?")
        values.append(date_gala.strip() or None)

    if fields:
        values.append(gala_id)
        conn.execute(
            f"UPDATE gala SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        conn.commit()

    summary_row = conn.execute(
        """
        SELECT g.id, g.nom, g.annee, g.lieu, g.date_gala,
               COUNT(DISTINCT gc.id) AS categories_count,
               COUNT(DISTINCT q.id) AS questions_count
        FROM gala AS g
        LEFT JOIN gala_categorie AS gc ON gc.gala_id = g.id
        LEFT JOIN question AS q ON q.gala_categorie_id = gc.id
        WHERE g.id = ?
        GROUP BY g.id
        """,
        (gala_id,),
    ).fetchone()
    lock_row = _get_gala_lock(conn, gala_id)
    submissions_count = conn.execute(
        "SELECT COUNT(*) AS total FROM juge_gala_submission WHERE gala_id = ?",
        (gala_id,),
    ).fetchone()["total"]
    conn.close()

    if not summary_row:
        return jsonify({"status": "error", "message": "Gala introuvable."}), 404

    payload = _serialize_gala_row(summary_row, lock_row, submissions_count)
    return jsonify({"status": "ok", "gala": payload})


@admin_bp.route("/api/galas/<int:gala_id>/lock", methods=["POST"])

def lock_gala(gala_id: int):

    conn = get_db_connection()

    gala_row = _fetch_gala(conn, gala_id)

    if not gala_row:

        conn.close()

        abort(404)



    existing = _get_gala_lock(conn, gala_id)

    if existing:

        conn.close()

        return jsonify({"status": "error", "message": "Gala deja verrouille."}), 409



    locked_by = session.get("user", {}).get("id")

    conn.execute(

        "INSERT INTO gala_lock (gala_id, locked_at, locked_by) VALUES (?, ?, ?)",

        (gala_id, datetime.now(UTC).isoformat(), locked_by),

    )

    conn.commit()

    conn.close()

    return gala_detail(gala_id)





@admin_bp.route("/api/galas/<int:gala_id>/lock", methods=["DELETE"])

def unlock_gala(gala_id: int):

    conn = get_db_connection()

    gala_row = _fetch_gala(conn, gala_id)

    if not gala_row:

        conn.close()

        abort(404)



    existing = _get_gala_lock(conn, gala_id)

    if not existing:

        conn.close()

        return jsonify({"status": "error", "message": "Gala non verrouille."}), 409



    conn.execute("DELETE FROM gala_lock WHERE gala_id = ?", (gala_id,))

    conn.commit()

    conn.close()

    return gala_detail(gala_id)





@admin_bp.route("/api/galas/<int:gala_id>/categories", methods=["POST"])
def add_categories_to_gala(gala_id: int):
    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("categorie_ids", [])
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"status": "error", "message": "Aucune categorie fournie."}), 400

    try:
        categorie_ids = {int(value) for value in raw_ids}
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Identifiants invalides."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    gala_row = _fetch_gala(conn, gala_id)
    if not gala_row:
        conn.close()
        abort(404)

    locked_response = _ensure_gala_unlocked(conn, gala_id)
    if locked_response:
        return locked_response


    placeholders = ",".join(["?"] * len(categorie_ids))
    existing = cursor.execute(
        f"SELECT id FROM categorie WHERE id IN ({placeholders})",
        tuple(categorie_ids),
    ).fetchall()
    valid_ids = {row["id"] for row in existing}

    if not valid_ids:
        conn.close()
        return jsonify({"status": "error", "message": "Categories inconnues."}), 400

    current_order_row = cursor.execute(
        "SELECT MAX(ordre_affichage) FROM gala_categorie WHERE gala_id = ?",
        (gala_id,),
    ).fetchone()
    next_order = (current_order_row[0] or 0) + 1

    for categorie_id in sorted(valid_ids):
        already = cursor.execute(
            "SELECT 1 FROM gala_categorie WHERE gala_id = ? AND categorie_id = ?",
            (gala_id, categorie_id),
        ).fetchone()
        if already:
            continue
        cursor.execute(
            """
            INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage)
            VALUES (?, ?, ?)
            """,
            (gala_id, categorie_id, next_order),
        )
        next_order += 1

    conn.commit()
    conn.close()

    return gala_detail(gala_id)


@admin_bp.route("/api/galas/<int:gala_id>/categories/<int:gala_categorie_id>", methods=["DELETE"])
def remove_category_from_gala(gala_id: int, gala_categorie_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    exists = cursor.execute(
        "SELECT id FROM gala_categorie WHERE id = ? AND gala_id = ?",
        (gala_categorie_id, gala_id),
    ).fetchone()
    if not exists:
        conn.close()
        abort(404)

    locked_response = _ensure_gala_unlocked(conn, gala_id)
    if locked_response:
        return locked_response


    cursor.execute(
        "DELETE FROM gala_categorie WHERE id = ?",
        (gala_categorie_id,),
    )
    conn.commit()
    conn.close()

    return gala_detail(gala_id)


@admin_bp.route("/api/galas/<int:gala_id>/categories/<int:gala_categorie_id>", methods=["PATCH"])
def update_gala_category(gala_id: int, gala_categorie_id: int):
    payload = request.get_json(silent=True) or {}
    ordre = payload.get("ordre_affichage")
    actif = payload.get("actif")

    conn = get_db_connection()
    cursor = conn.cursor()

    row = cursor.execute(
        "SELECT id FROM gala_categorie WHERE id = ? AND gala_id = ?",
        (gala_categorie_id, gala_id),
    ).fetchone()
    if not row:
        conn.close()
        abort(404)

    locked_response = _ensure_gala_unlocked(conn, gala_id)
    if locked_response:
        return locked_response


    fields = []
    values = []

    if ordre is not None:
        try:
            ordre_int = int(ordre)
        except (TypeError, ValueError):
            conn.close()
            return jsonify({"status": "error", "message": "Ordre invalide."}), 400
        fields.append("ordre_affichage = ?")
        values.append(ordre_int)

    if actif is not None:
        actif_int = 1 if bool(actif) else 0
        fields.append("actif = ?")
        values.append(actif_int)

    if fields:
        values.append(gala_categorie_id)
        cursor.execute(
            f"UPDATE gala_categorie SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        conn.commit()

    conn.close()
    return gala_detail(gala_id)


@admin_bp.route("/api/galas/<int:gala_id>/categories/reorder", methods=["PATCH"])
def reorder_gala_categories(gala_id: int):
    payload = request.get_json(silent=True) or {}
    new_order = payload.get("ordered_ids")
    if not isinstance(new_order, list) or not new_order:
        return jsonify({"status": "error", "message": "Liste d'ordre invalide."}), 400

    try:
        ordered_ids = [int(value) for value in new_order]
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Identifiants invalides."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    existing_rows = cursor.execute(
        "SELECT id FROM gala_categorie WHERE gala_id = ?",
        (gala_id,),
    ).fetchall()
    existing_ids = {row["id"] for row in existing_rows}
    if not set(ordered_ids).issubset(existing_ids):
        conn.close()
        return jsonify({"status": "error", "message": "Incoherence dans les categories."}), 400

    for position, gc_id in enumerate(ordered_ids, start=1):
        cursor.execute(
            "UPDATE gala_categorie SET ordre_affichage = ? WHERE id = ?",
            (position, gc_id),
        )
    conn.commit()
    conn.close()

    return gala_detail(gala_id)


@admin_bp.route("/api/categories", methods=["POST"])
def create_category():
    payload = request.get_json(silent=True) or {}
    nom = (payload.get("nom") or "").strip()
    description = (payload.get("description") or "").strip() or None

    if not nom:
        return jsonify({"status": "error", "message": "Le nom de la categorie est requis."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    duplicate = cursor.execute(
        """
        SELECT id FROM categorie WHERE LOWER(nom) = LOWER(?)
        """,
        (nom,),
    ).fetchone()
    if duplicate:
        conn.close()
        return jsonify({"status": "error", "message": "Une categorie portant ce nom existe deja."}), 409

    cursor.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        (nom, description),
    )
    category_id = cursor.lastrowid
    conn.commit()

    category_row = cursor.execute(
        "SELECT id, nom, description FROM categorie WHERE id = ?",
        (category_id,),
    ).fetchone()
    conn.close()

    category_payload = {
        "id": category_row["id"],
        "nom": category_row["nom"],
        "description": category_row["description"],
    }
    return jsonify({"status": "ok", "category": category_payload}), 201



def _fetch_question(conn, gala_categorie_id: int, question_id: int):
    return conn.execute(
        """
        SELECT id, gala_categorie_id, texte, ponderation
        FROM question
        WHERE id = ? AND gala_categorie_id = ?
        """,
        (question_id, gala_categorie_id),
    ).fetchone()


def _fetch_gala_category(conn, gala_id: int, gala_categorie_id: int):
    return conn.execute(
        """
        SELECT gc.id, gc.gala_id, gc.categorie_id, gc.ordre_affichage, gc.actif, c.nom AS categorie_nom
        FROM gala_categorie AS gc
        JOIN categorie AS c ON c.id = gc.categorie_id
        WHERE gc.id = ? AND gc.gala_id = ?
        """,
        (gala_categorie_id, gala_id),
    ).fetchone()


@admin_bp.route("/api/galas/<int:gala_id>/categories/<int:gala_categorie_id>/questions", methods=["GET"])
def list_questions_for_gala_category(gala_id: int, gala_categorie_id: int):
    conn = get_db_connection()
    gala_row = _fetch_gala(conn, gala_id)
    if not gala_row:
        conn.close()
        abort(404)


    gala_cat_row = _fetch_gala_category(conn, gala_id, gala_categorie_id)
    if not gala_cat_row:
        conn.close()
        abort(404)

    questions = conn.execute(
        """
        SELECT id, texte, ponderation
        FROM question
        WHERE gala_categorie_id = ?
        ORDER BY id ASC
        """,
        (gala_categorie_id,),
    ).fetchall()
    conn.close()

    payload = [
        {"id": row["id"], "texte": row["texte"], "ponderation": row["ponderation"]}
        for row in questions
    ]
    category_info = {
        "id": gala_cat_row["id"],
        "categorie_id": gala_cat_row["categorie_id"],
        "nom": gala_cat_row["categorie_nom"],
    }
    return jsonify({"questions": payload, "category": category_info})


@admin_bp.route("/api/galas/<int:gala_id>/categories/<int:gala_categorie_id>/questions", methods=["POST"])
def create_question_for_gala_category(gala_id: int, gala_categorie_id: int):
    payload = request.get_json(silent=True) or {}
    texte = (payload.get("texte") or "").strip()
    ponderation = payload.get("ponderation", 1.0)

    if not texte:
        return jsonify({"status": "error", "message": "Le texte est requis."}), 400

    try:
        ponderation_val = float(ponderation)
        if ponderation_val <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Ponderation invalide."}), 400

    conn = get_db_connection()
    gala_row = _fetch_gala(conn, gala_id)
    if not gala_row:
        conn.close()
        abort(404)

    locked_response = _ensure_gala_unlocked(conn, gala_id)
    if locked_response:
        return locked_response


    gala_cat_row = _fetch_gala_category(conn, gala_id, gala_categorie_id)
    if not gala_cat_row:
        conn.close()
        abort(404)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO question (gala_categorie_id, texte, ponderation)
        VALUES (?, ?, ?)
        """,
        (gala_categorie_id, texte, ponderation_val),
    )
    conn.commit()
    conn.close()

    return list_questions_for_gala_category(gala_id, gala_categorie_id)
@admin_bp.route("/api/galas/<int:gala_id>/categories/<int:gala_categorie_id>/questions/<int:question_id>", methods=["PATCH"])
def update_question_for_gala_category(gala_id: int, gala_categorie_id: int, question_id: int):
    payload = request.get_json(silent=True) or {}
    texte = payload.get("texte")
    ponderation = payload.get("ponderation")

    conn = get_db_connection()
    gala_row = _fetch_gala(conn, gala_id)
    if not gala_row:
        conn.close()
        abort(404)

    locked_response = _ensure_gala_unlocked(conn, gala_id)
    if locked_response:
        return locked_response


    gala_cat_row = _fetch_gala_category(conn, gala_id, gala_categorie_id)
    if not gala_cat_row:
        conn.close()
        abort(404)

    question_row = _fetch_question(conn, gala_categorie_id, question_id)
    if not question_row:
        conn.close()
        abort(404)

    cursor = conn.cursor()
    fields = []
    values = []

    if texte is not None:
        texte_value = (texte or "").strip()
        if not texte_value:
            conn.close()
            return jsonify({"status": "error", "message": "Le texte est requis."}), 400
        fields.append("texte = ?")
        values.append(texte_value)

    if ponderation is not None:
        try:
            ponderation_val = float(ponderation)
            if ponderation_val <= 0:
                raise ValueError
        except (TypeError, ValueError):
            conn.close()
            return jsonify({"status": "error", "message": "Ponderation invalide."}), 400
        fields.append("ponderation = ?")
        values.append(ponderation_val)

    if fields:
        values.append(question_id)
        cursor.execute(
            f"UPDATE question SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        conn.commit()

    conn.close()
    return list_questions_for_gala_category(gala_id, gala_categorie_id)


@admin_bp.route("/api/galas/<int:gala_id>/categories/<int:gala_categorie_id>/questions/<int:question_id>", methods=["DELETE"])
def delete_question_for_gala_category(gala_id: int, gala_categorie_id: int, question_id: int):
    conn = get_db_connection()
    gala_row = _fetch_gala(conn, gala_id)
    if not gala_row:
        conn.close()
        abort(404)

    locked_response = _ensure_gala_unlocked(conn, gala_id)
    if locked_response:
        return locked_response


    gala_cat_row = _fetch_gala_category(conn, gala_id, gala_categorie_id)
    if not gala_cat_row:
        conn.close()
        abort(404)

    question_row = _fetch_question(conn, gala_categorie_id, question_id)
    if not question_row:
        conn.close()
        abort(404)

    cursor = conn.cursor()
    cursor.execute("DELETE FROM question WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()

    return list_questions_for_gala_category(gala_id, gala_categorie_id)



# ==============================
# Admin Participant management
# ==============================
def _fetch_narratif_gala_categories(conn) -> Dict[int, List[int]]:
    rows = conn.execute(
        """
        SELECT gc.id AS gala_categorie_id, gc.gala_id
        FROM gala_categorie AS gc
        JOIN categorie AS c ON c.id = gc.categorie_id
        WHERE LOWER(c.nom) LIKE 'narratif%'
        """
    ).fetchall()

    mapping: Dict[int, List[int]] = {}
    for row in rows:
        mapping.setdefault(row["gala_id"], []).append(row["gala_categorie_id"])
    return mapping


def _build_admin_participant_filters(conn) -> List[Dict[str, Any]]:
    gala_rows = conn.execute(
        """
        SELECT
            g.id,
            g.nom,
            g.annee,
            COUNT(DISTINCT gc.id) AS categories_count,
            COUNT(DISTINCT p.id) AS participants_count
        FROM gala AS g
        LEFT JOIN gala_categorie AS gc ON gc.gala_id = g.id
        LEFT JOIN participant AS p ON p.gala_categorie_id = gc.id
        GROUP BY g.id
        ORDER BY g.annee DESC, g.nom COLLATE NOCASE
        """
    ).fetchall()

    gala_map: Dict[int, Dict[str, Any]] = {}
    for row in gala_rows:
        gala_map[row["id"]] = {
            "id": row["id"],
            "nom": row["nom"],
            "annee": row["annee"],
            "categories_count": row["categories_count"],
            "participants_count": row["participants_count"],
            "categories": [],
        }

    if not gala_map:
        return []

    gala_ids = tuple(gala_map.keys())
    placeholders = ",".join("?" for _ in gala_ids)
    narratif_map = _fetch_narratif_gala_categories(conn)
    narratif_ids = {cat_id for values in narratif_map.values() for cat_id in values}

    category_rows = conn.execute(
        f"""
        SELECT
            gc.id,
            gc.gala_id,
            c.nom AS categorie_nom,
            COUNT(DISTINCT p.id) AS participants_count
        FROM gala_categorie AS gc
        JOIN categorie AS c ON c.id = gc.categorie_id
        LEFT JOIN participant AS p ON p.gala_categorie_id = gc.id
        WHERE gc.gala_id IN ({placeholders})
        GROUP BY gc.id, gc.gala_id
        ORDER BY c.nom COLLATE NOCASE
        """,
        gala_ids,
    ).fetchall()

    for row in category_rows:
        gala_entry = gala_map.get(row["gala_id"])
        if not gala_entry:
            continue
        if row["id"] in narratif_ids:
            continue
        gala_entry["categories"].append(
            {
                "id": row["id"],
                "nom": row["categorie_nom"],
                "participants_count": row["participants_count"],
            }
        )

    for gala_entry in gala_map.values():
        gala_entry["categories"].sort(key=lambda item: item["nom"].lower())
        gala_entry["categories_count"] = len(gala_entry["categories"])
        gala_entry["participants_count"] = sum(cat["participants_count"] for cat in gala_entry["categories"])

    return list(gala_map.values())


def _fetch_questions_by_category(conn, category_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    if not category_ids:
        return {}

    unique_ids = sorted(set(category_ids))
    placeholders = ",".join("?" for _ in unique_ids)
    rows = conn.execute(
        f"""
        SELECT id, gala_categorie_id, texte, ponderation
        FROM question
        WHERE gala_categorie_id IN ({placeholders})
        ORDER BY id ASC
        """,
        tuple(unique_ids),
    ).fetchall()

    question_map: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows:
        bucket = question_map.setdefault(row["gala_categorie_id"], [])
        bucket.append(
            {
                "id": row["id"],
                "texte": row["texte"],
                "ponderation": row["ponderation"],
            }
        )

    for bucket in question_map.values():
        for index, question in enumerate(bucket, start=1):
            question["ordre"] = index

    return question_map


def _fetch_responses_by_participant(conn, participant_ids: List[int]) -> Dict[int, Dict[int, Optional[str]]]:
    if not participant_ids:
        return {}

    unique_ids = sorted(set(participant_ids))
    placeholders = ",".join("?" for _ in unique_ids)
    rows = conn.execute(
        f"""
        SELECT participant_id, question_id, contenu
        FROM reponse_participant
        WHERE participant_id IN ({placeholders})
        """,
        tuple(unique_ids),
    ).fetchall()

    responses: Dict[int, Dict[int, Optional[str]]] = {}
    for row in rows:
        participant_bucket = responses.setdefault(row["participant_id"], {})
        participant_bucket[row["question_id"]] = row["contenu"]
    return responses


MAX_RESPONSE_LENGTH = 10000


@admin_bp.route("/api/participants", methods=["GET"])
def list_admin_participants():
    gala_id = request.args.get("gala_id", type=int)
    categorie_id = request.args.get("categorie_id", type=int)
    search = (request.args.get("q") or "").strip()

    conn = get_db_connection()
    filters_payload = _build_admin_participant_filters(conn)
    narratif_by_gala = _fetch_narratif_gala_categories(conn)
    narratif_ids_set = {cat_id for values in narratif_by_gala.values() for cat_id in values}

    base_query = """
        SELECT
            p.id AS participant_id,
            p.segment_id,
            comp.id AS compagnie_id,
            comp.nom AS compagnie_nom,
            comp.secteur,
            comp.ville,
            comp.telephone,
            comp.courriel,
            comp.responsable_nom,
            comp.responsable_titre,
            comp.site_web,
            gc.id AS gala_categorie_id,
            cat.nom AS categorie_nom,
            g.id AS gala_id,
            g.nom AS gala_nom,
            g.annee AS gala_annee,
            seg.nom AS segment_nom
        FROM participant AS p
        JOIN compagnie AS comp ON comp.id = p.compagnie_id
        JOIN gala_categorie AS gc ON gc.id = p.gala_categorie_id
        JOIN categorie AS cat ON cat.id = gc.categorie_id
        JOIN gala AS g ON g.id = gc.gala_id
        LEFT JOIN segment AS seg ON seg.id = p.segment_id
    """

    clauses: List[str] = []
    params: List[Any] = []

    if gala_id:
        clauses.append("g.id = ?")
        params.append(gala_id)

    if categorie_id:
        clauses.append("gc.id = ?")
        params.append(categorie_id)

    if search:
        like_pattern = f"%{search}%"
        clauses.append(
            "("
            "comp.nom LIKE ? OR "
            "comp.courriel LIKE ? OR "
            "comp.ville LIKE ? OR "
            "comp.responsable_nom LIKE ? OR "
            "comp.responsable_titre LIKE ? OR "
            "comp.secteur LIKE ?"
            ")"
        )
        params.extend([like_pattern] * 6)

    if not categorie_id or categorie_id not in narratif_ids_set:
        clauses.append("LOWER(cat.nom) NOT LIKE 'narratif%'")

    where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    order_clause = " ORDER BY g.annee DESC, cat.nom COLLATE NOCASE, comp.nom COLLATE NOCASE"

    participant_rows = conn.execute(
        base_query + where_clause + order_clause,
        tuple(params),
    ).fetchall()

    participant_ids = [row["participant_id"] for row in participant_rows]
    category_ids = [row["gala_categorie_id"] for row in participant_rows]

    relevant_gala_ids = {row["gala_id"] for row in participant_rows}
    relevant_narratif_ids = sorted(
        {cat_id for gala in relevant_gala_ids for cat_id in narratif_by_gala.get(gala, [])}
    )

    narratif_participant_map: Dict[tuple[int, int], Dict[str, int]] = {}
    narrative_participant_ids: List[int] = []

    if relevant_narratif_ids:
        placeholders = ",".join("?" for _ in relevant_narratif_ids)
        narratif_rows = conn.execute(
            f"""
            SELECT
                p.id AS participant_id,
                p.compagnie_id,
                gc.gala_id,
                gc.id AS gala_categorie_id
            FROM participant AS p
            JOIN gala_categorie AS gc ON gc.id = p.gala_categorie_id
            WHERE p.gala_categorie_id IN ({placeholders})
            """,
            tuple(relevant_narratif_ids),
        ).fetchall()

        for row in narratif_rows:
            key = (row["gala_id"], row["compagnie_id"])
            narratif_participant_map[key] = {
                "participant_id": row["participant_id"],
                "gala_categorie_id": row["gala_categorie_id"],
            }
            narrative_participant_ids.append(row["participant_id"])

        category_ids.extend(relevant_narratif_ids)

    all_participant_ids = participant_ids + narrative_participant_ids

    questions_map = _fetch_questions_by_category(conn, category_ids)
    responses_map = _fetch_responses_by_participant(conn, all_participant_ids)

    participants_payload: List[Dict[str, Any]] = []
    for row in participant_rows:
        participant_id = row["participant_id"]
        gala_categorie_id = row["gala_categorie_id"]
        questions = questions_map.get(gala_categorie_id, [])
        participant_responses = responses_map.get(participant_id, {})

        responses_payload: List[Dict[str, Any]] = []
        answered_count = 0
        for question in questions:
            answer_text = participant_responses.get(question["id"])
            if answer_text is not None and str(answer_text).strip():
                answered_count += 1
            responses_payload.append(
                {
                    "question_id": question["id"],
                    "ordre": question["ordre"],
                    "texte": question["texte"],
                    "ponderation": question["ponderation"],
                    "contenu": answer_text,
                }
            )

        narratif_info = narratif_participant_map.get((row["gala_id"], row["compagnie_id"]))
        if narratif_info:
            narratif_questions = questions_map.get(narratif_info["gala_categorie_id"], [])
            narratif_responses = responses_map.get(narratif_info["participant_id"], {})
            for question in narratif_questions:
                answer_text = narratif_responses.get(question["id"])
                if answer_text is None:
                    continue
                if not str(answer_text).strip():
                    continue
                responses_payload.append(
                    {
                        "question_id": question["id"],
                        "ordre": question["ordre"],
                        "texte": question["texte"],
                        "ponderation": question["ponderation"],
                        "contenu": answer_text,
                        "origin": "narratif",
                    }
                )

        total_questions = len(questions)
        completion_percent = round((answered_count / total_questions) * 100, 1) if total_questions else 0.0

        participants_payload.append(
            {
                "id": participant_id,
                "gala": {
                    "id": row["gala_id"],
                    "nom": row["gala_nom"],
                    "annee": row["gala_annee"],
                },
                "categorie": {
                    "id": gala_categorie_id,
                    "nom": row["categorie_nom"],
                    "segment": row["segment_nom"],
                    "segment_id": row["segment_id"],
                },
                "compagnie": {
                    "id": row["compagnie_id"],
                    "nom": row["compagnie_nom"],
                    "ville": row["ville"],
                    "secteur": row["secteur"],
                    "telephone": row["telephone"],
                    "courriel": row["courriel"],
                    "responsable_nom": row["responsable_nom"],
                    "responsable_titre": row["responsable_titre"],
                    "site_web": row["site_web"],
                },
                "responses": responses_payload,
                "stats": {
                    "answered": answered_count,
                    "total_questions": total_questions,
                    "missing": max(total_questions - answered_count, 0),
                    "completion_percent": completion_percent,
                },
            }
        )

    conn.close()

    return jsonify(
        {
            "filters": {
                "galas": filters_payload,
                "selected": {
                    "gala_id": gala_id,
                    "categorie_id": categorie_id,
                    "q": search or None,
                },
            },
            "participants": participants_payload,
            "meta": {
                "total": len(participants_payload),
            },
        }
    )


@admin_bp.route("/api/participants/<int:participant_id>/responses", methods=["GET"])
def get_participant_responses(participant_id: int):
    conn = get_db_connection()
    participant_row = conn.execute(
        """
        SELECT
            p.id,
            p.gala_categorie_id,
            gc.gala_id,
            comp.nom AS compagnie_nom,
            comp.ville AS compagnie_ville,
            comp.secteur AS compagnie_secteur,
            c.nom AS categorie_nom
        FROM participant AS p
        JOIN compagnie AS comp ON comp.id = p.compagnie_id
        JOIN gala_categorie AS gc ON gc.id = p.gala_categorie_id
        JOIN categorie AS c ON c.id = gc.categorie_id
        WHERE p.id = ?
        """,
        (participant_id,),
    ).fetchone()
    if not participant_row:
        conn.close()
        abort(404)

    question_rows = conn.execute(
        """
        SELECT q.id, q.texte, q.ponderation, r.contenu AS reponse
        FROM question AS q
        LEFT JOIN reponse_participant AS r
            ON r.question_id = q.id AND r.participant_id = ?
        WHERE q.gala_categorie_id = ?
        ORDER BY q.id ASC
        """,
        (participant_id, participant_row["gala_categorie_id"]),
    ).fetchall()

    questions_payload = [
        {
            "id": row["id"],
            "texte": row["texte"],
            "ponderation": row["ponderation"],
            "reponse": row["reponse"],
        }
        for row in question_rows
    ]

    payload = {
        "participant": {
            "id": participant_row["id"],
            "compagnie": participant_row["compagnie_nom"],
            "ville": participant_row["compagnie_ville"],
            "secteur": participant_row["compagnie_secteur"],
        },
        "category": {
            "id": participant_row["gala_categorie_id"],
            "nom": participant_row["categorie_nom"],
        },
        "questions": questions_payload,
    }
    conn.close()
    return jsonify(payload)


@admin_bp.route("/api/participants/<int:participant_id>/questions/<int:question_id>", methods=["PATCH"])
def update_participant_response(participant_id: int, question_id: int):
    payload = request.get_json(silent=True) or {}
    contenu = payload.get("contenu")
    if contenu is not None:
        contenu = (contenu or "").strip()
        if len(contenu) > MAX_RESPONSE_LENGTH:
            return jsonify({"status": "error", "message": "Reponse trop longue."}), 400
        if not contenu:
            contenu = None

    conn = get_db_connection()
    participant_row = conn.execute(
        "SELECT id, gala_categorie_id FROM participant WHERE id = ?",
        (participant_id,),
    ).fetchone()
    if not participant_row:
        conn.close()
        abort(404)

    question_row = conn.execute(
        "SELECT id FROM question WHERE id = ? AND gala_categorie_id = ?",
        (question_id, participant_row["gala_categorie_id"]),
    ).fetchone()
    if not question_row:
        conn.close()
        abort(404)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO reponse_participant (participant_id, question_id, contenu)
        VALUES (?, ?, ?)
        ON CONFLICT(participant_id, question_id)
        DO UPDATE SET contenu = excluded.contenu
        """,
        (participant_id, question_id, contenu),
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "question_id": question_id, "contenu": contenu})



# ==============================
# Admin Results dashboard
# ==============================
@admin_bp.route("/api/results", methods=["GET"])
def admin_results_dashboard():
    gala_id = request.args.get("gala_id", type=int)
    selected_category_id = request.args.get("categorie_id", type=int)

    conn = get_db_connection()

    gala_rows = conn.execute(
        "SELECT id, nom, annee FROM gala ORDER BY annee DESC, id DESC"
    ).fetchall()

    gala_options = [
        {"id": row["id"], "nom": row["nom"], "annee": row["annee"]}
        for row in gala_rows
    ]

    if not gala_rows:
        conn.close()
        return jsonify({
            "filters": {
                "galas": [],
                "categories": [],
                "selected": {"gala_id": None, "categorie_id": None},
            },
            "meta": {
                "favorite_bonus": FAVORITE_BONUS,
            },
            "judges": [],
            "categories": [],
        })

    available_gala_ids = {row["id"] for row in gala_rows}
    target_gala_id = gala_id if gala_id in available_gala_ids else gala_rows[0]["id"]
    gala_info_row = next(row for row in gala_rows if row["id"] == target_gala_id)

    category_rows = conn.execute(
        """
        SELECT
            gc.id,
            gc.ordre_affichage,
            c.nom,
            COUNT(DISTINCT q.id) AS question_count,
            COUNT(DISTINCT p.id) AS participant_count
        FROM gala_categorie AS gc
        JOIN categorie AS c ON c.id = gc.categorie_id
        LEFT JOIN question AS q ON q.gala_categorie_id = gc.id
        LEFT JOIN participant AS p ON p.gala_categorie_id = gc.id
        WHERE gc.gala_id = ?
        GROUP BY gc.id
        ORDER BY gc.ordre_affichage, c.nom COLLATE NOCASE
        """,
        (target_gala_id,),
    ).fetchall()

    category_options = [
        {
            "id": row["id"],
            "nom": row["nom"],
            "question_count": row["question_count"],
            "participant_count": row["participant_count"],
        }
        for row in category_rows
    ]

    category_ids_all = [row["id"] for row in category_rows]

    if not category_rows:
        conn.close()
        return jsonify({
            "filters": {
                "galas": gala_options,
                "categories": [],
                "selected": {"gala_id": target_gala_id, "categorie_id": None},
            },
            "meta": {
                "gala": {
                    "id": gala_info_row["id"],
                    "nom": gala_info_row["nom"],
                    "annee": gala_info_row["annee"],
                },
                "favorite_bonus": FAVORITE_BONUS,
                "overall_completion_percent": 0.0,
                "overall_recorded": 0,
                "overall_expected": 0,
                "judges_total": 0,
                "judges_submitted": 0,
                "participants_total": 0,
                "categories_total": 0,
            },
            "judges": [],
            "categories": [],
        })

    if selected_category_id and selected_category_id not in category_ids_all:
        selected_category_id = None

    if selected_category_id:
        category_ids = [selected_category_id]
    else:
        category_ids = category_ids_all[:]

    categories_lookup: Dict[int, Dict[str, Any]] = {}
    for row in category_rows:
        categories_lookup[row["id"]] = {
            "id": row["id"],
            "nom": row["nom"],
            "question_count": row["question_count"],
            "participant_count": row["participant_count"],
            "judge_count": 0,
            "total_weight": 0.0,
            "participants": [],
            "recorded_notes": 0,
            "expected_notes_total": 0,
            "favorites_count": 0,
        }

    if category_ids_all:
        placeholders_all = ",".join("?" for _ in category_ids_all)
        judge_counts_rows = conn.execute(
            f"""
            SELECT jgc.gala_categorie_id, COUNT(DISTINCT jgc.juge_id) AS judge_count
            FROM juge_gala_categorie AS jgc
            WHERE jgc.gala_categorie_id IN ({placeholders_all})
            GROUP BY jgc.gala_categorie_id
            """,
            tuple(category_ids_all),
        ).fetchall()
        weight_rows = conn.execute(
            f"""
            SELECT gala_categorie_id, SUM(ponderation) AS total_weight
            FROM question
            WHERE gala_categorie_id IN ({placeholders_all})
            GROUP BY gala_categorie_id
            """,
            tuple(category_ids_all),
        ).fetchall()
    else:
        judge_counts_rows = []
        weight_rows = []

    judge_counts_map = {row["gala_categorie_id"]: row["judge_count"] for row in judge_counts_rows}
    weight_map = {row["gala_categorie_id"]: row["total_weight"] or 0.0 for row in weight_rows}

    for cat_id, info in categories_lookup.items():
        judge_count = judge_counts_map.get(cat_id, 0)
        info["judge_count"] = judge_count
        info["total_weight"] = weight_map.get(cat_id, 0.0) or 0.0
        info["expected_notes_total"] = info["question_count"] * info["participant_count"] * judge_count

    favorite_rows = conn.execute(
        """
        SELECT cdc.participant_id, cdc.juge_id, per.prenom, per.nom
        FROM coup_de_coeur AS cdc
        JOIN juge AS j ON j.id = cdc.juge_id
        JOIN user AS u ON u.id = j.user_id
        JOIN personne AS per ON per.id = u.personne_id
        WHERE cdc.gala_id = ?
        """,
        (target_gala_id,),
    ).fetchall()

    favorite_lists: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in favorite_rows:
        favorite_lists[row["participant_id"]].append(
            {
                "juge_id": row["juge_id"],
                "nom": f"{row['prenom']} {row['nom']}",
            }
        )

    judge_rows = conn.execute(
        """
        SELECT DISTINCT j.id AS juge_id, per.prenom, per.nom
        FROM juge_gala_categorie AS jgc
        JOIN juge AS j ON j.id = jgc.juge_id
        JOIN user AS u ON u.id = j.user_id
        JOIN personne AS per ON per.id = u.personne_id
        JOIN gala_categorie AS gc ON gc.id = jgc.gala_categorie_id
        WHERE gc.gala_id = ?
        ORDER BY per.nom COLLATE NOCASE, per.prenom COLLATE NOCASE
        """,
        (target_gala_id,),
    ).fetchall()

    if category_ids:
        placeholders_selected = ",".join("?" for _ in category_ids)
        expected_rows = conn.execute(
            f"""
            SELECT jgc.juge_id, COUNT(*) AS total_required
            FROM juge_gala_categorie AS jgc
            JOIN question AS q ON q.gala_categorie_id = jgc.gala_categorie_id
            JOIN participant AS p ON p.gala_categorie_id = jgc.gala_categorie_id
            WHERE jgc.gala_categorie_id IN ({placeholders_selected})
            GROUP BY jgc.juge_id
            """,
            tuple(category_ids),
        ).fetchall()
    else:
        expected_rows = []

    answered_rows = conn.execute(
        """
        SELECT n.juge_id, COUNT(*) AS total_answered
        FROM note AS n
        JOIN participant AS p ON p.id = n.participant_id
        JOIN gala_categorie AS gc ON gc.id = p.gala_categorie_id
        WHERE gc.gala_id = ?
        GROUP BY n.juge_id
        """,
        (target_gala_id,),
    ).fetchall()

    submission_rows = conn.execute(
        "SELECT juge_id, submitted_at FROM juge_gala_submission WHERE gala_id = ?",
        (target_gala_id,),
    ).fetchall()

    expected_map = {row["juge_id"]: row["total_required"] for row in expected_rows}
    answered_map = {row["juge_id"]: row["total_answered"] for row in answered_rows}
    submitted_map = {row["juge_id"]: row["submitted_at"] for row in submission_rows}

    judges_payload: List[Dict[str, Any]] = []
    for row in judge_rows:
        juge_id = row["juge_id"]
        expected_total = expected_map.get(juge_id, 0)
        answered_total = answered_map.get(juge_id, 0)
        percent = round((answered_total / expected_total) * 100, 1) if expected_total else 0.0
        submitted_at = submitted_map.get(juge_id)
        submitted = submitted_at is not None
        status = "soumis" if submitted else ("en_cours" if answered_total > 0 else "en_attente")
        judges_payload.append(
            {
                "id": juge_id,
                "prenom": row["prenom"],
                "nom": row["nom"],
                "answered_notes": answered_total,
                "expected_notes": expected_total,
                "progress_percent": percent,
                "submitted": submitted,
                "submitted_at": submitted_at,
                "status": status,
            }
        )

    if not category_ids:
        conn.close()
        return jsonify({
            "filters": {
                "galas": gala_options,
                "categories": category_options,
                "selected": {"gala_id": target_gala_id, "categorie_id": selected_category_id},
            },
            "meta": {
                "gala": {
                    "id": gala_info_row["id"],
                    "nom": gala_info_row["nom"],
                    "annee": gala_info_row["annee"],
                },
                "favorite_bonus": FAVORITE_BONUS,
                "overall_completion_percent": 0.0,
                "overall_recorded": 0,
                "overall_expected": 0,
                "judges_total": len(judges_payload),
                "judges_submitted": sum(1 for judge in judges_payload if judge["submitted"]),
                "participants_total": 0,
                "categories_total": 0,
            },
            "judges": judges_payload,
            "categories": [],
        })

    placeholders_selected = ",".join("?" for _ in category_ids)
    participant_rows = conn.execute(
        f"""
        SELECT
            p.id AS participant_id,
            p.gala_categorie_id,
            comp.nom AS compagnie_nom,
            comp.ville AS compagnie_ville,
            comp.secteur AS compagnie_secteur,
            SUM(CASE WHEN n.valeur IS NOT NULL THEN n.valeur * q.ponderation ELSE 0 END) AS weighted_sum,
            SUM(CASE WHEN n.valeur IS NOT NULL THEN q.ponderation ELSE 0 END) AS answered_weight,
            COUNT(DISTINCT CASE WHEN n.valeur IS NOT NULL THEN n.juge_id END) AS judges_answered,
            COUNT(DISTINCT CASE WHEN n.valeur IS NOT NULL THEN q.id || '-' || n.juge_id END) AS notes_recorded
        FROM participant AS p
        JOIN compagnie AS comp ON comp.id = p.compagnie_id
        JOIN question AS q ON q.gala_categorie_id = p.gala_categorie_id
        LEFT JOIN note AS n ON n.question_id = q.id AND n.participant_id = p.id
        WHERE p.gala_categorie_id IN ({placeholders_selected})
        GROUP BY p.id, p.gala_categorie_id, comp.nom, comp.ville, comp.secteur
        ORDER BY comp.nom COLLATE NOCASE
        """,
        tuple(category_ids),
    ).fetchall()

    categories_to_include = [row for row in category_rows if row["id"] in category_ids]

    for info in categories_lookup.values():
        info["recorded_notes"] = 0
        info["favorites_count"] = 0

    for row in participant_rows:
        category_id = row["gala_categorie_id"]
        info = categories_lookup.get(category_id)
        if not info:
            continue
        weighted_sum = row["weighted_sum"] or 0.0
        answered_weight = row["answered_weight"] or 0.0
        base_score = None
        if answered_weight > 0:
            base_score = weighted_sum / answered_weight
        favorite_entries = favorite_lists.get(row["participant_id"], [])
        bonus_value = len(favorite_entries) * FAVORITE_BONUS
        final_score = base_score + bonus_value if base_score is not None else None

        question_count = info["question_count"] or 0
        judge_count = info["judge_count"] or 0
        notes_expected = question_count * judge_count
        notes_recorded = row["notes_recorded"] or 0

        info["recorded_notes"] += notes_recorded
        info["favorites_count"] += len(favorite_entries)

        if notes_expected <= 0:
            participant_status = "en_attente"
        elif notes_recorded == 0:
            participant_status = "en_attente"
        elif notes_recorded >= notes_expected:
            participant_status = "complet"
        else:
            participant_status = "en_cours"

        progress_percent = round((notes_recorded / notes_expected) * 100, 1) if notes_expected else 0.0

        participant_payload = {
            "id": row["participant_id"],
            "compagnie": {
                "nom": row["compagnie_nom"],
                "ville": row["compagnie_ville"],
                "secteur": row["compagnie_secteur"],
            },
            "score_base": round(base_score, 2) if base_score is not None else None,
            "score_bonus": round(bonus_value, 2) if bonus_value else 0.0,
            "score_final": round(final_score, 2) if final_score is not None else None,
            "score_value": final_score,
            "status": participant_status,
            "notes": {
                "recorded": notes_recorded,
                "expected": notes_expected,
                "progress_percent": progress_percent,
            },
            "favorites": [fav["nom"] for fav in favorite_entries],
            "favorites_count": len(favorite_entries),
            "judges_answered": row["judges_answered"] or 0,
        }

        info["participants"].append(participant_payload)

    categories_payload: List[Dict[str, Any]] = []
    participants_total = 0
    overall_expected_notes = 0
    overall_recorded_notes = 0

    for category_row in categories_to_include:
        info = categories_lookup[category_row["id"]]
        total_expected = info["expected_notes_total"]
        overall_expected_notes += total_expected
        overall_recorded_notes += info["recorded_notes"]

        if total_expected == 0:
            category_status = "en_attente"
        elif info["recorded_notes"] == 0:
            category_status = "en_attente"
        elif info["recorded_notes"] >= total_expected:
            category_status = "complet"
        else:
            category_status = "en_cours"

        progress_percent = round((info["recorded_notes"] / total_expected) * 100, 1) if total_expected else 0.0



        participants_sorted = sorted(
            info["participants"],
            key=lambda item: (
                item.get("score_value") is None,
                -(item.get("score_value") or 0.0),
                (item["compagnie"]["nom"] or "").lower(),
            ),
        )

        participants_total += len(participants_sorted)

        rank_counter = 0
        current_rank = 0
        previous_score = None
        for participant in participants_sorted:
            value = participant.get("score_value")
            if value is None:
                participant["rank"] = None
                continue
            rank_counter += 1
            if previous_score is None or abs(value - previous_score) > 1e-6:
                current_rank = rank_counter
                previous_score = value
            participant["rank"] = current_rank

        top_participant = next((p for p in participants_sorted if p.get("rank") == 1), None)

        for participant in participants_sorted:
            participant.pop("score_value", None)

        categories_payload.append(
            {
                "id": info["id"],
                "nom": info["nom"],
                "question_count": info["question_count"],
                "participant_count": info["participant_count"],
                "judge_count": info["judge_count"],
                "status": category_status,
                "progress": {
                    "percent": progress_percent,
                    "recorded": info["recorded_notes"],
                    "expected": total_expected,
                },
                "participants": participants_sorted,
                "top_participant": top_participant,
                "favorites_count": info["favorites_count"],
            }
        )

    overall_completion_percent = round((overall_recorded_notes / overall_expected_notes) * 100, 1) if overall_expected_notes else 0.0

    judges_total = len(judges_payload)
    judges_submitted = sum(1 for judge in judges_payload if judge["submitted"])

    meta_payload = {
        "gala": {
            "id": gala_info_row["id"],
            "nom": gala_info_row["nom"],
            "annee": gala_info_row["annee"],
        },
        "favorite_bonus": FAVORITE_BONUS,
        "overall_completion_percent": overall_completion_percent,
        "overall_recorded": overall_recorded_notes,
        "overall_expected": overall_expected_notes,
        "judges_total": judges_total,
        "judges_submitted": judges_submitted,
        "participants_total": participants_total,
        "categories_total": len(categories_payload),
    }

    response = {
        "filters": {
            "galas": gala_options,
            "categories": category_options,
            "selected": {
                "gala_id": target_gala_id,
                "categorie_id": selected_category_id,
            },
        },
        "meta": meta_payload,
        "judges": judges_payload,
        "categories": categories_payload,
    }

    conn.close()
    return jsonify(response)
