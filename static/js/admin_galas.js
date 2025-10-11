(function () {
    const table = document.getElementById("galasTable");
    if (!table) {
        return;
    }

    const tableBody = table.querySelector("tbody");
    const detailContainer = document.getElementById("galaDetail");
    const createModalEl = document.getElementById("createGalaModal");
    const addCategoryModalEl = document.getElementById("addCategoryModal");
    const addQuestionModalEl = document.getElementById("addQuestionModal");
    const openCreateButton = document.getElementById("openCreateGalaModal");
    const submitCreateButton = document.getElementById("submitCreateGala");
    const confirmAddCategoriesButton = document.getElementById("confirmAddCategories");
    const confirmAddQuestionButton = document.getElementById("confirmAddQuestion");

    const createModal = createModalEl ? new bootstrap.Modal(createModalEl) : null;
    const addCategoryModal = addCategoryModalEl ? new bootstrap.Modal(addCategoryModalEl) : null;
    const addQuestionModal = addQuestionModalEl ? new bootstrap.Modal(addQuestionModalEl) : null;

    const createForm = document.getElementById("createGalaForm");
    const createFeedback = document.getElementById("createGalaFeedback");
    const addCategoryList = document.getElementById("availableCategoriesList");
    const addCategoryFeedback = document.getElementById("addCategoryFeedback");
    const createCategoryForm = document.getElementById("createCategoryForm");
    const createCategoryFeedback = document.getElementById("createCategoryFeedback");
    const createCategoryButton = document.getElementById("submitCreateCategory");
    const addQuestionForm = document.getElementById("addQuestionForm");
    const addQuestionFeedback = document.getElementById("addQuestionFeedback");
    const questionCategoryContext = document.getElementById("questionCategoryContext");

    let galas = [];
    let selectedGalaId = null;
    let selectedCategory = null; // { id, nom }
    let categoriesCache = [];
    let editingQuestionId = null;

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

    function showAlert(container, type, message) {
        if (!container) {
            return;
        }
        container.textContent = message;
        container.classList.remove("d-none", "alert-danger", "alert-success", "alert-info");
        container.classList.add(type === "success" ? "alert-success" : type === "info" ? "alert-info" : "alert-danger");
    }

    function hideAlert(container) {
        if (!container) {
            return;
        }
        container.classList.add("d-none");
        container.textContent = "";
    }

    function updateQuestionContext() {
        if (questionCategoryContext) {
            questionCategoryContext.textContent = selectedCategory ? 'Categorie: ' + selectedCategory.nom : 'Categorie cible';
        }
        const select = document.getElementById("questionCategorySelect");
        if (select && selectedCategory) {
            select.value = String(selectedCategory.id);
        }
    }

    function renderGalaRows() {
        tableBody.innerHTML = "";
        if (!galas.length) {
            const emptyRow = document.createElement("tr");
            emptyRow.innerHTML = '<td colspan="3" class="text-muted small">Aucun gala pour le moment.</td>';
            tableBody.appendChild(emptyRow);
            return;
        }
        galas.forEach(function (gala) {
            const tr = document.createElement("tr");
            tr.className = "gala-row";
            tr.dataset.galaId = String(gala.id);
            tr.innerHTML = [
                '<td>' + escapeHtml(gala.nom || "Gala") + '</td>',
                '<td class="text-muted">' + (gala.annee || '') + '</td>',
                '<td class="text-muted">' + (gala.categories_count || 0) + '</td>'
            ].join("");
            tr.addEventListener("click", function () {
                handleSelectGala(gala.id, tr);
            });
            if (Number(gala.id) === Number(selectedGalaId)) {
                tr.classList.add("table-active");
            }
            tableBody.appendChild(tr);
        });
    }

    function fetchGalas(options) {
        const opts = options || {};
        fetch("/admin/api/galas")
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Erreur lors du chargement des galas");
                }
                return response.json();
            })
            .then(function (payload) {
                galas = Array.isArray(payload.galas) ? payload.galas : [];
                renderGalaRows();
                if (opts.retainSelection && selectedGalaId) {
                    const row = tableBody.querySelector('tr[data-gala-id="' + selectedGalaId + '"]');
                    if (row) {
                        row.classList.add("table-active");
                    }
                }
            })
            .catch(function () {
                tableBody.innerHTML = '<tr><td colspan="3" class="text-danger small">Impossible de charger les galas.</td></tr>';
            });
    }

    function setDetailLoading() {
        detailContainer.innerHTML = [
            '<div class="card-body">',
            '  <div class="d-flex align-items-center gap-2">',
            '    <div class="spinner-border spinner-border-sm text-primary" role="status"></div>',
            '    <span class="text-muted">Chargement du gala...</span>',
            '  </div>',
            '</div>'
        ].join("");
    }

    function handleSelectGala(galaId, rowElement) {
        if (rowElement) {
            table.querySelectorAll("tr.table-active").forEach(function (row) {
                row.classList.remove("table-active");
            });
            rowElement.classList.add("table-active");
        }
        selectedGalaId = galaId;
        selectedCategory = null;
        setDetailLoading();
        loadGalaDetail(galaId);
    }

    function buildInfoTab(gala) {
        return [
            '<div class="mt-3">',
            '  <div id="galaInfoFeedback" class="alert d-none" role="alert"></div>',
            '  <form id="galaInfoForm" class="row g-3">',
            '    <div class="col-md-6">',
            '      <label class="form-label" for="detailNom">Nom</label>',
            '      <input class="form-control" id="detailNom" name="nom" value="' + escapeHtml(gala.nom || "") + '" required>',
            '    </div>',
            '    <div class="col-md-3">',
            '      <label class="form-label" for="detailAnnee">Annee</label>',
            '      <input class="form-control" id="detailAnnee" name="annee" type="number" min="1900" value="' + (gala.annee || "") + '">',
            '    </div>',
            '    <div class="col-md-3">',
            '      <label class="form-label" for="detailDate">Date</label>',
            '      <input class="form-control" id="detailDate" name="date_gala" value="' + escapeHtml(gala.date_gala || "") + '">',
            '    </div>',
            '    <div class="col-12">',
            '      <label class="form-label" for="detailLieu">Lieu</label>',
            '      <input class="form-control" id="detailLieu" name="lieu" value="' + escapeHtml(gala.lieu || "") + '">',
            '    </div>',
            '  </form>',
            '  <div class="mt-3 d-flex justify-content-end">',
            '    <button class="btn btn-primary" id="saveGalaInfo">Enregistrer</button>',
            '  </div>',
            '</div>'
        ].join("");
    }

    function buildCategoriesTab(detail) {
        const categories = Array.isArray(detail.categories) ? detail.categories : [];
        const rows = categories.length
            ? categories.map(function (cat) {
                  return [
                      '<div class="card border mb-3" data-gala-categorie-id="' + cat.id + '">',
                      '  <div class="card-body d-flex flex-wrap justify-content-between align-items-center gap-2">',
                      '    <div>',
                      '      <h3 class="h6 mb-1">' + escapeHtml(cat.nom) + '</h3>',
                      '      <p class="text-muted small mb-0" data-role="question-count">Questions: ' + (cat.questions_count || 0) + '</p>',
                      '    </div>',
                      '    <div class="d-flex gap-2">',
                      '      <button class="btn btn-sm btn-outline-primary" data-action="view-questions" data-gala-categorie-id="' + cat.id + '" data-categorie-nom="' + escapeHtml(cat.nom) + '">Questions</button>',
                      '      <button class="btn btn-sm btn-outline-danger" data-action="remove-categorie" data-gala-categorie-id="' + cat.id + '">Retirer</button>',
                      '    </div>',
                      '  </div>',
                      '</div>'
                  ].join("");
              }).join("")
            : '<p class="text-muted small mb-0">Aucune categorie associee.</p>';
        return [
            '<div class="mt-3">',
            '  <div class="d-flex justify-content-between align-items-center mb-3">',
            '    <h3 class="h6 mb-0">Categories associees</h3>',
            '    <button class="btn btn-sm btn-primary" id="openAddCategory">Associer des categories</button>',
            '  </div>',
            '  <div id="galaCategoriesList">' + rows + '</div>',
            '</div>'
        ].join("");
    }


    
    function buildQuestionsTab(categories) {
        const hasCategories = Array.isArray(categories) && categories.length > 0;
        const selectOptions = hasCategories
            ? categories.map(function (cat) {
                  const selected = selectedCategory && Number(selectedCategory.id) === Number(cat.id) ? ' selected' : '';
                  return '<option value="' + cat.id + '"' + selected + '>' + escapeHtml(cat.nom) + '</option>';
              }).join('')
            : '';
        const selector = hasCategories
            ? [
                  '<div class="d-flex align-items-center gap-2 mb-3">',
                  '  <label class="form-label small mb-0" for="questionCategorySelect">Categorie</label>',
                  '  <select class="form-select form-select-sm" id="questionCategorySelect">' + selectOptions + '</select>',
                  '</div>'
              ].join('')
            : '';
        const heading = selectedCategory ? escapeHtml(selectedCategory.nom) : 'Selectionnez une categorie pour afficher les questions.';
        const hasCategory = Boolean(selectedCategory);
        return [
            '<div class="mt-3">',
            '  <div class="d-flex justify-content-between align-items-center mb-3">',
            '    <h3 class="h6 mb-0">' + heading + '</h3>',
            hasCategory ? '    <button class="btn btn-sm btn-primary" id="openAddQuestion">Ajouter une question</button>' : '',
            '  </div>',
            selector,
            '  <div id="questionsFeedback" class="alert d-none" role="alert"></div>',
            '  <div id="galaQuestionsList">' + (hasCategory ? '<div class="text-muted small">Chargement...</div>' : '<p class="text-muted small mb-0">Aucune categorie selectionnee.</p>') + '</div>',
            '</div>'
        ].join('');
    }

    function renderDetail(detail) {
        const gala = detail.gala;
        const categories = Array.isArray(detail.categories) ? detail.categories : [];
        categoriesCache = categories;
        if (selectedCategory && !categories.some(function (cat) { return Number(cat.id) === Number(selectedCategory.id); })) {
            selectedCategory = null;
        }
        if (selectedCategory) {
            const matchedCategory = categories.find(function (cat) { return Number(cat.id) === Number(selectedCategory.id); });
            if (matchedCategory) {
                selectedCategory = { id: matchedCategory.id, nom: matchedCategory.nom };
            }
        }
        if (!selectedCategory && categories.length) {
            selectedCategory = {
                id: categories[0].id,
                nom: categories[0].nom,
            };
        }

        detailContainer.innerHTML = [
            '<div class="card-body">',
            '  <div class="d-flex flex-wrap justify-content-between align-items-start gap-3">',
            '    <div>',
            '      <h2 class="h4 mb-1">' + escapeHtml(gala.nom || "Gala") + '</h2>',
            '      <p class="text-muted small mb-0">Annee ' + (gala.annee || '') + ' - ' + escapeHtml(gala.lieu || 'Lieu a definir') + '</p>',
            '    </div>',
            '  </div>',
            '  <ul class="nav nav-tabs mt-4" id="galaDetailTabs" role="tablist">',
            '    <li class="nav-item" role="presentation">',
            '      <button class="nav-link active" id="info-tab" data-bs-toggle="tab" data-bs-target="#tabInfo" type="button" role="tab" aria-controls="tabInfo" aria-selected="true">Informations</button>',
            '    </li>',
            '    <li class="nav-item" role="presentation">',
            '      <button class="nav-link" id="categories-tab" data-bs-toggle="tab" data-bs-target="#tabCategories" type="button" role="tab" aria-controls="tabCategories" aria-selected="false">Categories</button>',
            '    </li>',
            '    <li class="nav-item" role="presentation">',
            '      <button class="nav-link" id="questions-tab" data-bs-toggle="tab" data-bs-target="#tabQuestions" type="button" role="tab" aria-controls="tabQuestions" aria-selected="false">Questions</button>',
            '    </li>',
            '  </ul>',
            '  <div class="tab-content pt-3">',
            '    <div class="tab-pane fade show active" id="tabInfo" role="tabpanel" aria-labelledby="info-tab">' + buildInfoTab(gala) + '</div>',
            '    <div class="tab-pane fade" id="tabCategories" role="tabpanel" aria-labelledby="categories-tab">' + buildCategoriesTab(detail) + '</div>',
            '    <div class="tab-pane fade" id="tabQuestions" role="tabpanel" aria-labelledby="questions-tab">' + buildQuestionsTab(categories) + '</div>',
            '  </div>',
            '</div>'
        ].join("");

        bindInfoForm(gala.id);
        bindCategoryActions(detail);
        bindQuestionActions(categories);
        if (selectedCategory) {
            loadQuestions(selectedCategory.id);
        }
    }


    function bindInfoForm(galaId) {
        const saveButton = document.getElementById("saveGalaInfo");
        const form = document.getElementById("galaInfoForm");
        const feedback = document.getElementById("galaInfoFeedback");
        if (!saveButton || !form) {
            return;
        }
        saveButton.addEventListener("click", function () {
            const formData = new FormData(form);
            const payload = {
                nom: formData.get("nom"),
                annee: formData.get("annee"),
                lieu: formData.get("lieu"),
                date_gala: formData.get("date_gala"),
            };
            saveButton.disabled = true;
            hideAlert(feedback);
            fetch('/admin/api/galas/' + galaId, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function (result) {
                    if (!result.ok || result.data.status !== 'ok') {
                        throw new Error(result.data && result.data.message ? result.data.message : 'Echec de la mise a jour');
                    }
                    showAlert(feedback, 'success', 'Informations mises a jour.');
                    fetchGalas({ retainSelection: true });
                })
                .catch(function (error) {
                    showAlert(feedback, 'error', error.message || 'Impossible de mettre a jour le gala.');
                })
                .finally(function () {
                    saveButton.disabled = false;
                });
        });
    }

    function bindCategoryActions(detail) {
        const button = document.getElementById("openAddCategory");
        if (button) {
            button.addEventListener("click", function () {
                renderAvailableCategories(detail.available_categories || []);
                hideAlert(addCategoryFeedback);
                if (createCategoryForm) {
                    createCategoryForm.reset();
                }
                hideAlert(createCategoryFeedback);
                if (addCategoryModal) {
                    addCategoryModal.show();
                }
            });
        }

        const list = document.getElementById("galaCategoriesList");
        if (list) {
            list.querySelectorAll('[data-action="remove-categorie"]').forEach(function (btn) {
                btn.addEventListener("click", function () {
                    const galaCategorieId = Number(btn.dataset.galaCategorieId);
                    removeCategory(galaCategorieId);
                });
            });
            list.querySelectorAll('[data-action="view-questions"]').forEach(function (btn) {
                btn.addEventListener("click", function () {
                    const galaCategorieId = Number(btn.dataset.galaCategorieId);
                    const categorieNom = btn.dataset.categorieNom || 'Categorie';
                    selectedCategory = { id: galaCategorieId, nom: categorieNom };
                    switchToQuestionsTab();
                    updateQuestionContext();
                    const select = document.getElementById("questionCategorySelect");
                    if (select) {
                        select.value = String(galaCategorieId);
                    }
                    loadQuestions(galaCategorieId);
                });
            });
        }
    }


    function bindQuestionActions(categories) {
        const select = document.getElementById("questionCategorySelect");
        if (select) {
            select.addEventListener("change", function () {
                const nextId = Number(this.value);
                const found = Array.isArray(categories) ? categories.find(function (cat) { return Number(cat.id) === nextId; }) : null;
                if (!found) {
                    return;
                }
                selectedCategory = { id: found.id, nom: found.nom };
                updateQuestionContext();
                loadQuestions(found.id);
            });
        }

        const addButton = document.getElementById("openAddQuestion");
        if (addButton) {
            addButton.addEventListener("click", function () {
                if (!selectedCategory) {
                    return;
                }
                editingQuestionId = null;
                if (questionCategoryContext) {
                    questionCategoryContext.textContent = 'Categorie: ' + selectedCategory.nom;
                }
                hideAlert(addQuestionFeedback);
                if (addQuestionForm) {
                    addQuestionForm.reset();
                    const weightInput = addQuestionForm.querySelector('#questionPonderation');
                    if (weightInput) {
                        weightInput.value = '1.0';
                    }
                }
                const modalTitle = addQuestionModalEl ? addQuestionModalEl.querySelector('.modal-title') : null;
                if (modalTitle) {
                    modalTitle.textContent = 'Nouvelle question';
                }
                if (addQuestionModalEl) {
        addQuestionModalEl.addEventListener('hidden.bs.modal', function () {
            editingQuestionId = null;
            if (confirmAddQuestionButton) {
                confirmAddQuestionButton.textContent = 'Ajouter';
            }
            const modalTitle = addQuestionModalEl.querySelector('.modal-title');
            if (modalTitle) {
                modalTitle.textContent = 'Nouvelle question';
            }
            if (addQuestionForm) {
                addQuestionForm.reset();
                const weightField = addQuestionForm.querySelector('#questionPonderation');
                if (weightField) {
                    weightField.value = '1.0';
                }
            }
            hideAlert(addQuestionFeedback);
            updateQuestionContext();
        });
    }

    if (confirmAddQuestionButton) {
                    confirmAddQuestionButton.textContent = 'Ajouter';
                }
                updateQuestionContext();
                if (addQuestionModal) {
                    addQuestionModal.show();
                }
            });
        }

        updateQuestionContext();
    }

    function switchToQuestionsTab() {
        const questionsTabButton = document.getElementById("questions-tab");
        if (questionsTabButton) {
            const tab = new bootstrap.Tab(questionsTabButton);
            tab.show();
            updateQuestionContext();
        }
        const questionsList = document.getElementById("galaQuestionsList");
        if (questionsList) {
            questionsList.innerHTML = '<div class="text-muted small">Chargement...</div>';
        }
    }

    function renderAvailableCategories(categories) {
        if (!addCategoryList) {
            return;
        }
        addCategoryList.innerHTML = "";
        if (!categories.length) {
            addCategoryList.innerHTML = '<div class="col-12 text-muted small">Toutes les categories sont deja associees.</div>';
            return;
        }
        categories.forEach(function (cat) {
            const col = document.createElement("div");
            col.className = "col-md-6";
            col.innerHTML = [
                '<div class="form-check border rounded p-3 h-100">',
                '  <input class="form-check-input" type="checkbox" value="' + cat.id + '" id="category-' + cat.id + '">',
                '  <label class="form-check-label" for="category-' + cat.id + '">',
                '    <span class="fw-semibold">' + escapeHtml(cat.nom) + '</span>',
                '  </label>',
                '</div>'
            ].join("");
            addCategoryList.appendChild(col);
        });
    }

    function loadGalaDetail(galaId) {
        fetch('/admin/api/galas/' + galaId)
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Impossible de charger le gala.');
                }
                return response.json();
            })
            .then(function (detail) {
                renderDetail(detail);
            })
            .catch(function (error) {
                detailContainer.innerHTML = '<div class="card-body"><p class="text-danger mb-0">' + escapeHtml(error.message || 'Erreur lors du chargement du gala.') + '</p></div>';
            });
    }

    function removeCategory(galaCategorieId) {
        if (!selectedGalaId) {
            return;
        }
        fetch('/admin/api/galas/' + selectedGalaId + '/categories/' + galaCategorieId, {
            method: 'DELETE'
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Impossible de retirer la categorie.');
                }
                return response.json();
            })
            .then(function (detail) {
                renderDetail(detail);
                fetchGalas({ retainSelection: true });
            })
            .catch(function (error) {
                showAlert(addCategoryFeedback, 'error', error.message || 'Erreur lors du retrait.');
            });
    }

    function loadQuestions(galaCategorieId) {
        if (!selectedGalaId) {
            return;
        }
        updateQuestionContext();
        fetch('/admin/api/galas/' + selectedGalaId + '/categories/' + galaCategorieId + '/questions')
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Impossible de charger les questions.');
                }
                return response.json();
            })
            .then(function (payload) {
                const list = document.getElementById("galaQuestionsList");
                if (!list) {
                    return;
                }
                const questions = Array.isArray(payload.questions) ? payload.questions : [];
                if (!questions.length) {
                    list.innerHTML = '<p class="text-muted small mb-0">Aucune question pour cette categorie.</p>';
                    return;
                }
                const items = questions.map(function (question) {
                    const rawText = question.texte || '';
                    const displayText = escapeHtml(rawText);
                    const dataText = encodeURIComponent(rawText);
                    const ponderationValue = question.ponderation != null ? question.ponderation : 0;
                    return [
                        '<div class="border rounded p-3 mb-2">',
                        '  <div class="d-flex justify-content-between align-items-start gap-3">',
                        '    <div>',
                        '      <p class="mb-1">' + displayText + '</p>',
                        '      <p class="text-muted small mb-0">Ponderation: ' + ponderationValue + '</p>',
                        '    </div>',
                        '    <div class="d-flex flex-column align-items-stretch gap-2">',
                        '      <button class="btn btn-sm btn-outline-secondary" data-action="edit-question" data-question-id="' + question.id + '" data-question-texte="' + dataText + '" data-question-ponderation="' + ponderationValue + '">Modifier</button>',
                        '      <button class="btn btn-sm btn-outline-danger" data-action="delete-question" data-question-id="' + question.id + '">Supprimer</button>',
                        '    </div>',
                        '  </div>',
                        '</div>'
                    ].join("");
                }).join("");
                list.innerHTML = items;
                list.querySelectorAll('[data-action=\"edit-question\"]').forEach(function (button) {
                    button.addEventListener("click", function () {
                        const questionId = Number(button.dataset.questionId);
                        if (!selectedCategory || Number.isNaN(questionId)) {
                            return;
                        }
                        editingQuestionId = questionId;
                        const modalTitle = addQuestionModalEl ? addQuestionModalEl.querySelector('.modal-title') : null;
                        if (modalTitle) {
                            modalTitle.textContent = 'Modifier la question';
                        }
                        if (confirmAddQuestionButton) {
                            confirmAddQuestionButton.textContent = 'Enregistrer';
                        }
                        if (addQuestionForm) {
                            const texteField = addQuestionForm.querySelector('#questionTexte');
                            const weightField = addQuestionForm.querySelector('#questionPonderation');
                            if (texteField) {
                                texteField.value = decodeURIComponent(button.dataset.questionTexte || '');
                            }
                            if (weightField) {
                                weightField.value = button.dataset.questionPonderation || '1.0';
                            }
                        }
                        updateQuestionContext();
                        hideAlert(addQuestionFeedback);
                        if (addQuestionModal) {
                            addQuestionModal.show();
                        }
                    });
                });
                list.querySelectorAll('[data-action=\"delete-question\"]').forEach(function (button) {
                    button.addEventListener("click", function () {
                        const questionId = Number(button.dataset.questionId);
                        if (!selectedCategory || Number.isNaN(questionId)) {
                            return;
                        }
                        deleteQuestion(questionId, button);
                    });
                });
            })
            .catch(function (error) {
                const list = document.getElementById("galaQuestionsList");
                if (list) {
                    list.innerHTML = '<p class="text-danger small mb-0">' + escapeHtml(error.message || 'Erreur lors du chargement des questions.') + '</p>';
                }
            });
    }


    function deleteQuestion(questionId, triggerButton) {
        if (!selectedGalaId || !selectedCategory) {
            return;
        }
        if (typeof window !== 'undefined' && !window.confirm('Voulez-vous supprimer cette question ?')) {
            return;
        }
        const feedback = document.getElementById("questionsFeedback");
        hideAlert(feedback);
        if (triggerButton) {
            triggerButton.disabled = true;
        }
        fetch('/admin/api/galas/' + selectedGalaId + '/categories/' + selectedCategory.id + '/questions/' + questionId, {
            method: 'DELETE'
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data && result.data.message ? result.data.message : 'Impossible de supprimer la question.');
                }
                if (editingQuestionId === questionId) {
                    editingQuestionId = null;
                    if (confirmAddQuestionButton) {
                        confirmAddQuestionButton.textContent = 'Ajouter';
                    }
                    if (addQuestionForm) {
                        addQuestionForm.reset();
                        const weightField = addQuestionForm.querySelector('#questionPonderation');
                        if (weightField) {
                            weightField.value = '1.0';
                        }
                    }
                }
                showAlert(feedback, 'success', 'Question supprimee.');
                loadQuestions(selectedCategory.id);
                fetchGalas({ retainSelection: true });
                const countElement = document.querySelector('[data-gala-categorie-id="' + selectedCategory.id + '"] [data-role="question-count"]');
                if (countElement) {
                    countElement.textContent = 'Questions: ' + (Array.isArray(result.data.questions) ? result.data.questions.length : 0);
                }
            })
            .catch(function (error) {
                showAlert(feedback, 'error', error.message || 'Impossible de supprimer la question.');
            })
            .finally(function () {
                if (triggerButton) {
                    triggerButton.disabled = false;
                }
            });
    }

    function handleCreateGala() {
        if (!createForm) {
            return;
        }
        const formData = new FormData(createForm);
        const payload = {
            nom: formData.get("nom"),
            annee: formData.get("annee"),
            lieu: formData.get("lieu"),
            date_gala: formData.get("date_gala"),
        };
        submitCreateButton.disabled = true;
        hideAlert(createFeedback);
        fetch('/admin/api/galas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok || result.data.status !== 'ok') {
                    throw new Error(result.data && result.data.message ? result.data.message : 'Creation impossible');
                }
                if (createModal) {
                    createModal.hide();
                }
                createForm.reset();
                fetchGalas();
            })
            .catch(function (error) {
                showAlert(createFeedback, 'error', error.message || 'Impossible de creer le gala.');
            })
            .finally(function () {
                submitCreateButton.disabled = false;
            });
    }

    function handleCreateCategory() {
        if (!selectedGalaId || !createCategoryForm) {
            return;
        }
        const formData = new FormData(createCategoryForm);
        const payload = {
            nom: formData.get("nom"),
            description: formData.get("description"),
        };
        if (!payload.nom || !String(payload.nom).trim()) {
            showAlert(createCategoryFeedback, 'error', 'Le nom de la categorie est requis.');
            return;
        }
        createCategoryButton.disabled = true;
        hideAlert(createCategoryFeedback);
        fetch('/admin/api/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nom: payload.nom,
                description: payload.description,
            })
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok || result.data.status !== 'ok') {
                    throw new Error(result.data && result.data.message ? result.data.message : 'Impossible de creer la categorie.');
                }
                const categoryId = result.data.category.id;
                if (createCategoryForm) {
                    createCategoryForm.reset();
                }
                return fetch('/admin/api/galas/' + selectedGalaId + '/categories', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ categorie_ids: [categoryId] })
                });
            })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (data) {
                        throw new Error(data && data.message ? data.message : "Echec de l'ajout");
                    });
                }
                return response.json();
            })
            .then(function (detail) {
                if (addCategoryModal) {
                    addCategoryModal.hide();
                }
                renderDetail(detail);
                fetchGalas({ retainSelection: true });
            })
            .catch(function (error) {
                showAlert(createCategoryFeedback, 'error', error.message || 'Impossible de creer la categorie.');
            })
            .finally(function () {
                createCategoryButton.disabled = false;
            });
    }

    function handleAddCategories() {
        if (!selectedGalaId) {
            return;
        }
        if (!addCategoryList) {
            return;
        }
        const checked = Array.from(addCategoryList.querySelectorAll('input[type="checkbox"]:checked')).map(function (input) {
            return Number(input.value);
        });
        if (!checked.length) {
            showAlert(addCategoryFeedback, 'error', 'Selectionnez au moins une categorie.');
            return;
        }
        confirmAddCategoriesButton.disabled = true;
        hideAlert(addCategoryFeedback);
        fetch('/admin/api/galas/' + selectedGalaId + '/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ categorie_ids: checked })
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (data) {
                        throw new Error(data && data.message ? data.message : "Echec de l'ajout");
                    });
                }
                return response.json();
            })
            .then(function (detail) {
                if (addCategoryModal) {
                    addCategoryModal.hide();
                }
                fetchGalas({ retainSelection: true });
                renderDetail(detail);
            })
            .catch(function (error) {
                showAlert(addCategoryFeedback, 'error', error.message || "Impossible d'associer les categories.");
            })
            .finally(function () {
                confirmAddCategoriesButton.disabled = false;
            });
    }


    function handleAddQuestion() {
        if (!selectedGalaId || !selectedCategory || !addQuestionForm) {
            return;
        }
        const formData = new FormData(addQuestionForm);
        const payload = {
            texte: formData.get("texte"),
            ponderation: formData.get("ponderation"),
        };
        const isEdit = editingQuestionId !== null;
        const endpoint = '/admin/api/galas/' + selectedGalaId + '/categories/' + selectedCategory.id + '/questions' + (isEdit ? '/' + editingQuestionId : '');
        const method = isEdit ? 'PATCH' : 'POST';

        confirmAddQuestionButton.disabled = true;
        hideAlert(addQuestionFeedback);

        fetch(endpoint, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data && result.data.message ? result.data.message : (isEdit ? "Impossible de modifier la question." : "Impossible d'ajouter la question."));
                }
                if (addQuestionModal) {
                    addQuestionModal.hide();
                }
                if (addQuestionForm) {
                    addQuestionForm.reset();
                    const weightField = addQuestionForm.querySelector('#questionPonderation');
                    if (weightField) {
                        weightField.value = '1.0';
                    }
                }
                editingQuestionId = null;
                if (confirmAddQuestionButton) {
                    confirmAddQuestionButton.textContent = 'Ajouter';
                }
                const modalTitle = addQuestionModalEl ? addQuestionModalEl.querySelector('.modal-title') : null;
                if (modalTitle) {
                    modalTitle.textContent = 'Nouvelle question';
                }
                if (selectedGalaId) {
                    loadGalaDetail(selectedGalaId);
                }
                fetchGalas({ retainSelection: true });
            })
            .catch(function (error) {
                showAlert(addQuestionFeedback, 'error', error.message || (isEdit ? 'Impossible de modifier la question.' : "Impossible d'ajouter la question."));
            })
            .finally(function () {
                confirmAddQuestionButton.disabled = false;
            });
    }


    if (openCreateButton && createModal) {
        openCreateButton.addEventListener("click", function () {
            createForm.reset();
            hideAlert(createFeedback);
            createModal.show();
        });
    }

    if (submitCreateButton) {
        submitCreateButton.addEventListener("click", handleCreateGala);
    }

    if (createCategoryButton) {
        createCategoryButton.addEventListener("click", handleCreateCategory);
    }

    if (confirmAddCategoriesButton) {
        confirmAddCategoriesButton.addEventListener("click", handleAddCategories);
    }

    if (confirmAddQuestionButton) {
        confirmAddQuestionButton.addEventListener("click", handleAddQuestion);
    }

    fetchGalas();
})();
