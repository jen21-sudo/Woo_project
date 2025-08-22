document.addEventListener('DOMContentLoaded', () => {
    const blocPalette = document.querySelector('.bloc-palette');
    const codeArea = document.getElementById('code-area');
    const character = document.getElementById('character');
    const runBtn = document.getElementById('run-btn');
    const startCoordsSpan = document.getElementById('start-coords');
    const endCoordsSpan = document.getElementById('end-coords');
    const currentCoordsSpan = document.getElementById('current-coords');
    const levelTextSpan = document.getElementById('level-text');
    const goalText = document.getElementById('goal-text');
    const target = document.getElementById('target');
    
    let currentLevel = 0;
    const levels = [
        { start: { h: 0, v: 0 }, end: { h: 2, v: 2 } }, // Niveau 1
        { start: { h: 0, v: 0 }, end: { h: 3, v: 1 } }, // Niveau 2
        { start: { h: 2, v: 0 }, end: { h: 0, v: 3 } }, // Niveau 3
        { start: { h: 0, v: 3 }, end: { h: 4, v: 1 } }, // Niveau 4
        { start: { h: 0, v: 0 }, end: { h: 5, v: 5 } }  // Niveau 5
    ];

    let characterPosition = { h: 0, v: 0 };
    let draggedBloc = null;
    let ws;
    let turn = 'player'; // 'player' or 'ai'

    function connectWebSocket() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            return;
        }
        ws = new WebSocket("ws://127.0.0.1:8000/ws");

        ws.onopen = () => {
            console.log("WebSocket connected.");
            goalText.textContent = "IA connectée. Votre tour de jouer !";
            initLevel(0);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.goal) {
                goalText.textContent = `Objectif de l'IA : ${data.goal}`;
            } else if (data.error) {
                goalText.textContent = `Erreur de l'IA : ${data.error}`;
                console.error("AI Goal Error:", data.error);
            } else if (data.aiPath) {
                // The AI returns the full path, now we run it.
                runAIMove(data.aiPath);
            }
        };

        ws.onclose = () => {
            console.log("WebSocket déconnectée. Tentative de reconnexion...");
            setTimeout(connectWebSocket, 1000);
        };

        ws.onerror = (error) => {
            console.error("Erreur WebSocket:", error);
        };
    }

    function initLevel(levelIndex) {
        if (levelIndex >= levels.length) {
            alert("Félicitations ! Vous avez terminé tous les niveaux !");
            return;
        }

        currentLevel = levelIndex;
        const level = levels[currentLevel];
        
        characterPosition = { h: level.start.h, v: level.start.v };
        
        levelTextSpan.textContent = currentLevel + 1;
        startCoordsSpan.textContent = `(${level.start.h}, ${level.start.v})`;
        endCoordsSpan.textContent = `(${level.end.h}, ${level.end.v})`;
        
        updateCharacterPosition();
        updateTargetPosition();
        
        codeArea.innerHTML = '<p class="instruction">Glisse les blocs ici pour programmer ton personnage !</p>';
        turn = 'player';
        goalText.textContent = "C'est votre tour de jouer !";
    }

    function updateCharacterPosition() {
        const hStep = 50;
        const vStep = 50;
        character.style.left = `${characterPosition.h * hStep}px`;
        character.style.top = `${characterPosition.v * vStep}px`;
        currentCoordsSpan.textContent = `(${characterPosition.h}, ${characterPosition.v})`;
    }

    function updateTargetPosition() {
        const hStep = 50;
        const vStep = 50;
        target.style.left = `${levels[currentLevel].end.h * hStep}px`;
        target.style.top = `${levels[currentLevel].end.v * vStep}px`;
    }

    // Glisser-déposer
    blocPalette.addEventListener('dragstart', (e) => {
        if (turn === 'ai') return;
        if (e.target.classList.contains('bloc')) {
            draggedBloc = e.target;
            e.dataTransfer.setData('text/plain', e.target.dataset.action);
        }
    });

    codeArea.addEventListener('dragover', (e) => e.preventDefault());

    codeArea.addEventListener('drop', (e) => {
        e.preventDefault();
        if (turn === 'ai') return;
        if (draggedBloc && e.target.closest('#code-area')) {
            const newBloc = draggedBloc.cloneNode(true);
            newBloc.draggable = false;
            newBloc.classList.add('in-code-area');
            codeArea.appendChild(newBloc);
            draggedBloc = null;
            
            newBloc.addEventListener('click', () => {
                newBloc.remove();
            });
        }
    });

    // Lancer le programme
    runBtn.addEventListener('click', async () => {
        if (turn === 'ai') {
            alert("Ce n'est pas votre tour !");
            return;
        }

        const blocks = Array.from(codeArea.querySelectorAll('.bloc.in-code-area'));
        const initialPosition = { ...characterPosition };
        
        for (const bloc of blocks) {
            const action = bloc.dataset.action;
            bloc.style.backgroundColor = '#FFD700';

            switch (action) {
                case 'right': characterPosition.h += 1; break;
                case 'left': characterPosition.h -= 1; break;
                case 'up': characterPosition.v -= 1; break;
                case 'down': characterPosition.v += 1; break;
            }
            updateCharacterPosition();
            await new Promise(resolve => setTimeout(resolve, 500));
            bloc.style.backgroundColor = '';
        }

        checkVictory(initialPosition);
    });

    function checkVictory(initialPosition) {
        const currentGoal = levels[currentLevel].end;
        if (characterPosition.h === currentGoal.h && characterPosition.v === currentGoal.v) {
            alert(`Félicitations ! Vous avez atteint la cible du niveau ${currentLevel + 1} !`);
            initLevel(currentLevel + 1);
        } else {
            alert("Dommage ! Le programme est incomplet. Retour au point de départ.");
            characterPosition = initialPosition;
            updateCharacterPosition();
            
            // C'est au tour de l'IA
            turn = 'ai';
            goalText.textContent = "C'est au tour de l'IA de jouer...";
            
            // Demander le mouvement de l'IA
            const level = levels[currentLevel];
            ws.send(JSON.stringify({ 
                turn: 'ai',
                playerPos: initialPosition,
                targetPos: level.end
            }));
        }
    }

    async function runAIMove(aiPath) {
        console.log("AI is playing: ", aiPath);

        // Clear player's blocks
        codeArea.innerHTML = '';
        
        // Add AI's blocks to the code area
        for (const move of aiPath) {
            const blocInPalette = document.querySelector(`.bloc[data-action="${move}"]`);
            if (blocInPalette) {
                const newBloc = blocInPalette.cloneNode(true);
                newBloc.draggable = false;
                newBloc.classList.add('in-code-area');
                codeArea.appendChild(newBloc);
            }
        }
        
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Now, execute the AI's program
        const blocksToExecute = Array.from(codeArea.querySelectorAll('.bloc.in-code-area'));
        for (const bloc of blocksToExecute) {
            const action = bloc.dataset.action;
            bloc.style.backgroundColor = '#FFD700';

            switch (action) {
                case 'right': characterPosition.h += 1; break;
                case 'left': characterPosition.h -= 1; break;
                case 'up': characterPosition.v -= 1; break;
                case 'down': characterPosition.v += 1; break;
            }
            updateCharacterPosition();
            await new Promise(resolve => setTimeout(resolve, 500));
            bloc.style.backgroundColor = '';
        }

        const currentGoal = levels[currentLevel].end;
        if (characterPosition.h === currentGoal.h && characterPosition.v === currentGoal.v) {
            alert("L'IA a réussi ! À vous de jouer le prochain niveau.");
            initLevel(currentLevel + 1);
        } else {
            alert("L'IA a échoué. Retour à la case départ, c'est votre tour de jouer !");
            initLevel(currentLevel);
        }
        turn = 'player';
        goalText.textContent = "C'est votre tour de jouer !";
    }

    initLevel(0);
    connectWebSocket();
});