document.addEventListener('DOMContentLoaded', () => {
    // ... (le definizioni delle costanti iniziali rimangono le stesse)
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');
    const uploadStatus = document.getElementById('upload-status');
    
    const askButton = document.getElementById('ask-button');
    const questionInput = document.getElementById('question-input');
    const chatHistory = document.getElementById('chat-history');

    const generateReportBtn = document.getElementById('generate-report-btn');
    const reportStatus = document.getElementById('report-status');
    const emailSection = document.getElementById('email-section');
    const sendEmailBtn = document.getElementById('send-email-btn');
    const emailRecipientInput = document.getElementById('email-recipient');
    const emailStatus = document.getElementById('email-status');

    const API_URL = 'http://localhost:8000';
    let generatedPdfBlob = null; // <-- Variabile per conservare il PDF generato

    // --- Gestione Upload Documenti (invariato) ---
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        uploadStatus.textContent = 'Caricamento e addestramento in corso...';
        try {
            const response = await fetch(`${API_URL}/upload-document/`, {
                method: 'POST',
                body: formData,
            });
            const result = await response.json();
            if (response.ok) {
                uploadStatus.textContent = `✅ ${result.message}`;
            } else {
                throw new Error(result.detail);
            }
        } catch (error) {
            uploadStatus.textContent = `❌ Errore: ${error.message}`;
        }
    });

    // --- Gestione Chat (invariato) ---
    askButton.addEventListener('click', handleQuery);
    questionInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleQuery();
    });

    async function handleQuery() {
        const question = questionInput.value.trim();
        if (!question) return;
        addMessage(question, 'user-message');
        questionInput.value = '';
        addMessage('Elaborazione...', 'ai-message', true);
        try {
            const response = await fetch(`${API_URL}/query/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question }),
            });
            const result = await response.json();
            updateLastMessage(result.answer);
        } catch (error) {
            updateLastMessage(`Errore nella comunicazione con l'AI: ${error.message}`);
        }
    }

    function addMessage(text, className, isTyping = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', className);
        messageDiv.textContent = text;
        if (isTyping) {
            messageDiv.id = 'typing-indicator';
        }
        chatHistory.appendChild(messageDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
    
    function updateLastMessage(text) {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.textContent = text;
            typingIndicator.id = '';
        }
    }
    
    // --- GESTIONE REPORT E EMAIL (MODIFICATA) ---
    generateReportBtn.addEventListener('click', async () => {
        const chatContent = chatHistory.innerText;
        if (!chatContent.trim()) {
            reportStatus.textContent = 'La chat è vuota. Non posso generare un report.';
            return;
        }

        reportStatus.textContent = 'Generazione del PDF in corso...';
        const htmlContent = `
            <h1>Report di Analisi - Aegis AI</h1>
            <p>Data: ${new Date().toLocaleString('it-IT')}</p>
            <hr>
            <h2>Dialogo e Analisi</h2>
            <pre>${chatContent.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</pre>
        `;

        try {
            // Chiama il nuovo endpoint che restituisce il file binario
            const response = await fetch(`${API_URL}/generate-pdf-binary/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ html_content: htmlContent }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail);
            }

            // Converte la risposta in un Blob (Binary Large Object)
            generatedPdfBlob = await response.blob();
            
            // --- Logica per il download automatico ---
            const url = URL.createObjectURL(generatedPdfBlob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'Report_Aegis_AI.pdf';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url); // Libera la memoria
            a.remove();
            // --- Fine logica download ---

            reportStatus.innerHTML = `✅ Report PDF scaricato con successo.`;
            emailSection.classList.remove('hidden');

        } catch (error) {
            reportStatus.textContent = `❌ Errore PDF: ${error.message}`;
        }
    });

    sendEmailBtn.addEventListener('click', async () => {
        const recipient = emailRecipientInput.value.trim();
        if (!recipient || !generatedPdfBlob) { // Controlla se il blob del PDF esiste
            emailStatus.textContent = 'Inserisci un destinatario e genera prima il PDF.';
            return;
        }

        emailStatus.textContent = 'Invio email in corso...';
        const formData = new FormData();
        formData.append('recipient', recipient);
        formData.append('subject', 'Report di Analisi Strategica - Aegis AI');
        formData.append('body', 'In allegato il report generato dal sistema Aegis AI.');
        // Usa direttamente il blob salvato
        formData.append('pdf_file', generatedPdfBlob, 'Report_Aegis_AI.pdf');
        
        try {
            const response = await fetch(`${API_URL}/send-email/`, {
                method: 'POST',
                body: formData,
            });
            const result = await response.json();

            if (response.ok) {
                emailStatus.textContent = `✅ ${result.message}`;
            } else {
                throw new Error(result.detail);
            }
        } catch (error) {
            emailStatus.textContent = `❌ Errore Email: ${error.message}`;
        }
    });
});
