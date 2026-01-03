import os
import re
import hashlib
import uuid
from datetime import datetime
import io
from urllib.parse import urlparse

from azure.core.credentials import AzureNamedKeyCredential
from azure.data.tables import TableServiceClient, TableClient, UpdateMode
from azure.storage.blob import BlobServiceClient
from PyPDF2 import PdfReader

from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_core.prompts import ChatPromptTemplate

# ========= Azure Table Storage ===========

TABLE_ACCOUNT_NAME = "mystorageetudiant2"
TABLE_ACCOUNT_KEY  = " "
USERS_TABLE_NAME   = "Users"
DOCS_TABLE_NAME    = "Documents"
QUESTIONS_TABLE_NAME = "Questions"

cred = AzureNamedKeyCredential(name=TABLE_ACCOUNT_NAME, key=TABLE_ACCOUNT_KEY)
table_service = TableServiceClient(
    endpoint=f"https://{TABLE_ACCOUNT_NAME}.table.core.windows.net",
    credential=cred
)

def ensure_tables() -> None:
    for name in [USERS_TABLE_NAME, DOCS_TABLE_NAME, QUESTIONS_TABLE_NAME]:
        try:
            table_service.create_table(name)
        except Exception:
            pass

ensure_tables()
users_table: TableClient = table_service.get_table_client(USERS_TABLE_NAME)
documents_table: TableClient = table_service.get_table_client(DOCS_TABLE_NAME)
questions_table: TableClient = table_service.get_table_client(QUESTIONS_TABLE_NAME)

#  Azure Blob Storage  

BLOB_ACCOUNT_NAME = "mystorageetudiant2"
BLOB_ACCOUNT_KEY  =  "  "
BLOB_CONTAINER    = "container1"

blob_service = BlobServiceClient(
    account_url=f"https://{BLOB_ACCOUNT_NAME}.blob.core.windows.net",
    credential=BLOB_ACCOUNT_KEY
)

def upload_pdf_blob(user_id: str, file_name: str, file_bytes: bytes):
    container_client = blob_service.get_container_client(BLOB_CONTAINER)
    try:
        container_client.create_container()
    except Exception:
        pass
    blob_name = f"{user_id}/{file_name}"
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(file_bytes, overwrite=True)
    return blob_client.url

def get_blob_size_from_url(blob_url: str) -> int:
    try:
        parsed = urlparse(blob_url)
        path = parsed.path.lstrip('/')  # container/blobpath
        if not path:
            return 0
        parts = path.split('/', 1)
        container = parts[0]
        blob_path = parts[1] if len(parts) > 1 else ''
        if not blob_path:
            return 0
        blob_client = blob_service.get_blob_client(container=container, blob=blob_path)
        props = blob_client.get_blob_properties()
        return int(getattr(props, 'size', 0))
    except Exception:
        return 0

# ============== Utils Users ==============

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(email: str, password: str):
    try:
        _ = users_table.get_entity(partition_key="users", row_key=email)
        return False, "Utilisateur déjà existant"
    except Exception:
        existing = list(users_table.list_entities(filter="PartitionKey eq 'users'"))
        user_id = str(len(existing) + 1)
        users_table.create_entity({
            "PartitionKey": "users",
            "RowKey": email,
            "PasswordHash": hash_password(password),
            "UserID": user_id
        })
        return True, "Inscription réussie"

def login_user(email: str, password: str):
    try:
        entity = users_table.get_entity(partition_key="users", row_key=email)
        if entity["PasswordHash"] == hash_password(password):
            return True, entity["UserID"]
        return False, None
    except Exception:
        return False, None

# ============ Utils Documents ============

def create_document_row(user_id: str, file_name: str, blob_url: str, index_name: str, status: str = "indexing", file_size_bytes: int | None = None):
    doc_id = uuid.uuid4().hex[:10]
    entity = {
        "PartitionKey": user_id,
        "RowKey": doc_id,
        "FileName": file_name,
        "BlobURL": blob_url,
        "IndexName": index_name,
        "UploadDate": datetime.utcnow().isoformat() + "Z",
        "Status": status
    }
    if file_size_bytes is not None:
        entity["FileSize"] = int(file_size_bytes)
    documents_table.create_entity(entity)
    return doc_id

def update_document_status(user_id: str, doc_id: str, status: str):
    entity = documents_table.get_entity(partition_key=user_id, row_key=doc_id)
    entity["Status"] = status
    documents_table.update_entity(entity, mode=UpdateMode.MERGE)

def list_user_documents(user_id: str):
    return list(documents_table.list_entities(filter=f"PartitionKey eq '{user_id}'"))

def get_doc_by_filename(user_id: str, file_name: str):
    docs = list_user_documents(user_id)
    for d in docs:
        if d.get("FileName") == file_name:
            return d
    return None

def delete_document(user_id: str, doc_id: str):
    try:
        documents_table.delete_entity(partition_key=user_id, row_key=doc_id)
    except Exception:
        pass

def cleanup_orphaned_documents(user_id: str):
    """Nettoie les documents qui n'existent plus dans Azure Storage."""
    try:
        docs = list_user_documents(user_id)
        cleaned_count = 0
        
        for doc in docs:
            blob_url = doc.get("BlobURL")
            if blob_url:
                try:
                    size = get_blob_size_from_url(blob_url)
                    if size == 0:  # Le blob n'existe plus
                        documents_table.delete_entity(
                            partition_key=doc["PartitionKey"], 
                            row_key=doc["RowKey"]
                        )
                        cleaned_count += 1
                except Exception:
                    documents_table.delete_entity(
                        partition_key=doc["PartitionKey"], 
                        row_key=doc["RowKey"]
                    )
                    cleaned_count += 1
        
        return cleaned_count
    except Exception as e:
        print(f"Erreur lors du nettoyage: {e}")
        return 0

# =============== RAG Utils ===============

def extract_text_from_pdf_bytes(file_bytes) -> str:
    bio = io.BytesIO(file_bytes)
    reader = PdfReader(bio)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text += page_text + "\n"
    return text

# Azure embeddings config
AZURE_EMBEDDINGS_ENDPOINT = "https://ftopenaiservice.openai.azure.com/"
AZURE_EMBEDDINGS_API_KEY  = " "
AZURE_EMBEDDINGS_DEPLOYMENT = "text-embedding-3-large"
AZURE_EMBEDDINGS_API_VERSION = "2024-02-01"

def get_embeddings():
    """Toujours utiliser Azure embeddings."""
    return AzureOpenAIEmbeddings(
        azure_endpoint=AZURE_EMBEDDINGS_ENDPOINT,
        api_key=AZURE_EMBEDDINGS_API_KEY,
        deployment=AZURE_EMBEDDINGS_DEPLOYMENT,
        model="text-embedding-3-large",
        api_version=AZURE_EMBEDDINGS_API_VERSION
    )

# Cognitive Search
AZURE_SEARCH_ENDPOINT = "https://ftsearch.search.windows.net"
AZURE_SEARCH_KEY      = " "

def create_index_and_ingest(text: str, index_name: str):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(text)
    embeddings = get_embeddings()
    vector_store = AzureSearch(
        azure_search_endpoint=AZURE_SEARCH_ENDPOINT,
        azure_search_key=AZURE_SEARCH_KEY,
        index_name=index_name,
        embedding_function=embeddings
    )
    vector_store.add_texts(chunks)

def load_vector_store(index_name: str):
    embeddings = get_embeddings()
    return AzureSearch(
        azure_search_endpoint=AZURE_SEARCH_ENDPOINT,
        azure_search_key=AZURE_SEARCH_KEY,
        index_name=index_name,
        embedding_function=embeddings
    )

AZURE_OPENAI_ENDPOINT = "https://ftopenaiservice.openai.azure.com/"
AZURE_OPENAI_API_KEY  = " "
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_DEPLOYMENT_NAME    = "gpt-4o-mini"

def build_qa_chain(index_name: str, streaming: bool = False):
    vector_store = load_vector_store(index_name)
    retriever = vector_store.as_retriever()

    # Toujours Azure ChatOpenAI avec gpt-4o-mini
    llm = AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        deployment_name=AZURE_DEPLOYMENT_NAME,
        temperature=0,
        streaming=streaming,   
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Vous êtes un assistant utile. Utilisez uniquement le contexte fourni pour répondre. "
                   "Si l'information n'est pas dans le contexte, répondez que vous ne savez pas.\n\n"
                   "RÈGLES STRICTES:\n"
                   "- Répondez DIRECTEMENT avec la réponse finale\n"
                   "- N'incluez JAMAIS de section 'thinking', 'réflexion', 'reasoning', 'analysis' ou 'raisonnement'\n"
                   "- Ne commencez pas par 'Let me think', 'Je vais réfléchir', 'First', 'D'abord', etc.\n"
                   "- Allez directement au fait\n"
                   "- Si vous devez analyser, faites-le mentalement et donnez directement le résultat\n\n"
                   "Contexte:\n{context}"),
        ("human", "{input}")
    ])

    document_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(retriever, document_chain)

 
#  Correction "thinking"  
 
def clean_response(response: str) -> str:
    """Nettoie la réponse en supprimant toute trace de réflexion/thinking."""
    if not response:
        return ""
    
    response = re.sub(r"(?is)(thinking:.*?)(answer:|réponse:|$)", r"\2", response)
    response = re.sub(r"(?is)(réflexion:.*?)(answer:|réponse:|$)", r"\2", response)
    response = re.sub(r"(?is)(reasoning:.*?)(answer:|réponse:|$)", r"\2", response)
    response = re.sub(r"(?is)(analysis:.*?)(answer:|réponse:|$)", r"\2", response)

    response = re.sub(r"(?i)(^|\n)(réponse:|answer:)", "", response)
    return response.strip()

def stream_qa_response(index_name: str, question: str):
    """Générateur pour le streaming de la réponse RAG, sans la partie 'thinking'."""
    try:
        qa_chain = build_qa_chain(index_name, streaming=True)
        
        for chunk in qa_chain.astream({"input": question}):
            if "answer" in chunk:
                cleaned_chunk = clean_response(chunk["answer"])
                if cleaned_chunk:
                    yield cleaned_chunk
    except Exception as e:
        yield f"Erreur: {str(e)}"

#   Questions History  

def add_question_history(user_id: str, file_name: str, question: str, answer: str):
    qid = uuid.uuid4().hex[:12]
    questions_table.create_entity({
        "PartitionKey": user_id,
        "RowKey": qid,
        "FileName": file_name,
        "Question": question,
        "Answer": answer,
        "AskedAt": datetime.utcnow().isoformat() + "Z",
    })

def list_questions_history(user_id: str):
    questions = list(questions_table.list_entities(filter=f"PartitionKey eq '{user_id}'"))
    def get_timestamp(question):
        timestamp = question.get('AskedAt') or question.get('Timestamp')
        if timestamp:
            try:
                from datetime import datetime
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                pass
        return datetime.min
    questions.sort(key=get_timestamp, reverse=True)
    return questions

def delete_questions_for_user(user_id: str) -> int:
    try:
        entities = list(questions_table.list_entities(filter=f"PartitionKey eq '{user_id}'"))
        count = 0
        for ent in entities:
            try:
                pk = ent.get("PartitionKey", user_id)
                rk = ent.get("RowKey")
                if rk:
                    questions_table.delete_entity(partition_key=pk, row_key=rk, etag='*')
                count += 1
            except Exception:
                pass
        return count
    except Exception:
        return 0

def delete_question(user_id: str, question_id: str) -> bool:
    try:
        ent = questions_table.get_entity(partition_key=user_id, row_key=question_id)
        pk = ent.get("PartitionKey", user_id)
        rk = ent.get("RowKey", question_id)
        questions_table.delete_entity(partition_key=pk, row_key=rk, etag='*')
        return True
    except Exception:
        return False

def delete_question_by_keys(partition_key: str, row_key: str) -> bool:
    try:
        questions_table.delete_entity(partition_key=partition_key, row_key=row_key, etag='*')
        return True
    except Exception:
        return False
