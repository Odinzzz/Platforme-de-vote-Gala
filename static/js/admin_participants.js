(function () {
    const galaSelect = document.getElementById("participantsGalaSelect");
    const categorieSelect = document.getElementById("participantsCategorieSelect");
    const searchInput = document.getElementById("participantsSearchInput");
    const missingOnlySwitch = document.getElementById("participantsMissingOnlySwitch");
    const refreshButton = document.getElementById("participantsRefreshButton");
    const refreshSpinner = document.getElementById("participantsRefreshSpinner");
    const cardsContainer = document.getElementById("participantsList");
    const tableWrapper = document.getElementById("participantsTableWrapper");
    const tableElement = document.getElementById("participantsTable");
    const tableBody = tableElement ? tableElement.querySelector("tbody") : null;
    const loadingState = document.getElementById("participantsLoadingState");
    const emptyState = document.getElementById("participantsEmptyState");
    const errorState = document.getElementById("participantsErrorState");
    const subtitle = document.getElementById("participantsSubtitle");
    const countBadge = document.getElementById("participantsCountBadge");
    const viewCardsButton = document.getElementById("participantsViewCardsButton");
    const viewTableButton = document.getElementById("participantsViewTableButton");
    const responsesModalEl = document.getElementById("participantResponsesModal");
    const responsesModalTitle = document.getElementById("participantResponsesModalTitle");
    const responsesModalBody = document.getElementById("participantResponsesBody");
    const responsesModalAlert = document.getElementById("participantResponsesAlert");
    const responsesModalSaveButton = document.getElementById("participantResponsesSaveButton");
    let responsesModal = null;
    if (responsesModalEl && typeof bootstrap !== "undefined") {
        responsesModal = new bootstrap.Modal(responsesModalEl);
    }

    const addParticipantButton = document.getElementById("participantsAddButton");
    const createModalEl = document.getElementById("participantCreateModal");
    const createForm = document.getElementById("participantCreateForm");
    const createFeedback = document.getElementById("participantCreateFeedback");
    const createGalaSelect = document.getElementById("participantCreateGalaSelect");
    const createCategorieSelect = document.getElementById("participantCreateCategorieSelect");
    const createSubmitButton = document.getElementById("participantCreateSubmitButton");
    let createModal = null;
    if (createModalEl && typeof bootstrap !== "undefined") {
        createModal = new bootstrap.Modal(createModalEl);
    }

    if (!galaSelect || !categorieSelect || !cardsContainer) {
        return;
    }

    const state = {
        loading: false,
        filters: {
            galas: []
        },
        selectedGalaId: null,
        selectedCategorieId: null,
        search: "",
        missingOnly: false,
        participants: [],
        filteredParticipants: [],
        view: "cards",
        editingParticipantId: null,
        currentResponses: null
    };

    function escapeHtml(value) {
        if (value === null || value === undefined) {
            return "";
        }
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function formatCountLabel(filtered, total) {
        if (total === 0) {
            return "0 participant";
        }
        if (filtered === total) {
            return `${filtered} participant${filtered > 1 ? "s" : ""}`;
        }
        return `${filtered} / ${total} participants`;
    }

    function setLoading(isLoading) {
        state.loading = isLoading;
        if (isLoading) {
            loadingState?.classList.remove("d-none");
            emptyState?.classList.add("d-none");
            errorState?.classList.add("d-none");
            cardsContainer.innerHTML = "";
            if (tableBody) {
                tableBody.innerHTML = "";
            }
            refreshButton?.setAttribute("disabled", "disabled");
            refreshSpinner?.classList.remove("d-none");
        } else {
            loadingState?.classList.add("d-none");
            refreshButton?.removeAttribute("disabled");
            refreshSpinner?.classList.add("d-none");
        }
    }

        function showResponsesAlert(type, message) {
        if (!responsesModalAlert) {
            return;
        }
        responsesModalAlert.className = "alert d-none";
        responsesModalAlert.textContent = "";
        if (!type || !message) {
            return;
        }
        var bootstrapClass = "alert-info";
        if (type === "success") {
            bootstrapClass = "alert-success";
        } else if (type === "danger") {
            bootstrapClass = "alert-danger";
        } else if (type === "warning") {
            bootstrapClass = "alert-warning";
        }
        responsesModalAlert.className = "alert " + bootstrapClass;
        responsesModalAlert.textContent = message;
    }

    function showCreateFeedback(type, message) {
        if (!createFeedback) {
            return;
        }
        createFeedback.className = "alert d-none";
        createFeedback.textContent = "";
        if (!type || !message) {
            return;
        }
        var bootstrapClass = "alert-info";
        if (type === "success") {
            bootstrapClass = "alert-success";
        } else if (type === "danger") {
            bootstrapClass = "alert-danger";
        } else if (type === "warning") {
            bootstrapClass = "alert-warning";
        }
        createFeedback.className = "alert " + bootstrapClass;
        createFeedback.textContent = message;
    }

    function resetResponsesModal() {
        if (responsesModalSaveButton) {
            responsesModalSaveButton.disabled = false;
        }
        showResponsesAlert(null, "");
        if (responsesModalBody) {
            responsesModalBody.innerHTML = "<div class=\"placeholder-glow\"><div class=\"placeholder col-12 mb-2\" style=\"height: 32px;\"></div><div class=\"placeholder col-12 mb-2\" style=\"height: 80px;\"></div><div class=\"placeholder col-10\" style=\"height: 80px;\"></div></div>";
        }
        if (responsesModalTitle) {
            responsesModalTitle.textContent = "Modifier les reponses";
        }
    }

    function renderResponsesModalContent(data) {
        if (!responsesModalBody) {
            return;
        }
        var participant = data.participant || {};
        var category = data.category || {};
        var questions = Array.isArray(data.questions) ? data.questions : [];
        var titleParts = [];
        if (participant.compagnie) {
            titleParts.push(participant.compagnie);
        } else if (participant.id) {
            titleParts.push("Participant #" + participant.id);
        }
        if (category.nom) {
            titleParts.push(category.nom);
        }
        if (responsesModalTitle) {
            responsesModalTitle.textContent = titleParts.join(" - ") || "Modifier les reponses";
        }
        if (!questions.length) {
            responsesModalBody.innerHTML = "<p class=\"text-muted small mb-0\">Aucune question disponible pour ce participant.</p>";
            return;
        }
        var blocks = questions.map(function (question, index) {
            var value = question.reponse || "";
            var label = "Question " + (index + 1);
            return [
                "<div class=\"mb-3\">",
                "  <label class=\"form-label\">" + escapeHtml(label) + "<span class=\"text-muted\"> - " + escapeHtml(question.texte || "") + "</span></label>",
                "  <textarea class=\"form-control\" rows=\"4\" data-question-id=\"" + question.id + "\" data-original-value=\"\">" + escapeHtml(value) + "</textarea>",
                "</div>"
            ].join("");
        }).join("");
        responsesModalBody.innerHTML = blocks;
        Array.from(responsesModalBody.querySelectorAll("textarea[data-question-id]"))
            .forEach(function (textarea) {
                textarea.dataset.originalValue = textarea.value.trim();
            });
    }

    async function openResponsesModal(participantId) {
        if (!responsesModal) {
            return;
        }
        state.editingParticipantId = participantId;
        state.currentResponses = null;
        resetResponsesModal();
        responsesModal.show();
        try {
            const response = await fetch("/admin/api/participants/" + participantId + "/responses");
            if (!response.ok) {
                throw new Error("Erreur de chargement");
            }
            const payload = await response.json();
            state.currentResponses = payload;
            renderResponsesModalContent(payload);
        } catch (error) {
            showResponsesAlert("danger", "Impossible de charger les reponses.");
            if (responsesModalBody) {
                responsesModalBody.innerHTML = "<p class=\"text-danger small mb-0\">Une erreur est survenue lors du chargement.</p>";
            }
        }
    }

    async function saveParticipantResponses() {
        if (!state.editingParticipantId || !responsesModalBody) {
            return;
        }
        const textareas = Array.from(responsesModalBody.querySelectorAll("textarea[data-question-id]"));
        const changes = textareas.map(function (textarea) {
            const questionId = Number(textarea.getAttribute("data-question-id"));
            const originalValue = textarea.dataset.originalValue || "";
            const currentValue = textarea.value.trim();
            if (!Number.isFinite(questionId)) {
                return null;
            }
            if (originalValue === currentValue) {
                return null;
            }
            return { questionId: questionId, contenu: currentValue };
        }).filter(Boolean);
        if (!changes.length) {
            showResponsesAlert("info", "Aucune modification a enregistrer.");
            return;
        }
        if (responsesModalSaveButton) {
            responsesModalSaveButton.disabled = true;
        }
        try {
            for (const change of changes) {
                const response = await fetch("/admin/api/participants/" + state.editingParticipantId + "/questions/" + change.questionId, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ contenu: change.contenu })
                });
                if (!response.ok) {
                    const payload = await response.json().catch(function () { return null; });
                    const message = payload && payload.message ? payload.message : "Echec de l'enregistrement.";
                    throw new Error(message);
                }
                const textarea = responsesModalBody.querySelector('textarea[data-question-id="' + change.questionId + '"]');
                if (textarea) {
                    textarea.dataset.originalValue = change.contenu || "";
                }
            }
            showResponsesAlert("success", "Reponses enregistrees.");
            state.currentResponses = null;
            fetchParticipants();
        } catch (error) {
            showResponsesAlert("danger", error.message || "Echec de l'enregistrement.");
        } finally {
            if (responsesModalSaveButton) {
                responsesModalSaveButton.disabled = false;
            }
        }
    }


function normalizeId(value) {
        if (value === null || value === undefined || value === "") {
            return null;
        }
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }

    function findGalaById(galaId) {
        if (!Array.isArray(state.filters.galas)) {
            return null;
        }
        return state.filters.galas.find(function (gala) {
            return gala && gala.id === galaId;
        }) || null;
    }

    function collectCategories() {
        const galas = Array.isArray(state.filters.galas) ? state.filters.galas : [];
        if (!galas.length) {
            return [];
        }
        if (state.selectedGalaId) {
            const gala = findGalaById(state.selectedGalaId);
            return gala && Array.isArray(gala.categories) ? gala.categories.slice() : [];
        }

        const seen = new Set();
        const categories = [];
        galas.forEach(function (gala) {
            if (!Array.isArray(gala.categories)) {
                return;
            }
            gala.categories.forEach(function (category) {
                if (!category || seen.has(category.id)) {
                    return;
                }
                seen.add(category.id);
                categories.push(category);
            });
        });
        categories.sort(function (a, b) {
            const nameA = (a.nom || "").toString().toLowerCase();
            const nameB = (b.nom || "").toString().toLowerCase();
            if (nameA < nameB) {
                return -1;
            }
            if (nameA > nameB) {
                return 1;
            }
            return 0;
        });
        return categories;
    }

    function populateGalaOptions() {
        const galas = Array.isArray(state.filters.galas) ? state.filters.galas : [];
        const currentValue = state.selectedGalaId ? String(state.selectedGalaId) : "";
        galaSelect.innerHTML = "";
        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Tous les galas";
        galaSelect.appendChild(defaultOption);
        galas.forEach(function (gala) {
            if (!gala) {
                return;
            }
            const option = document.createElement("option");
            option.value = String(gala.id);
            const labelParts = [];
            if (gala.annee) {
                labelParts.push(gala.annee);
            }
            if (gala.nom) {
                labelParts.push(gala.nom);
            }
            option.textContent = labelParts.join(" - ") || `Gala ${gala.id}`;
            galaSelect.appendChild(option);
        });
        galaSelect.value = currentValue;
    }

    function populateCategorieOptions() {
        const categories = collectCategories();
        const currentValue = state.selectedCategorieId ? String(state.selectedCategorieId) : "";
        categorieSelect.innerHTML = "";
        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Toutes les categories";
        categorieSelect.appendChild(defaultOption);

        categories.forEach(function (category) {
            if (!category) {
                return;
            }
            const option = document.createElement("option");
            option.value = String(category.id);
            option.textContent = category.nom || `Categorie ${category.id}`;
            categorieSelect.appendChild(option);
        });

        categorieSelect.disabled = categories.length === 0;
        if (!categories.length) {
            state.selectedCategorieId = null;
        }
        categorieSelect.value = currentValue && !categorieSelect.disabled ? currentValue : "";
        if (categorieSelect.disabled) {
            categorieSelect.value = "";
        }
        state.selectedCategorieId = normalizeId(categorieSelect.value);
    }

    function resetCreateModal() {
        showCreateFeedback(null, "");
        if (createForm) {
            createForm.reset();
        }
        if (createGalaSelect) {
            createGalaSelect.innerHTML = '<option value="">Selectionnez un gala</option>';
            createGalaSelect.disabled = false;
        }
        if (createCategorieSelect) {
            createCategorieSelect.innerHTML = '<option value="">Choisissez un gala pour afficher les categories</option>';
            createCategorieSelect.disabled = true;
        }
    }

    function populateCreateGalaOptions() {
        if (!createGalaSelect) {
            return;
        }
        const galas = Array.isArray(state.filters.galas) ? state.filters.galas : [];
        createGalaSelect.innerHTML = "";
        if (!galas.length) {
            createGalaSelect.disabled = true;
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "Aucun gala disponible";
            createGalaSelect.appendChild(option);
            if (createCategorieSelect) {
                createCategorieSelect.innerHTML = '<option value="">Aucune categorie disponible</option>';
                createCategorieSelect.disabled = true;
            }
            return;
        }
        createGalaSelect.disabled = false;
        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Selectionnez un gala";
        createGalaSelect.appendChild(defaultOption);
        let initialGalaId = state.selectedGalaId || null;
        const hasSelected = galas.some(function (gala) {
            return gala && initialGalaId !== null && gala.id === initialGalaId;
        });
        if (!hasSelected) {
            initialGalaId = galas[0] ? galas[0].id : null;
        }
        galas.forEach(function (gala) {
            if (!gala) {
                return;
            }
            const option = document.createElement("option");
            option.value = String(gala.id);
            const labelParts = [];
            if (gala.annee) {
                labelParts.push(gala.annee);
            }
            if (gala.nom) {
                labelParts.push(gala.nom);
            }
            option.textContent = labelParts.join(" - ") || ("Gala " + gala.id);
            createGalaSelect.appendChild(option);
        });
        createGalaSelect.value = initialGalaId ? String(initialGalaId) : "";
        populateCreateCategorieOptions();
    }

    function populateCreateCategorieOptions() {
        if (!createCategorieSelect) {
            return;
        }
        const galaId = createGalaSelect ? normalizeId(createGalaSelect.value) : null;
        const gala = galaId ? findGalaById(galaId) : null;
        const categories = gala && Array.isArray(gala.categories) ? gala.categories : [];
        createCategorieSelect.innerHTML = "";
        if (!categories.length) {
            createCategorieSelect.disabled = true;
            const option = document.createElement("option");
            option.value = "";
            option.textContent = gala ? "Aucune categorie disponible" : "Choisissez un gala pour afficher les categories";
            createCategorieSelect.appendChild(option);
            return;
        }
        createCategorieSelect.disabled = false;
        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Selectionnez une categorie";
        createCategorieSelect.appendChild(defaultOption);
        let initialCategorieId = state.selectedCategorieId || null;
        let hasSelected = false;
        categories.forEach(function (category) {
            if (!category) {
                return;
            }
            const option = document.createElement("option");
            option.value = String(category.id);
            option.textContent = category.nom || ("Categorie " + category.id);
            if (initialCategorieId !== null && category.id === initialCategorieId) {
                hasSelected = true;
            }
            createCategorieSelect.appendChild(option);
        });
        if (!hasSelected) {
            createCategorieSelect.value = "";
        } else {
            createCategorieSelect.value = String(initialCategorieId);
        }
    }

    function openCreateParticipantModal() {
        if (!createModal || !createForm) {
            return;
        }
        showCreateFeedback(null, "");
        createForm.reset();
        populateCreateGalaOptions();
        populateCreateCategorieOptions();
        createModal.show();
        const focusTarget = createForm.querySelector("#participantCreateCompanyName");
        if (focusTarget) {
            setTimeout(function () {
                focusTarget.focus();
            }, 150);
        }
    }

    function handleCreateParticipantSubmit(event) {
        if (event) {
            event.preventDefault();
        }
        if (!createForm || !createCategorieSelect) {
            return;
        }
        const selectedCategorieId = normalizeId(createCategorieSelect.value);
        if (!selectedCategorieId) {
            showCreateFeedback("danger", "Selectionnez une categorie.");
            return;
        }
        const formData = new FormData(createForm);
        const compagnieNom = (formData.get("compagnie_nom") || "").toString().trim();
        if (!compagnieNom) {
            showCreateFeedback("danger", "Le nom de l'entreprise est requis.");
            return;
        }
        const payload = {
            gala_categorie_id: selectedCategorieId,
            compagnie: {
                nom: compagnieNom,
            },
        };
        const optionalMap = {
            secteur: "compagnie_secteur",
            ville: "compagnie_ville",
            courriel: "compagnie_courriel",
            telephone: "compagnie_telephone",
            responsable_nom: "compagnie_responsable",
            responsable_titre: "compagnie_responsable_titre",
            site_web: "compagnie_site_web",
        };
        Object.keys(optionalMap).forEach(function (key) {
            const field = optionalMap[key];
            const value = (formData.get(field) || "").toString().trim();
            if (value) {
                payload.compagnie[key] = value;
            }
        });

        showCreateFeedback(null, "");
        if (createSubmitButton) {
            createSubmitButton.disabled = true;
        }

        fetch("/admin/api/participants", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                }).catch(function () {
                    return { ok: response.ok, data: null };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    const message = result.data && result.data.message ? result.data.message : "Impossible d'ajouter le participant.";
                    throw new Error(message);
                }
                if (createModal) {
                    createModal.hide();
                }
                fetchParticipants();
            })
            .catch(function (error) {
                console.error("admin_participants create error", error);
                showCreateFeedback("danger", error.message || "Impossible d'ajouter le participant.");
            })
            .finally(function () {
                if (createSubmitButton) {
                    createSubmitButton.disabled = false;
                }
            });
    }

    function updateSubtitle() {
        if (!subtitle) {
            return;
        }
        const parts = [];
        const gala = state.selectedGalaId ? findGalaById(state.selectedGalaId) : null;
        if (gala) {
            const galaLabel = [gala.annee, gala.nom].filter(Boolean).join(" - ");
            parts.push(galaLabel || "Gala selectionne");
        } else {
            parts.push("Tous les galas");
        }

        if (state.selectedCategorieId) {
            const categories = collectCategories();
            const category = categories.find(function (item) {
                return item && item.id === state.selectedCategorieId;
            });
            parts.push(category && category.nom ? category.nom : "Categorie selectionnee");
        } else {
            parts.push("Toutes les categories");
        }

        if (state.search) {
            parts.push('Recherche "' + escapeHtml(state.search) + '"');
        }

        subtitle.innerHTML = parts.join(" - ");
    }

    function formatField(label, value) {
        if (!value) {
            return "";
        }
        return `<span><span class="text-muted">${escapeHtml(label)} :</span> ${escapeHtml(value)}</span>`;
    }

    function formatResponseContent(value) {
        if (value === null || value === undefined || value === "") {
            return '<span class="text-muted fst-italic">Aucune reponse</span>';
        }
        return escapeHtml(String(value)).replace(/\r?\n/g, "<br>");
    }

    function setActiveViewButton(view) {
        if (!viewCardsButton || !viewTableButton) {
            return;
        }
        if (view === "table") {
            viewTableButton.classList.add("active");
            viewCardsButton.classList.remove("active");
        } else {
            viewCardsButton.classList.add("active");
            viewTableButton.classList.remove("active");
        }
    }

    function renderTableView(participants) {
        if (!tableBody || !tableWrapper) {
            return;
        }
        const categoriesMap = new Map();
        participants.forEach(function (participant) {
            if (!participant) {
                return;
            }
            const category = participant.categorie || {};
            const key = (category.id || "unknown") + "::" + (category.nom || "");
            if (!categoriesMap.has(key)) {
                categoriesMap.set(key, {
                    id: category.id,
                    nom: category.nom || "Categorie",
                    segment: category.segment || "",
                    participants: []
                });
            }
            categoriesMap.get(key).participants.push(participant);
        });

        const sortedCategories = Array.from(categoriesMap.values()).sort(function (a, b) {
            const nameA = (a.nom || "").toLowerCase();
            const nameB = (b.nom || "").toLowerCase();
            if (nameA < nameB) {
                return -1;
            }
            if (nameA > nameB) {
                return 1;
            }
            return 0;
        });

        const rows = [];

        sortedCategories.forEach(function (categoryGroup) {
            const participantsInCategory = categoryGroup.participants.slice().sort(function (a, b) {
                const nameA = (a.compagnie?.nom || "").toLowerCase();
                const nameB = (b.compagnie?.nom || "").toLowerCase();
                if (nameA < nameB) {
                    return -1;
                }
                if (nameA > nameB) {
                    return 1;
                }
                return 0;
            });

            participantsInCategory.forEach(function (participant, index) {
                const stats = participant.stats || {};
                const answered = Number(stats.answered) || 0;
                const total = Number(stats.total_questions) || 0;
                const missing = Number(stats.missing) || 0;
                const percent = typeof stats.completion_percent === "number" ? stats.completion_percent.toFixed(1) : "0.0";
                const responses = Array.isArray(participant.responses) ? participant.responses : [];
                const narrativeCount = responses.filter(function (item) {
                    return item && item.origin === "narratif";
                }).length;
                const responseLabel = narrativeCount
                    ? `${answered}/${total} (+${narrativeCount} narratif${narrativeCount > 1 ? "s" : ""})`
                    : `${answered}/${total}`;
                const statusClass = missing > 0 ? "text-bg-warning" : "text-bg-success";
                const statusLabel = missing > 0 ? "Incomplet" : "Complet";

                const participantName = participant.compagnie?.nom || `Participant #${participant.id}`;
                const city = participant.compagnie?.ville || "";
                const rowCells = [];

                if (index === 0) {
                    rowCells.push(
                        `<td rowspan="${participantsInCategory.length}" class="fw-semibold">${escapeHtml(categoryGroup.nom || "")}</td>`
                    );
                    rowCells.push(
                        `<td rowspan="${participantsInCategory.length}">${categoryGroup.segment ? escapeHtml(categoryGroup.segment) : "<span class='text-muted'>-</span>"}</td>`
                    );
                }

                rowCells.push(
                    `<td>${escapeHtml(participantName)}</td>`
                );
                rowCells.push(
                    `<td>${city ? escapeHtml(city) : "<span class='text-muted'>-</span>"}</td>`
                );
                rowCells.push(
                    `<td><span class="badge ${statusClass}">${escapeHtml(statusLabel)}</span><div class="small text-muted">${percent}%</div></td>`
                );
                rowCells.push(
                    `<td>${escapeHtml(responseLabel)}</td>`
                );
                rowCells.push(
                    `<td><button class="btn btn-sm btn-outline-secondary" type="button" data-action="edit-responses" data-participant-id="${participant.id}">Modifier</button></td>`
                );

                rows.push(`<tr>${rowCells.join("")}</tr>`);
            });
        });

        tableBody.innerHTML = rows.join("") || '<tr><td colspan="7" class="text-muted text-center">Aucun participant</td></tr>';
        tableWrapper.classList.toggle("d-none", rows.length === 0);
    }

    function renderCardView(participants) {
        cardsContainer.innerHTML = "";
        if (!participants.length) {
            return;
        }
        const fragment = document.createDocumentFragment();
        participants.forEach(function (participant) {
            if (!participant) {
                return;
            }
            const stats = participant.stats || {};
            const answered = Number(stats.answered) || 0;
            const total = Number(stats.total_questions) || 0;
            const missing = Number(stats.missing) || 0;
            const percent = typeof stats.completion_percent === "number"
                ? stats.completion_percent.toFixed(1)
                : (total ? ((answered / total) * 100).toFixed(1) : "0.0");

            const badgeClass = missing > 0 ? "text-bg-warning" : "text-bg-success";
            const badgeLabel = missing > 0 ? `${missing} en attente` : "Complet";

            const card = document.createElement("div");
            card.className = "card shadow-sm";

            const collapseId = `participantResponses-${participant.id}`;
            const compagnie = participant.compagnie || {};
            const gala = participant.gala || {};
            const categorie = participant.categorie || {};
            const responses = Array.isArray(participant.responses) ? participant.responses : [];

            const headerParts = [];
            if (gala.annee) {
                headerParts.push(escapeHtml(String(gala.annee)));
            }
            if (gala.nom) {
                headerParts.push(escapeHtml(gala.nom));
            }
            if (categorie.nom) {
                headerParts.push(escapeHtml(categorie.nom));
            }
            const segmentLabel = categorie.segment ? `<span class="badge rounded-pill text-bg-light ms-2">${escapeHtml(categorie.segment)}</span>` : "";
            const headerLine = headerParts.join(" - ");
            const detailLine = [headerLine, segmentLabel].filter(Boolean).join(" ");

            const metaFields = [
                formatField("Secteur", compagnie.secteur),
                formatField("Ville", compagnie.ville),
                formatField("Responsable", compagnie.responsable_nom),
                formatField("Titre", compagnie.responsable_titre)
            ].filter(Boolean).join(" | ");

            const contactFields = [
                formatField("Courriel", compagnie.courriel),
                formatField("Telephone", compagnie.telephone),
                formatField("Site web", compagnie.site_web)
            ].filter(Boolean).join(" | ");

            const responsesList = responses.length
                ? responses.map(function (item) {
                    if (!item) {
                        return "";
                    }
                    const missingClass = !item.contenu ? "bg-warning-subtle" : "";
                    const isNarratif = item.origin === "narratif";
                    const escapedQuestion = escapeHtml(item.texte || "");
                    const heading = isNarratif
                        ? '<span class="badge text-bg-info me-2">Narratif</span>' + escapedQuestion
                        : 'Q' + item.ordre + ': ' + escapedQuestion;
                    return (
                        `<div class="list-group-item ${missingClass}">` +
                        `<div class="fw-semibold small mb-1">${heading}</div>` +
                        `<div class="text-body-secondary small">${formatResponseContent(item.contenu)}</div>` +
                        `</div>`
                    );
                }).join("")
                : '<div class="list-group-item"><span class="text-muted fst-italic">Aucune question configuree pour cette categorie.</span></div>';

            card.innerHTML = [
                '<div class="card-body">',
                '  <div class="d-flex flex-wrap justify-content-between align-items-start gap-3">',
                `    <div>`,
                `      <h3 class="h6 mb-1">${escapeHtml(compagnie.nom || "Participant #" + participant.id)}</h3>`,
                `      <p class="text-muted small mb-2">${detailLine || "&nbsp;"}</p>`,
                metaFields ? `      <div class="small text-muted">${metaFields}</div>` : "",
                '    </div>',
                '    <div class="text-end">',
                `      <span class="badge ${badgeClass}">${escapeHtml(badgeLabel)}</span>`,
                `      <div class="small text-muted">${answered} / ${total} reponses</div>`,
                `      <div class="small fw-semibold">${percent}%</div>`,
                '    </div>',
                '  </div>',
                contactFields ? `  <div class="small text-muted mt-3 d-flex flex-wrap gap-2">${contactFields}</div>` : "",
                '  <div class="mt-3 d-flex flex-wrap gap-2">',
                `    <button class="btn btn-sm btn-outline-secondary" type="button" data-action="edit-responses" data-participant-id="${participant.id}">Modifier les reponses</button>`,
                `    <button class="btn btn-sm btn-outline-primary" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}" aria-expanded="false">Voir les reponses</button>`,
                '  </div>',
                `  <div class="collapse mt-3" id="${collapseId}">`,
                '    <div class="list-group list-group-flush">',
                responsesList,
                '    </div>',
                '  </div>',
                '</div>'
            ].join("");

            fragment.appendChild(card);
        });

        cardsContainer.appendChild(fragment);
    }

    function renderParticipants() {
        const participants = state.filteredParticipants;
        emptyState?.classList.add("d-none");
        errorState?.classList.add("d-none");
        countBadge.textContent = formatCountLabel(participants.length, state.participants.length);
        updateSubtitle();

        setActiveViewButton(state.view);

        if (state.view === "table") {
            cardsContainer.classList.add("d-none");
            if (tableWrapper) {
                tableWrapper.classList.remove("d-none");
            }
        } else {
            cardsContainer.classList.remove("d-none");
            if (tableWrapper) {
                tableWrapper.classList.add("d-none");
            }
        }

        if (!participants.length) {
            emptyState?.classList.remove("d-none");
            cardsContainer.innerHTML = "";
            if (tableBody) {
                tableBody.innerHTML = "";
            }
            return;
        }

        if (state.view === "table") {
            renderTableView(participants);
        } else {
            if (tableBody) {
                tableBody.innerHTML = "";
            }
            renderCardView(participants);
        }
    }

    function applyClientFilters() {
        const base = Array.isArray(state.participants) ? state.participants : [];
        state.filteredParticipants = base.filter(function (participant) {
            if (!participant) {
                return false;
            }
            if (!state.missingOnly) {
                return true;
            }
            const stats = participant.stats || {};
            return Number(stats.missing) > 0;
        });
        renderParticipants();
    }

    function syncControls() {
        populateGalaOptions();
        populateCategorieOptions();
        updateSubtitle();
        if (searchInput) {
            searchInput.value = state.search;
        }
        if (missingOnlySwitch) {
            missingOnlySwitch.checked = state.missingOnly;
        }
    }

    let searchDebounce = null;

    async function fetchParticipants() {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (state.selectedGalaId) {
                params.set("gala_id", String(state.selectedGalaId));
            }
            if (state.selectedCategorieId) {
                params.set("categorie_id", String(state.selectedCategorieId));
            }
            if (state.search) {
                params.set("q", state.search);
            }

            const response = await fetch(`/admin/api/participants?${params.toString()}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const payload = await response.json();
            state.filters.galas = Array.isArray(payload?.filters?.galas) ? payload.filters.galas : [];
            const selected = payload?.filters?.selected || {};
            state.selectedGalaId = normalizeId(selected.gala_id);
            state.selectedCategorieId = normalizeId(selected.categorie_id);
            state.search = selected.q || "";
            state.participants = Array.isArray(payload?.participants) ? payload.participants : [];
            populateCreateGalaOptions();
            populateCreateCategorieOptions();
            syncControls();
            applyClientFilters();
        } catch (error) {
            console.error("admin_participants fetch error", error);
            if (errorState) {
                errorState.classList.remove("d-none");
            }
            state.participants = [];
            state.filteredParticipants = [];
            listContainer.innerHTML = "";
            emptyState?.classList.add("d-none");
            countBadge.textContent = "0 participant";
        } finally {
            setLoading(false);
        }
    }

    galaSelect.addEventListener("change", function (event) {
        const newGalaId = normalizeId(event.target.value);
        const hasChanged = state.selectedGalaId !== newGalaId;
        state.selectedGalaId = newGalaId;
        if (hasChanged) {
            state.selectedCategorieId = null;
        }
        fetchParticipants();
    });

    categorieSelect.addEventListener("change", function (event) {
        state.selectedCategorieId = normalizeId(event.target.value);
        fetchParticipants();
    });

    if (searchInput) {
        searchInput.addEventListener("input", function (event) {
            const value = event.target.value || "";
            state.search = value.trim();
            if (searchDebounce) {
                clearTimeout(searchDebounce);
            }
            searchDebounce = setTimeout(function () {
                fetchParticipants();
            }, 350);
        });
    }

    if (missingOnlySwitch) {
        missingOnlySwitch.addEventListener("change", function (event) {
            state.missingOnly = Boolean(event.target.checked);
            applyClientFilters();
        });
    }

    if (refreshButton) {
        refreshButton.addEventListener("click", function () {
            fetchParticipants();
        });
    }

    function switchView(view) {
        if (state.view === view) {
            return;
        }
        state.view = view;
        renderParticipants();
    }

    if (viewCardsButton) {
        viewCardsButton.addEventListener("click", function () {
            switchView("cards");
        });
    }

    if (viewTableButton) {
        viewTableButton.addEventListener("click", function () {
            switchView("table");
        });
    }


    if (responsesModalSaveButton) {
        responsesModalSaveButton.addEventListener("click", function () {
            saveParticipantResponses();
        });
    }

    if (responsesModalEl) {
        responsesModalEl.addEventListener("hidden.bs.modal", function () {
            state.editingParticipantId = null;
            state.currentResponses = null;
            resetResponsesModal();
        });
    }

    if (createModalEl) {
        createModalEl.addEventListener("hidden.bs.modal", function () {
            resetCreateModal();
        });
    }

    if (createGalaSelect) {
        createGalaSelect.addEventListener("change", function () {
            populateCreateCategorieOptions();
        });
    }

    if (createForm) {
        createForm.addEventListener("submit", handleCreateParticipantSubmit);
    }

    if (addParticipantButton) {
        addParticipantButton.addEventListener("click", function () {
            if (!Array.isArray(state.filters.galas) || !state.filters.galas.length) {
                resetCreateModal();
                showCreateFeedback("warning", "Aucun gala disponible. Actualisez les donnees en premier.");
                if (createModal) {
                    createModal.show();
                }
                return;
            }
            openCreateParticipantModal();
        });
    }

    if (cardsContainer) {
        cardsContainer.addEventListener("click", function (event) {
            var trigger = event.target.closest('[data-action="edit-responses"]');
            if (!trigger) {
                return;
            }
            event.preventDefault();
            var participantId = Number(trigger.getAttribute("data-participant-id"));
            if (!Number.isFinite(participantId)) {
                return;
            }
            openResponsesModal(participantId);
        });
    }

    if (tableWrapper) {
        tableWrapper.addEventListener("click", function (event) {
            var trigger = event.target.closest('[data-action="edit-responses"]');
            if (!trigger) {
                return;
            }
            event.preventDefault();
            var participantId = Number(trigger.getAttribute("data-participant-id"));
            if (!Number.isFinite(participantId)) {
                return;
            }
            openResponsesModal(participantId);
        });
    }

    fetchParticipants();
})();
