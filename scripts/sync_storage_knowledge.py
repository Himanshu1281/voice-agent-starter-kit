import os
import json
import tempfile
from pathlib import Path
import fitz  # PyMuPDF
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai

load_dotenv()

# Setup Supabase
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SECRET_KEY")
if not supabase_url or not supabase_key:
    print("Error: SUPABASE_URL or SUPABASE_SECRET_KEY is missing.")
    exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

# Setup Google Gemini
google_api_key = os.environ.get("GOOGLE_API_KEY")
if not google_api_key:
    print("Error: GOOGLE_API_KEY is missing.")
    exit(1)

ai_client = genai.Client(api_key=google_api_key)

# Constants
BUCKET_NAME = "knowledge_base"
PROCESSED_LOG = Path(__file__).parent.parent / "data" / "processed_knowledge.json"

def get_processed_files() -> set:
    if not PROCESSED_LOG.exists():
        return set()
    try:
        with PROCESSED_LOG.open("r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_processed_file(filename: str):
    processed = get_processed_files()
    processed.add(filename)
    PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PROCESSED_LOG.open("w", encoding="utf-8") as f:
        json.dump(list(processed), f)

def extract_text_from_pdf(filepath: str) -> str:
    print(f"Extracting text from {filepath}...")
    doc = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        i += chunk_size - overlap
    return chunks

def embed_text(text: str) -> list[float]:
    response = ai_client.models.embed_content(
        model='gemini-embedding-2',
        contents=text
    )
    return response.embeddings[0].values

def main():
    print(f"Checking Supabase Storage Bucket: {BUCKET_NAME}")
    
    # Check if bucket exists, if not, print instruction.
    try:
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        if BUCKET_NAME not in bucket_names:
            print(f"\n[WARNING] Bucket '{BUCKET_NAME}' does not exist in Supabase Storage.")
            print(f"Please create a private bucket named '{BUCKET_NAME}' in your Supabase Dashboard.")
            return
    except Exception as e:
        print(f"Error checking buckets: {e}")
        return

    # List files in bucket
    files = supabase.storage.from_(BUCKET_NAME).list()
    processed = get_processed_files()
    
    new_files = [f for f in files if f['name'].endswith('.pdf') and f['name'] not in processed]
    
    if not new_files:
        print("No new PDF files found to process.")
        return
        
    print(f"Found {len(new_files)} new PDF(s). Processing...")
    
    for f in new_files:
        filename = f['name']
        print(f"\n--- Processing {filename} ---")
        
        # Download file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            temp_path = tmp.name
            
        try:
            res = supabase.storage.from_(BUCKET_NAME).download(filename)
            with open(temp_path, "wb") as tmp:
                tmp.write(res)
                
            # Parse text
            raw_text = extract_text_from_pdf(temp_path)
            
            # Chunk it
            chunks = chunk_text(raw_text)
            print(f"Created {len(chunks)} chunks.")
            
            # Embed and insert
            for i, chunk in enumerate(chunks):
                print(f"  Embedding chunk {i+1}/{len(chunks)}...")
                emb = embed_text(chunk)
                
                # Insert into zryth_knowledge
                data = {
                    "content": chunk,
                    "metadata": {"source": filename, "chunk_index": i},
                    "embedding": emb
                }
                supabase.table("zryth_knowledge").insert(data).execute()
                
            print(f"Successfully ingested {filename} into vector database.")
            save_processed_file(filename)
            
        except Exception as e:
            print(f"Error processing {filename}: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    print("\nKnowledge base sync complete.")

if __name__ == "__main__":
    main()
