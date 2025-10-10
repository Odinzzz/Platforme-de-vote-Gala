from flask import Blueprint, render_template, session

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    # Exemple d’utilisateur connecté (plus tard tu mettras la vraie logique de login)
    user = session.get("user")  # ex: {"prenom": "Tommy", "nom": "Massé"}
    return render_template("index.html", user=user)
