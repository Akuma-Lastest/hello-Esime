const socket = io();
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message');
const messagesDiv = document.getElementById('messages');
const uploadForm = document.getElementById('upload-form');
const filesList = document.getElementById('files-list');

function createMessageElement(data) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${data.sender === username ? 'sent' : 'received'}`;
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    const sender = document.createElement('span');
    sender.className = 'message-sender';
    sender.textContent = data.sender === username ? 'Tú' : data.sender;
    
    const text = document.createElement('p');
    text.className = 'message-text';
    text.textContent = data.message;
    
    const time = document.createElement('span');
    time.className = 'message-time';
    time.textContent = data.timestamp;
    
    messageContent.appendChild(sender);
    messageContent.appendChild(text);
    messageContent.appendChild(time);
    messageDiv.appendChild(messageContent);
    
    return messageDiv;
}

messageForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = messageInput.value;
    if (message.trim()) {
        socket.emit('message', { message: message });
        messageInput.value = '';
    }
});

uploadForm.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData();
    const fileInput = document.getElementById('file-input');
    
    if (fileInput.files.length === 0) {
        alert('Por favor selecciona un archivo');
        return;
    }
    
    formData.append('file', fileInput.files[0]);
    
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error al subir el archivo');
    });
});

socket.on('message', (data) => {
    const messageElement = createMessageElement(data);
    messagesDiv.appendChild(messageElement);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
});
