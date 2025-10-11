import sqlite3

from models import db as db_module


def seed_roles(conn):
    roles = {}
    for name, description in [
        ("admin", "Administrateur"),
        ("juge", "Juge"),
        ("membre", "Membre"),
    ]:
        roles[name] = conn.execute(
            "INSERT INTO role (nom, description) VALUES (?, ?)",
            (name, description),
        ).lastrowid
    return roles


def create_user(conn, prenom, nom, username, role_id):
    personne_id = conn.execute(
        "INSERT INTO personne (prenom, nom, courriel, telephone) VALUES (?, ?, ?, ?)",
        (prenom, nom, f"{username}@example.com", None),
    ).lastrowid
    user_id = conn.execute(
        "INSERT INTO user (personne_id, username, password_hash, role_id) VALUES (?, ?, ?, ?)",
        (personne_id, username, "hash", role_id),
    ).lastrowid
    return user_id


def admin_session(client, user_id, prenom="Admin", nom="Test", username="admin"):
    with client.session_transaction() as session:
        session["user"] = {
            "id": user_id,
            "username": username,
            "prenom": prenom,
            "nom": nom,
            "role": "admin",
        }


def test_admin_user_listing_groups_by_role(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    judge_id = create_user(conn, "Julie", "Juge", "juliejuge", roles["juge"])
    member_id = create_user(conn, "Marc", "Membre", "marcmembre", roles["membre"])
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    response = client.get("/admin/api/users")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["role_order"] == ["admin", "juge", "membre"]
    assert len(payload["users_by_role"]["admin"]) == 1
    assert payload["users_by_role"]["admin"][0]["username"] == "adminchef"
    assert len(payload["users_by_role"]["juge"]) == 1
    assert payload["users_by_role"]["juge"][0]["username"] == "juliejuge"
    assert len(payload["users_by_role"]["membre"]) == 1
    assert payload["users_by_role"]["membre"][0]["username"] == "marcmembre"


def test_admin_user_detail_includes_judge_assignments(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    judge_id = create_user(conn, "Julie", "Juge", "juliejuge", roles["juge"])

    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Distinction", 2025, "Quebec", "2025-05-01"),
    ).lastrowid
    categorie_a = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    categorie_b = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Croissance", ""),
    ).lastrowid
    gala_cat_a = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_a, 1),
    ).lastrowid
    gala_cat_b = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_b, 2),
    ).lastrowid

    judge_row_id = conn.execute(
        "INSERT INTO juge (user_id) VALUES (?)",
        (judge_id,),
    ).lastrowid
    conn.execute(
        "INSERT INTO juge_gala_categorie (juge_id, gala_categorie_id) VALUES (?, ?)",
        (judge_row_id, gala_cat_a),
    )
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    response = client.get(f"/admin/api/users/{judge_id}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["user"]["username"] == "juliejuge"
    assert (payload["user"]["role"] or "").lower() == "juge"
    assert isinstance(payload["roles"], list) and len(payload["roles"]) >= 3
    judge_section = payload["judge"]
    assert judge_section["judge_id"] is not None
    assert len(judge_section["assigned_ids"]) == 1
    assert judge_section["assigned_ids"][0] == gala_cat_a
    assert len(judge_section["galas"]) == 1
    categories = judge_section["galas"][0]["categories"]
    assert any(cat["assigned"] for cat in categories)
    assert any(not cat["assigned"] for cat in categories)


def test_admin_update_role_promotes_to_judge(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    member_id = create_user(conn, "Lou", "Membre", "loumembre", roles["membre"])
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    response = client.patch(
        f"/admin/api/users/{member_id}/role",
        json={"role_id": roles["juge"]},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert (payload["user"]["role"] or "").lower() == "juge"

    conn = db_module.get_db_connection()
    judge_row = conn.execute(
        "SELECT id FROM juge WHERE user_id = ?",
        (member_id,),
    ).fetchone()
    conn.close()
    assert judge_row is not None


def test_admin_update_assignments_success(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    judge_id = create_user(conn, "Julie", "Juge", "juliejuge", roles["juge"])

    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Distinction", 2025, "Quebec", "2025-05-01"),
    ).lastrowid
    cat_a = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    cat_b = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Croissance", ""),
    ).lastrowid
    gala_cat_a = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, cat_a, 1),
    ).lastrowid
    gala_cat_b = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, cat_b, 2),
    ).lastrowid

    judge_row_id = conn.execute(
        "INSERT INTO juge (user_id) VALUES (?)",
        (judge_id,),
    ).lastrowid
    conn.execute(
        "INSERT INTO juge_gala_categorie (juge_id, gala_categorie_id) VALUES (?, ?)",
        (judge_row_id, gala_cat_a),
    )
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    response = client.patch(
        f"/admin/api/users/{judge_id}/assignments",
        json={"gala_categorie_ids": [gala_cat_b]},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert gala_cat_b in payload["judge"]["assigned_ids"]
    assert gala_cat_a not in payload["judge"]["assigned_ids"]

    conn = db_module.get_db_connection()
    rows = conn.execute(
        "SELECT gala_categorie_id FROM juge_gala_categorie WHERE juge_id = ?",
        (payload["judge"]["judge_id"],),
    ).fetchall()
    conn.close()
    saved_ids = {row["gala_categorie_id"] for row in rows}
    assert saved_ids == {gala_cat_b}


def test_admin_update_assignments_requires_judge_role(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    member_id = create_user(conn, "Lou", "Membre", "loumembre", roles["membre"])
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    response = client.patch(
        f"/admin/api/users/{member_id}/assignments",
        json={"gala_categorie_ids": []},
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "juge" in payload["message"].lower()
