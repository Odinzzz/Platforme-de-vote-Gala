from typing import Any, Dict, List

from flask import Blueprint, render_template, session, jsonify, request, abort

from models.db import get_db_connection

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ROLE_DISPLAY_ORDER = ["admin", "juge", "membre"]


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
