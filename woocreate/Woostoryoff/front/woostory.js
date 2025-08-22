// === Variables globales ===
let socket;
let closeButtonMain = null;  // Bouton ✕ dans mainContainer
let closeButtonIa = null;    // Bouton ✕ dans iaContainer

// === Fonction pour créer les boutons de fermeture (✕) ===
function createCloseButtons() {
  const startScreen = document.getElementById('startScreen');
  const mainContainer = document.getElementById('mainContainer');
  const iaContainer = document.getElementById('iaContainer');

  if (!mainContainer || !iaContainer) return;

  // S'assurer que les conteneurs ont une position relative pour le positionnement absolu du ✕
  mainContainer.style.position = 'relative';
  iaContainer.style.position = 'relative';

  // Style commun pour les boutons ✕
  const btnStyle = `
    position: absolute;
    top: 15px;
    right: 15px;
    width: 40px;
    height: 40px;
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid #8e44ad;
    border-radius: 50%;
    font-size: 24px;
    color: #8e44ad;
    display: flex;
    justify-content: center;
    align-items: center;
    cursor: pointer;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    transition: all 0.3s ease;
    z-index: 100;
    font-family: 'Comic Neue', cursive;
    font-weight: bold;
    border: none;
    outline: none;
    margin: 0;
    padding: 0;
    line-height: 1;
  `;

  // --- Bouton pour iaContainer : retour → mainContainer ---
  if (!closeButtonIa && iaContainer) {
    closeButtonIa = document.createElement('button');
    closeButtonIa.innerHTML = '✕';
    closeButtonIa.title = 'Back to Story';
    closeButtonIa.style.cssText = btnStyle;
    closeButtonIa.addEventListener('click', (e) => {
      e.stopPropagation();
      iaContainer.style.display = 'none';
      mainContainer.style.display = 'flex';
      window.scrollTo(0, 0); // Remonter en haut
    });
    iaContainer.appendChild(closeButtonIa);
  }

  // --- Bouton pour mainContainer : retour → startScreen (état initial) ---
  if (!closeButtonMain && mainContainer) {
    closeButtonMain = document.createElement('button');
    closeButtonMain.innerHTML = '✕';
    closeButtonMain.title = 'Back to Start';
    closeButtonMain.style.cssText = btnStyle;
    closeButtonMain.addEventListener('click', (e) => {
      e.stopPropagation();

      // Cacher les écrans actifs
      mainContainer.style.display = 'none';
      iaContainer.style.display = 'none';

      // Réafficher le startScreen → comme au chargement initial
      startScreen.style.display = 'inline'; // ou 'block' → mais 'flex' est cohérent avec .overlay

      // Réinitialiser les champs saisis
      document.getElementById('charInput').value = '';
      document.getElementById('sceneInput').value = '';
      document.getElementById('storyInput').value = '';

      // Réinitialiser le contenu IA
      const iaContent = document.getElementById('iaContent');
      if (iaContent) {
        iaContent.innerHTML = '<p>Your story will appear here!</p>';
      }

      // Cacher le bouton retour flèche (←) s'il existe
      const backBtn = document.getElementById('backBtn');
      if (backBtn) {
        backBtn.style.display = 'none';
      }

      // Remonter en haut de la page
      window.scrollTo(0, 0);
    });
    mainContainer.appendChild(closeButtonMain);
  }
}

// === Connexion WebSocket ===
function connectWebSocket() {
  socket = new WebSocket('ws://127.0.0.1:3000/ws');

  socket.onopen = () => {
    console.log('✅ Connecté au serveur WebSocket');
  };

  socket.onmessage = (event) => {
    const iaContent = document.getElementById('iaContent');
    if (iaContent) {
      iaContent.innerHTML = `<p>${event.data.replace(/\n/g, '<br>')}</p>`;
    }
  };

  socket.onclose = () => {
    console.log('🔌 WebSocket fermé. Tentative de reconnexion...');
    setTimeout(connectWebSocket, 2000);
  };

  socket.onerror = (error) => {
    console.error('❌ Erreur WebSocket:', error);
    const iaContent = document.getElementById('iaContent');
    if (iaContent) {
      iaContent.innerHTML = `
        <p style="color: red;">
          Erreur de connexion à l’IA.<br>
          Vérifiez que le serveur tourne sur <code>ws://127.0.0.1:3000</code>
        </p>`;
    }
  };
}

// === Générer l'histoire ===
function generateStory() {
  const char = document.getElementById('charInput').value.trim();
  const scene = document.getElementById('sceneInput').value.trim();
  const story = document.getElementById('storyInput').value.trim();

  const data = {
    personnage: char || "un personnage anonyme",
    scene: scene || "un endroit mystérieux",
    scenario: story || "une aventure simple"
  };

  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(data));
    console.log('📤 Données envoyées:', data);

    document.getElementById('mainContainer').style.display = 'none';
    document.getElementById('iaContainer').style.display = 'flex';
  } else {
    document.getElementById('iaContent').innerHTML = `
      <p style="color: red;">
        Impossible de se connecter au serveur.<br>
        Vérifiez que le serveur Python est lancé.
      </p>`;
    document.getElementById('mainContainer').style.display = 'none';
    document.getElementById('iaContainer').style.display = 'flex';
  }

  // S'assurer que les boutons ✕ sont présents
  createCloseButtons();
}

// === Initialisation au chargement ===
document.addEventListener('DOMContentLoaded', () => {
  const startScreen = document.getElementById('startScreen');
  const mainContainer = document.getElementById('mainContainer');
  const iaContainer = document.getElementById('iaContainer');
  const backBtn = document.getElementById('backBtn'); // Peut être null si non présent

  // Appliquer position relative aux conteneurs
  if (mainContainer) mainContainer.style.position = 'relative';
  if (iaContainer) iaContainer.style.position = 'relative';

  // Créer les boutons ✕ dès le départ
  createCloseButtons();

  // Connexion WebSocket
  connectWebSocket();

  // Gestion des livres : ouvrir l'interface principale
  const bookItems = document.querySelectorAll('.book-item');
  bookItems.forEach(book => {
    book.addEventListener('click', () => {
      startScreen.style.display = 'none';
      mainContainer.style.display = 'flex';
      if (backBtn) backBtn.style.display = 'flex';
      // Recréer les boutons ✕ au cas où (léger délai pour stabilité)
      setTimeout(createCloseButtons, 10);
    });
  });

  // Gestion du bouton retour flèche ← (si présent)
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      if (iaContainer.style.display === 'flex') {
        iaContainer.style.display = 'none';
        mainContainer.style.display = 'flex';
      } else if (mainContainer.style.display === 'flex') {
        mainContainer.style.display = 'none';
        startScreen.style.display = 'flex';
        backBtn.style.display = 'none';
      }
      window.scrollTo(0, 0);
    });
  }
});