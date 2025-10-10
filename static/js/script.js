(function () {
    const authArea = document.getElementById("auth-area");
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");
    const loginModalEl = document.getElementById("loginModal");
    const registerModalEl = document.getElementById("registerModal");
    const loginFeedback = document.getElementById("loginFeedback");
    const registerFeedback = document.getElementById("registerFeedback");

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

    function renderAuthenticated(user) {
        if (!authArea || !user) {
            return;
        }
        const initial = (user.prenom || "").charAt(0).toUpperCase() || "?";
        authArea.innerHTML = [
            '<div class="d-flex align-items-center gap-2">',
            '  <div class="avatar-circle"><span class="initial">' + initial + '</span></div>',
            '  <span class="fw-semibold">' + user.prenom + ' ' + user.nom + '</span>',
            '  <button class="btn btn-link text-decoration-none" id="logoutButton">Deconnexion</button>',
            '</div>'
        ].join("");
        attachLogoutHandler();
    }

    function renderUnauthenticated() {
        if (!authArea) {
            return;
        }
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

    if (window.__currentUser__) {
        renderAuthenticated(window.__currentUser__);
    } else {
        renderUnauthenticated();
    }
})();
