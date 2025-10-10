import sqlite3
from importlib import reload

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from models import db as db_module
from models import init_db as init_db_module


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    monkeypatch.setattr(init_db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(init_db_module, "DB_FILE", db_path)

    conn = sqlite3.connect(db_path)
    conn.executescript(init_db_module.SCHEMA_SQL)
    conn.close()

    import routes.main_routes as main_routes
    main_routes = reload(main_routes)

    app = Flask(__name__)
    app.config.update(SECRET_KEY="test-secret", TESTING=True)
    app.register_blueprint(main_routes.main_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


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

    conn = db_module.get_db_connection()
    row = conn.execute(
        """
        SELECT user.username, role.nom AS role_nom
        FROM user
        JOIN role ON user.role_id = role.id
        WHERE user.username = ?
        """,
        (payload["username"],),
    ).fetchone()
    conn.close()
    assert row is not None
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
        json={"username": "jeanmartin", "password": "motdepasse123"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
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
