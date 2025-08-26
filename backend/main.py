import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
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

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# --- Configurazione Iniziale ---
app = FastAPI(title="Aegis AI Backend")

# Configura CORS per permettere al frontend di comunicare con il backend
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

# --- Modelli Dati Pydantic ---
class QueryRequest(BaseModel):
    question: str

class ReportRequest(BaseModel):
    html_content: str

class EmailRequest(BaseModel):
    recipient: str
    subject: str
    body: str
    pdf_content: bytes


# --- Logica AI (LangChain) ---
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

        # Crea la catena conversazionale con memoria
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

# Inizializza i componenti AI all'avvio dell'applicazione
@app.on_event("startup")
def on_startup():
    # Per questo esempio, la chiave API di OpenAI va settata come variabile d'ambiente
    # Es. in Linux: export OPENAI_API_KEY='tua_chiave'
    # Docker Compose la può passare dal file .env
    if not os.getenv("OPENAI_API_KEY"):
        print("ATTENZIONE: La variabile d'ambiente OPENAI_API_KEY non è impostata!")
    initialize_ai_components()

# --- Endpoint API ---

@app.post("/upload-document/")
async def upload_document(file: UploadFile = File(...)):
    """Endpoint per caricare un documento PDF e aggiornare la base di conoscenza."""
    global vector_store, conversation_chain
    
    file_path = os.path.join(DOCUMENTS_DIR, file.filename)
    
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        # 1. Carica il PDF
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        # 2. Suddivide il testo in chunks
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)

        # 3. Crea gli embeddings e aggiorna/crea il Vector Store
        embeddings = OpenAIEmbeddings()
        if vector_store:
            vector_store.add_documents(chunks)
        else:
            vector_store = FAISS.from_documents(chunks, embeddings)
        
        vector_store.save_local(VECTOR_STORE_PATH)
        
        # Re-inizializza la catena conversazionale con i nuovi dati
        initialize_ai_components()

        return {"status": "success", "filename": file.filename, "message": "Base di conoscenza aggiornata."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nell'elaborazione del file: {e}")


@app.post("/query/")
async def handle_query(request: QueryRequest):
    """Endpoint per interrogare l'AI."""
    if not conversation_chain:
        raise HTTPException(status_code=400, detail="Il sistema non è pronto. Carica prima un documento.")
    
    try:
        response = conversation_chain.invoke({"question": request.question})
        return {"answer": response["answer"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-pdf/")
async def generate_pdf(request: ReportRequest):
    """Genera un PDF da un contenuto HTML."""
    try:
        pdf_bytes = HTML(string=request.html_content).write_pdf()
        return {
            "status": "success",
            "pdf_content_base64": os.path.basename(pdf_bytes.decode('latin-1')) # Invia in base64
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nella generazione del PDF: {e}")

@app.post("/send-email/")
async def send_email(
    recipient: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    pdf_file: UploadFile = File(...)
):
    """Invia un'email con un report PDF in allegato."""
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv("SMTP_USER")
        msg['To'] = recipient
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Allega il PDF
        pdf_content = await pdf_file.read()
        part = MIMEApplication(pdf_content, Name=pdf_file.filename)
        part['Content-Disposition'] = f'attachment; filename="{pdf_file.filename}"'
        msg.attach(part)
        
        # Connessione e invio
        server = smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT")))
        server.starttls()
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        server.sendmail(os.getenv("SMTP_USER"), recipient, msg.as_string())
        server.quit()
        
        return {"status": "success", "message": f"Email inviata a {recipient}"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nell'invio dell'email: {e}")
