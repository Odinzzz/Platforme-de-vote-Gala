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


# ==============================
# Admin Gala management
# ==============================
@admin_bp.route("/galas", methods=["GET"])
def galas_page():
    return render_template("admin/galas.html", user=session.get("user"))


def _serialize_gala_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "nom": row["nom"],
        "annee": row["annee"],
        "lieu": row["lieu"],
        "date_gala": row["date_gala"],
        "categories_count": row["categories_count"],
        "questions_count": row["questions_count"],
    }


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
    conn.close()
    payload = [_serialize_gala_row(row) for row in rows]
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

    conn.close()

    gala_payload = {
        "id": gala_row["id"],
        "nom": gala_row["nom"],
        "annee": gala_row["annee"],
        "lieu": gala_row["lieu"],
        "date_gala": gala_row["date_gala"],
    }
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

    updated_row = _fetch_gala(conn, gala_id)
    conn.close()

    data = {
        "id": updated_row["id"],
        "nom": updated_row["nom"],
        "annee": updated_row["annee"],
        "lieu": updated_row["lieu"],
        "date_gala": updated_row["date_gala"],
    }
    return jsonify({"status": "ok", "gala": data})


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


