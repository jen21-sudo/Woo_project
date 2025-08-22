const chosenQuestion = document.getElementById('chosen-question');
const answerText = document.getElementById('answer-text');
const backToBoxes = document.getElementById('back-to-boxes');
const backToQuestions = document.getElementById('back-to-questions');

// Connexion WebSocket
const ws = new WebSocket("ws://localhost:5000/ws");

ws.onopen = () => console.log("Connecté au serveur WebSocket.");

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "questions") {
        questionsList.innerHTML = '';
        data.questions.forEach(q => {
            const button = document.createElement('button');
            button.className = 'question-button';
            button.textContent = q;
            button.addEventListener('click', () => getAnswer(q));
            questionsList.appendChild(button);
        });
    } else if (data.type === "reponse") {
        // Nettoyer le markdown
        let cleanText = data.reponse
            .replace(/\*\*(.*?)\*\*/g, '$1')  // **gras**
            .replace(/\*(.*?)\*/g, '<em>$1</em>')  // *italique*
            .replace(/^- /gm, '• ')  // listes
            .trim();

        answerText.innerHTML = cleanText;
    }
};

ws.onclose = () => console.log("Déconnecté du serveur WebSocket.");
ws.onerror = (error) => console.error("Erreur WebSocket:", error);

// Clic sur une boîte → affiche les questions
document.querySelectorAll('.box1, .box2, .box3, .box4, .box5').forEach(box => {
    box.addEventListener('click', () => {
        const theme = box.dataset.theme;
        questionsSection.style.display = 'block';
        answerSection.style.display = 'none'; // S'assurer que la réponse est cachée
        questionsList.innerHTML = '🌀 Loading questions...';

        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "get_questions", theme }));
        }
    });
});

// Fonction pour afficher la réponse
function getAnswer(question) {
    chosenQuestion.textContent = question;
    answerText.textContent = '🔍 Searching the magic answer...';
    answerSection.style.display = 'block';

    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "get_reponse", question: question }));
    }
}

// Retour : Réponse → Questions
backToQuestions.addEventListener('click', () => {
    answerSection.style.display = 'none';
    questionsSection.style.display = 'block';
});

// Retour : Questions → Boîtes
backToBoxes.addEventListener('click', () => {
    questionsSection.style.display = 'none';
    // Aucune autre section affichée : retour aux boîtes
});