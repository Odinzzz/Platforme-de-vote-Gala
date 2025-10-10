from datetime import datetime, UTC
from flask import Blueprint, render_template, session, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from models.db import get_db_connection

main_bp = Blueprint("main", __name__)


def _serialize_user_row(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "prenom": row["prenom"],
        "nom": row["nom"],
    }


@main_bp.route("/")
def home():
    user = session.get("user")
    return render_template("index.html", user=user)


@main_bp.route("/auth/register", methods=["POST"])
def register():
    payload = request.get_json(silent=True) or {}
    prenom = (payload.get("prenom") or "").strip()
    nom = (payload.get("nom") or "").strip()
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    courriel = (payload.get("courriel") or "").strip() or None
    telephone = (payload.get("telephone") or "").strip() or None

    missing = [field for field, value in {
        "prenom": prenom,
        "nom": nom,
        "username": username,
        "password": password,
    }.items() if not value]

    if missing:
        return jsonify({"status": "error", "message": "Champs manquants: " + ", ".join(missing)}), 400

    if len(password) < 8:
        return jsonify({"status": "error", "message": "Le mot de passe doit contenir au moins 8 caracteres."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    existing = cursor.execute(
        """
        SELECT user.id
        FROM user
        WHERE LOWER(username) = LOWER(?)
        """,
        (username,),
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({"status": "error", "message": "Ce nom d'utilisateur est deja utilise."}), 409

    role_name = "membre"
    role_row = cursor.execute(
        """
        SELECT id
        FROM role
        WHERE LOWER(nom) = LOWER(?)
        """,
        (role_name,),
    ).fetchone()

    if role_row:
        role_id = role_row["id"]
    else:
        cursor.execute(
            """
            INSERT INTO role (nom, description)
            VALUES (?, ?)
            """,
            (role_name, "Role membre par defaut"),
        )
        role_id = cursor.lastrowid

    password_hash = generate_password_hash(password)

    cursor.execute(
        """
        INSERT INTO personne (prenom, nom, courriel, telephone)
        VALUES (?, ?, ?, ?)
        """,
        (prenom, nom, courriel, telephone),
    )
    personne_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO user (personne_id, username, password_hash, role_id)
        VALUES (?, ?, ?, ?)
        """,
        (personne_id, username, password_hash, role_id),
    )
    user_id = cursor.lastrowid

    conn.commit()

    row = cursor.execute(
        """
        SELECT user.id, user.username, personne.prenom, personne.nom
        FROM user
        JOIN personne ON user.personne_id = personne.id
        WHERE user.id = ?
        """,
        (user_id,),
    ).fetchone()
    conn.close()

    user_data = _serialize_user_row(row)
    session["user"] = user_data

    return jsonify({"status": "ok", "user": user_data}), 201


@main_bp.route("/auth/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return jsonify({"status": "error", "message": "Nom d'utilisateur et mot de passe requis."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        """
        SELECT user.id, user.username, user.password_hash, user.actif, personne.prenom, personne.nom
        FROM user
        JOIN personne ON user.personne_id = personne.id
        WHERE LOWER(user.username) = LOWER(?)
        """,
        (username,),
    ).fetchone()

    if not row or not row["actif"]:
        conn.close()
        return jsonify({"status": "error", "message": "Identifiants invalides."}), 401

    if not check_password_hash(row["password_hash"], password):
        conn.close()
        return jsonify({"status": "error", "message": "Identifiants invalides."}), 401

    cursor.execute(
        "UPDATE user SET last_login = ? WHERE id = ?",
        (datetime.now(UTC).isoformat(), row["id"]),
    )
    conn.commit()
    conn.close()

    user_data = _serialize_user_row(row)
    session["user"] = user_data

    return jsonify({"status": "ok", "user": user_data}), 200


@main_bp.route("/auth/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return jsonify({"status": "ok"}), 200
