from routes.admin_routes import FAVORITE_BONUS
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


def test_admin_results_api_returns_scores_and_progress(client):
    conn = db_module.get_db_connection()
    roles = seed_roles(conn)

    admin_id = create_user(conn, "Alice", "Admin", "aliceadmin", roles["admin"])
    judge_user_a = create_user(conn, "Jean", "Juge", "jg", roles["juge"])
    judge_user_b = create_user(conn, "Julia", "Juge", "jl", roles["juge"])

    juge_a = conn.execute(
        "INSERT INTO juge (user_id) VALUES (?)",
        (judge_user_a,),
    ).lastrowid
    juge_b = conn.execute(
        "INSERT INTO juge (user_id) VALUES (?)",
        (judge_user_b,),
    ).lastrowid

    gala_id = conn.execute(
        "INSERT INTO gala (nom, annee, lieu, date_gala) VALUES (?, ?, ?, ?)",
        ("Gala Resultats", 2025, "Montreal", "2025-05-15"),
    ).lastrowid

    cat_innov = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Innovation", ""),
    ).lastrowid
    cat_repr = conn.execute(
        "INSERT INTO categorie (nom, description) VALUES (?, ?)",
        ("Repreneuriat", ""),
    ).lastrowid

    gala_cat_innov = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, cat_innov, 1),
    ).lastrowid
    gala_cat_repr = conn.execute(
        "INSERT INTO gala_categorie (gala_id, categorie_id, ordre_affichage) VALUES (?, ?, ?)",
        (gala_id, cat_repr, 2),
    ).lastrowid

    # Assign both judges to both categories
    for juge_id in (juge_a, juge_b):
        conn.execute(
            "INSERT INTO juge_gala_categorie (juge_id, gala_categorie_id) VALUES (?, ?)",
            (juge_id, gala_cat_innov),
        )
        conn.execute(
            "INSERT INTO juge_gala_categorie (juge_id, gala_categorie_id) VALUES (?, ?)",
            (juge_id, gala_cat_repr),
        )

    compagnie_a = conn.execute(
        "INSERT INTO compagnie (nom, secteur, ville) VALUES (?, ?, ?)",
        ("Alpha Inc.", "Tech", "Montreal"),
    ).lastrowid
    compagnie_b = conn.execute(
        "INSERT INTO compagnie (nom, secteur, ville) VALUES (?, ?, ?)",
        ("Beta Solutions", "Services", "Quebec"),
    ).lastrowid
    compagnie_c = conn.execute(
        "INSERT INTO compagnie (nom, secteur, ville) VALUES (?, ?, ?)",
        ("Gamma Groupe", "Industrie", "Laval"),
    ).lastrowid

    participant_a = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_a, gala_cat_innov, None),
    ).lastrowid
    participant_b = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_b, gala_cat_innov, None),
    ).lastrowid
    participant_c = conn.execute(
        "INSERT INTO participant (compagnie_id, gala_categorie_id, segment_id) VALUES (?, ?, ?)",
        (compagnie_c, gala_cat_repr, None),
    ).lastrowid

    # Questions
    q_innov_1 = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_innov, "Innovation produit", 1.0),
    ).lastrowid
    q_innov_2 = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_innov, "Impact marche", 1.0),
    ).lastrowid
    q_repr_1 = conn.execute(
        "INSERT INTO question (gala_categorie_id, texte, ponderation) VALUES (?, ?, ?)",
        (gala_cat_repr, "Transmission", 1.0),
    ).lastrowid

    # Notes for Innovation
    conn.execute(
        "INSERT INTO note (juge_id, participant_id, question_id, valeur) VALUES (?, ?, ?, ?)",
        (juge_a, participant_a, q_innov_1, 6),
    )
    conn.execute(
        "INSERT INTO note (juge_id, participant_id, question_id, valeur) VALUES (?, ?, ?, ?)",
        (juge_a, participant_a, q_innov_2, 5),
    )
    conn.execute(
        "INSERT INTO note (juge_id, participant_id, question_id, valeur) VALUES (?, ?, ?, ?)",
        (juge_a, participant_b, q_innov_1, 4),
    )
    conn.execute(
        "INSERT INTO note (juge_id, participant_id, question_id, valeur) VALUES (?, ?, ?, ?)",
        (juge_a, participant_b, q_innov_2, 4),
    )
    conn.execute(
        "INSERT INTO note (juge_id, participant_id, question_id, valeur) VALUES (?, ?, ?, ?)",
        (juge_b, participant_a, q_innov_1, 5),
    )
    conn.execute(
        "INSERT INTO note (juge_id, participant_id, question_id, valeur) VALUES (?, ?, ?, ?)",
        (juge_b, participant_a, q_innov_2, 5),
    )

    # Notes for Repreneuriat
    conn.execute(
        "INSERT INTO note (juge_id, participant_id, question_id, valeur) VALUES (?, ?, ?, ?)",
        (juge_a, participant_c, q_repr_1, 5),
    )

    # Coup de coeur
    conn.execute(
        "INSERT INTO coup_de_coeur (juge_id, gala_id, participant_id) VALUES (?, ?, ?)",
        (juge_a, gala_id, participant_a),
    )

    # Judge A submitted
    conn.execute(
        "INSERT INTO juge_gala_submission (juge_id, gala_id, submitted_at) VALUES (?, ?, ?)",
        (juge_a, gala_id, "2025-05-10T10:00:00Z"),
    )

    conn.commit()
    conn.close()

    admin_session(client, admin_id, prenom="Alice", nom="Admin", username="aliceadmin")

    resp = client.get(f"/admin/api/results?gala_id={gala_id}")
    assert resp.status_code == 200
    payload = resp.get_json()

    assert payload["filters"]["selected"]["gala_id"] == gala_id
    assert payload["meta"]["gala"]["id"] == gala_id
    assert payload["meta"]["favorite_bonus"] == FAVORITE_BONUS

    categories = payload["categories"]
    assert len(categories) == 2

    innov_category = next(cat for cat in categories if cat["id"] == gala_cat_innov)
    assert innov_category["status"] == "en_cours"
    participants = innov_category["participants"]
    assert len(participants) == 2

    top_participant = participants[0]
    assert top_participant["id"] == participant_a
    assert top_participant["score_bonus"] == round(FAVORITE_BONUS, 2)
    assert top_participant["rank"] == 1

    judges = payload["judges"]
    assert len(judges) == 2
    judge_a_payload = next(j for j in judges if j["id"] == juge_a)
    judge_b_payload = next(j for j in judges if j["id"] == juge_b)
    assert judge_a_payload["submitted"] is True
    assert judge_a_payload["status"] == "soumis"
    assert judge_b_payload["submitted"] is False
    assert judge_b_payload["status"] == "en_cours"

    # Check filtered category request
    resp_filtered = client.get(f"/admin/api/results?gala_id={gala_id}&categorie_id={gala_cat_innov}")
    assert resp_filtered.status_code == 200
    filtered_payload = resp_filtered.get_json()
    assert len(filtered_payload["categories"]) == 1
    assert filtered_payload["filters"]["selected"]["categorie_id"] == gala_cat_innov
