from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Dict, List, Tuple, Optional

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from models.db import get_db_connection

judge_bp = Blueprint("judge", __name__, url_prefix="/judge")


def _current_user() -> Dict[str, Any] | None:
    return session.get("user")


def _require_judge_user() -> Dict[str, Any]:
    user = _current_user()
    if not user:
        abort(401)
    role = (user.get("role") or "").lower()
    if role != "juge":
        abort(403)
    return user


def _get_judge_id(conn, user_id: int) -> int:
    row = conn.execute(
        "SELECT id FROM juge WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        abort(403)
    return row["id"]


def _fetch_lock_info(conn, gala_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    if not gala_ids:
        return {}
    placeholders = ",".join("?" for _ in gala_ids)
    rows = conn.execute(
        f"SELECT gala_id, locked_at, locked_by FROM gala_lock WHERE gala_id IN ({placeholders})",
        tuple(gala_ids),
    ).fetchall()
    return {row["gala_id"]: {"locked_at": row["locked_at"], "locked_by": row["locked_by"]} for row in rows}


def _fetch_submission_info(conn, juge_id: int, gala_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    if not gala_ids:
        return {}
    placeholders = ",".join("?" for _ in gala_ids)
    rows = conn.execute(
        f"""
        SELECT gala_id, submitted_at
        FROM juge_gala_submission
        WHERE juge_id = ? AND gala_id IN ({placeholders})
        """,
        (juge_id, *gala_ids),
    ).fetchall()
    return {row["gala_id"]: {"submitted_at": row["submitted_at"]} for row in rows}


def _fetch_narratif_category_ids(conn, gala_id: int) -> List[int]:
    rows = conn.execute(
        """
        SELECT gc.id
        FROM gala_categorie AS gc
        JOIN categorie AS c ON c.id = gc.categorie_id
        WHERE gc.gala_id = ? AND LOWER(c.nom) LIKE 'narratif%'
        """,
        (gala_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def _find_narratif_participant(
    conn,
    compagnie_id: int,
    narratif_category_ids: List[int],
) -> Optional[Dict[str, Any]]:
    if not narratif_category_ids:
        return None
    placeholders = ",".join("?" for _ in narratif_category_ids)
    rows = conn.execute(
        f"""
        SELECT id, gala_categorie_id
        FROM participant
        WHERE compagnie_id = ? AND gala_categorie_id IN ({placeholders})
        ORDER BY id ASC
        LIMIT 1
        """,
        (compagnie_id, *narratif_category_ids),
    ).fetchall()
    if not rows:
        return None
    row = rows[0]
    return {"id": row["id"], "gala_categorie_id": row["gala_categorie_id"]}


def _load_questions_with_notes(
    conn,
    participant_id: int,
    juge_id: int,
    gala_categorie_id: int,
) -> List[Dict[str, Any]]:
    return conn.execute(
        """
        SELECT q.id, q.texte, q.ponderation,
               r.contenu AS reponse,
               n.valeur AS note_valeur,
               n.commentaire AS note_commentaire
        FROM question AS q
        LEFT JOIN reponse_participant AS r
            ON r.question_id = q.id AND r.participant_id = ?
        LEFT JOIN note AS n
            ON n.question_id = q.id AND n.participant_id = ? AND n.juge_id = ?
        WHERE q.gala_categorie_id = ?
        ORDER BY q.id ASC
        """,
        (participant_id, participant_id, juge_id, gala_categorie_id),
    ).fetchall()


def _compute_progress(question_count: int, participant_ids: List[int], note_counts: Dict[int, int]) -> Tuple[float, int, int, int]:
    total_required = question_count * len(participant_ids)
    if total_required == 0:
        return 0.0, 0, 0, total_required

    recorded = 0
    completed_participants = 0
    for participant_id in participant_ids:
        notes = note_counts.get(participant_id, 0)
        capped = min(notes, question_count)
        recorded += capped
        if question_count > 0 and notes >= question_count:
            completed_participants += 1

    percent = round((recorded / total_required) * 100, 1) if total_required else 0.0
    return percent, completed_participants, recorded, total_required


def _category_status(percent: float, total_required: int, recorded: int) -> str:
    if total_required == 0:
        return "non_disponible"
    if recorded == 0:
        return "en_attente"
    if recorded < total_required:
        return "en_cours"
    return "termine"


@judge_bp.route("/")
def judge_root():
    user = _require_judge_user()
    conn = get_db_connection()
    juge_id = _get_judge_id(conn, user["id"])
    row = conn.execute(
        """
        SELECT gala.id
        FROM juge_gala_categorie AS jgc
        JOIN gala_categorie AS gc ON gc.id = jgc.gala_categorie_id
        JOIN gala ON gala.id = gc.gala_id
        WHERE jgc.juge_id = ?
        ORDER BY gala.annee DESC, gala.id DESC
        LIMIT 1
        """,
        (juge_id,),
    ).fetchone()
    conn.close()

    if not row:
        return render_template("judge/empty.html", user=user)

    return redirect(url_for("judge.judge_gala_dashboard", gala_id=row["id"]))


@judge_bp.route("/galas/<int:gala_id>")
def judge_gala_dashboard(gala_id: int):
    user = _require_judge_user()
    return render_template("judge/dashboard.html", user=user, gala_id=gala_id, category_id=None, participant_id=None)


@judge_bp.route("/galas/<int:gala_id>/categories/<int:gala_categorie_id>")
def judge_category_view(gala_id: int, gala_categorie_id: int):
    user = _require_judge_user()
    conn = get_db_connection()
    juge_id = _get_judge_id(conn, user["id"])
    _ensure_category_access(conn, juge_id, gala_id, gala_categorie_id)
    conn.close()
    return render_template("judge/dashboard.html", user=user, gala_id=gala_id, category_id=gala_categorie_id, participant_id=None)


@judge_bp.route("/galas/<int:gala_id>/categories/<int:gala_categorie_id>/participants/<int:participant_id>")
def judge_participant_view(gala_id: int, gala_categorie_id: int, participant_id: int):
    user = _require_judge_user()
    conn = get_db_connection()
    juge_id = _get_judge_id(conn, user["id"])
    _ensure_category_access(conn, juge_id, gala_id, gala_categorie_id)
    participant_exists = conn.execute(
        "SELECT 1 FROM participant WHERE id = ? AND gala_categorie_id = ?",
        (participant_id, gala_categorie_id),
    ).fetchone()
    conn.close()
    if not participant_exists:
        abort(404)
    return render_template("judge/dashboard.html", user=user, gala_id=gala_id, category_id=gala_categorie_id, participant_id=participant_id)


@judge_bp.route("/api/galas", methods=["GET"])
def api_list_galas():
    user = _require_judge_user()
    conn = get_db_connection()
    juge_id = _get_judge_id(conn, user["id"])

    rows = conn.execute(
        """
        SELECT g.id AS gala_id, g.nom AS gala_nom, g.annee AS gala_annee,
               gc.id AS gala_categorie_id, c.nom AS categorie_nom
        FROM juge_gala_categorie AS jgc
        JOIN gala_categorie AS gc ON gc.id = jgc.gala_categorie_id
        JOIN gala AS g ON g.id = gc.gala_id
        JOIN categorie AS c ON c.id = gc.categorie_id
        WHERE jgc.juge_id = ?
        ORDER BY g.annee DESC, c.nom COLLATE NOCASE
        """,
        (juge_id,),
    ).fetchall()

    galas: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        gala_id = row["gala_id"]
        if gala_id not in galas:
            galas[gala_id] = {
                "id": gala_id,
                "nom": row["gala_nom"],
                "annee": row["gala_annee"],
                "categories": [],
                "progress": {"percent": 0.0, "recorded": 0, "total": 0},
                "status": "en_attente",
            }
        galas[gala_id]["categories"].append(
            {
                "id": row["gala_categorie_id"],
                "nom": row["categorie_nom"],
            }
        )

    gala_ids = list(galas.keys())
    locks = _fetch_lock_info(conn, gala_ids)
    submissions = _fetch_submission_info(conn, juge_id, gala_ids)

    for gala in galas.values():
        gala["locked"] = gala["id"] in locks
        gala["locked_at"] = locks.get(gala["id"], {}).get("locked_at")
        submission = submissions.get(gala["id"])
        gala["submitted"] = bool(submission)
        gala["submitted_at"] = submission.get("submitted_at") if submission else None

        gala_progress_recorded = 0
        gala_progress_total = 0

        for category in gala["categories"]:
            question_count = conn.execute(
                "SELECT COUNT(*) AS total FROM question WHERE gala_categorie_id = ?",
                (category["id"],),
            ).fetchone()["total"]
            participant_rows = conn.execute(
                "SELECT id FROM participant WHERE gala_categorie_id = ?",
                (category["id"],),
            ).fetchall()
            participant_ids = [r["id"] for r in participant_rows]
            note_counts: Dict[int, int] = {}
            if participant_ids:
                placeholders = ",".join("?" for _ in participant_ids)
                note_rows = conn.execute(
                    f"SELECT participant_id, COUNT(*) AS total FROM note WHERE juge_id = ? AND participant_id IN ({placeholders}) GROUP BY participant_id",
                    (juge_id, *participant_ids),
                ).fetchall()
                note_counts = {r["participant_id"]: r["total"] for r in note_rows}

            percent, completed_participants, recorded, total_required = _compute_progress(
                question_count, participant_ids, note_counts
            )
            status = _category_status(percent, total_required, recorded)
            gala_progress_recorded += recorded
            gala_progress_total += total_required

            category.update(
                {
                    "question_count": question_count,
                    "participant_count": len(participant_ids),
                    "progress": {
                        "percent": percent,
                        "completed_participants": completed_participants,
                        "total_participants": len(participant_ids),
                        "recorded": recorded,
                        "total": total_required,
                    },
                    "status": status,
                }
            )

        if gala_progress_total:
            percent = round((gala_progress_recorded / gala_progress_total) * 100, 1)
        else:
            percent = 0.0
        gala["progress"] = {
            "percent": percent,
            "recorded": gala_progress_recorded,
            "total": gala_progress_total,
        }
        if gala["locked"]:
            gala["status"] = "verrouille"
        elif gala["submitted"]:
            gala["status"] = "soumis"
        elif gala_progress_total == 0:
            gala["status"] = "non_disponible"
        elif gala_progress_recorded == 0:
            gala["status"] = "en_attente"
        elif gala_progress_recorded < gala_progress_total:
            gala["status"] = "en_cours"
        else:
            gala["status"] = "termine"

    payload = {"galas": sorted(galas.values(), key=lambda g: (-g["annee"], g["nom"]))}
    conn.close()
    return jsonify(payload)


def _ensure_category_access(conn, juge_id: int, gala_id: int, gala_categorie_id: int) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT gc.id, gc.gala_id, gc.categorie_id, c.nom AS categorie_nom,
               g.nom AS gala_nom, g.annee AS gala_annee
        FROM juge_gala_categorie AS jgc
        JOIN gala_categorie AS gc ON gc.id = jgc.gala_categorie_id
        JOIN gala AS g ON g.id = gc.gala_id
        JOIN categorie AS c ON c.id = gc.categorie_id
        WHERE jgc.juge_id = ? AND gc.id = ? AND gc.gala_id = ?
        """,
        (juge_id, gala_categorie_id, gala_id),
    ).fetchone()
    if not row:
        abort(404)
    return row


def _is_gala_locked(conn, gala_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM gala_lock WHERE gala_id = ?",
        (gala_id,),
    ).fetchone() is not None


def _has_submitted(conn, juge_id: int, gala_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM juge_gala_submission WHERE juge_id = ? AND gala_id = ?",
        (juge_id, gala_id),
    ).fetchone() is not None


@judge_bp.route("/api/galas/<int:gala_id>/categories/<int:gala_categorie_id>/participants", methods=["GET"])
def api_list_participants(gala_id: int, gala_categorie_id: int):
    user = _require_judge_user()
    conn = get_db_connection()
    juge_id = _get_judge_id(conn, user["id"])
    category_row = _ensure_category_access(conn, juge_id, gala_id, gala_categorie_id)

    question_rows = conn.execute(
        "SELECT id FROM question WHERE gala_categorie_id = ? ORDER BY id",
        (gala_categorie_id,),
    ).fetchall()
    question_count = len(question_rows)

    participant_rows = conn.execute(
        """
        SELECT p.id, comp.nom AS compagnie_nom, comp.ville, comp.responsable_nom
        FROM participant AS p
        JOIN compagnie AS comp ON comp.id = p.compagnie_id
        WHERE p.gala_categorie_id = ?
        ORDER BY comp.nom COLLATE NOCASE
        """,
        (gala_categorie_id,),
    ).fetchall()
    participant_ids = [row["id"] for row in participant_rows]

    note_counts: Dict[int, int] = {}
    if participant_ids:
        placeholders = ",".join("?" for _ in participant_ids)
        rows = conn.execute(
            f"SELECT participant_id, COUNT(*) AS total FROM note WHERE juge_id = ? AND participant_id IN ({placeholders}) GROUP BY participant_id",
            (juge_id, *participant_ids),
        ).fetchall()
        note_counts = {row["participant_id"]: row["total"] for row in rows}

    percent, completed_participants, recorded, total_required = _compute_progress(
        question_count, participant_ids, note_counts
    )
    status = _category_status(percent, total_required, recorded)

    participants_payload = []
    for row in participant_rows:
        participant_id = row["id"]
        notes = note_counts.get(participant_id, 0)
        completed_questions = min(notes, question_count)
        participant_percent = 0.0
        if question_count:
            participant_percent = round((completed_questions / question_count) * 100, 1)
        if question_count == 0:
            participant_status = "non_disponible"
        elif completed_questions == 0:
            participant_status = "en_attente"
        elif completed_questions < question_count:
            participant_status = "en_cours"
        else:
            participant_status = "termine"

        participants_payload.append(
            {
                "id": participant_id,
                "compagnie": row["compagnie_nom"],
                "ville": row["ville"],
                "responsable": row["responsable_nom"],
                "progress": {
                    "percent": participant_percent,
                    "completed_questions": completed_questions,
                    "total_questions": question_count,
                },
                "status": participant_status,
            }
        )

    response = {
        "gala": {
            "id": category_row["gala_id"],
            "nom": category_row["gala_nom"],
            "annee": category_row["gala_annee"],
        },
        "category": {
            "id": category_row["id"],
            "nom": category_row["categorie_nom"],
            "question_count": question_count,
        },
        "participants": participants_payload,
        "progress": {
            "percent": percent,
            "completed_participants": completed_participants,
            "total_participants": len(participant_ids),
            "recorded": recorded,
            "total": total_required,
        },
        "status": status,
        "locked": _is_gala_locked(conn, gala_id),
        "submitted": _has_submitted(conn, juge_id, gala_id),
    }
    conn.close()
    return jsonify(response)


@judge_bp.route(
    "/api/galas/<int:gala_id>/categories/<int:gala_categorie_id>/participants/<int:participant_id>",
    methods=["GET"],
)
def api_participant_detail(gala_id: int, gala_categorie_id: int, participant_id: int):
    user = _require_judge_user()
    conn = get_db_connection()
    juge_id = _get_judge_id(conn, user["id"])
    category_row = _ensure_category_access(conn, juge_id, gala_id, gala_categorie_id)

    participant_row = conn.execute(
        """
        SELECT
            p.id,
            p.compagnie_id,
            p.gala_categorie_id,
            comp.nom AS compagnie_nom,
            comp.ville,
            comp.secteur,
            comp.responsable_nom,
            comp.responsable_titre
        FROM participant AS p
        JOIN compagnie AS comp ON comp.id = p.compagnie_id
        WHERE p.id = ? AND p.gala_categorie_id = ?
        """,
        (participant_id, gala_categorie_id),
    ).fetchone()
    if not participant_row:
        conn.close()
        abort(404)

    base_question_rows = _load_questions_with_notes(conn, participant_id, juge_id, gala_categorie_id)

    narratif_questions_rows: List[Dict[str, Any]] = []
    narratif_participant: Optional[Dict[str, Any]] = None
    narrative_category_ids = _fetch_narratif_category_ids(conn, gala_id)
    if narrative_category_ids and participant_row["compagnie_id"] is not None:
        narratif_participant = _find_narratif_participant(
            conn,
            participant_row["compagnie_id"],
            narrative_category_ids,
        )
        if narratif_participant:
            narratif_questions_rows = _load_questions_with_notes(
                conn,
                narratif_participant["id"],
                juge_id,
                narratif_participant["gala_categorie_id"],
            )

    questions_payload: List[Dict[str, Any]] = []
    seen_ids: Dict[int, Dict[str, Any]] = {}

    def _collect_question_rows(rows: List[Dict[str, Any]], source: Optional[str], scope_participant_id: int) -> None:
        for row in rows:
            question_id = row["id"]
            existing = seen_ids.get(question_id)
            if existing:
                if existing.get("note") is None and row["note_valeur"] is not None:
                    existing["note"] = row["note_valeur"]
                if not existing.get("commentaire") and row["note_commentaire"]:
                    existing["commentaire"] = row["note_commentaire"]
                if not existing.get("reponse") and row["reponse"]:
                    existing["reponse"] = row["reponse"]
                continue

            payload = {
                "id": question_id,
                "ordre": 0,
                "texte": row["texte"],
                "ponderation": row["ponderation"],
                "reponse": row["reponse"],
                "note": row["note_valeur"],
                "commentaire": row["note_commentaire"],
                "source": source,
                "shared": source == "narratif",
                "scope_participant_id": scope_participant_id,
                "counts_for_progress": source != "narratif",
            }
            questions_payload.append(payload)
            seen_ids[question_id] = payload

    _collect_question_rows(base_question_rows, None, participant_id)

    if narratif_participant and narratif_questions_rows:
        _collect_question_rows(
            narratif_questions_rows,
            "narratif",
            narratif_participant["id"],
        )

    completed = 0
    counted_completed = 0
    counted_total = 0
    for index, question in enumerate(questions_payload, start=1):
        question["ordre"] = index
        if question.get("note") is not None:
            completed += 1
            if question.get("counts_for_progress", True):
                counted_completed += 1
        if question.get("counts_for_progress", True):
            counted_total += 1

    total_questions = len(questions_payload)

    percent = round((counted_completed / counted_total) * 100, 1) if counted_total else 0.0

    response = {
        "gala": {
            "id": category_row["gala_id"],
            "nom": category_row["gala_nom"],
            "annee": category_row["gala_annee"],
        },
        "category": {
            "id": category_row["id"],
            "nom": category_row["categorie_nom"],
        },
        "participant": {
            "id": participant_row["id"],
            "compagnie": participant_row["compagnie_nom"],
            "ville": participant_row["ville"],
            "secteur": participant_row["secteur"],
            "responsable_nom": participant_row["responsable_nom"],
            "responsable_titre": participant_row["responsable_titre"],
        },
        "questions": questions_payload,
        "progress": {
            "percent": percent,
            "completed": counted_completed,
            "total": counted_total,
            "extra": total_questions - counted_total,
        },
        "locked": _is_gala_locked(conn, gala_id),
        "submitted": _has_submitted(conn, juge_id, gala_id),
    }
    conn.close()
    return jsonify(response)


@judge_bp.route(
    "/api/galas/<int:gala_id>/categories/<int:gala_categorie_id>/participants/<int:participant_id>/questions/<int:question_id>",
    methods=["PATCH"],
)
def api_update_note(gala_id: int, gala_categorie_id: int, participant_id: int, question_id: int):
    user = _require_judge_user()
    payload = request.get_json(silent=True) or {}
    has_valeur = "valeur" in payload
    has_commentaire = "commentaire" in payload
    valeur = payload.get("valeur") if has_valeur else None
    commentaire = payload.get("commentaire") if has_commentaire else None

    conn = get_db_connection()
    juge_id = _get_judge_id(conn, user["id"])
    _ensure_category_access(conn, juge_id, gala_id, gala_categorie_id)

    participant_exists = conn.execute(
        "SELECT 1 FROM participant WHERE id = ? AND gala_categorie_id = ?",
        (participant_id, gala_categorie_id),
    ).fetchone()
    if not participant_exists:
        conn.close()
        abort(404)

    question_row = conn.execute(
        "SELECT id, gala_categorie_id FROM question WHERE id = ?",
        (question_id,),
    ).fetchone()
    if not question_row:
        conn.close()
        abort(404)

    if _is_gala_locked(conn, gala_id):
        conn.close()
        return jsonify({"status": "error", "message": "Ce gala est verrouille."}), 409

    if _has_submitted(conn, juge_id, gala_id):
        conn.close()
        return jsonify({"status": "error", "message": "Vous avez deja soumis vos evaluations pour ce gala."}), 409

    if has_valeur:
        if valeur is None or valeur == "":
            valeur = None
        else:
            try:
                valeur = float(valeur)
            except (TypeError, ValueError):
                conn.close()
                return jsonify({"status": "error", "message": "Note invalide."}), 400
            if valeur < 0 or valeur > 10:
                conn.close()
                return jsonify({"status": "error", "message": "La note doit etre comprise entre 0 et 10."}), 400
    if has_commentaire:
        if commentaire is not None and commentaire != "":
            if not isinstance(commentaire, str):
                conn.close()
                return jsonify({"status": "error", "message": "Commentaire invalide."}), 400
            commentaire = commentaire.strip()
            if len(commentaire) > 1000:
                conn.close()
                return jsonify({"status": "error", "message": "Le commentaire est trop long."}), 400
            if commentaire == "":
                commentaire = None
        else:
            commentaire = None

    target_participant_id = participant_id
    target_participant_raw = payload.get("target_participant_id")
    if target_participant_raw is not None:
        try:
            target_participant_id = int(target_participant_raw)
        except (TypeError, ValueError):
            conn.close()
            return jsonify({"status": "error", "message": "Participant cible invalide."}), 400

    target_participant_row = conn.execute(
        "SELECT id FROM participant WHERE id = ? AND gala_categorie_id = ?",
        (target_participant_id, question_row["gala_categorie_id"]),
    ).fetchone()
    if not target_participant_row:
        conn.close()
        abort(404)

    existing = conn.execute(
        "SELECT valeur, commentaire FROM note WHERE juge_id = ? AND participant_id = ? AND question_id = ?",
        (juge_id, target_participant_id, question_id),
    ).fetchone()

    valeur_to_save = valeur if has_valeur else (existing["valeur"] if existing else None)
    commentaire_to_save = commentaire if has_commentaire else (existing["commentaire"] if existing else None)

    conn.execute(
        """
        INSERT INTO note (juge_id, participant_id, question_id, valeur, commentaire)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(juge_id, participant_id, question_id)
        DO UPDATE SET valeur = excluded.valeur, commentaire = excluded.commentaire
        """,
        (juge_id, target_participant_id, question_id, valeur_to_save, commentaire_to_save),
    )
    conn.commit()

    notes_row = conn.execute(
        "SELECT valeur, commentaire FROM note WHERE juge_id = ? AND participant_id = ? AND question_id = ?",
        (juge_id, target_participant_id, question_id),
    ).fetchone()
    conn.close()

    saved_at = datetime.now(UTC).isoformat()
    return jsonify(
        {
            "status": "ok",
            "note": {
                "valeur": notes_row["valeur"],
                "commentaire": notes_row["commentaire"],
                "target_participant_id": target_participant_id,
            },
            "saved_at": saved_at,
        }
    )


@judge_bp.route("/api/galas/<int:gala_id>/submit", methods=["POST"])
def api_submit_gala(gala_id: int):
    user = _require_judge_user()
    conn = get_db_connection()
    juge_id = _get_judge_id(conn, user["id"])

    # Ensure judge has assignments for this gala
    assigned = conn.execute(
        """
        SELECT 1
        FROM juge_gala_categorie AS jgc
        JOIN gala_categorie AS gc ON gc.id = jgc.gala_categorie_id
        WHERE jgc.juge_id = ? AND gc.gala_id = ?
        LIMIT 1
        """,
        (juge_id, gala_id),
    ).fetchone()
    if not assigned:
        conn.close()
        abort(404)

    if _is_gala_locked(conn, gala_id):
        conn.close()
        return jsonify({"status": "error", "message": "Ce gala est verrouille."}), 409

    if _has_submitted(conn, juge_id, gala_id):
        conn.close()
        return jsonify({"status": "error", "message": "Deja soumis."}), 409

    # Validate completion
    rows = conn.execute(
        """
        SELECT gc.id AS gala_categorie_id
        FROM juge_gala_categorie AS jgc
        JOIN gala_categorie AS gc ON gc.id = jgc.gala_categorie_id
        WHERE jgc.juge_id = ? AND gc.gala_id = ?
        """,
        (juge_id, gala_id),
    ).fetchall()
    for row in rows:
        category_id = row["gala_categorie_id"]
        question_count = conn.execute(
            "SELECT COUNT(*) AS total FROM question WHERE gala_categorie_id = ?",
            (category_id,),
        ).fetchone()["total"]
        participant_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM participant WHERE gala_categorie_id = ?",
                (category_id,),
            ).fetchall()
        ]
        if question_count == 0 or not participant_ids:
            continue
        placeholders = ",".join("?" for _ in participant_ids)
        note_rows = conn.execute(
            f"SELECT participant_id, COUNT(*) AS total FROM note WHERE juge_id = ? AND participant_id IN ({placeholders}) GROUP BY participant_id",
            (juge_id, *participant_ids),
        ).fetchall()
        counts = {r["participant_id"]: r["total"] for r in note_rows}
        for participant_id in participant_ids:
            if counts.get(participant_id, 0) < question_count:
                conn.close()
                return jsonify({
                    "status": "error",
                    "message": "Toutes les questions doivent etre notees avant la soumission.",
                }), 400

    conn.execute(
        "INSERT INTO juge_gala_submission (juge_id, gala_id, submitted_at) VALUES (?, ?, ?)",
        (juge_id, gala_id, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})
