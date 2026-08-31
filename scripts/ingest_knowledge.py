import os
import json
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai

load_dotenv()

# --- Config ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not all([SUPABASE_URL, SUPABASE_SECRET_KEY, GOOGLE_API_KEY]):
    raise ValueError("Missing required environment variables (SUPABASE_URL, SUPABASE_SECRET_KEY, GOOGLE_API_KEY).")

# --- Clients ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
client = genai.Client(api_key=GOOGLE_API_KEY)

DATA_FILE = Path(__file__).parent.parent / "data" / "knowledge.txt"

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

def main():
    if not DATA_FILE.exists():
        print(f"Error: {DATA_FILE} not found.")
        return

    print("Reading knowledge base...")
    text = DATA_FILE.read_text(encoding="utf-8")
    chunks = chunk_text(text)
    
    print(f"Created {len(chunks)} chunks. Generating embeddings...")
    
    # We will upload them one by one for simplicity
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
            
        print(f"Processing chunk {i+1}/{len(chunks)}...")
        
        # 1. Generate Embedding
        response = client.models.embed_content(
            model='gemini-embedding-2',
            contents=chunk,
        )
        
        embedding = response.embeddings[0].values
        
        # 2. Upload to Supabase
        data = {
            "content": chunk,
            "embedding": embedding,
            "metadata": {"source": "knowledge.txt", "chunk_index": i}
        }
        
        supabase.table("zryth_knowledge").insert(data).execute()
        
    print("Ingestion complete!")

if __name__ == "__main__":
    main()
