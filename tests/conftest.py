import sqlite3
from importlib import reload

import pytest
from flask import Flask

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
    import routes.admin_routes as admin_routes
    admin_routes = reload(admin_routes)

    test_app = Flask(__name__)
    test_app.config.update(SECRET_KEY="test-secret", TESTING=True)

    test_app.register_blueprint(main_routes.main_bp)
    test_app.register_blueprint(admin_routes.admin_bp)

    return test_app


@pytest.fixture
def client(app):
    return app.test_client()
