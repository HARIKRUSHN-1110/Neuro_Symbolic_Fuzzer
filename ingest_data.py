# ingest_data.py
# This is the script to feed the data into the knowledge base to create the vectordatabase and indexing.
import os
import glob
import time
from tqdm import tqdm 

# LangChain Imports
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter, Language
from langchain_huggingface import HuggingFaceEmbeddings 
from langchain_chroma import Chroma 

# Configuration
DATA_DIR = "ADASdata"
DB_DIR = "chroma_db"
EMBEDDING_MODEL = "all-mpnet-base-v2"
BATCH_SIZE = 50 

def load_documents(data_path: str):
    docs = []
    print(f"--- Scanning {data_path} ---")

    # Loading Python Code
    py_files = glob.glob(os.path.join(data_path, "**/*.py"), recursive=True)
    print(f"Found {len(py_files)} Python files.")
    for f in py_files:
        if "scenariogeneration" in f or "examples" in f:
            try:
                loader = TextLoader(f, encoding='utf-8')
                docs.extend(loader.load())
            except Exception:
                pass

    # Loading XML Files
    xosc_files = glob.glob(os.path.join(data_path, "**/*.xosc"), recursive=True)
    print(f"Found {len(xosc_files)} XOSC files.")
    for f in xosc_files:
        try:
            loader = TextLoader(f, encoding='utf-8')
            xosc_docs = loader.load()
            for d in xosc_docs:
                d.metadata["type"] = "template"
            docs.extend(xosc_docs)
        except Exception:
            pass

    # Loading PDFs
    pdf_files = glob.glob(os.path.join(data_path, "**/*.pdf"), recursive=True)
    print(f"Found {len(pdf_files)} PDF manuals.")
    for f in pdf_files:
        try:
            loader = PyPDFLoader(f)
            docs.extend(loader.load())
        except Exception:
            pass
            
    return docs

def create_knowledge_base():
    # Loading Data
    if not os.path.exists(DATA_DIR):
        print(f"ERROR: Folder '{DATA_DIR}' not found.")
        return

    raw_docs = load_documents(DATA_DIR)
    print(f"Loaded {len(raw_docs)} raw documents.")

    # Spliting Data
    print("Splitting text...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    code_splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON, chunk_size=1000, chunk_overlap=100
    )

    final_chunks = []
    for doc in raw_docs:
        source = doc.metadata.get("source", "")
        if source.endswith(".py"):
            final_chunks.extend(code_splitter.split_documents([doc]))
        else:
            final_chunks.extend(text_splitter.split_documents([doc]))

    print(f"Created {len(final_chunks)} chunks to ingest.")

    # Initialize Embedding Model (On CPU to save VRAM/RAM if needed)
    print("Loading Embedding Model...")
    model_kwargs = {'device': 'cpu'} 
    encode_kwargs = {'normalize_embeddings': False}
    embedding_func = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )

    # Process in Batches (The RAM Fix)
    print(f"Ingesting into ChromaDB in batches of {BATCH_SIZE}...")
    
    # Initialize DB connection
    vector_db = Chroma(
        persist_directory=DB_DIR, 
        embedding_function=embedding_func
    )

    total_chunks = len(final_chunks)
    
    # Using tqdm for a progress bar so it's not frozen
    for i in tqdm(range(0, total_chunks, BATCH_SIZE), desc="Processing Batches"):
        batch = final_chunks[i : i + BATCH_SIZE]
        vector_db.add_documents(documents=batch)
        time.sleep(0.05) 

    print(f"\nSUCCESS! Knowledge Base saved to '{DB_DIR}'.")

if __name__ == "__main__":
    create_knowledge_base()