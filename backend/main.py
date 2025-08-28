import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

from weasyprint import HTML
from dotenv import load_dotenv

# NUOVI IMPORT PER LA CONNESSIONE AL DB
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# --- Configurazione Iniziale ---
app = FastAPI(title="Aegis AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Percorsi per i dati persistenti
DOCUMENTS_DIR = "/app/documents_storage"
VECTOR_STORE_PATH = "/app/vector_store/aegis_index"

# --- NUOVA FUNZIONE: VERIFICA E CREAZIONE DATABASE ---
def check_and_create_db():
    db_name = os.getenv("POSTGRES_DB")
    db_user = os.getenv("POSTGRES_USER")
    db_password = os.getenv("POSTGRES_PASSWORD")
    db_host = "database" # Nome del servizio nel docker-compose

    # Connessione al server PostgreSQL (usando il db di default 'postgres')
    engine_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:5432/postgres"
    
    retries = 5
    while retries > 0:
        try:
            engine = create_engine(engine_url)
            with engine.connect() as connection:
                print("✅ Connessione a PostgreSQL riuscita.")
                
                # Verifica esistenza DB
                db_exists_query = text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
                result = connection.execute(db_exists_query).scalar()
                
                if not result:
                    print(f"Database '{db_name}' non trovato. Creazione in corso...")
                    # 'CREATE DATABASE' non può essere eseguito in una transazione, quindi isoliamo la connessione
                    connection.connection.set_isolation_level(0)
                    create_db_query = text(f"CREATE DATABASE {db_name}")
                    connection.execute(create_db_query)
                    connection.connection.set_isolation_level(1)
                    print(f"✅ Database '{db_name}' creato con successo.")
                else:
                    print(f"Database '{db_name}' già esistente.")
            break # Esce dal ciclo se la connessione ha successo
        except OperationalError as e:
            print(f"❌ PostgreSQL non è ancora pronto... Riprovo tra 5 secondi. (Tentativi rimasti: {retries-1})")
            retries -= 1
            time.sleep(5)
            if retries == 0:
                print("❌ Impossibile connettersi a PostgreSQL dopo diversi tentativi.")
                raise e

# --- Modelli Dati Pydantic ---
class QueryRequest(BaseModel):
    question: str

class ReportRequest(BaseModel):
    html_content: str

# --- Logica AI (LangChain) ---
# ... (questa parte rimane invariata)
vector_store = None
conversation_chain = None

def initialize_ai_components():
    """Inizializza o carica il vector store e la catena conversazionale."""
    global vector_store, conversation_chain
    try:
        if os.path.exists(VECTOR_STORE_PATH):
            print("Caricamento Vector Store esistente...")
            embeddings = OpenAIEmbeddings()
            vector_store = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
            print("Vector Store caricato.")
        else:
            print("Nessun Vector Store trovato. In attesa di upload documenti.")
            return

        llm = ChatOpenAI(model_name="gpt-4", temperature=0)
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        conversation_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vector_store.as_retriever(),
            memory=memory
        )
        print("Catena conversazionale pronta.")

    except Exception as e:
        print(f"Errore durante l'inizializzazione AI: {e}")

@app.on_event("startup")
def on_startup():
    if not os.getenv("OPENAI_API_KEY"):
        print("ATTENZIONE: La variabile d'ambiente OPENAI_API_KEY non è impostata!")
    
    # Esegue il controllo del database all'avvio
    check_and_create_db()
    
    initialize_ai_components()

# --- Endpoint API ---

@app.post("/upload-document/")
async def upload_document(file: UploadFile = File(...)):
    # ... (questo endpoint rimane invariato)
    global vector_store, conversation_chain
    file_path = os.path.join(DOCUMENTS_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)
        embeddings = OpenAIEmbeddings()
        if vector_store:
            vector_store.add_documents(chunks)
        else:
            vector_store = FAISS.from_documents(chunks, embeddings)
        vector_store.save_local(VECTOR_STORE_PATH)
        initialize_ai_components()
        return {"status": "success", "filename": file.filename, "message": "Base di conoscenza aggiornata."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nell'elaborazione del file: {e}")


@app.post("/query/")
async def handle_query(request: QueryRequest):
    # ... (questo endpoint rimane invariato)
    if not conversation_chain:
        raise HTTPException(status_code=400, detail="Il sistema non è pronto. Carica prima un documento.")
    try:
        response = conversation_chain.invoke({"question": request.question})
        return {"answer": response["answer"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINT PDF MODIFICATO ---
@app.post("/generate-pdf-binary/")
async def generate_pdf_binary(request: ReportRequest):
    """Genera un PDF da un contenuto HTML e lo restituisce come file binario."""
    try:
        pdf_bytes = HTML(string=request.html_content).write_pdf()
        
        headers = {
            'Content-Disposition': 'attachment; filename="Report_Aegis_AI.pdf"'
        }
        
        return Response(content=pdf_bytes, media_type='application/pdf', headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nella generazione del PDF: {e}")


@app.post("/send-email/")
async def send_email(
    recipient: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    pdf_file: UploadFile = File(...)
):
    # ... (questo endpoint rimane invariato)
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv("SMTP_USER")
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        pdf_content = await pdf_file.read()
        part = MIMEApplication(pdf_content, Name=pdf_file.filename)
        part['Content-Disposition'] = f'attachment; filename="{pdf_file.filename}"'
        msg.attach(part)
        server = smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT")))
        server.starttls()
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        server.sendmail(os.getenv("SMTP_USER"), recipient, msg.as_string())
        server.quit()
        return {"status": "success", "message": f"Email inviata a {recipient}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nell'invio dell'email: {e}")
