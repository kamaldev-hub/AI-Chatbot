document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM content loaded');
    const chatMessages = document.getElementById('chatMessages') || console.error('chatMessages element not found');
    const userInput = document.getElementById('userInput') || console.error('userInput element not found');
    const sendButton = document.getElementById('sendButton') || console.error('sendButton element not found');
    const themeButtons = document.querySelectorAll('.theme-button');

    if (themeButtons.length === 0) console.error('No theme buttons found');

    let currentTheme = localStorage.getItem('theme') || 'light';
    let chatId = null;
    let sendInProgress = false;

    function setTheme(theme) {
        console.log(`Setting theme to: ${theme}`);
        document.body.className = theme;
        currentTheme = theme;
        themeButtons.forEach(button => {
            button.classList.toggle('active', button.id === `${theme}Theme`);
        });
        localStorage.setItem('theme', theme);
    }

    themeButtons.forEach(button => {
        button.addEventListener('click', () => {
            console.log(`Theme button clicked: ${button.id}`);
            setTheme(button.id.replace('Theme', ''));
        });
    });

    // Set initial theme
    setTheme(currentTheme);

    function addMessage(text, sender) {
        console.log(`Adding message from ${sender}: ${text}`);
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender === 'user' ? 'user-message' : 'bot-message'}`;

        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="sender-name">${sender === 'user' ? 'You' : 'AI'}</span>
            </div>
            <div class="message-content">${text}</div>
        `;

        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function sendMessage() {
        console.log('sendMessage function called');
        if (sendInProgress) {
            console.log('Send already in progress');
            return;
        }
        sendInProgress = true;

        const message = userInput.value.trim();
        console.log('User input:', message);

        if (message) {
            addMessage(message, 'user');
            userInput.value = '';

            try {
                console.log('Attempting to send message to server');
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message, chat_id: chatId }),
                });

                console.log('Server response status:', response.status);

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                console.log('Parsed response data:', data);
                addMessage(data.response, 'bot');
                chatId = data.chat_id;
            } catch (error) {
                console.error('Error in sendMessage:', error);
                addMessage(`Sorry, there was an error processing your request: ${error.message}`, 'bot');
            } finally {
                sendInProgress = false;
            }
        } else {
            console.log('Empty message, not sending');
            sendInProgress = false;
        }
    }

    console.log('Send button:', sendButton);
    sendButton.addEventListener('click', () => {
        console.log('Send button clicked');
        sendMessage();
    });

    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            console.log('Enter key pressed');
            e.preventDefault();
            sendMessage();
        }
    });

    console.log('Script fully loaded');
});