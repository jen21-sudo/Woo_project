let player; // Déplacé en dehors de l'écouteur d'événement

// Cette fonction est appelée automatiquement par l'API YouTube lorsqu'elle est prête
function onYouTubeIframeAPIReady() {
    console.log("YouTube IFrame API est prête.");
}

// Fonction pour gérer les changements d'état du lecteur
function onPlayerStateChange(event) {
    if (event.data === YT.PlayerState.ENDED) {
        const chatPage = document.querySelector('#chat-page-2');
        const videoResults = chatPage.querySelector('.video-results-container');
        const videoPlayerContainer = chatPage.querySelector('.video-player-container');
        const aiMessageBubble = chatPage.querySelector('.ai-message.speech-bubble');
        
        if (player) {
            player.destroy();
        }

        videoPlayerContainer.style.display = 'none';
        videoResults.style.display = 'grid';
        if (aiMessageBubble) {
            aiMessageBubble.classList.remove('hidden');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    const fullscreenContainer = document.querySelector('.fullscreen-container');
    const mainPage = document.getElementById('main-page');
    const characterContainers = document.querySelectorAll('.character-container');
    const backButtons = document.querySelectorAll('.back-button');

    const authOverlay = document.getElementById('auth-overlay');
    const registerBtnOverlay = document.getElementById('register-btn-overlay');
    const loginBtnOverlay = document.getElementById('login-btn-overlay');

    const userAvatarContainer = document.getElementById('user-avatar-container');
    const userAvatar = document.getElementById('user-avatar');

    const profilePanel = document.getElementById('profile-panel');
    const profileOverlay = document.getElementById('profile-panel-overlay');
    const profileCloseBtn = document.querySelector('.profile-close-btn');
    const profileAvatarDiv = document.getElementById('profile-avatar');
    const profileNameSpan = document.getElementById('profile-name');
    const profileEmailSpan = document.getElementById('profile-email');
    const editNameInput = document.getElementById('edit-name');
    const saveNameBtn = document.getElementById('save-name-btn');
    const photoUploadInput = document.getElementById('photo-upload');
    const logoutBtn = document.getElementById('logout-btn');

    const contactLink = document.getElementById('contact-link');
    const languageSelect = document.getElementById('language-select');

    const avatars = {
        'avatar1': 'Découverte.png',
        'avatar2': 'Art.png',
        'avatar3': 'Games.png'
    };

    let ws;
    let currentUserId = null;

    // === Connexion WebSocket (lancée uniquement quand nécessaire) ===
    function connectToAuthBackend(callback) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            callback();
            return;
        }

        if (ws && ws.readyState === WebSocket.CONNECTING) {
            const interval = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    clearInterval(interval);
                    callback();
                }
            }, 100);
            return;
        }

        ws = new WebSocket("ws://localhost:8000/ws");

        ws.onopen = () => {
            console.log("Connecté au serveur d'authentification WebSocket.");
            callback();
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("Message reçu du serveur:", data);

            if (data.type === "auth_success") {
                currentUserId = data.userId;
                localStorage.setItem('userId', data.userId);
                localStorage.setItem('userAvatar', data.avatar);
                localStorage.setItem('userName', data.child_name);
                localStorage.setItem('userEmail', data.email);
                updateAuthUI();
                if (data.message) alert(data.message);
                const modal = document.querySelector('.form-modal');
                if (modal) modal.remove();
            } else if (data.type === "auth_error") {
                alert(data.message);
            } else if (data.type === "profile_update_success") {
                if (data.new_name) localStorage.setItem('userName', data.new_name);
                if (data.new_avatar_url) localStorage.setItem('userAvatarUrl', data.new_avatar_url);
                updateProfileView();
                alert(data.message);
            } else if (data.type === "categories") {
                initializeCategories(data.categories);
            } else if (data.type === "message") {
                displayAiMessage(data.text);
            } else if (data.type === "videos") {
                displayVideos(data.videos);
            }
        };

        ws.onclose = () => console.log("Déconnecté du serveur WebSocket.");
        ws.onerror = (error) => console.error("Erreur WebSocket :", error);
    }

    // ✅ Appliquer les catégories uniquement à #chat-page-2
    function initializeCategories(categories) {
        const categoryContainer = document.querySelector('#chat-page-2 .category-buttons');
        if (!categoryContainer) return;

        categoryContainer.innerHTML = '';
        categories.forEach(category => {
            const button = document.createElement('button');
            button.className = 'category-button';
            button.textContent = category;
            button.addEventListener('click', () => {
                categoryContainer.querySelectorAll('.category-button').forEach(btn => {
                    btn.classList.remove('selected');
                });
                button.classList.add('selected');

                if (ws && ws.readyState === WebSocket.OPEN && currentUserId) {
                    ws.send(JSON.stringify({
                        type: "category_query",
                        text: category,
                        user_id: currentUserId
                    }));
                }
            });
            categoryContainer.appendChild(button);
        });
    }

    // ✅ Affiche le message IA
    function displayAiMessage(message) {
        const currentPage = document.querySelector('.chat-page[style*="translateX(0)"]');
        if (currentPage) {
            const conversationArea = currentPage.querySelector('.conversation-area');
            if (conversationArea) {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'ai-message speech-bubble';
                messageDiv.textContent = message;
                conversationArea.insertBefore(messageDiv, conversationArea.firstChild);
            }
        }
    }

    // ✅ Affiche les vidéos
    function displayVideos(videos) {
        const videoContainer = document.querySelector('#chat-page-2 .video-results-container');
        const videoPlayer = document.querySelector('#chat-page-2 .video-player-container');

        if (videoContainer) {
            if (videoPlayer) videoPlayer.style.display = 'none';
            videoContainer.style.display = 'grid';
            videoContainer.style.overflowY = 'auto';
            videoContainer.style.maxHeight = '60vh';
            videoContainer.innerHTML = '';

            let html = "";
            videos.forEach(video => {
                const sanitizedTitle = (video.title || "Vidéo").replace(/"/g, "'");
                html += `
                    <div class="video-card" data-id="${video.id}" data-title="${sanitizedTitle}">
                        <img src="https://img.youtube.com/vi/${video.id}/hqdefault.jpg" alt="${sanitizedTitle}">
                        <p class="video-title">${sanitizedTitle}</p>
                    </div>
                `;
            });
            videoContainer.innerHTML = html;
            addVideoCardListeners();
        }
    }

    function addVideoCardListeners() {
        const videoContainer = document.querySelector('#chat-page-2 .video-results-container');
        if (videoContainer) {
            videoContainer.querySelectorAll(".video-card").forEach(card => {
                card.addEventListener("click", () => {
                    const videoId = card.dataset.id;
                    const videoPlayerContainer = document.querySelector('#chat-page-2 .video-player-container');
                    showVideoPlayer(videoId, videoPlayerContainer);
                });
            });
        }
    }

    // Fonction pour afficher le lecteur vidéo
    function showVideoPlayer(videoId, container) {
        const chatPage = container.closest('.chat-page');
        const videoResults = chatPage.querySelector('.video-results-container');
        const aiMessageBubble = chatPage.querySelector('.ai-message.speech-bubble');

        if (aiMessageBubble) {
            aiMessageBubble.classList.add('hidden');
        }

        container.style.display = 'flex';
        videoResults.style.display = 'none';

        const videoCard = document.querySelector(`.video-card[data-id="${videoId}"]`);
        const videoTitle = videoCard ? videoCard.dataset.title : "Vidéo";

        container.innerHTML = `
            <div style="width: 100%; padding: 10px; background: #1a1a1a; color: white; display: flex; align-items: center; gap: 10px;">
                <button class="video-close-button" style="background: none; border: none; color: white; font-size: 24px; cursor: pointer;">&times;</button>
                <h4 style="margin: 0; font-size: 16px; overflow: hidden; text-overflow: ellipsis;">${videoTitle}</h4>
            </div>
            <div id="youtube-player" style="width: 100%; height: 400px;"></div>
        `;
        
        if (typeof YT !== 'undefined' && YT.Player) {
            createPlayer(videoId, container);
        } else {
            setTimeout(() => createPlayer(videoId, container), 500);
        }

        container.querySelector('.video-close-button').addEventListener('click', () => {
            if (player) {
                player.destroy();
            }
            container.style.display = 'none';
            videoResults.style.display = 'grid';
            if (aiMessageBubble) {
                aiMessageBubble.classList.remove('hidden');
            }
        });
    }

    // Initialiser le lecteur YouTube
    function createPlayer(videoId, container) {
        if (player) {
            player.destroy();
        }

        player = new YT.Player('youtube-player', {
            videoId: videoId,
            playerVars: {
                'autoplay': 1,
                'rel': 0,
                'modestbranding': 1
            },
            events: {
                'onReady': (event) => event.target.playVideo(),
                'onStateChange': onPlayerStateChange
            }
        });
    }

    // Animation de chargement
    function displayLoadingAnimation() {
        const videoContainer = document.querySelector('#chat-page-2 .video-results-container');
        if (!videoContainer) return;

        videoContainer.style.display = 'flex';
        videoContainer.style.flexDirection = 'column';
        videoContainer.style.alignItems = 'center';
        videoContainer.style.justifyContent = 'center';
        videoContainer.style.maxHeight = '60vh';
        videoContainer.style.gap = '20px';
        videoContainer.innerHTML = '';

        const title = document.createElement('div');
        title.textContent = "Je cherche ça tout de suite ! 🎬";
        title.style.fontSize = '18px';
        title.style.color = 'white';
        title.style.marginBottom = '15px';
        videoContainer.appendChild(title);

        const dotsContainer = document.createElement('div');
        dotsContainer.className = 'loading-dots';
        dotsContainer.style.display = 'flex';
        dotsContainer.style.gap = '8px';

        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.style.width = '12px';
            dot.style.height = '12px';
            dot.style.backgroundColor = '#ff69b4';
            dot.style.borderRadius = '50%';
            dot.style.animation = `bounce 1.4s ease-in-out infinite ${i * 0.2}s`;
            dotsContainer.appendChild(dot);
        }
        videoContainer.appendChild(dotsContainer);

        if (!document.querySelector('#loading-style')) {
            const style = document.createElement('style');
            style.id = 'loading-style';
            style.textContent = `
                @keyframes bounce {
                    0%, 80%, 100% { transform: translateY(0); }
                    40% { transform: translateY(-10px); }
                }
            `;
            document.head.appendChild(style);
        }
    }

    // === FORMULAIRE D'INSCRIPTION (affiché IMMÉDIATEMENT) ===
    function createRegisterForm() {
        if (document.querySelector('.form-modal')) return;

        const modal = document.createElement('div');
        modal.className = 'form-modal';
        modal.innerHTML = `
            <div class="form-container">
                <span class="form-close">&times;</span>
                <h2 data-i18n="registerFormTitle">Inscription</h2>
                <form id="register-form">
                    <div class="form-group">
                        <label for="child-name" data-i18n="childNameLabel">Prénom de l'enfant :</label>
                        <input type="text" id="child-name" required>
                    </div>
                    <div class="form-group">
                        <label for="parent-email" data-i18n="parentEmailLabel">Email des parents :</label>
                        <input type="email" id="parent-email" required>
                    </div>
                    <div class="form-group">
                        <label for="new-password" data-i18n="newPasswordLabel">Nouveau mot de passe :</label>
                        <input type="password" id="new-password" required>
                    </div>
                    <div class="form-group">
                        <label for="child-age" data-i18n="childAgeLabel">Âge de l'enfant :</label>
                        <select id="child-age" required></select>
                    </div>
                    <div class="form-group">
                        <label data-i18n="chooseAvatarLabel">Choisir un avatar :</label>
                        <div class="avatar-choices">
                            <div class="avatar-choice" data-avatar="avatar1" style="background-image: url('Découverte.png');"></div>
                            <div class="avatar-choice" data-avatar="avatar2" style="background-image: url('Art.png');"></div>
                            <div class="avatar-choice" data-avatar="avatar3" style="background-image: url('Games.png');"></div>
                        </div>
                    </div>
                    <button type="submit" class="form-button" data-i18n="registerBtn">S'inscrire</button>
                </form>
            </div>
        `;
        document.body.appendChild(modal);

        const ageSelect = modal.querySelector('#child-age');
        for (let i = 4; i <= 15; i++) {
            const option = document.createElement('option');
            option.value = i;
            option.textContent = i + ' ans';
            ageSelect.appendChild(option);
        }

        let selectedAvatar = '';
        modal.querySelectorAll('.avatar-choice').forEach(choice => {
            choice.addEventListener('click', () => {
                modal.querySelectorAll('.avatar-choice').forEach(c => c.classList.remove('selected'));
                choice.classList.add('selected');
                selectedAvatar = choice.dataset.avatar;
            });
        });

        modal.querySelector('#register-form').addEventListener('submit', (e) => {
            e.preventDefault();
            if (!selectedAvatar) {
                alert(translations[currentLanguage].alertChooseAvatar);
                return;
            }
            const parentEmail = modal.querySelector('#parent-email').value;
            const childName = modal.querySelector('#child-name').value;
            const password = modal.querySelector('#new-password').value;
            const childAge = modal.querySelector('#child-age').value;

            // ✅ Connexion lancée ici, pas avant
            connectToAuthBackend(() => {
                ws.send(JSON.stringify({
                    type: "register",
                    email: parentEmail,
                    password: password,
                    child_name: childName,
                    child_age: childAge,
                    avatar: selectedAvatar
                }));
            });
        });

        modal.querySelector('.form-close').addEventListener('click', () => {
            modal.remove();
        });
    }

    // === FORMULAIRE DE CONNEXION (affiché IMMÉDIATEMENT) ===
    function createLoginForm() {
        if (document.querySelector('.form-modal')) return;

        const modal = document.createElement('div');
        modal.className = 'form-modal';
        modal.innerHTML = `
            <div class="form-container">
                <span class="form-close">&times;</span>
                <h2 data-i18n="loginFormTitle">Connexion</h2>
                <form id="login-form">
                    <div class="form-group">
                        <label for="login-email" data-i18n="emailLabel">Email :</label>
                        <input type="email" id="login-email" required>
                    </div>
                    <div class="form-group">
                        <label for="login-password" data-i18n="passwordLabel">Mot de passe :</label>
                        <input type="password" id="login-password" required>
                    </div>
                    <button type="submit" class="form-button" data-i18n="loginBtn">Se connecter</button>
                </form>
            </div>
        `;
        document.body.appendChild(modal);

        modal.querySelector('#login-form').addEventListener('submit', (e) => {
            e.preventDefault();
            const email = modal.querySelector('#login-email').value;
            const password = modal.querySelector('#login-password').value;

            // ✅ Connexion lancée ici
            connectToAuthBackend(() => {
                ws.send(JSON.stringify({
                    type: "login",
                    email: email,
                    password: password
                }));
            });
        });

        modal.querySelector('.form-close').addEventListener('click', () => {
            modal.remove();
        });
    }

    // === TRADUCTIONS ===
    const translations = {
        fr: {
            appTitle: 'Design WOO',
            welcomeTitle: 'Bienvenue sur WOO !',
            authText: 'Veuillez vous inscrire ou vous connecter pour continuer.',
            registerBtn: 'S\'inscrire',
            loginBtn: 'Se connecter',
            fullscreenTitle: 'Bienvenue sur WOO !',
            fullscreenText: 'Cliquez pour une expérience immersive en plein écran.',
            fullscreenBtn: 'Lancer en plein écran',
            wooSecretsTooltip: 'Woo Secrets',
            wooTubeTooltip: 'Woo Tube',
            wooCreatesTooltip: 'Woo Creates',
            wooSongsTooltip: 'Woo Songs',
            wooGamesTooltip: 'Woo Games',
            changePhotoText: 'Changer de photo',
            editProfileTitle: 'Modifier le profil',
            newNameLabel: 'Nouveau nom :',
            newNamePlaceholder: 'Entrer un nouveau nom',
            saveNameBtn: 'Sauvegarder le nom',
            helpTitle: 'Aide et Support',
            contactLink: 'Contact us',
            languageTitle: 'Langue',
            settingsTitle: 'Paramètres',
            settingsText: 'Gérer les paramètres du compte.',
            privacyTitle: 'Confidentialité',
            privacyText: 'Consulter la politique de confidentialité.',
            termsTitle: 'Règlements',
            termsText: 'Lire les termes et conditions.',
            logoutBtn: 'Déconnexion',
            backBtn: '←',
            inputPlaceholder: 'Écris ton message ici...',
            sendBtn: 'Envoyer',
            wooSecretsGreeting: 'Bonjour ! Je suis Woo Secrets. Prêt à explorer le monde avec moi ?',
            wooCreatesGreeting: 'Salut ! Je suis Woo Creates. L\'aventure de la création commence !',
            wooSongsGreeting: 'Enchanté ! Je suis Woo Songs. Prêt à faire de la musique ensemble ?',
            wooGamesGreeting: 'Yo ! Je suis Woo Games. On se fait une partie ?',
            registerFormTitle: 'Inscription',
            childNameLabel: 'Prénom de l\'enfant :',
            parentEmailLabel: 'Email des parents :',
            newPasswordLabel: 'Nouveau mot de passe :',
            childAgeLabel: 'Âge de l\'enfant :',
            chooseAvatarLabel: 'Choisir un avatar :',
            loginFormTitle: 'Connexion',
            emailLabel: 'Email :',
            passwordLabel: 'Mot de passe :',
            alertChooseAvatar: 'Veuillez choisir un avatar.',
            alertLogout: 'Vous avez été déconnecté.',
            alertUpdateError: 'Erreur de connexion : Impossible de mettre à jour le profil.'
        },
        en: {
            appTitle: 'WOO Design',
            welcomeTitle: 'Welcome to WOO!',
            authText: 'Please register or log in to continue.',
            registerBtn: 'Register',
            loginBtn: 'Log in',
            fullscreenTitle: 'Welcome to WOO!',
            fullscreenText: 'Click for an immersive full-screen experience.',
            fullscreenBtn: 'Launch full screen',
            wooSecretsTooltip: 'Woo Secrets',
            wooTubeTooltip: 'Woo Tube',
            wooCreatesTooltip: 'Woo Creates',
            wooSongsTooltip: 'Woo Songs',
            wooGamesTooltip: 'Woo Games',
            changePhotoText: 'Change photo',
            editProfileTitle: 'Edit profile',
            newNameLabel: 'New name:',
            newNamePlaceholder: 'Enter a new name',
            saveNameBtn: 'Save name',
            helpTitle: 'Help and Support',
            contactLink: 'Contact us',
            languageTitle: 'Language',
            settingsTitle: 'Settings',
            settingsText: 'Manage account settings.',
            privacyTitle: 'Privacy',
            privacyText: 'View privacy policy.',
            termsTitle: 'Terms',
            termsText: 'Read terms and conditions.',
            logoutBtn: 'Log out',
            backBtn: '←',
            inputPlaceholder: 'Write your message here...',
            sendBtn: 'Send',
            wooSecretsGreeting: 'Hello! I am Woo Secrets. Ready to explore the world with me?',
            wooCreatesGreeting: 'Hi! I am Woo Creates. The creation adventure begins!',
            wooSongsGreeting: 'Nice to meet you! I am Woo Songs. Ready to make music together?',
            wooGamesGreeting: 'Yo! I am Woo Games. Wanna play a game?',
            registerFormTitle: 'Registration',
            childNameLabel: 'Child\'s name:',
            parentEmailLabel: 'Parents\' email:',
            newPasswordLabel: 'New password:',
            childAgeLabel: 'Child\'s age:',
            chooseAvatarLabel: 'Choose an avatar:',
            loginFormTitle: 'Login',
            emailLabel: 'Email :',
            passwordLabel: 'Password:',
            alertChooseAvatar: 'Please choose an avatar.',
            alertLogout: 'You have been logged out.',
            alertUpdateError: 'Connection error: Unable to update profile.'
        }
    };

    let currentLanguage = localStorage.getItem('language') || 'fr';

    function updateLanguage(lang) {
        currentLanguage = lang;
        localStorage.setItem('language', lang);
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            if (translations[lang][key]) {
                if (element.tagName === 'INPUT' && element.getAttribute('type') === 'text') {
                    element.placeholder = translations[lang][key];
                } else {
                    element.textContent = translations[lang][key];
                }
            }
        });
    }

    function openProfilePanel() {
        updateProfileView();
        profilePanel.classList.add('active');
        profileOverlay.classList.add('active');
    }

    function updateProfileView() {
        const userName = localStorage.getItem('userName') || 'Utilisateur';
        const userEmail = localStorage.getItem('userEmail') || 'Non renseigné';
        const userAvatarUrl = localStorage.getItem('userAvatarUrl') || avatars[localStorage.getItem('userAvatar')];

        profileNameSpan.textContent = userName;
        profileEmailSpan.textContent = userEmail;
        profileAvatarDiv.style.backgroundImage = `url('${userAvatarUrl}')`;
        editNameInput.value = userName;
        userAvatar.src = userAvatarUrl;
    }

    function closeProfilePanel() {
        profilePanel.classList.remove('active');
        profileOverlay.classList.remove('active');
    }

    function updateAuthUI() {
        const userId = localStorage.getItem('userId');
        if (userId) {
            currentUserId = userId;
            authOverlay.classList.add('hidden');
            mainPage.classList.add('active');
            userAvatarContainer.style.display = 'flex';
            updateProfileView();
        } else {
            authOverlay.classList.remove('hidden');
            mainPage.classList.remove('active');
            userAvatarContainer.style.display = 'none';
        }
    }

    function setupWooTube() {
        const inputField = document.getElementById('input-chat-2');
        const sendButton = document.getElementById('send-chat-2');

        function sendMessage() {
            const userQuery = inputField.value.trim();
            if (userQuery) {
                displayLoadingAnimation();
                if (ws && ws.readyState === WebSocket.OPEN && currentUserId) {
                    ws.send(JSON.stringify({
                        type: "query",
                        text: userQuery,
                        user_id: currentUserId
                    }));
                }
                inputField.value = "";
            }
        }

        if (sendButton) sendButton.addEventListener('click', sendMessage);
        if (inputField) {
            inputField.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }
    }

    // === ÉCOUTEURS D'ÉVÉNEMENTS ===
    fullscreenBtn.addEventListener('click', () => {
        if (document.documentElement.requestFullscreen) {
            document.documentElement.requestFullscreen();
        } else if (document.documentElement.mozRequestFullScreen) {
            document.documentElement.mozRequestFullScreen();
        } else if (document.documentElement.webkitRequestFullscreen) {
            document.documentElement.webkitRequestFullscreen();
        } else if (document.documentElement.msRequestFullscreen) {
            document.documentElement.msRequestFullscreen();
        }
        fullscreenContainer.classList.add('hidden');
    });

    characterContainers.forEach(container => {
        const character = container.querySelector('.character');
        let hasSpun = false;
        container.addEventListener('mouseenter', () => {
            if (!hasSpun) {
                character.classList.add('spin-once');
                hasSpun = true;
            }
        });
        container.addEventListener('mouseleave', () => {
            if (hasSpun) {
                character.classList.remove('spin-once');
                hasSpun = false;
            }
        });
    });

    document.querySelectorAll('.island').forEach(island => {
        island.addEventListener('click', (e) => {
            e.preventDefault();
            const targetPageId = island.dataset.target;
            const targetPage = document.getElementById(targetPageId);
            mainPage.classList.add('inactive');
            mainPage.style.transform = 'translateX(-100%)';
            targetPage.style.transform = 'translateX(0)';
            localStorage.setItem('lastPage', targetPageId);
        });
    });

    backButtons.forEach(button => {
        button.addEventListener('click', () => {
            const currentPage = button.closest('.chat-page');
            mainPage.classList.remove('inactive');
            mainPage.style.transform = 'translateX(0)';
            currentPage.style.transform = 'translateX(100%)';
            localStorage.setItem('lastPage', 'main-page');
        });
    });

    // ✅ Clic → formulaire affiché IMMÉDIATEMENT
    registerBtnOverlay.addEventListener('click', createRegisterForm);
    loginBtnOverlay.addEventListener('click', createLoginForm);

    userAvatarContainer.addEventListener('click', openProfilePanel);
    profileCloseBtn.addEventListener('click', closeProfilePanel);
    profileOverlay.addEventListener('click', closeProfilePanel);

    photoUploadInput.addEventListener('change', function (e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (e) {
                const newAvatarUrl = e.target.result;
                const userId = localStorage.getItem('userId');
                if (ws && ws.readyState === WebSocket.OPEN && userId) {
                    ws.send(JSON.stringify({
                        type: "update_profile",
                        userId: userId,
                        new_avatar_url: newAvatarUrl
                    }));
                } else {
                    alert(translations[currentLanguage].alertUpdateError);
                    localStorage.setItem('userAvatarUrl', newAvatarUrl);
                    updateProfileView();
                }
            };
            reader.readAsDataURL(file);
        }
    });

    saveNameBtn.addEventListener('click', () => {
        const newName = editNameInput.value.trim();
        const userId = localStorage.getItem('userId');
        if (newName && userId) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: "update_profile",
                    userId: userId,
                    new_name: newName
                }));
            } else {
                alert(translations[currentLanguage].alertUpdateError);
                localStorage.setItem('userName', newName);
                updateProfileView();
            }
        }
    });

    languageSelect.addEventListener('change', (e) => {
        updateLanguage(e.target.value);
    });

    logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('userId');
        localStorage.removeItem('userAvatar');
        localStorage.removeItem('userAvatarUrl');
        localStorage.removeItem('userName');
        localStorage.removeItem('userEmail');
        localStorage.removeItem('lastPage');
        currentUserId = null;
        updateAuthUI();
        closeProfilePanel();
        alert(translations[currentLanguage].alertLogout);
    });

    contactLink.addEventListener('click', (e) => {
        e.preventDefault();
        alert('Fonctionnalité de contact à implémenter');
    });

    // === Chargement initial ===
    window.addEventListener('load', () => {
        updateLanguage(currentLanguage);
        languageSelect.value = currentLanguage;

        const userId = localStorage.getItem('userId');
        const lastPage = localStorage.getItem('lastPage');

        if (userId) {
            currentUserId = userId;
            updateAuthUI();
            connectToAuthBackend(() => {
                console.log("Reconnecté au backend");
            });

            if (lastPage && lastPage !== 'main-page') {
                const targetPage = document.getElementById(lastPage);
                if (targetPage) {
                    mainPage.classList.add('inactive');
                    mainPage.style.transform = 'translateX(-100%)';
                    targetPage.style.transform = 'translateX(0)';
                }
            }
        } else {
            updateAuthUI();
        }

        setupWooTube();
    });
});