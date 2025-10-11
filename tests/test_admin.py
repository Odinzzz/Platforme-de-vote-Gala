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


def test_admin_create_and_list_galas(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    create_resp = client.post(
        "/admin/api/galas",
        json={"nom": "Gala 2025", "annee": 2025, "lieu": "Quebec", "date_gala": "2025-05-01"},
    )
    assert create_resp.status_code == 201
    payload = create_resp.get_json()
    assert payload["status"] == "ok"
    gala_id = payload["gala"]["id"]

    list_resp = client.get("/admin/api/galas")
    assert list_resp.status_code == 200
    data = list_resp.get_json()
    assert any(gala["id"] == gala_id for gala in data["galas"])


def test_admin_gala_detail_lists_categories(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Test", 2024, "Quebec", "2024-06-01"),
    ).lastrowid
    cat_a = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    cat_b = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("RH", ""),
    ).lastrowid
    cat_c = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Developpement durable", ""),
    ).lastrowid
    conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, cat_a, 1),
    )
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    detail_resp = client.get(f"/admin/api/galas/{gala_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    assert detail["gala"]["nom"] == "Gala Test"
    assert len(detail["categories"]) == 1
    available_ids = {cat["id"] for cat in detail["available_categories"]}
    assert available_ids == {cat_b, cat_c}


def test_admin_add_categories_and_questions(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Questions", 2026, "Quebec", "2026-04-15"),
    ).lastrowid
    cat_a = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    cat_b = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Croissance", ""),
    ).lastrowid
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    add_resp = client.post(
        f"/admin/api/galas/{gala_id}/categories",
        json={"categorie_ids": [cat_a, cat_b]},
    )
    assert add_resp.status_code == 200
    detail = add_resp.get_json()
    assert len(detail["categories"]) == 2

    gala_cat_id = detail["categories"][0]["id"]

    question_resp = client.post(
        f"/admin/api/galas/{gala_id}/categories/{gala_cat_id}/questions",
        json={"texte": "Vision strategique", "ponderation": 2},
    )
    assert question_resp.status_code == 200
    questions_payload = question_resp.get_json()
    assert any(q["texte"] == "Vision strategique" for q in questions_payload["questions"])
    question_id = questions_payload["questions"][0]["id"]

    list_resp = client.get(
        f"/admin/api/galas/{gala_id}/categories/{gala_cat_id}/questions"
    )
    assert list_resp.status_code == 200
    questions = list_resp.get_json()["questions"]
    assert len(questions) == 1
    assert questions[0]["ponderation"] == 2.0

    refreshed_detail = client.get(f"/admin/api/galas/{gala_id}").get_json()
    counts_after_create = {cat["id"]: cat["questions_count"] for cat in refreshed_detail["categories"]}
    assert counts_after_create[gala_cat_id] == 1

    update_resp = client.patch(
        f"/admin/api/galas/{gala_id}/categories/{gala_cat_id}/questions/{question_id}",
        json={"texte": "Vision revisee", "ponderation": 3},
    )
    assert update_resp.status_code == 200
    updated_payload = update_resp.get_json()
    assert any(q["texte"] == "Vision revisee" and q["ponderation"] == 3 for q in updated_payload["questions"])

    refreshed_after_update = client.get(f"/admin/api/galas/{gala_id}").get_json()
    counts_after_update = {cat["id"]: cat["questions_count"] for cat in refreshed_after_update["categories"]}
    assert counts_after_update[gala_cat_id] == 1

    delete_resp = client.delete(
        f"/admin/api/galas/{gala_id}/categories/{gala_cat_id}/questions/{question_id}"
    )
    assert delete_resp.status_code == 200
    delete_payload = delete_resp.get_json()
    assert delete_payload["questions"] == []

    refreshed_after_delete = client.get(f"/admin/api/galas/{gala_id}").get_json()
    counts_after_delete = {cat["id"]: cat["questions_count"] for cat in refreshed_after_delete["categories"]}
    assert counts_after_delete[gala_cat_id] == 0


def test_admin_create_category_and_attach(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Nouveau", 2027, "Quebec", "2027-05-10"),
    ).lastrowid
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    create_resp = client.post(
        "/admin/api/categories",
        json={"nom": "Categorie Unique", "description": "Description"},
    )
    assert create_resp.status_code == 201
    category_payload = create_resp.get_json()
    assert category_payload["status"] == "ok"
    category_id = category_payload["category"]["id"]

    attach_resp = client.post(
        f"/admin/api/galas/{gala_id}/categories",
        json={"categorie_ids": [category_id]},
    )
    assert attach_resp.status_code == 200
    detail = attach_resp.get_json()
    assert any(cat["categorie_id"] == category_id for cat in detail["categories"])

    conn = db_module.get_db_connection()
    row = conn.execute(
        "SELECT id FROM categorie WHERE LOWER(nom) = LOWER(?)",
        ("Categorie Unique",),
    ).fetchone()
    conn.close()
    assert row is not None
