import os
import json
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
import PyPDF2

load_dotenv()

# --- Config ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
BUCKET_NAME = "knowledge_base"

if not all([SUPABASE_URL, SUPABASE_SECRET_KEY, GOOGLE_API_KEY]):
    raise ValueError("Missing required environment variables (SUPABASE_URL, SUPABASE_SECRET_KEY, GOOGLE_API_KEY).")

# --- Clients ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
client = genai.Client(api_key=GOOGLE_API_KEY)

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Basic chunking: splits text into overlapping chunks of roughly `chunk_size` characters."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        
        # Try to break at a newline or space if we aren't at the end of the text
        if end < len(text):
            last_newline = text.rfind('\n', start, end)
            if last_newline != -1 and last_newline > start + chunk_size // 2:
                end = last_newline + 1
            else:
                last_space = text.rfind(' ', start, end)
                if last_space != -1 and last_space > start + chunk_size // 2:
                    end = last_space + 1
                    
        chunks.append(text[start:end].strip())
        start = end - overlap
        if start < 0 or end >= len(text):
            break
            
    return [c for c in chunks if c]

def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    return text

def main():
    print(f"Connecting to Supabase Storage bucket '{BUCKET_NAME}'...")
    
    # 1. Find the PDF file
    files = supabase.storage.from_(BUCKET_NAME).list()
    pdf_files = [f['name'] for f in files if f['name'].endswith('.pdf')]
    
    if not pdf_files:
        print("Error: No PDF files found in the knowledge_base bucket.")
        return
        
    pdf_name = pdf_files[0]
    print(f"Found PDF: {pdf_name}. Downloading...")
    
    # 2. Download PDF to temp file
    pdf_data = supabase.storage.from_(BUCKET_NAME).download(pdf_name)
    temp_pdf_path = Path(tempfile.gettempdir()) / pdf_name
    temp_pdf_path.write_bytes(pdf_data)
    
    # 3. Extract Text
    print(f"Extracting text from {pdf_name}...")
    text = extract_text_from_pdf(str(temp_pdf_path))
    
    if not text.strip():
        print("Error: Could not extract any text from the PDF.")
        return
        
    # 4. Chunking
    chunks = chunk_text(text)
    print(f"Created {len(chunks)} chunks from the PDF. Generating embeddings...")
    
    # Clear existing knowledge (optional, but good for fresh ingest)
    print("Clearing old knowledge from database...")
    try:
        supabase.table("zryth_knowledge").delete().neq("id", 0).execute()
    except Exception as e:
        print(f"Note: Could not clear old table (might be empty). {e}")
    
    # 5. Ingestion
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
            
        print(f"Processing chunk {i+1}/{len(chunks)}...")
        
        # Generate Embedding
        response = client.models.embed_content(
            model='gemini-embedding-2',
            contents=chunk,
        )
        
        embedding = response.embeddings[0].values
        
        # Upload to Supabase
        data = {
            "content": chunk,
            "embedding": embedding,
            "metadata": {"source": pdf_name, "chunk_index": i}
        }
        
        supabase.table("zryth_knowledge").insert(data).execute()
        
    print(f"Success! {pdf_name} has been fully ingested into the zryth_knowledge vector database.")
    
    # Cleanup
    try:
        temp_pdf_path.unlink()
    except Exception:
        pass

if __name__ == "__main__":
    main()
