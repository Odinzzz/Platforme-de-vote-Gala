from models import db as db_module
from tests.helpers import seed_roles, create_user, set_session


def judge_session(client, user_id, prenom="Julie", nom="Juge", username="juliejuge"):
    set_session(client, {
        "id": user_id,
        "username": username,
        "prenom": prenom,
        "nom": nom,
        "role": "juge",
    })


def test_judge_api_requires_role(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    member_id = create_user(conn, "Membre", "Test", "membretest", roles["membre"])
    conn.commit()
    conn.close()

    set_session(client, {
        "id": member_id,
        "username": "membretest",
        "prenom": "Membre",
        "nom": "Test",
        "role": "membre",
    })

    response = client.get("/judge/api/galas")
    assert response.status_code == 403


def test_judge_dashboard_summary_and_participant_flow(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    judge_user_id = create_user(conn, "Julie", "Juge", "juliejuge", roles["juge"])
    judge_id = conn.execute(
        "INSERT INTO juge (user_id) VALUES (?)",
        (judge_user_id,),
    ).lastrowid

    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Innovation", 2025, "Quebec", "2025-05-01"),
    ).lastrowid
    categorie_id = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    gala_cat_id = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_id, 1),
    ).lastrowid

    conn.execute(
        "INSERT INTO juge_gala_categorie (juge_id, gala_categorie_id) VALUES (?, ?)",
        (judge_id, gala_cat_id),
    )

    compagnie_a = conn.execute(
        "INSERT INTO compagnie (nom, secteur, annee_fondation, nombre_employes) VALUES (?, ?, ?, ?)",
        ("Alpha", "Tech", 2010, 50),
    ).lastrowid
    compagnie_b = conn.execute(
        "INSERT INTO compagnie (nom, secteur, annee_fondation, nombre_employes) VALUES (?, ?, ?, ?)",
        ("Beta", "Manufacture", 2005, 120),
    ).lastrowid

    participant_a = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_a, gala_cat_id, None),
    ).lastrowid
    participant_b = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_b, gala_cat_id, None),
    ).lastrowid

    question_1 = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_id, "Vision strategique", 1.0),
    ).lastrowid
    question_2 = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_id, "Impact communautaire", 1.0),
    ).lastrowid

    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_a, question_1, "Reponse A1"),
    )
    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_a, question_2, "Reponse A2"),
    )
    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_b, question_1, "Reponse B1"),
    )
    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_b, question_2, "Reponse B2"),
    )

    conn.commit()
    conn.close()

    judge_session(client, judge_user_id)

    summary_resp = client.get("/judge/api/galas")
    assert summary_resp.status_code == 200
    summary_payload = summary_resp.get_json()
    assert summary_payload["galas"], "Summary should contain at least one gala"
    gala_entry = next(item for item in summary_payload["galas"] if item["id"] == gala_id)
    assert gala_entry["progress"]["percent"] == 0
    assert len(gala_entry["categories"]) == 1

    category_resp = client.get(f"/judge/api/galas/{gala_id}/categories/{gala_cat_id}/participants")
    assert category_resp.status_code == 200
    category_payload = category_resp.get_json()
    assert len(category_payload["participants"]) == 2
    participant_entry = next(item for item in category_payload["participants"] if item["id"] == participant_a)
    assert participant_entry["progress"]["completed_questions"] == 0

    detail_resp = client.get(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_id}/participants/{participant_a}"
    )
    assert detail_resp.status_code == 200
    detail_payload = detail_resp.get_json()
    assert len(detail_payload["questions"]) == 2
    assert detail_payload["questions"][0]["reponse"] == "Reponse A1"

    patch_resp = client.patch(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_id}/participants/{participant_a}/questions/{question_1}",
        json={"valeur": 6, "commentaire": "Solide"},
    )
    assert patch_resp.status_code == 200
    check_conn = db_module.get_db_connection()
    note_row = check_conn.execute(
        "SELECT valeur, commentaire FROM note WHERE juge_id = ? AND participant_id = ? AND question_id = ?",
        (judge_id, participant_a, question_1),
    ).fetchone()
    check_conn.close()
    assert note_row is not None
    assert note_row["valeur"] == 6
    assert note_row["commentaire"] == "Solide"

    client.patch(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_id}/participants/{participant_a}/questions/{question_2}",
        json={"valeur": 5},
    )
    client.patch(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_id}/participants/{participant_b}/questions/{question_1}",
        json={"valeur": 4},
    )
    client.patch(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_id}/participants/{participant_b}/questions/{question_2}",
        json={"valeur": 5},
    )


    submit_resp = client.post(f"/judge/api/galas/{gala_id}/submit")
    assert submit_resp.status_code == 200
    assert submit_resp.get_json()["status"] == "ok"

    blocked_resp = client.patch(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_id}/participants/{participant_a}/questions/{question_2}",
        json={"valeur": 6},
    )
    assert blocked_resp.status_code == 409
    assert "soumis" in blocked_resp.get_json()["message"].lower()


def test_judge_narratif_questions_shared_across_categories(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)
    judge_user_id = create_user(conn, "Nadia", "Juge", "nadiajuge", roles["juge"])
    judge_id = conn.execute(
        "INSERT INTO juge (user_id) VALUES (?)",
        (judge_user_id,),
    ).lastrowid

    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Entrepreneuriat", 2025, "Montreal", "2025-04-20"),
    ).lastrowid
    categorie_innov = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    categorie_repr = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Repreneuriat", ""),
    ).lastrowid
    categorie_narratif = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Narratif (general)", ""),
    ).lastrowid

    gala_cat_innov = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_innov, 1),
    ).lastrowid
    gala_cat_repr = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_repr, 2),
    ).lastrowid
    gala_cat_narratif = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, categorie_narratif, 0),
    ).lastrowid

    conn.execute(
        "INSERT INTO juge_gala_categorie (juge_id, gala_categorie_id) VALUES (?, ?)",
        (judge_id, gala_cat_innov),
    )
    conn.execute(
        "INSERT INTO juge_gala_categorie (juge_id, gala_categorie_id) VALUES (?, ?)",
        (judge_id, gala_cat_repr),
    )

    compagnie_id = conn.execute(
        "INSERT INTO compagnie (nom, secteur) VALUES (?, ?)",
        ("Compagnie X", "Tech"),
    ).lastrowid

    participant_innov = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_id, gala_cat_innov, None),
    ).lastrowid
    participant_repr = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_id, gala_cat_repr, None),
    ).lastrowid
    participant_narratif = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_id, gala_cat_narratif, None),
    ).lastrowid

    question_innov = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_innov, "Innovation cle", 1.0),
    ).lastrowid
    question_repr = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_repr, "Transmission", 1.0),
    ).lastrowid
    question_narratif = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_narratif, "Narratif global", 1.0),
    ).lastrowid

    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_innov, question_innov, "Reponse innovation"),
    )
    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_repr, question_repr, "Reponse repreneuriat"),
    )
    conn.execute(
        "INSERT INTO reponse_participant (participant_id, question_id, contenu) VALUES (?, ?, ?)",
        (participant_narratif, question_narratif, "Narratif commun"),
    )

    conn.commit()
    conn.close()

    judge_session(client, judge_user_id)

    detail_innov_resp = client.get(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_innov}/participants/{participant_innov}"
    )
    assert detail_innov_resp.status_code == 200
    detail_innov = detail_innov_resp.get_json()
    assert detail_innov["progress"]["total"] == 1
    assert detail_innov["progress"]["extra"] == 1
    narratif_question = next(
        item for item in detail_innov["questions"] if item.get("source") == "narratif"
    )
    assert narratif_question["shared"] is True
    assert narratif_question["scope_participant_id"] == participant_narratif
    assert narratif_question["note"] is None

    patch_resp = client.patch(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_innov}/participants/{participant_innov}/questions/{question_narratif}",
        json={"valeur": 6, "target_participant_id": participant_narratif},
    )
    assert patch_resp.status_code == 200

    check_conn = db_module.get_db_connection()
    note_row = check_conn.execute(
        "SELECT participant_id, valeur FROM note WHERE juge_id = ? AND question_id = ?",
        (judge_id, question_narratif),
    ).fetchone()
    check_conn.close()
    assert note_row is not None
    assert note_row["participant_id"] == participant_narratif
    assert note_row["valeur"] == 6

    detail_repr_resp = client.get(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_repr}/participants/{participant_repr}"
    )
    assert detail_repr_resp.status_code == 200
    detail_repr = detail_repr_resp.get_json()
    shared_again = next(
        item for item in detail_repr["questions"] if item.get("source") == "narratif"
    )
    assert shared_again["note"] == 6

    favorite_resp = client.post(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_innov}/participants/{participant_innov}/favorite"
    )
    assert favorite_resp.status_code == 200
    favorite_payload = favorite_resp.get_json()
    assert favorite_payload["favorite"]["selected"] is True
    assert favorite_payload["favorite"]["participant_id"] == participant_innov

    detail_innov_again = client.get(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_innov}/participants/{participant_innov}"
    ).get_json()
    assert detail_innov_again["favorite"]["selected"] is True

    detail_repr_again = client.get(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_repr}/participants/{participant_repr}"
    ).get_json()
    assert detail_repr_again["favorite"]["selected"] is False
    assert detail_repr_again["favorite"]["participant_id"] == participant_innov

    remove_resp = client.delete(
        f"/judge/api/galas/{gala_id}/categories/{gala_cat_innov}/participants/{participant_innov}/favorite"
    )
    assert remove_resp.status_code == 200
    remove_payload = remove_resp.get_json()
    assert remove_payload["favorite"]["selected"] is False
