document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('idea-generator-form');
    const responseArea = document.getElementById('response-area');
    const radioButtons = document.querySelectorAll('input[name="option"]');
    const inputGroups = document.querySelectorAll('.input-group');

    // Mettez à jour l'URL du WebSocket pour qu'elle corresponde à votre backend
    const socket = new WebSocket('ws://127.0.0.1:3000/ws');

    socket.onopen = (event) => {
        responseArea.textContent = 'Connecté au serveur WebSocket.';
    };

    socket.onmessage = (event) => {
        responseArea.textContent += `\nMessage du serveur: ${event.data}`;
    };

    socket.onclose = (event) => {
        responseArea.textContent += '\nDéconnecté du serveur WebSocket.';
    };

    socket.onerror = (error) => {
        responseArea.textContent += '\nErreur WebSocket: ' + error.message;
    };

    // Function to handle the display of input text areas
    const handleInputDisplay = () => {
        const selectedOption = document.querySelector('input[name="option"]:checked').value;
        inputGroups.forEach(group => {
            if (group.dataset.option === selectedOption) {
                group.classList.add('active');
            } else {
                group.classList.remove('active');
            }
        });
    };

    // Add event listener to each radio button to switch the active input group
    radioButtons.forEach(radio => {
        radio.addEventListener('change', handleInputDisplay);
    });

    // Set initial display on page load
    handleInputDisplay();

    // Event listener for form submission
    form.addEventListener('submit', (e) => {
        e.preventDefault();

        // Create an object to store all prompts
        const jsonData = {};

        // Loop through all input groups to get each prompt text
        inputGroups.forEach(group => {
            const mode = group.dataset.option;
            const prompt = group.querySelector('textarea').value.trim();
            jsonData[mode] = prompt;
        });

        // Envoyer le JSON via WebSocket
        if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(jsonData));
            responseArea.textContent = `Données envoyées: ${JSON.stringify(jsonData, null, 2)}`;
        } else {
            responseArea.textContent = 'Connexion WebSocket non ouverte. Veuillez réessayer.';
        }
    });
});