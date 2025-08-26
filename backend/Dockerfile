# Usa un'immagine Python ufficiale come base
FROM python:3.10-slim

# Imposta la cartella di lavoro nel container
WORKDIR /app

# Copia i file dei requisiti e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il codice dell'applicazione
COPY . .

# Esponi la porta su cui gira l'applicazione (es. FastAPI)
EXPOSE 8000

# Comando per avviare l'applicazione quando il container parte
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
