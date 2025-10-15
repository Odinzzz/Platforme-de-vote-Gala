(function () {
    const galaSelect = document.getElementById("resultsGalaSelect");
    const categorySelect = document.getElementById("resultsCategorieSelect");
    const bonusValueEl = document.getElementById("resultsFavoriteBonusValue");
    const summaryTitle = document.getElementById("resultsSummaryTitle");
    const summarySubtitle = document.getElementById("resultsSummarySubtitle");
    const summaryCardsContainer = document.getElementById("resultsSummaryCards");
    const loadingSpinner = document.getElementById("resultsLoadingSpinner");
    const errorState = document.getElementById("resultsErrorState");
    const emptyState = document.getElementById("resultsEmptyState");
    const categoriesContainer = document.getElementById("resultsCategoriesContainer");
    const judgesContainer = document.getElementById("resultsJudgesContainer");
    const judgesBadge = document.getElementById("resultsJudgeProgressBadge");

    if (!galaSelect || !categorySelect) {
        return;
    }

    const state = {
        loading: false,
        selectedGalaId: null,
        selectedCategoryId: null,
        suppressEvents: false,
    };

    function formatPercent(value) {
        if (typeof value !== "number" || Number.isNaN(value)) {
            return "0%";
        }
        return (Math.round(value * 10) / 10) + "%";
    }

    function formatScore(value) {
        if (value === null || value === undefined || Number.isNaN(value)) {
            return "—";
        }
        return (Math.round(value * 100) / 100).toFixed(2);
    }

    function formatStatusBadge(status) {
        const mapping = {
            complet: "text-bg-success",
            en_cours: "text-bg-warning",
            en_attente: "text-bg-secondary",
            non_disponible: "text-bg-secondary",
        };
        const labels = {
            complet: "Complet",
            en_cours: "En cours",
            en_attente: "En attente",
            non_disponible: "N/A",
        };
        const css = mapping[status] || "text-bg-secondary";
        const label = labels[status] || status || "N/A";
        return `<span class="badge ${css}">${label}</span>`;
    }

    function clearContainers() {
        summaryCardsContainer.innerHTML = "";
        categoriesContainer.innerHTML = "";
        judgesContainer.innerHTML = "";
    }

    function setLoading(isLoading) {
        state.loading = isLoading;
        if (isLoading) {
            errorState.classList.add("d-none");
            emptyState.classList.add("d-none");
            loadingSpinner.classList.remove("d-none");
            clearContainers();
        } else {
            loadingSpinner.classList.add("d-none");
        }
    }

    function populateFilters(filters) {
        if (!filters) {
            return;
        }
        state.suppressEvents = true;

        const selected = filters.selected || {};
        const selectedGalaId = selected.gala_id || null;
        const selectedCategoryId = selected.categorie_id || null;

        const galas = Array.isArray(filters.galas) ? filters.galas : [];
        galaSelect.innerHTML = "";
        galas.forEach(function (gala) {
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
            galaSelect.appendChild(option);
        });
        if (selectedGalaId && galas.some(function (g) { return Number(g.id) === Number(selectedGalaId); })) {
            galaSelect.value = String(selectedGalaId);
        } else if (galas.length) {
            galaSelect.value = String(galas[0].id);
        } else {
            galaSelect.value = "";
        }

        const categories = Array.isArray(filters.categories) ? filters.categories : [];
        categorySelect.innerHTML = "";
        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Toutes les catégories";
        categorySelect.appendChild(defaultOption);

        categories.forEach(function (category) {
            const option = document.createElement("option");
            option.value = String(category.id);
            option.textContent = category.nom || ("Catégorie " + category.id);
            categorySelect.appendChild(option);
        });

        if (selectedCategoryId && categories.some(function (c) { return Number(c.id) === Number(selectedCategoryId); })) {
            categorySelect.value = String(selectedCategoryId);
        } else {
            categorySelect.value = "";
        }

        categorySelect.disabled = categories.length === 0;

        state.selectedGalaId = galaSelect.value ? Number(galaSelect.value) : null;
        state.selectedCategoryId = categorySelect.value ? Number(categorySelect.value) : null;

        state.suppressEvents = false;
    }

    function renderSummary(meta) {
        summaryCardsContainer.innerHTML = "";
        if (!meta) {
            summarySubtitle.textContent = "Aucun jeu de données disponible.";
            return;
        }

        const cardsData = [
            {
                label: "Progression globale",
                value: formatPercent(meta.overall_completion_percent || 0),
                detail: `${meta.overall_recorded || 0} / ${meta.overall_expected || 0} notes`,
            },
            {
                label: "Juges ayant soumis",
                value: `${meta.judges_submitted || 0} / ${meta.judges_total || 0}`,
                detail: "Juges ayant finalisé leur évaluation",
            },
            {
                label: "Participants suivis",
                value: String(meta.participants_total || 0),
                detail: `${meta.categories_total || 0} catégorie(s)`,
            },
        ];

        cardsData.forEach(function (card) {
            const col = document.createElement("div");
            col.className = "col-sm-6 col-xl-4";
            col.innerHTML = [
                '<div class="card border shadow-sm h-100">',
                '  <div class="card-body">',
                '    <p class="text-muted small mb-1">' + card.label + '</p>',
                '    <h3 class="h4 mb-1">' + card.value + '</h3>',
                '    <p class="text-muted small mb-0">' + card.detail + '</p>',
                '  </div>',
                '</div>',
            ].join("");
            summaryCardsContainer.appendChild(col);
        });

        summaryTitle.textContent = "Synthèse";
        const galaMeta = meta.gala || {};
        const subtitleParts = [];
        if (galaMeta.nom) {
            subtitleParts.push(galaMeta.nom);
        }
        if (galaMeta.annee) {
            subtitleParts.push("Édition " + galaMeta.annee);
        }
        summarySubtitle.textContent = subtitleParts.join(" • ") || "Résumé des résultats";

        if (bonusValueEl && typeof meta.favorite_bonus === "number") {
            bonusValueEl.textContent = "+" + formatScore(meta.favorite_bonus);
        }
    }

    function renderCategories(categories) {
        categoriesContainer.innerHTML = "";
        if (!Array.isArray(categories) || !categories.length) {
            emptyState.classList.remove("d-none");
            return;
        }
        emptyState.classList.add("d-none");

        categories.forEach(function (category) {
            const card = document.createElement("div");
            card.className = "card shadow-sm";
            const progress = category.progress || {};
            const participants = Array.isArray(category.participants) ? category.participants : [];
            card.innerHTML = [
                '<div class="card-body">',
                '  <div class="d-flex flex-column flex-lg-row justify-content-between align-items-start gap-3 mb-3">',
                '    <div>',
                '      <h3 class="h6 mb-1">' + (category.nom || "Catégorie") + '</h3>',
                '      <p class="text-muted small mb-0">Questions : ' + (category.question_count || 0) + ' • Participants : ' + (category.participant_count || 0) + ' • Juges : ' + (category.judge_count || 0) + '</p>',
                '    </div>',
                '    <div class="text-end">',
                '      ' + formatStatusBadge(category.status || "en_attente"),
                '      <div class="text-muted small">Progression ' + formatPercent(progress.percent || 0) + '</div>',
                '    </div>',
                '  </div>',
                '  <div class="table-responsive">',
                '    <table class="table table-sm align-middle">',
                '      <thead class="table-light">',
                '        <tr>',
                '          <th scope="col">Rang</th>',
                '          <th scope="col">Participant</th>',
                '          <th scope="col">Score</th>',
                '          <th scope="col">Bonus</th>',
                '          <th scope="col">Score final</th>',
                '          <th scope="col">Notes</th>',
                '          <th scope="col">Statut</th>',
                '          <th scope="col">Favoris</th>',
                '        </tr>',
                '      </thead>',
                '      <tbody id="resultsCategoryBody-' + category.id + '"></tbody>',
                '    </table>',
                '  </div>',
                '</div>',
            ].join("");

            const tbody = card.querySelector("tbody");
            participants.forEach(function (participant) {
                const favorites = Array.isArray(participant.favorites) ? participant.favorites : [];
                const notes = participant.notes || {};
                const judgesAnswered = participant.judges_answered || 0;
                const row = document.createElement("tr");
                row.innerHTML = [
                    '<td>' + (participant.rank || "—") + '</td>',
                    '<td>',
                    '  <div class="fw-semibold">' + (participant.compagnie && participant.compagnie.nom ? participant.compagnie.nom : "Participant #" + participant.id) + '</div>',
                    '  <div class="text-muted small">' + [participant.compagnie && participant.compagnie.ville || "", participant.compagnie && participant.compagnie.secteur || ""].filter(Boolean).join(" • ") + '</div>',
                    '</td>',
                    '<td>' + formatScore(participant.score_base) + '</td>',
                    '<td>' + formatScore(participant.score_bonus) + '</td>',
                    '<td><span class="fw-semibold">' + formatScore(participant.score_final) + '</span></td>',
                    '<td>' + (notes.recorded || 0) + ' / ' + (notes.expected || 0) + '<div class="text-muted small">' + formatPercent(notes.progress_percent || 0) + '</div></td>',
                    '<td>' + formatStatusBadge(participant.status || "en_attente") + '</td>',
                    '<td>' + (favorites.length ? favorites.join(", ") : "—") + '<div class="text-muted small">' + judgesAnswered + ' juge(s)</div></td>',
                ].join("");
                tbody.appendChild(row);
            });

            if (!participants.length) {
                const row = document.createElement("tr");
                row.innerHTML = '<td colspan="8" class="text-muted text-center small">Aucun participant pour cette catégorie.</td>';
                tbody.appendChild(row);
            }

            categoriesContainer.appendChild(card);
        });
    }

    function renderJudges(judges, meta) {
        judgesContainer.innerHTML = "";
        const total = meta && meta.judges_total ? meta.judges_total : 0;
        const submitted = meta && meta.judges_submitted ? meta.judges_submitted : 0;
        judgesBadge.textContent = submitted + " / " + total;

        if (!Array.isArray(judges) || !judges.length) {
            const empty = document.createElement("div");
            empty.className = "text-muted small";
            empty.textContent = "Aucun juge assigné.";
            judgesContainer.appendChild(empty);
            return;
        }

        judges.forEach(function (judge) {
            const card = document.createElement("div");
            card.className = "card border-0 border-bottom rounded-0";
            const submittedInfo = judge.submitted && judge.submitted_at ? '<div class="text-muted small">Soumis</div>' : '';
            const unlockButton = judge.submitted
                ? '<button class="btn btn-outline-danger btn-sm mt-2" type="button" data-action="reset-submission" data-judge-id="' + judge.id + '">Debloquer</button>'
                : '';
            card.innerHTML = [
                '<div class="card-body py-3">',
                '  <div class="d-flex justify-content-between align-items-start gap-3">',
                '    <div>',
                '      <div class="fw-semibold">' + (judge.prenom || "") + ' ' + (judge.nom || "") + '</div>',
                '      <div class="text-muted small">' + (judge.answered_notes || 0) + ' / ' + (judge.expected_notes || 0) + ' notes • ' + formatPercent(judge.progress_percent || 0) + '</div>',
                '    </div>',
                '    <div class="text-end">',
                formatStatusBadge(judge.status || "en_attente"),
                submittedInfo,
                unlockButton,
                '    </div>',
                '  </div>',
                '</div>',
            ].join("");
            judgesContainer.appendChild(card);
        });
    }

    async function fetchResults() {
        if (state.loading) {
            return;
        }
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (state.selectedGalaId) {
                params.set("gala_id", String(state.selectedGalaId));
            }
            if (state.selectedCategoryId) {
                params.set("categorie_id", String(state.selectedCategoryId));
            }
            const query = params.toString();
            const response = await fetch("/admin/api/results" + (query ? "?" + query : ""));
            if (!response.ok) {
                throw new Error("Réponse invalide du serveur");
            }
            const payload = await response.json();
            errorState.classList.add("d-none");
            populateFilters(payload.filters || {});
            renderSummary(payload.meta || {});
            renderCategories(payload.categories || []);
            renderJudges(payload.judges || [], payload.meta || {});
            if (Array.isArray(payload.categories) && payload.categories.length > 0) {
                emptyState.classList.add("d-none");
            }
        } catch (error) {
            clearContainers();
            errorState.classList.remove("d-none");
            console.error("admin_results load error", error);
        } finally {
            setLoading(false);
        }
    }

    if (judgesContainer) {
        judgesContainer.addEventListener("click", function (event) {
            const trigger = event.target.closest("[data-action=\"reset-submission\"]");
            if (!trigger) {
                return;
            }
            event.preventDefault();
            if (!state.selectedGalaId) {
                return;
            }
            const judgeId = Number(trigger.getAttribute("data-judge-id"));
            if (!Number.isFinite(judgeId)) {
                return;
            }
            const button = trigger;
            button.disabled = true;
            fetch("/admin/api/galas/" + state.selectedGalaId + "/judges/" + judgeId + "/submission", {
                method: "DELETE",
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
                        const message = result.data && result.data.message ? result.data.message : "Impossible de reinitialiser la soumission.";
                        throw new Error(message);
                    }
                    fetchResults();
                })
                .catch(function (error) {
                    console.error("admin_results reset submission error", error);
                    if (errorState) {
                        errorState.textContent = error.message || "Impossible de reinitialiser la soumission.";
                        errorState.classList.remove("d-none");
                    }
                })
                .finally(function () {
                    button.disabled = false;
                });
        });
    }

    galaSelect.addEventListener("change", function () {
        if (state.suppressEvents) {
            return;
        }
        state.selectedGalaId = galaSelect.value ? Number(galaSelect.value) : null;
        state.selectedCategoryId = null;
        fetchResults();
    });

    categorySelect.addEventListener("change", function () {
        if (state.suppressEvents) {
            return;
        }
        state.selectedCategoryId = categorySelect.value ? Number(categorySelect.value) : null;
        fetchResults();
    });

    fetchResults();
})();
