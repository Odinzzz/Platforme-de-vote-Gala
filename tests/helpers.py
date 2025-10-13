

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


def set_session(client, user_payload):
    with client.session_transaction() as session:
        session["user"] = user_payload


