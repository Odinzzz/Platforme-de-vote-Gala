(function () {
    const authArea = document.getElementById("auth-area");
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");
    const loginModalEl = document.getElementById("loginModal");
    const registerModalEl = document.getElementById("registerModal");
    const loginFeedback = document.getElementById("loginFeedback");
    const registerFeedback = document.getElementById("registerFeedback");
    let currentUser = window.__currentUser__ || null;

    function getAdminMenu() {
        return document.getElementById("admin-menu");
    }

    function updateCurrentUser(user) {
        currentUser = user;
        window.__currentUser__ = user;
    }

    function hideModal(modalEl) {
        if (!modalEl) {
            return;
        }
        let modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (!modalInstance) {
            modalInstance = new bootstrap.Modal(modalEl);
        }
        modalInstance.hide();
    }

    function renderAdminMenu(user) {
        const menu = getAdminMenu();
        if (!menu) {
            return;
        }
        const isAdmin = user && typeof user.role === "string" && user.role.toLowerCase() === "admin";
        if (!isAdmin) {
            menu.innerHTML = "";
            return;
        }
        menu.innerHTML = [
            '<li class="nav-item dropdown">',
            '  <a class="nav-link dropdown-toggle" href="#" id="adminMenuToggle" role="button" data-bs-toggle="dropdown" aria-expanded="false">Admin</a>',
            '  <ul class="dropdown-menu" aria-labelledby="adminMenuToggle">',
            '    <li><a class="dropdown-item" href="/admin/dashboard">Tableau de bord</a></li>',
            '    <li><a class="dropdown-item" href="/admin/users">Utilisateurs</a></li>',
            '  </ul>',
            '</li>'
        ].join("");
    }

    function renderAuthenticated(user) {
        if (!authArea || !user) {
            return;
        }
        updateCurrentUser(user);
        renderAdminMenu(user);
        const initial = (user.prenom || "").charAt(0).toUpperCase() || "?";
        authArea.innerHTML = [
            '<div class="d-flex align-items-center gap-2">',
            '  <div class="avatar-circle"><span class="initial">' + initial + '</span></div>',
            '  <span class="fw-semibold">' + (user.prenom || "") + ' ' + (user.nom || "") + '</span>',
            '  <button class="btn btn-link text-decoration-none" id="logoutButton">Deconnexion</button>',
            '</div>'
        ].join("");
        attachLogoutHandler();
    }

    function renderUnauthenticated() {
        if (!authArea) {
            return;
        }
        updateCurrentUser(null);
        renderAdminMenu(null);
        authArea.innerHTML = [
            '<button class="btn btn-outline-primary me-2" data-bs-toggle="modal" data-bs-target="#loginModal">Connexion</button>',
            '<button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#registerModal">Inscription</button>'
        ].join("");
    }

    function showFeedback(container, message) {
        if (!container) {
            return;
        }
        container.textContent = message;
        container.classList.remove("d-none");
    }

    function clearFeedback(container) {
        if (!container) {
            return;
        }
        container.classList.add("d-none");
        container.textContent = "";
    }

    async function submitAuthForm(form, endpoint, feedbackContainer, onSuccess) {
        if (!form) {
            return;
        }
        const submitButton = form.querySelector('button[type="submit"]');
        const formData = Object.fromEntries(new FormData(form).entries());
        clearFeedback(feedbackContainer);
        if (submitButton) {
            submitButton.disabled = true;
        }

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(formData)
            });
            const payload = await response.json();
            if (!response.ok || payload.status !== "ok") {
                const message = payload && payload.message ? payload.message : "Une erreur est survenue.";
                showFeedback(feedbackContainer, message);
                return;
            }
            if (typeof onSuccess === "function") {
                onSuccess(payload.user);
            }
        } catch (error) {
            showFeedback(feedbackContainer, "Impossible de contacter le serveur. Essayez de nouveau.");
        } finally {
            if (submitButton) {
                submitButton.disabled = false;
            }
        }
    }

    function attachLogoutHandler() {
        const logoutButton = document.getElementById("logoutButton");
        if (!logoutButton) {
            return;
        }
        logoutButton.addEventListener("click", async function (event) {
            event.preventDefault();
            try {
                await fetch("/auth/logout", { method: "POST" });
            } catch (error) {
                // ignore network failures for logout
            }
            renderUnauthenticated();
        });
    }

    if (loginForm) {
        loginForm.addEventListener("submit", function (event) {
            event.preventDefault();
            submitAuthForm(loginForm, "/auth/login", loginFeedback, function (user) {
                hideModal(loginModalEl);
                loginForm.reset();
                renderAuthenticated(user);
            });
        });
    }

    if (registerForm) {
        registerForm.addEventListener("submit", function (event) {
            event.preventDefault();
            submitAuthForm(registerForm, "/auth/register", registerFeedback, function (user) {
                hideModal(registerModalEl);
                registerForm.reset();
                renderAuthenticated(user);
            });
        });
    }

    if (currentUser) {
        renderAuthenticated(currentUser);
    } else {
        renderUnauthenticated();
    }
})();
