(function () {
    const adminTable = document.getElementById("users-table-admin");
    if (!adminTable) {
        return;
    }

    const ROLE_ORDER_DEFAULT = ["admin", "juge", "membre"];
    let roleOrder = ROLE_ORDER_DEFAULT.slice();

    const tableBodies = {
        admin: document.querySelector("#users-table-admin tbody"),
        juge: document.querySelector("#users-table-juge tbody"),
        membre: document.querySelector("#users-table-membre tbody"),
    };
    const counters = {
        admin: document.getElementById("count-admin"),
        juge: document.getElementById("count-juge"),
        membre: document.getElementById("count-membre"),
    };

    const detailContainer = document.getElementById("user-detail");

    let selectedUserId = null;
    let selectedRowElement = null;

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

    function formatFullName(user) {
        const prenom = escapeHtml(user.prenom || "");
        const nom = escapeHtml(user.nom || "");
        return (prenom + " " + nom).trim() || "(Nom indisponible)";
    }

    function clearDetail(message) {
        detailContainer.innerHTML = [
            '<div class="card-body">',
            '  <h2 class="h5">Fiche utilisateur</h2>',
            '  <p class="text-muted mb-0">' + escapeHtml(message || "Selectionnez un utilisateur dans la liste pour afficher ses informations.") + '</p>',
            '</div>'
        ].join("");
    }

    function setLoadingDetail() {
        detailContainer.innerHTML = [
            '<div class="card-body">',
            '  <div class="d-flex align-items-center gap-2">',
            '    <div class="spinner-border spinner-border-sm text-primary" role="status"></div>',
            '    <span class="text-muted">Chargement de la fiche...</span>',
            '  </div>',
            '</div>'
        ].join("");
    }

    function handleRowSelection(row, userId) {
        if (selectedRowElement && selectedRowElement !== row) {
            selectedRowElement.classList.remove("table-active");
        }
        selectedUserId = userId;
        selectedRowElement = row;
        row.classList.add("table-active");
        loadUserDetail(userId);
    }

    function renderTables(usersByRole) {
        selectedRowElement = null;
        roleOrder.forEach(function (roleKey) {
            const tbody = tableBodies[roleKey];
            if (!tbody) {
                return;
            }
            const rows = usersByRole && usersByRole[roleKey] ? usersByRole[roleKey] : [];
            tbody.innerHTML = "";
            if (counters[roleKey]) {
                counters[roleKey].textContent = rows.length;
            }
            if (!rows.length) {
                const emptyRow = document.createElement("tr");
                emptyRow.className = "placeholder-row";
                emptyRow.innerHTML = '<td colspan="2" class="text-muted small">Aucun utilisateur.</td>';
                tbody.appendChild(emptyRow);
                return;
            }

            rows.forEach(function (user) {
                const tr = document.createElement("tr");
                tr.className = "user-row";
                tr.dataset.userId = String(user.id);
                tr.innerHTML = [
                    "<td>" + formatFullName(user) + "</td>",
                    '<td class="text-muted">@' + escapeHtml(user.username || "") + "</td>"
                ].join("");
                tr.addEventListener("click", function () {
                    handleRowSelection(tr, Number(user.id));
                });
                if (Number(user.id) === Number(selectedUserId)) {
                    selectedRowElement = tr;
                    tr.classList.add("table-active");
                }
                tbody.appendChild(tr);
            });
        });
    }

    async function fetchUsers(preserveSelection) {
        try {
            const response = await fetch("/admin/api/users");
            if (!response.ok) {
                throw new Error("Impossible de charger les utilisateurs");
            }
            const payload = await response.json();
            if (Array.isArray(payload.role_order) && payload.role_order.length) {
                roleOrder = payload.role_order.slice();
            }
            renderTables(payload.users_by_role || {});
            if (preserveSelection && selectedUserId !== null) {
                const matchingRow = document.querySelector('tr.user-row[data-user-id="' + selectedUserId + '"]');
                if (matchingRow) {
                    selectedRowElement = matchingRow;
                    matchingRow.classList.add("table-active");
                } else {
                    selectedUserId = null;
                }
            }
        } catch (error) {
            console.error(error);
            Object.values(tableBodies).forEach(function (tbody) {
                if (!tbody) {
                    return;
                }
                tbody.innerHTML = '<tr><td colspan="2" class="text-danger small">Erreur lors du chargement des utilisateurs.</td></tr>';
            });
        }
    }

    function renderJudgeSection(judge) {
        if (!judge || !Array.isArray(judge.galas) || !judge.galas.length) {
            return '<p class="text-muted small mb-0">Aucun gala disponible pour le moment.</p>';
        }
        return judge.galas.map(function (gala) {
            const header = escapeHtml(gala.nom || "Gala");
            const year = gala.annee ? ' <span class="text-muted">(' + escapeHtml(gala.annee) + ')</span>' : "";
            const categories = Array.isArray(gala.categories) && gala.categories.length
                ? gala.categories.map(function (cat) {
                    const inputId = 'judge-cat-' + gala.gala_id + '-' + cat.id;
                    return [
                        '<div class="form-check">',
                        '  <input class="form-check-input judge-category-checkbox" type="checkbox" value="' + cat.id + '" id="' + inputId + '"' + (cat.assigned ? " checked" : "") + '>',
                        '  <label class="form-check-label" for="' + inputId + '">' + escapeHtml(cat.nom) + '</label>',
                        '</div>'
                    ].join("");
                }).join("")
                : '<p class="text-muted small mb-0">Aucune categorie disponible.</p>';
            return [
                '<div class="mb-3" data-gala-id="' + gala.gala_id + '">',
                '  <h3 class="h6 mb-2">' + header + year + '</h3>',
                '  <div class="judge-category-list">' + categories + '</div>',
                '</div>'
            ].join("");
        }).join("");
    }

    function renderUserDetail(data) {
        const user = data.user;
        const roles = Array.isArray(data.roles) ? data.roles : [];
        const judge = data.judge || null;
        const fullName = formatFullName(user);
        const username = escapeHtml(user.username || "");
        const email = escapeHtml(user.courriel || "");
        const currentRoleId = user.role_id;
        const isJudge = (user.role || "").toLowerCase() === "juge";

        const roleOptions = roles.map(function (role) {
            const selected = Number(role.id) === Number(currentRoleId) ? " selected" : "";
            return '<option value="' + role.id + '"' + selected + '>' + escapeHtml(role.nom) + '</option>';
        }).join("");

        const judgeSection = isJudge
            ? [
                '<div class="card-body border-top">',
                '  <div class="d-flex justify-content-between align-items-center mb-3">',
                '    <h3 class="h6 mb-0">Assignations aux galas</h3>',
                '    <button class="btn btn-sm btn-primary" id="saveAssignmentsBtn">Enregistrer</button>',
                '  </div>',
                '  <div id="assignmentsFeedback" class="alert d-none" role="alert"></div>',
                '  <div class="judge-galas">' + renderJudgeSection(judge) + '</div>',
                '</div>'
            ].join("")
            : '';

        detailContainer.innerHTML = [
            '<div class="card-body">',
            '  <div class="d-flex flex-column flex-sm-row justify-content-between align-items-start align-items-sm-center gap-3">',
            '    <div>',
            '      <h2 class="h5 mb-1">' + fullName + '</h2>',
            '      <p class="text-muted small mb-1">@' + username + '</p>',
            email ? '      <p class="text-muted small mb-0">' + email + '</p>' : '',
            '    </div>',
            '  </div>',
            '  <div class="mt-4">',
            '    <label class="form-label" for="detailRoleSelect">Role</label>',
            '    <select class="form-select" id="detailRoleSelect">' + roleOptions + '</select>',
            '    <div class="form-text">La modification du role est enregistree immediatement.</div>',
            '    <div id="roleFeedback" class="alert d-none mt-3" role="alert"></div>',
            '  </div>',
            '</div>',
            judgeSection
        ].join("");

        const roleSelect = detailContainer.querySelector("#detailRoleSelect");
        const roleFeedback = detailContainer.querySelector("#roleFeedback");

        function displayRoleFeedback(kind, message) {
            if (!roleFeedback) {
                return;
            }
            roleFeedback.textContent = message;
            roleFeedback.classList.remove("d-none", "alert-success", "alert-danger");
            roleFeedback.classList.add(kind === "success" ? "alert-success" : "alert-danger");
        }

        function hideRoleFeedback() {
            if (roleFeedback) {
                roleFeedback.classList.add("d-none");
                roleFeedback.textContent = "";
            }
        }

        async function handleRoleChange() {
            const selectedValue = Number(roleSelect.value);
            if (Number.isNaN(selectedValue) || selectedValue === Number(currentRoleId)) {
                return;
            }

            roleSelect.disabled = true;
            hideRoleFeedback();
            try {
                const response = await fetch('/admin/api/users/' + user.id + '/role', {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role_id: selectedValue })
                });
                const payload = await response.json();
                if (!response.ok || payload.status !== 'ok') {
                    displayRoleFeedback('error', payload && payload.message ? payload.message : "Impossible de mettre a jour le role.");
                    roleSelect.value = String(currentRoleId);
                    return;
                }
                displayRoleFeedback('success', 'Role mis a jour avec succes.');
                await fetchUsers(true);
                await loadUserDetail(user.id, { preserveSelection: true, skipSelectionUpdate: true });
            } catch (error) {
                console.error(error);
                displayRoleFeedback('error', "Erreur reseau lors de la mise a jour du role.");
                roleSelect.value = String(currentRoleId);
            } finally {
                roleSelect.disabled = false;
            }
        }

        if (roleSelect) {
            roleSelect.addEventListener('change', handleRoleChange);
        }

        if (isJudge) {
            const saveButton = detailContainer.querySelector('#saveAssignmentsBtn');
            const feedbackEl = detailContainer.querySelector('#assignmentsFeedback');

            function showAssignmentsFeedback(kind, message) {
                if (!feedbackEl) {
                    return;
                }
                feedbackEl.textContent = message;
                feedbackEl.classList.remove('d-none', 'alert-success', 'alert-danger');
                feedbackEl.classList.add(kind === 'success' ? 'alert-success' : 'alert-danger');
            }

            function hideAssignmentsFeedback() {
                if (feedbackEl) {
                    feedbackEl.classList.add('d-none');
                    feedbackEl.textContent = '';
                }
            }

            async function handleAssignmentsSave() {
                if (!saveButton) {
                    return;
                }
                saveButton.disabled = true;
                hideAssignmentsFeedback();
                const selectedIds = Array.from(detailContainer.querySelectorAll('.judge-category-checkbox:checked')).map(function (input) {
                    return Number(input.value);
                });
                try {
                    const response = await fetch('/admin/api/users/' + user.id + '/assignments', {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ gala_categorie_ids: selectedIds })
                    });
                    const payload = await response.json();
                    if (!response.ok || payload.status !== 'ok') {
                        showAssignmentsFeedback('error', payload && payload.message ? payload.message : "Impossible d'enregistrer les assignations.");
                        return;
                    }
                    showAssignmentsFeedback('success', 'Assignations mises a jour.');
                    await loadUserDetail(user.id, { preserveSelection: true, skipSelectionUpdate: true });
                } catch (error) {
                    console.error(error);
                    showAssignmentsFeedback('error', "Erreur reseau lors de l'enregistrement.");
                } finally {
                    saveButton.disabled = false;
                }
            }

            if (saveButton) {
                saveButton.addEventListener('click', handleAssignmentsSave);
            }
        }
    }

    async function loadUserDetail(userId, options) {
        const opts = options || {};
        if (!opts.skipSelectionUpdate) {
            selectedUserId = userId;
        }
        setLoadingDetail();
        try {
            const response = await fetch('/admin/api/users/' + userId);
            if (!response.ok) {
                throw new Error('Impossible de charger la fiche');
            }
            const payload = await response.json();
            renderUserDetail(payload);
            if (!opts.skipSelectionUpdate) {
                const matchingRow = document.querySelector('tr.user-row[data-user-id="' + userId + '"]');
                if (matchingRow) {
                    if (selectedRowElement && selectedRowElement !== matchingRow) {
                        selectedRowElement.classList.remove('table-active');
                    }
                    selectedRowElement = matchingRow;
                    matchingRow.classList.add('table-active');
                }
            }
        } catch (error) {
            console.error(error);
            clearDetail("Impossible de charger la fiche utilisateur.");
        }
    }

    clearDetail();
    fetchUsers(false);
})();
