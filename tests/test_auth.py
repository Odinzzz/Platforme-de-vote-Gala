import sqlite3
from werkzeug.security import generate_password_hash

from models import db as db_module
def test_register_creates_member_role(client):
    payload = {
        "prenom": "Alice",
        "nom": "Dupont",
        "courriel": "alice@example.com",
        "telephone": "555-0001",
        "username": "alice_dupont",
        "password": "motdepasse123",
    }

    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["user"]["role"] == "membre"

    conn = db_module.get_db_connection()
    row = conn.execute(
        """
        SELECT user.username, role.nom AS role_nom
        FROM user
        JOIN role ON user.role_id = role.id
        WHERE user.username = ?
        """,
        (payload["username"].lower(),),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["username"] == payload["username"].lower()
    assert row["role_nom"].lower() == "membre"


def test_login_succeeds_with_valid_credentials(client):
    conn = db_module.get_db_connection()
    membre_role = conn.execute(
        "INSERT INTO role (nom, description) VALUES (?, ?)",
        ("membre", "Role par defaut"),
    ).lastrowid
    personne_id = conn.execute(
        "INSERT INTO personne (prenom, nom, courriel, telephone) VALUES (?, ?, ?, ?)",
        ("Jean", "Martin", "jean@example.com", "555-0002"),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO user (personne_id, username, password_hash, role_id)
        VALUES (?, ?, ?, ?)
        """,
        (
            personne_id,
            "jeanmartin",
            generate_password_hash("motdepasse123"),
            membre_role,
        ),
    )
    conn.commit()
    conn.close()

    response = client.post(
        "/auth/login",
        json={"username": "JEANMARTIN", "password": "motdepasse123"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["user"]["role"] == "membre"
    assert data["user"]["username"] == "jeanmartin"


def test_login_rejects_bad_password(client):
    conn = db_module.get_db_connection()
    membre_role = conn.execute(
        "INSERT INTO role (nom, description) VALUES (?, ?)",
        ("membre", "Role par defaut"),
    ).lastrowid
    personne_id = conn.execute(
        "INSERT INTO personne (prenom, nom, courriel, telephone) VALUES (?, ?, ?, ?)",
        ("Luc", "Bernard", "luc@example.com", "555-0003"),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO user (personne_id, username, password_hash, role_id)
        VALUES (?, ?, ?, ?)
        """,
        (
            personne_id,
            "lucbernard",
            generate_password_hash("correctPass123"),
            membre_role,
        ),
    )
    conn.commit()
    conn.close()

    response = client.post(
        "/auth/login",
        json={"username": "lucbernard", "password": "mauvaisPass"},
    )

    assert response.status_code == 401
    data = response.get_json()
    assert data["status"] == "error"
    assert "Identifiants invalides" in data["message"]
