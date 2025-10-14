(function () {
    const root = document.getElementById("judgeDashboardRoot");
    if (!root) {
        return;
    }

    const state = {
        galaId: Number(root.dataset.galaId),
        categoryId: root.dataset.categoryId ? Number(root.dataset.categoryId) : null,
        participantId: root.dataset.participantId ? Number(root.dataset.participantId) : null,
        galaSummary: null,
        categoryData: null,
        participantData: null,
        favoriteParticipantId: null,
        currentQuestionIndex: 0,
        saving: false,
    };

    const elements = {
        feedback: document.getElementById("judgeFeedback"),
        submitButton: document.getElementById("judgeSubmitButton"),
        subtitle: document.getElementById("judgeGalaSubtitle"),
        statusBadge: document.getElementById("judgeGalaStatusBadge"),
        title: document.getElementById("judgeGalaTitle"),
    };

    const CLASS_STATUS = {
        en_attente: "text-bg-warning",
        en_cours: "text-bg-primary",
        termine: "text-bg-success",
        verrouille: "text-bg-dark",
        soumis: "text-bg-info",
        non_disponible: "text-bg-secondary",
    };

    const RATING_OPTIONS = [
        {
            value: 1,
            title: "1 - Modeste",
            description: "Reponses tres partielles ou sans structure. Peu d'elements concrets.",
        },
        {
            value: 2,
            title: "2 - Faible",
            description: "Criteres abordes superficiellement avec peu de preuves a l'appui.",
        },
        {
            value: 3,
            title: "3 - Acceptable",
            description: "Les criteres de base sont couverts mais l'analyse manque de profondeur.",
        },
        {
            value: 4,
            title: "4 - Bon",
            description: "Reponses structurees, claires et refletant une demarche reflechie.",
        },
        {
            value: 5,
            title: "5 - Tres bon",
            description: "Qualite remarquable et dossier convaincant qui se distingue.",
        },
        {
            value: 6,
            title: "6 - Exceptionnel",
            description: "Impact fort, dossier inspire et depasse largement les attentes.",
        },
    ];

    function escapeHtml(value) {
        if (value === null || value === undefined) {
            return "";
        }
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll("\"", "&quot;")
            .replaceAll("'", "&#39;");
    }

    function formatStatusLabel(status) {
        if (!status) {
            return "";
        }
        const mapping = {
            en_attente: "En attente",
            en_cours: "En cours",
            termine: "Termine",
            verrouille: "Verrouille",
            soumis: "Soumis",
            non_disponible: "N/A",
        };
        return mapping[status] || status;
    }

    function formatPercent(value) {
        if (typeof value !== "number" || Number.isNaN(value)) {
            return "0%";
        }
        const rounded = Math.round(value * 10) / 10;
        return String(rounded) + "%";
    }

    function ensureLayout() {
        if (root.dataset.initialized === "true") {
            return;
        }
        root.dataset.initialized = "true";
        root.innerHTML = [
            '<div class="row g-4">',
            '  <div class="col-lg-4" id="judgeSidebar"></div>',
            '  <div class="col-lg-8">',
            '    <div id="judgeMain"></div>',
            '  </div>',
            '</div>'
        ].join("");
    }

    function getSidebar() {
        return document.getElementById("judgeSidebar");
    }

    function getMain() {
        return document.getElementById("judgeMain");
    }

    function clearFeedback() {
        if (!elements.feedback) {
            return;
        }
        elements.feedback.classList.add("d-none");
        elements.feedback.classList.remove("alert-success", "alert-danger", "alert-info");
        elements.feedback.textContent = "";
    }

    function showFeedback(type, message) {
        if (!elements.feedback) {
            return;
        }
        const className = type === "success" ? "alert-success" : type === "info" ? "alert-info" : "alert-danger";
        elements.feedback.classList.remove("d-none", "alert-success", "alert-danger", "alert-info");
        elements.feedback.classList.add(className);
        elements.feedback.textContent = message;
    }

    function updateStatusBadge() {
        if (!elements.statusBadge || !state.galaSummary) {
            return;
        }
        const status = (state.galaSummary.status || "").toLowerCase();
        const css = CLASS_STATUS[status] || "text-bg-secondary";
        elements.statusBadge.className = "badge " + css;
        elements.statusBadge.textContent = formatStatusLabel(status);
    }

    function updateSubmitButton() {
        if (!elements.submitButton || !state.galaSummary) {
            return;
        }
        const summary = state.galaSummary;
        const locked = Boolean(summary.locked);
        const submitted = Boolean(summary.submitted);
        const total = summary.progress ? summary.progress.total : 0;
        const recorded = summary.progress ? summary.progress.recorded : 0;
        const isComplete = total > 0 && recorded >= total;

        if (locked || submitted) {
            elements.submitButton.classList.add("d-none");
            return;
        }
        elements.submitButton.classList.remove("d-none");
        elements.submitButton.disabled = !isComplete;
        elements.submitButton.textContent = isComplete ? "Soumettre mes evaluations" : "Completez vos evaluations";
    }

    function renderHeader() {
        if (!state.galaSummary) {
            return;
        }
        const summary = state.galaSummary;
        if (elements.title) {
            elements.title.textContent = summary.nom ? "Espace juge – " + summary.nom : "Espace juge";
        }
        if (elements.subtitle) {
            const parts = [];
            if (summary.annee) {
                parts.push("Edition " + summary.annee);
            }
            if (summary.progress && typeof summary.progress.percent === "number") {
                parts.push("Progression " + formatPercent(summary.progress.percent));
            }
            elements.subtitle.textContent = parts.join(" • ");
        }
        updateStatusBadge();
        updateSubmitButton();
    }

    function renderSidebar() {
        const sidebar = getSidebar();
        if (!sidebar) {
            return;
        }
        if (!state.galaSummary) {
            sidebar.innerHTML = '<div class="card border"><div class="card-body text-muted">Chargement des categories...</div></div>';
            return;
        }
        const categories = Array.isArray(state.galaSummary.categories) ? state.galaSummary.categories : [];
        if (!categories.length) {
            sidebar.innerHTML = '<div class="card border"><div class="card-body text-muted">Aucune categorie assignee.</div></div>';
            return;
        }
        sidebar.innerHTML = categories.map(function (category) {
            const isActive = Number(category.id) === Number(state.categoryId);
            const percent = category.progress && typeof category.progress.percent === "number" ? category.progress.percent : 0;
            const participants = category.progress && typeof category.progress.completed_participants === "number" ? category.progress.completed_participants : 0;
            const totalParticipants = category.progress && typeof category.progress.total_participants === "number" ? category.progress.total_participants : 0;
            const status = (category.status || "").toLowerCase();
            const badgeClass = CLASS_STATUS[status] || "text-bg-secondary";
            const cardClasses = ["card", "border", "mb-3", "shadow-sm"];
            if (isActive) {
                cardClasses.push("border-primary", "focus-ring");
            }
            return [
                '<div class="' + cardClasses.join(' ') + '">',
                '  <div class="card-body">',
                '    <div class="d-flex justify-content-between align-items-start">',
                '      <div>',
                '        <h3 class="h6 mb-1">' + escapeHtml(category.nom || 'Categorie') + '</h3>',
                '        <p class="text-muted small mb-2">' + participants + '/' + totalParticipants + ' participants evalues</p>',
                '        <div class="progress" style="height: 6px;">',
                '          <div class="progress-bar" role="progressbar" style="width: ' + Math.min(percent, 100) + '%;"></div>',
                '        </div>',
                '      </div>',
                '      <span class="badge ' + badgeClass + '">' + formatStatusLabel(status) + '</span>',
                '    </div>',
                '    <button class="btn btn-sm btn-outline-primary mt-3" data-action="open-category" data-category-id="' + category.id + '">Voir les participants</button>',
                '  </div>',
                '</div>'
            ].join("");
        }).join("");

        sidebar.querySelectorAll('[data-action="open-category"]').forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                const categoryId = Number(button.dataset.categoryId);
                if (!Number.isNaN(categoryId)) {
                    navigateToCategory(categoryId);
                }
            });
        });
    }

    function participantStatus(completed, total) {
        if (total === 0) {
            return "non_disponible";
        }
        if (completed === 0) {
            return "en_attente";
        }
        if (completed < total) {
            return "en_cours";
        }
        return "termine";
    }

    function renderDefault() {
        const main = getMain();
        if (!main) {
            return;
        }
        main.innerHTML = [
            '<div class="card border shadow-sm">',
            '  <div class="card-body text-center py-5">',
            '    <h2 class="h5 mb-2">Choisissez une categorie a evaluer</h2>',
            '    <p class="text-muted mb-0">Selectionnez une categorie dans la colonne de gauche pour voir les participants associes.</p>',
            '  </div>',
            '</div>'
        ].join("");
    }

    function updateCategoryProgressMetrics() {
        if (!state.categoryData) {
            return;
        }
        const questionCount = state.categoryData.category ? state.categoryData.category.question_count : 0;
        const participants = Array.isArray(state.categoryData.participants) ? state.categoryData.participants : [];
        const totalRequired = questionCount * participants.length;
        let recorded = 0;
        let completedParticipants = 0;
        participants.forEach(function (participant) {
            const completed = participant.progress ? participant.progress.completed_questions || 0 : 0;
            recorded += Math.min(completed, questionCount);
            if (questionCount > 0 && completed >= questionCount) {
                completedParticipants += 1;
            }
        });
        const percent = totalRequired ? Math.round((recorded / totalRequired) * 1000) / 10 : 0;
        state.categoryData.progress = {
            percent: percent,
            completed_participants: completedParticipants,
            total_participants: participants.length,
            recorded: recorded,
            total: totalRequired,
        };
        state.categoryData.status = participantStatus(recorded, totalRequired);
    }

    function updateGalaProgressFromCategories() {
        if (!state.galaSummary) {
            return;
        }
        let recorded = 0;
        let total = 0;
        state.galaSummary.categories.forEach(function (category) {
            const catRecorded = category.progress && typeof category.progress.recorded === "number" ? category.progress.recorded : 0;
            const catTotal = category.progress && typeof category.progress.total === "number" ? category.progress.total : 0;
            recorded += catRecorded;
            total += catTotal;
        });
        const percent = total ? Math.round((recorded / total) * 1000) / 10 : 0;
        state.galaSummary.progress = {
            percent: percent,
            recorded: recorded,
            total: total,
        };
        if (state.galaSummary.locked) {
            state.galaSummary.status = "verrouille";
        } else if (state.galaSummary.submitted) {
            state.galaSummary.status = "soumis";
        } else if (total === 0) {
            state.galaSummary.status = "non_disponible";
        } else if (recorded === 0) {
            state.galaSummary.status = "en_attente";
        } else if (recorded < total) {
            state.galaSummary.status = "en_cours";
        } else {
            state.galaSummary.status = "termine";
        }
    }

    function renderCategory() {
        const main = getMain();
        if (!main || !state.categoryData) {
            renderDefault();
            return;
        }
        const data = state.categoryData;
        const percent = data.progress ? data.progress.percent : 0;
        const locked = Boolean(data.locked);
        const submitted = Boolean(data.submitted);
        const questionCount = data.category ? data.category.question_count : 0;

        main.innerHTML = '';
        const container = document.createElement('div');
        container.className = 'd-flex flex-column gap-4';

        const headerCard = document.createElement('div');
        headerCard.className = 'card border shadow-sm';
        headerCard.innerHTML = [
            '<div class="card-body">',
            '  <div class="d-flex flex-column flex-lg-row justify-content-between align-items-lg-center gap-3">',
            '    <div>',
            '      <h2 class="h5 mb-1">' + escapeHtml(data.category.nom || 'Categorie') + '</h2>',
            '      <p class="text-muted mb-0">' + questionCount + ' questions • ' + data.progress.total_participants + ' participants</p>',
            '    </div>',
            '    <div class="text-end">',
            '      <div class="fw-semibold">' + formatPercent(percent) + '</div>',
            '      <div class="progress" style="height: 6px; width: 160px;">',
            '        <div class="progress-bar" role="progressbar" style="width: ' + Math.min(percent, 100) + '%;"></div>',
            '      </div>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('');
        container.appendChild(headerCard);

        if (locked || submitted) {
            const alert = document.createElement('div');
            const type = locked ? 'alert-secondary' : 'alert-info';
            alert.className = 'alert ' + type;
            alert.textContent = locked ? 'Ce gala est verrouille. Aucune modification n est possible.' : 'Vous avez soumis vos evaluations. En attente de validation.';
            container.appendChild(alert);
        }

        if (!data.participants || !data.participants.length) {
            const empty = document.createElement('div');
            empty.className = 'card border';
            empty.innerHTML = '<div class="card-body text-muted">Aucun participant a evaluer pour cette categorie.</div>';
            container.appendChild(empty);
        } else {
            const list = document.createElement('div');
            list.className = 'd-flex flex-column gap-3';
            data.participants.forEach(function (participant) {
                const participantPercent = participant.progress ? participant.progress.percent : 0;
                const status = participantStatus(participant.progress ? participant.progress.completed_questions : 0, participant.progress ? participant.progress.total_questions : 0);
                const badgeClass = CLASS_STATUS[status] || 'text-bg-secondary';
                const card = document.createElement('div');
                card.className = 'card border shadow-sm';
                card.innerHTML = [
                    '<div class="card-body">',
                    '  <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3">',
                    '    <div>',
                    '      <h3 class="h6 mb-1">' + escapeHtml(participant.compagnie || 'Participant') + '</h3>',
                    participant.ville ? '      <p class="text-muted small mb-0">' + escapeHtml(participant.ville) + '</p>' : '',
                    '    </div>',
                    '    <div class="text-md-end">',
                    '      <div class="progress mb-2" style="height: 6px; width: 160px;"><div class="progress-bar" role="progressbar" style="width: ' + Math.min(participantPercent, 100) + '%;"></div></div>',
                    '      <span class="badge ' + badgeClass + '">' + formatStatusLabel(status) + '</span>',
                    '    </div>',
                    '  </div>',
                    '  <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mt-3">',
                    '    <div class="text-muted small">' + participant.progress.completed_questions + '/' + participant.progress.total_questions + ' questions completees</div>',
                    '    <button class="btn btn-sm btn-outline-primary" data-action="open-participant" data-participant-id="' + participant.id + '">Evaluer</button>',
                    '  </div>',
                    '</div>'
                ].join('');
                list.appendChild(card);
            });
            container.appendChild(list);
        }

        main.appendChild(container);

        main.querySelectorAll('[data-action="open-participant"]').forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                const participantId = Number(button.dataset.participantId);
                if (!Number.isNaN(participantId)) {
                    navigateToParticipant(participantId);
                }
            });
        });
    }

    function renderParticipant() {
        const main = getMain();
        if (!main || !state.participantData) {
            renderCategory();
            return;
        }
        const data = state.participantData;
        const locked = Boolean(data.locked);
        const submitted = Boolean(data.submitted);
        const questions = Array.isArray(data.questions) ? data.questions : [];
        if (state.currentQuestionIndex >= questions.length) {
            state.currentQuestionIndex = questions.length ? questions.length - 1 : 0;
        }

        main.innerHTML = '';
        const container = document.createElement('div');
        container.className = 'd-flex flex-column gap-4';

        const breadcrumbs = document.createElement('div');
        breadcrumbs.className = 'small text-muted';
        breadcrumbs.innerHTML = [
            '<a href="/judge/galas/' + state.galaId + '/categories/' + state.categoryId + '" class="text-decoration-none">' + (state.categoryData && state.categoryData.category ? escapeHtml(state.categoryData.category.nom || 'Categorie') : 'Categorie') + '</a>',
            ' / ',
            escapeHtml(data.participant.compagnie || 'Participant')
        ].join('');
        container.appendChild(breadcrumbs);

        if (locked || submitted) {
            const alert = document.createElement('div');
            const type = locked ? 'alert-secondary' : 'alert-info';
            alert.className = 'alert ' + type;
            alert.textContent = locked ? 'Ce gala est verrouille. Consultation en lecture seule.' : 'Vous avez soumis vos evaluations. Consultation en lecture seule.';
            container.appendChild(alert);
        }

        const progressInfo = data.progress || {};
        let participantMetaLabel = formatPercent(progressInfo.percent || 0) + ' • ' +
            (progressInfo.completed || 0) + '/' + (progressInfo.total || 0) + ' questions';
        if (progressInfo.extra) {
            participantMetaLabel += ' (+ ' + progressInfo.extra + ' narratif' + (progressInfo.extra > 1 ? 's' : '') + ')';
        }

        const card = document.createElement('div');
        card.className = 'card border shadow-sm';
        card.innerHTML = [
            '<div class="card-body">',
            '  <div class="d-flex flex-column flex-lg-row justify-content-between align-items-lg-center gap-3 mb-3">',
            '    <div>',
            '      <h2 class="h5 mb-1" id="judgeParticipantTitle">' + escapeHtml(data.participant.compagnie || 'Participant') + '</h2>',
            '      <p class="text-muted mb-0" id="judgeParticipantMeta">' + participantMetaLabel + '</p>',
            '    </div>',
            '    <div class="d-flex flex-column flex-md-row align-items-stretch align-items-md-center gap-2">',
            '      <button class="btn btn-outline-warning" type="button" id="judgeFavoriteToggle">',
            '        <span class="favorite-label">Coup de coeur</span>',
            '      </button>',
            '      <div class="btn-group" role="group">',
            '        <button class="btn btn-outline-secondary" id="judgeQuestionPrev">Precedent</button>',
            '        <button class="btn btn-outline-secondary" id="judgeQuestionNext">Suivant</button>',
            '      </div>',
            '    </div>',
            '  </div>',
            '  <hr>',
            '  <div id="judgeQuestionContainer"></div>',
            '  <div class="mt-4">',
            '    <a class="btn btn-link" href="/judge/galas/' + state.galaId + '/categories/' + state.categoryId + '">Retour aux participants</a>',
            '  </div>',
            '</div>'
        ].join('');
        container.appendChild(card);

        main.appendChild(container);

        const prevButton = card.querySelector('#judgeQuestionPrev');
        const nextButton = card.querySelector('#judgeQuestionNext');
        const questionContainer = card.querySelector('#judgeQuestionContainer');
        const favoriteButton = card.querySelector('#judgeFavoriteToggle');
        const favoriteLabel = favoriteButton ? favoriteButton.querySelector('.favorite-label') : null;

        function isFavoriteAllowed() {
            const allowedFlag = data.favorite ? data.favorite.allowed !== false : !(locked || submitted);
            return !locked && !submitted && allowedFlag;
        }

        function syncFavoriteButton() {
            if (!favoriteButton) {
                return;
            }
            const selected = state.favoriteParticipantId && Number(state.favoriteParticipantId) === Number(data.participant.id);
            const allowed = isFavoriteAllowed();
            favoriteButton.disabled = !allowed;
            favoriteButton.classList.remove('btn-outline-warning', 'btn-warning', 'btn-outline-secondary', 'btn-secondary');
            if (!allowed) {
                favoriteButton.classList.add(selected ? 'btn-secondary' : 'btn-outline-secondary');
            } else {
                favoriteButton.classList.add(selected ? 'btn-warning' : 'btn-outline-warning');
            }
            const labelText = selected ? 'Retirer coup de coeur' : 'Choisir coup de coeur';
            if (favoriteLabel) {
                favoriteLabel.textContent = labelText;
            } else {
                favoriteButton.textContent = labelText;
            }
        }

        async function toggleFavorite() {
            if (!favoriteButton || !isFavoriteAllowed()) {
                return;
            }
            const alreadySelected = state.favoriteParticipantId && Number(state.favoriteParticipantId) === Number(data.participant.id);
            const method = alreadySelected ? 'DELETE' : 'POST';
            favoriteButton.disabled = true;
            try {
                const response = await fetch('/judge/api/galas/' + state.galaId + '/categories/' + state.categoryId + '/participants/' + state.participantId + '/favorite', {
                    method: method,
                });
                const payload = await response.json().catch(function () { return null; });
                if (!response.ok || !payload || payload.status !== 'ok') {
                    const message = payload && payload.message ? payload.message : 'Action impossible.';
                    showFeedback('error', message);
                    return;
                }
                const favoriteInfo = payload.favorite || {};
                state.favoriteParticipantId = favoriteInfo.participant_id || null;
                data.favorite = favoriteInfo;
                syncFavoriteButton();
                const successMessage = favoriteInfo.selected ? 'Coup de coeur enregistre.' : 'Coup de coeur retire.';
                showFeedback('success', successMessage);
            } catch (error) {
                showFeedback('error', 'Erreur reseau lors de la mise a jour du coup de coeur.');
            } finally {
                syncFavoriteButton();
            }
        }

        syncFavoriteButton();

        if (favoriteButton) {
            favoriteButton.addEventListener('click', function () {
                toggleFavorite();
            });
        }

        function showQuestionStatus(message, isError) {
            const statusEl = card.querySelector('#judgeQuestionSaveStatus');
            if (!statusEl) {
                return;
            }
            statusEl.classList.toggle('text-danger', Boolean(isError));
            statusEl.textContent = message || '';
        }

        let pendingTimer = null;
        let pendingQuestionId = null;
        let pendingPayload = {};

        function resetPendingState() {
            pendingQuestionId = null;
            pendingPayload = {};
        }

        function flushPendingSave(options) {
            const opts = options || {};
            if (pendingTimer) {
                clearTimeout(pendingTimer);
                pendingTimer = null;
            }


            if (pendingQuestionId !== null && pendingPayload && Object.keys(pendingPayload).length) {
                const payload = Object.assign({}, pendingPayload);
                const targetId = pendingQuestionId;
                resetPendingState();
                persistNote(targetId, payload, opts);
            }
        }



        state.flushPendingSaves = flushPendingSave;

        function findQuestionById(questionId) {
            if (!questionId) {
                return null;
            }
            return questions.find(function (item) {
                return Number(item.id) === Number(questionId);
            }) || null;
        }

        function queuePersist(questionId, partialPayload) {
            if (!questionId) {
                return;
            }
            if (pendingTimer && pendingQuestionId !== null && pendingQuestionId !== questionId && pendingPayload && Object.keys(pendingPayload).length) {
                flushPendingSave({ silent: true });
            }
            if (pendingQuestionId !== questionId) {
                pendingPayload = {};
            }
            pendingQuestionId = questionId;
            pendingPayload = Object.assign({}, pendingPayload, partialPayload || {});
            if (pendingTimer) {
                clearTimeout(pendingTimer);
            }
            pendingTimer = window.setTimeout(function () {
                const payload = Object.assign({}, pendingPayload);
                const targetId = pendingQuestionId;
                pendingTimer = null;
                resetPendingState();
                persistNote(targetId, payload);
            }, 2000);
            showQuestionStatus('Sauvegarde dans 2 secondes...', false);
        }

        async function persistNote(questionId, payload, options) {
            if (!questionId || !payload || !Object.keys(payload).length) {
                return;
            }
            const opts = options || {};
            if (state.saving) {
                window.setTimeout(function () {
                    persistNote(questionId, payload, opts);
                }, 250);
                return;
            }
            state.saving = true;
            if (!opts.silent) {
                showQuestionStatus('Enregistrement...', false);
            }
            try {
                const questionMeta = findQuestionById(questionId);
                let targetParticipantId = state.participantId;
                if (questionMeta && questionMeta.scope_participant_id && Number(questionMeta.scope_participant_id) !== Number(state.participantId)) {
                    targetParticipantId = Number(questionMeta.scope_participant_id);
                }
                const body = Object.assign({}, payload);
                if (Number(targetParticipantId) !== Number(state.participantId)) {
                    body.target_participant_id = targetParticipantId;
                }
                const response = await fetch('/judge/api/galas/' + state.galaId + '/categories/' + state.categoryId + '/participants/' + state.participantId + '/questions/' + questionId, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const result = await response.json().catch(function () { return null; });
                if (!response.ok || !result || result.status !== 'ok') {
                    const message = result && result.message ? result.message : 'Erreur lors de la sauvegarde.';
                    showQuestionStatus(message, true);
                    return;
                }
                applyNoteUpdate(questionId, result.note || {});
                if (!opts.silent) {
                    showQuestionStatus('Enregistre', false);
                }
            } catch (error) {
                showQuestionStatus('Erreur reseau.', true);
            } finally {
                state.saving = false;
            }
        }

        function applyNoteUpdate(questionId, notePayload) {
            const questionMeta = findQuestionById(questionId);
            if (!questionMeta) {
                return;
            }
            if (notePayload && Object.prototype.hasOwnProperty.call(notePayload, 'valeur')) {
                questionMeta.note = notePayload.valeur !== null && notePayload.valeur !== undefined
                    ? Number(notePayload.valeur)
                    : null;
            }
            if (notePayload && Object.prototype.hasOwnProperty.call(notePayload, 'commentaire')) {
                questionMeta.commentaire = notePayload.commentaire;
            }
            if (notePayload && Object.prototype.hasOwnProperty.call(notePayload, 'target_participant_id') && notePayload.target_participant_id) {
                questionMeta.scope_participant_id = notePayload.target_participant_id;
            }
            recalculateParticipantMetrics();
            if (questions[state.currentQuestionIndex] && Number(questions[state.currentQuestionIndex].id) === Number(questionId)) {
                renderQuestion();
            }
        }

        function renderQuestion() {
            if (!questionContainer) {
                return;
            }
            const question = questions[state.currentQuestionIndex];
            if (!question) {
                questionContainer.innerHTML = '<p class="text-muted">Aucune question disponible.</p>';
                return;
            }
            const disabled = locked || submitted;
            const badgeParts = [];
            if (question.shared) {
                badgeParts.push('<span class="badge text-bg-info">Narratif</span>');
            }
            badgeParts.push('<span class="badge text-bg-light">Ponderation ' + (question.ponderation || 1) + '</span>');
            const badgesHtml = badgeParts.join(' ');
            const sharedHint = question.shared
                ? '<p class="text-info small mb-2">Question narrative commune a toutes les categories (note unique).</p>'
                : '';
            const ratingOptionsHtml = RATING_OPTIONS.map(function (option) {
                const isActive = Number(question.note) === Number(option.value);
                const classes = ['btn', 'text-start', 'w-100'];
                if (disabled) {
                    classes.push(isActive ? 'btn-secondary' : 'btn-outline-secondary');
                } else {
                    classes.push(isActive ? 'btn-primary' : 'btn-outline-primary');
                }
                classes.push('mb-2');
                return '<button type="button" class="' + classes.join(' ') + '" data-note-value="' + option.value + '" ' + (disabled ? 'disabled' : '') + '>' +
                    '<div><strong>' + escapeHtml(option.title) + '</strong></div>' +
                    '<div class="small text-muted">' + escapeHtml(option.description) + '</div>' +
                    '</button>';
            }).join('');

            questionContainer.innerHTML = [
                '<div class="d-flex justify-content-between align-items-center mb-3">',
                '  <div>',
                '    <h3 class="h6 mb-1">Question ' + (state.currentQuestionIndex + 1) + ' / ' + questions.length + '</h3>',
                '    <p class="text-muted small mb-0">' + formatPercent(state.participantData.progress ? state.participantData.progress.percent : 0) + ' complete</p>',
                '  </div>',
                '  <div class="d-flex align-items-center gap-2">' + badgesHtml + '</div>',
                '</div>',
                sharedHint,
                '<p class="mb-3">' + escapeHtml(question.texte || '') + '</p>',
                '<div class="mb-4">',
                '  <h4 class="h6 text-muted">Reponse du participant</h4>',
                '  <p class="mb-0">' + (question.reponse ? escapeHtml(question.reponse) : '<span class="text-muted">Aucune reponse</span>') + '</p>',
                '</div>',
                '<div class="row g-3">',
                '  <div class="col-12">',
                '    <h4 class="h6 text-muted mb-2">Evaluation (1 a 6)</h4>',
                '    <div class="rating-options d-grid gap-2" id="judgeRatingOptions">',
                ratingOptionsHtml,
                '    </div>',
                '  </div>',
                '  <div class="col-12">',
                '    <label class="form-label" for="judgeQuestionComment">Commentaire</label>',
                '    <textarea class="form-control" id="judgeQuestionComment" rows="3" ' + (disabled ? 'disabled' : '') + '>' + (question.commentaire ? escapeHtml(question.commentaire) : '') + '</textarea>',
                '    <div class="form-text text-muted" id="judgeQuestionSaveStatus"></div>',
                '  </div>',
                '</div>'
            ].join('');

            if (prevButton) {
                prevButton.disabled = state.currentQuestionIndex === 0;
            }
            if (nextButton) {
                nextButton.disabled = state.currentQuestionIndex >= questions.length - 1;
            }

            if (!disabled) {
                const ratingButtons = questionContainer.querySelectorAll('#judgeRatingOptions [data-note-value]');
                ratingButtons.forEach(function (button) {
                    button.addEventListener('click', function () {
                        const value = Number(button.getAttribute('data-note-value'));
                        if (!Number.isFinite(value) || value < 1 || value > 6) {
                            showQuestionStatus('Note invalide', true);
                            return;
                        }
                        ratingButtons.forEach(function (btn) {
                            const btnValue = Number(btn.getAttribute('data-note-value'));
                            btn.classList.remove('btn-primary', 'btn-outline-primary', 'btn-secondary', 'btn-outline-secondary');
                            if (btnValue === value) {
                                btn.classList.add('btn-primary');
                            } else {
                                btn.classList.add('btn-outline-primary');
                            }
                        });
                        question.note = value;
                        recalculateParticipantMetrics();
                        persistNote(question.id, { valeur: value });
                    });
                });
                const commentInput = questionContainer.querySelector('#judgeQuestionComment');
                if (commentInput) {
                    commentInput.addEventListener('blur', function () {
                        const value = commentInput.value.trim();
                        persistNote(question.id, { commentaire: value || null });
                    });
                }
            }
        }

        if (prevButton) {
            prevButton.addEventListener('click', function () {
                if (state.currentQuestionIndex > 0) {
                    state.currentQuestionIndex -= 1;
                    renderQuestion();
                }
            });
        }
        if (nextButton) {
            nextButton.addEventListener('click', function () {
                if (state.currentQuestionIndex < questions.length - 1) {
                    state.currentQuestionIndex += 1;
                    renderQuestion();
                }
            });
        }

        renderQuestion();
    }

    async function fetchGalaSummary() {
        const response = await fetch('/judge/api/galas');
        if (!response.ok) {
            throw new Error('Impossible de charger les galas.');
        }
        const payload = await response.json();
        const galas = Array.isArray(payload.galas) ? payload.galas : [];
        const gala = galas.find(function (item) { return Number(item.id) === Number(state.galaId); });
        if (!gala) {
            throw new Error('Gala introuvable.');
        }
        state.galaSummary = gala;
    }

    async function fetchCategoryData(categoryId) {
        const response = await fetch('/judge/api/galas/' + state.galaId + '/categories/' + categoryId + '/participants');
        if (!response.ok) {
            const payload = await response.json().catch(function () { return null; });
            const message = payload && payload.message ? payload.message : 'Impossible de charger la categorie.';
            throw new Error(message);
        }
        const payload = await response.json();
        state.categoryData = payload;
        state.categoryId = categoryId;
        state.participantId = null;
        state.participantData = null;
        state.currentQuestionIndex = 0;
        const categoryEntry = state.galaSummary ? state.galaSummary.categories.find(function (item) { return Number(item.id) === Number(categoryId); }) : null;
        if (categoryEntry) {
            categoryEntry.progress = {
                percent: payload.progress.percent,
                completed_participants: payload.progress.completed_participants,
                total_participants: payload.progress.total_participants,
                recorded: payload.progress.recorded,
                total: payload.progress.total,
            };
            categoryEntry.status = payload.status;
        }
        updateGalaProgressFromCategories();
    }

    async function fetchParticipantData(participantId) {
        const response = await fetch('/judge/api/galas/' + state.galaId + '/categories/' + state.categoryId + '/participants/' + participantId);
        if (!response.ok) {
            const payload = await response.json().catch(function () { return null; });
            const message = payload && payload.message ? payload.message : 'Impossible de charger le participant.';
            throw new Error(message);
        }
        const payload = await response.json();
        if (!payload.favorite) {
            payload.favorite = {
                selected: false,
                participant_id: null,
                allowed: !(payload.locked || payload.submitted),
            };
        } else if (!Object.prototype.hasOwnProperty.call(payload.favorite, "allowed")) {
            payload.favorite.allowed = !(payload.locked || payload.submitted);
        }
        state.favoriteParticipantId = payload.favorite && payload.favorite.participant_id ? payload.favorite.participant_id : null;
        state.participantData = payload;
        state.participantId = participantId;
        state.currentQuestionIndex = 0;
        recalculateParticipantMetrics();
    }

    function recalculateParticipantMetrics() {
        if (!state.participantData) {
            return;
        }
        const effectiveQuestions = state.participantData.questions.filter(function (item) {
            return item && item.counts_for_progress !== false;
        });
        const completed = effectiveQuestions.filter(function (item) {
            return item.note !== null && item.note !== undefined;
        }).length;
        const total = effectiveQuestions.length;
        const extra = state.participantData.questions.length - total;
        const percent = total ? Math.round((completed / total) * 1000) / 10 : 0;
        state.participantData.progress = {
            completed: completed,
            total: total,
            extra: extra > 0 ? extra : 0,
            percent: percent,
        };
        const metaEl = document.getElementById('judgeParticipantMeta');
        if (metaEl) {
            let label = formatPercent(percent) + ' • ' + completed + '/' + total + ' questions';
            if (extra > 0) {
                label += ' (+ ' + extra + ' narratif' + (extra > 1 ? 's' : '') + ')';
            }
            metaEl.textContent = label;
        }
        if (state.categoryData) {
            const participantEntry = state.categoryData.participants.find(function (item) {
                return Number(item.id) === Number(state.participantId);
            });
            if (participantEntry) {
                const baseTotal = state.categoryData.category ? state.categoryData.category.question_count : total;
                const totalQuestions = Math.max(total, baseTotal);
                participantEntry.progress.completed_questions = completed;
                participantEntry.progress.total_questions = totalQuestions;
                participantEntry.progress.percent = totalQuestions ? Math.round((completed / totalQuestions) * 1000) / 10 : 0;
                participantEntry.status = participantStatus(completed, totalQuestions);
            }
            updateCategoryProgressMetrics();
            const categoryEntry = state.galaSummary ? state.galaSummary.categories.find(function (item) {
                return Number(item.id) === Number(state.categoryId);
            }) : null;
            if (categoryEntry) {
                categoryEntry.progress = {
                    percent: state.categoryData.progress.percent,
                    completed_participants: state.categoryData.progress.completed_participants,
                    total_participants: state.categoryData.progress.total_participants,
                    recorded: state.categoryData.progress.recorded,
                    total: state.categoryData.progress.total,
                };
                categoryEntry.status = state.categoryData.status;
            }
            updateGalaProgressFromCategories();
        }
    }

    async function navigateToCategory(categoryId, options) {
        const opts = options || {};
        const push = opts.push !== false;
        const targetUrl = '/judge/galas/' + state.galaId + '/categories/' + categoryId;
        if (push) {
            window.history.pushState({ galaId: state.galaId, categoryId: categoryId, participantId: null }, '', targetUrl);
        }
        clearFeedback();
        const main = getMain();
        if (main) {
            main.innerHTML = '<div class="card border"><div class="card-body text-muted">Chargement des participants...</div></div>';
        }
        try {
            await fetchGalaSummary();
            await fetchCategoryData(categoryId);
            renderHeader();
            renderSidebar();
            renderCategory();
            if (opts.participantId) {
                await navigateToParticipant(opts.participantId, { push: false });
            }
        } catch (error) {
            showFeedback('error', error.message || 'Impossible de charger la categorie.');
            renderHeader();
            renderSidebar();
            renderDefault();
        }
    }

    async function navigateToParticipant(participantId, options) {
        const opts = options || {};
        const push = opts.push !== false;
        const targetUrl = '/judge/galas/' + state.galaId + '/categories/' + state.categoryId + '/participants/' + participantId;
        if (push) {
            window.history.pushState({ galaId: state.galaId, categoryId: state.categoryId, participantId: participantId }, '', targetUrl);
        }
        clearFeedback();
        const main = getMain();
        if (main) {
            main.innerHTML = '<div class="card border"><div class="card-body text-muted">Chargement de la fiche d evaluation...</div></div>';
        }
        try {
            await fetchParticipantData(participantId);
            renderHeader();
            renderSidebar();
            renderParticipant();
        } catch (error) {
            showFeedback('error', error.message || 'Impossible de charger la fiche.');
            renderHeader();
            renderSidebar();
            renderCategory();
        }
    }
    async function submitEvaluations() {
        if (!elements.submitButton || elements.submitButton.disabled) {
            return;
        }
        const confirmation = window.confirm('Confirmer la soumission finale de vos evaluations ? Vous ne pourrez plus les modifier.');
        if (!confirmation) {
            return;
        }
        elements.submitButton.disabled = true;
        try {
            const response = await fetch('/judge/api/galas/' + state.galaId + '/submit', {
                method: 'POST',
            });
            const payload = await response.json().catch(function () { return null; });
            if (!response.ok || !payload || payload.status !== 'ok') {
                const message = payload && payload.message ? payload.message : 'Impossible de soumettre.';
                showFeedback('error', message);
                elements.submitButton.disabled = false;
                return;
            }
            await fetchGalaSummary();
            renderHeader();
            renderSidebar();
            if (state.categoryId) {
                await fetchCategoryData(state.categoryId);
                renderCategory();
                if (state.participantId) {
                    await fetchParticipantData(state.participantId);
                    renderParticipant();
                }
            } else {
                renderDefault();
            }
            showFeedback('success', 'Soumission enregistree. Merci.');
        } catch (error) {
            showFeedback('error', 'Erreur reseau lors de la soumission.');
            elements.submitButton.disabled = false;
        }
    }

    function initHistory() {
        const currentState = {
            galaId: state.galaId,
            categoryId: state.categoryId,
            participantId: state.participantId,
        };
        window.history.replaceState(currentState, '', window.location.pathname + window.location.search);
        window.addEventListener('popstate', function (event) {
            const popped = event.state || {};
            if (Number(popped.galaId) !== Number(state.galaId)) {
                window.location.reload();
                return;
            }
            if (!popped.categoryId) {
                state.categoryId = null;
                state.categoryData = null;
                state.participantId = null;
                state.participantData = null;
                state.currentQuestionIndex = 0;
                renderHeader();
                renderSidebar();
                renderDefault();
                return;
            }
            navigateToCategory(Number(popped.categoryId), {
                push: false,
                participantId: popped.participantId ? Number(popped.participantId) : null,
            });
        });
    }

    async function initialise() {
        ensureLayout();
        clearFeedback();
        try {
            await fetchGalaSummary();
            renderHeader();
            renderSidebar();
            if (state.categoryId) {
                await navigateToCategory(state.categoryId, {
                    push: false,
                    participantId: state.participantId,
                });
            } else {
                renderDefault();
            }
        } catch (error) {
            renderHeader();
            showFeedback('error', error.message || 'Chargement impossible.');
            renderDefault();
        }
        initHistory();
    }

    if (elements.submitButton) {
        elements.submitButton.addEventListener('click', function (event) {
            event.preventDefault();
            submitEvaluations();
        });
    }

    initialise();
})();
