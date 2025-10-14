import sqlite3
from pathlib import Path

# ==============================
# 📂 Emplacement de la base
# ==============================
DATA_DIR = Path("data")
DB_FILE = DATA_DIR / "gala.db"

# ==============================
# 🔧 Schéma complet
# ==============================
SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- =========================================
-- 🏛️ GALA & CATÉGORIES
-- =========================================
CREATE TABLE IF NOT EXISTS gala (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    annee INTEGER NOT NULL,
    lieu TEXT,
    date_gala TEXT
);

CREATE TABLE IF NOT EXISTS categorie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS gala_categorie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gala_id INTEGER NOT NULL,
    categorie_id INTEGER NOT NULL,
    ordre_affichage INTEGER,
    actif INTEGER DEFAULT 1,
    FOREIGN KEY (gala_id) REFERENCES gala(id) ON DELETE CASCADE,
    FOREIGN KEY (categorie_id) REFERENCES categorie(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS segment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gala_categorie_id INTEGER NOT NULL,
    nom TEXT NOT NULL,
    FOREIGN KEY (gala_categorie_id) REFERENCES gala_categorie(id) ON DELETE CASCADE
);

-- =========================================
-- 🧍 PERSONNES / UTILISATEURS / RÔLES / JUGES
-- =========================================
CREATE TABLE IF NOT EXISTS personne (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prenom TEXT NOT NULL,
    nom TEXT NOT NULL,
    courriel TEXT,
    telephone TEXT
);

CREATE TABLE IF NOT EXISTS role (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    personne_id INTEGER NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role_id INTEGER,
    actif INTEGER DEFAULT 1,
    last_login TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (personne_id) REFERENCES personne(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES role(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS juge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS juge_gala_categorie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    juge_id INTEGER NOT NULL,
    gala_categorie_id INTEGER NOT NULL,
    FOREIGN KEY (juge_id) REFERENCES juge(id) ON DELETE CASCADE,
    FOREIGN KEY (gala_categorie_id) REFERENCES gala_categorie(id) ON DELETE CASCADE
);

-- =========================================
-- 🏢 COMPAGNIES / PARTICIPANTS
-- =========================================
CREATE TABLE IF NOT EXISTS compagnie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    secteur TEXT,
    annee_fondation INTEGER,
    nombre_employes INTEGER,
    adresse TEXT,
    ville TEXT,
    code_postal TEXT,
    telephone TEXT,
    courriel TEXT,
    responsable_nom TEXT,
    responsable_titre TEXT,
    neq TEXT,
    site_web TEXT,
    date_creation TEXT DEFAULT CURRENT_TIMESTAMP,
    actif INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS participant (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compagnie_id INTEGER NOT NULL,
    gala_categorie_id INTEGER NOT NULL,
    segment_id INTEGER,
    FOREIGN KEY (compagnie_id) REFERENCES compagnie(id) ON DELETE CASCADE,
    FOREIGN KEY (gala_categorie_id) REFERENCES gala_categorie(id) ON DELETE CASCADE,
    FOREIGN KEY (segment_id) REFERENCES segment(id) ON DELETE SET NULL
);

-- =========================================
-- 📝 QUESTIONS / NOTES
-- =========================================
CREATE TABLE IF NOT EXISTS question (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gala_categorie_id INTEGER NOT NULL,
    texte TEXT NOT NULL,
    ponderation REAL DEFAULT 1.0,
    FOREIGN KEY (gala_categorie_id) REFERENCES gala_categorie(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    juge_id INTEGER NOT NULL,
    participant_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    valeur INTEGER CHECK(valeur BETWEEN 1 AND 6),
    commentaire TEXT,
    FOREIGN KEY (juge_id) REFERENCES juge(id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES participant(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES question(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS reponse_participant (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    contenu TEXT,
    FOREIGN KEY (participant_id) REFERENCES participant(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES question(id) ON DELETE CASCADE,
    UNIQUE (participant_id, question_id)
);

CREATE TABLE IF NOT EXISTS gala_lock (
    gala_id INTEGER PRIMARY KEY,
    locked_at TEXT NOT NULL,
    locked_by INTEGER,
    FOREIGN KEY (gala_id) REFERENCES gala(id) ON DELETE CASCADE,
    FOREIGN KEY (locked_by) REFERENCES user(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_note_unique ON note (juge_id, participant_id, question_id);

CREATE TABLE IF NOT EXISTS juge_gala_submission (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    juge_id INTEGER NOT NULL,
    gala_id INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    FOREIGN KEY (juge_id) REFERENCES juge(id) ON DELETE CASCADE,
    FOREIGN KEY (gala_id) REFERENCES gala(id) ON DELETE CASCADE,
    UNIQUE (juge_id, gala_id)
);

CREATE TABLE IF NOT EXISTS coup_de_coeur (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    juge_id INTEGER NOT NULL,
    gala_id INTEGER NOT NULL,
    participant_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (juge_id) REFERENCES juge(id) ON DELETE CASCADE,
    FOREIGN KEY (gala_id) REFERENCES gala(id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES participant(id) ON DELETE CASCADE,
    UNIQUE (juge_id, gala_id),
    UNIQUE (juge_id, participant_id)
);


"""

# ==============================
# 🚀 Création automatique
# ==============================
def init_database() -> None:
    """Crée la base de données SQLite pour le Gala Distinction."""
    # S'assure que le dossier data/ existe
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True)
        print(f"📁 Dossier créé : {DATA_DIR.resolve()}")

    # Création de la base de données
    if DB_FILE.exists():
        print(f"📁 Base existante : {DB_FILE.resolve()}")
    else:
        print("📦 Création d'une nouvelle base de données...")

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")  # ⚠️ Activation obligatoire
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    print(f"✅ Base de données créée avec succès : {DB_FILE.resolve()}")

# ==============================
# 🧩 Point d’entrée
# ==============================
if __name__ == "__main__":
    init_database()
