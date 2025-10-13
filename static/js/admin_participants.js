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
        view: "cards"
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

                rows.push(`<tr>${rowCells.join("")}</tr>`);
            });
        });

        tableBody.innerHTML = rows.join("") || '<tr><td colspan="6" class="text-muted text-center">Aucun participant</td></tr>';
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
                '  <div class="mt-3">',
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

    fetchParticipants();
})();
