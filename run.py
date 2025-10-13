from flask import Flask, render_template, session
from models.init_db import init_database
from routes.main_routes import main_bp
from routes.admin_routes import admin_bp
from routes.judge_routes import judge_bp
import os

app = Flask(__name__)
app.secret_key = "secret-key-change-me"  # ⚠️ à sécuriser plus tard

# Initialise la base si nécessaire
if not os.path.exists("data/gala.db"):
    init_database()

# Enregistre le blueprint des routes
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(judge_bp)

if __name__ == "__main__":
    app.run(debug=True)
