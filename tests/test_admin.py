from models import db as db_module
from tests.helpers import seed_roles, create_user, set_session


def admin_session(client, user_id, prenom="Admin", nom="Test", username="admin"):
    set_session(client, {
        "id": user_id,
        "username": username,
        "prenom": prenom,
        "nom": nom,
        "role": "admin",
    })




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


def test_admin_lock_and_unlock_gala(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala a verrouiller", 2028, "Montreal", "2028-06-01"),
    ).lastrowid
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    lock_resp = client.post(f"/admin/api/galas/{gala_id}/lock")
    assert lock_resp.status_code == 200
    lock_payload = lock_resp.get_json()
    assert lock_payload["gala"]["locked"] is True
    assert lock_payload["gala"].get("locked_at")

    duplicate_resp = client.post(f"/admin/api/galas/{gala_id}/lock")
    assert duplicate_resp.status_code == 409
    duplicate_payload = duplicate_resp.get_json()
    assert duplicate_payload["message"] == "Gala deja verrouille."

    unlock_resp = client.delete(f"/admin/api/galas/{gala_id}/lock")
    assert unlock_resp.status_code == 200
    unlock_payload = unlock_resp.get_json()
    assert unlock_payload["gala"]["locked"] is False

    update_resp = client.patch(
        f"/admin/api/galas/{gala_id}",
        json={"nom": "Gala Actualise"},
    )
    assert update_resp.status_code == 200
    update_payload = update_resp.get_json()
    assert update_payload["status"] == "ok"
    assert update_payload["gala"]["nom"] == "Gala Actualise"



def test_admin_lock_prevents_mutations(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])
    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Controle", 2029, "Quebec", "2029-05-15"),
    ).lastrowid
    cat_a = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    cat_b = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Croissance", ""),
    ).lastrowid
    gala_cat_id = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, cat_a, 1),
    ).lastrowid
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    create_question_resp = client.post(
        f"/admin/api/galas/{gala_id}/categories/{gala_cat_id}/questions",
        json={"texte": "Qualite", "ponderation": 1},
    )
    assert create_question_resp.status_code == 200
    created_questions = create_question_resp.get_json()["questions"]
    question_id = next(q["id"] for q in created_questions if q["texte"] == "Qualite")

    lock_resp = client.post(f"/admin/api/galas/{gala_id}/lock")
    assert lock_resp.status_code == 200

    update_resp = client.patch(
        f"/admin/api/galas/{gala_id}",
        json={"lieu": "Nouvel endroit"},
    )
    assert update_resp.status_code == 409
    assert update_resp.get_json()["message"] == "Ce gala est verrouille."

    add_category_resp = client.post(
        f"/admin/api/galas/{gala_id}/categories",
        json={"categorie_ids": [cat_b]},
    )
    assert add_category_resp.status_code == 409
    assert add_category_resp.get_json()["message"] == "Ce gala est verrouille."

    create_question_locked = client.post(
        f"/admin/api/galas/{gala_id}/categories/{gala_cat_id}/questions",
        json={"texte": "Nouvelle question", "ponderation": 2},
    )
    assert create_question_locked.status_code == 409
    assert create_question_locked.get_json()["message"] == "Ce gala est verrouille."

    delete_question_locked = client.delete(
        f"/admin/api/galas/{gala_id}/categories/{gala_cat_id}/questions/{question_id}"
    )
    assert delete_question_locked.status_code == 409
    assert delete_question_locked.get_json()["message"] == "Ce gala est verrouille."


def test_admin_participants_api_returns_responses_and_filters(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])

    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Distinction", 2026, "Quebec", "2026-05-15"),
    ).lastrowid
    categorie_innov = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    categorie_croissance = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Croissance", ""),
    ).lastrowid
    categorie_narratif = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Narratif (general)", ""),
    ).lastrowid
    gala_cat_innov = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_innov, 1),
    ).lastrowid
    gala_cat_narratif = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_narratif, 0),
    ).lastrowid
    gala_cat_croissance = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_croissance, 2),
    ).lastrowid
    segment_id = conn.execute(
        "INSERT INTO segment (gala_categorie_id, nom) VALUES (?, ?)",
        (gala_cat_innov, "PME"),
    ).lastrowid

    compagnie_alpha = conn.execute(
        """
        INSERT INTO compagnie (nom, secteur, ville, courriel, telephone, responsable_nom, responsable_titre, site_web)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("Alpha Inc.", "Technologie", "Quebec", "alpha@example.com", "111-111-1111", "Alice Alpha", "PDG", "alpha.example.com"),
    ).lastrowid
    compagnie_beta = conn.execute(
        """
        INSERT INTO compagnie (nom, secteur, ville, courriel, telephone, responsable_nom, responsable_titre, site_web)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("Beta Corp.", "Service", "Montreal", "beta@example.com", "222-222-2222", "Benoit Beta", "Directeur", "beta.example.com"),
    ).lastrowid

    participant_alpha = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_alpha, gala_cat_innov, segment_id),
    ).lastrowid
    participant_alpha_narratif = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_alpha, gala_cat_narratif, None),
    ).lastrowid
    participant_beta = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_beta, gala_cat_croissance, None),
    ).lastrowid

    question_innov_a = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_innov, "Decrivez votre innovation.", 1.0),
    ).lastrowid
    question_innov_b = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_innov, "Quel impact sur votre marche?", 1.0),
    ).lastrowid
    question_croissance = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_croissance, "Quel est votre taux de croissance annuel moyen?", 1.0),
    ).lastrowid
    question_narratif = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_narratif, "Decrivez l'histoire de votre entreprise.", 1.0),
    ).lastrowid

    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_alpha, question_innov_a, "Une plateforme numerique pour le secteur manufacturier."),
    )
    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_alpha, question_innov_b, "Hausse de 30% des ventes chez nos clients."),
    )
    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_beta, question_croissance, ""),
    )
    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_alpha_narratif, question_narratif, "Nous avons debute dans un garage et grandi grace aux innovations."),
    )
    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Admin", nom="Chef", username="adminchef")

    response = client.get("/admin/api/participants")
    assert response.status_code == 200
    payload = response.get_json()

    filters = payload["filters"]
    assert filters["selected"]["gala_id"] is None
    assert filters["selected"]["categorie_id"] is None
    assert filters["selected"]["q"] is None
    assert len(filters["galas"]) == 1
    gala_entry = filters["galas"][0]
    assert gala_entry["id"] == gala_id
    assert gala_entry["participants_count"] == 2
    assert gala_entry["categories_count"] == 2
    categorie_ids = {cat["id"] for cat in gala_entry["categories"]}
    assert categorie_ids == {gala_cat_innov, gala_cat_croissance}

    participants = payload["participants"]
    assert payload["meta"]["total"] == len(participants) == 2
    alpha_entry = next(p for p in participants if p["id"] == participant_alpha)
    beta_entry = next(p for p in participants if p["id"] == participant_beta)

    assert alpha_entry["categorie"]["id"] == gala_cat_innov
    assert alpha_entry["categorie"]["segment_id"] == segment_id
    assert alpha_entry["compagnie"]["nom"] == "Alpha Inc."
    assert alpha_entry["stats"]["answered"] == 2
    assert alpha_entry["stats"]["missing"] == 0
    assert alpha_entry["stats"]["completion_percent"] == 100.0
    assert len(alpha_entry["responses"]) == 3
    assert any(resp["contenu"].startswith("Une plateforme") and resp.get("origin") is None for resp in alpha_entry["responses"])
    narratif_entries = [resp for resp in alpha_entry["responses"] if resp.get("origin") == "narratif"]
    assert len(narratif_entries) == 1
    assert narratif_entries[0]["contenu"].startswith("Nous avons debute dans un garage")

    assert beta_entry["categorie"]["id"] == gala_cat_croissance
    assert beta_entry["stats"]["answered"] == 0
    assert beta_entry["stats"]["missing"] == 1
    assert len(beta_entry["responses"]) == 1
    assert beta_entry["responses"][0]["contenu"] == ""

    filtered_resp = client.get(f"/admin/api/participants?categorie_id={gala_cat_innov}")
    assert filtered_resp.status_code == 200
    filtered_payload = filtered_resp.get_json()
    assert filtered_payload["meta"]["total"] == 1
    assert filtered_payload["participants"][0]["id"] == participant_alpha
    assert filtered_payload["filters"]["selected"]["categorie_id"] == gala_cat_innov

    search_resp = client.get("/admin/api/participants?q=beta")
    assert search_resp.status_code == 200
    search_payload = search_resp.get_json()
    assert search_payload["meta"]["total"] == 1
    assert search_payload["participants"][0]["compagnie"]["nom"] == "Beta Corp."


def test_admin_can_update_participant_response(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    admin_id = create_user(conn, "Admin", "Chef", "adminchef", roles["admin"])

    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Test", 2026, "Quebec", "2026-06-01"),
    ).lastrowid
    categorie_id = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    gala_cat_id = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_id, 1),
    ).lastrowid

    compagnie_id = conn.execute(
        "INSERT INTO compagnie (nom, secteur, ville) VALUES (?, ?, ?)",
        ("Alpha Inc.", "Tech", "Quebec"),
    ).lastrowid
    participant_id = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_id, gala_cat_id, None),
    ).lastrowid

    question_id = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_id, "Decrivez votre innovation", 1.0),
    ).lastrowid

    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_id, question_id, "Ancienne reponse"),
    )
    conn.commit()
    conn.close()

    admin_session(client, admin_id)

    get_resp = client.get(f"/admin/api/participants/{participant_id}/responses")
    assert get_resp.status_code == 200
    payload = get_resp.get_json()
    assert len(payload["questions"]) == 1
    assert payload["questions"][0]["reponse"] == "Ancienne reponse"

    patch_resp = client.patch(
        f"/admin/api/participants/{participant_id}/questions/{question_id}",
        json={"contenu": "Nouvelle valeur"},
    )
    assert patch_resp.status_code == 200

    conn = db_module.get_db_connection()
    row = conn.execute(
        "SELECT contenu FROM reponse_participant WHERE participant_id = ? AND question_id = ?",
        (participant_id, question_id),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["contenu"] == "Nouvelle valeur"

    client.patch(
        f"/admin/api/participants/{participant_id}/questions/{question_id}",
        json={"contenu": ""},
    )
    conn = db_module.get_db_connection()
    row = conn.execute(
        "SELECT contenu FROM reponse_participant WHERE participant_id = ? AND question_id = ?",
        (participant_id, question_id),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["contenu"] in (None, "")
