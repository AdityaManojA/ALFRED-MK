"""
actions/doc_rag.py — Local Document RAG with ChromaDB and nomic-embed-text-v1.5

Provides semantic vector search across local PDFs, TXT, DOCX, and MD files
in Desktop and Documents directories using local embeddings.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import json

# Lazy-loaded dependencies to avoid heavy startup overhead (PyTorch, ChromaDB, Transformers)
chromadb = None
Settings = None
SentenceTransformer = None
Observer = None
FileSystemEventHandler = None

# Tokenizer for chunking (we'll use the sentence-transformers tokenizer)
# We'll load the model and use its tokenizer

# Local imports
from core.path_guard import check_path_access, get_allowed_c_roots, is_heavenly_restricted
# We might also want to use file_processor for text extraction
from actions.file_processor import file_processor

# Constants
CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50
EMBEDDING_MODEL_NAME = "nomic-embed-text-v1.5"  # or a local path
CHROMA_DB_PATH = str(Path("memory") / "vector_db")
COLLECTION_NAME = "alfred_local_docs"

# Global variables (initialized on first use)
_chroma_client = None
_collection = None
_embedding_model = None
_observer = None


def _init_chroma():
    """Initialize ChromaDB client and collection."""
    global _chroma_client, _collection, chromadb
    if chromadb is None:
        try:
            import chromadb
        except ImportError:
            raise ImportError("chromadb is not installed. Please install with: pip install chromadb")

    # Ensure the directory exists
    Path(CHROMA_DB_PATH).mkdir(parents=True, exist_ok=True)

    _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    # Try to get existing collection, or create new
    try:
        _collection = _chroma_client.get_collection(name=COLLECTION_NAME)
    except Exception:
        _collection = _chroma_client.create_collection(name=COLLECTION_NAME)
    return _collection


def _init_embedding_model():
    """Initialize the sentence-transformers embedding model."""
    global _embedding_model, SentenceTransformer
    if SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("sentence-transformers is not installed. Please install with: pip install sentence-transformers")

    _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def _get_chroma_collection():
    """Get or initialize the ChromaDB collection."""
    if _collection is None:
        return _init_chroma()
    return _collection


def _get_embedding_model():
    """Get or initialize the embedding model."""
    if _embedding_model is None:
        return _init_embedding_model()
    return _embedding_model


def _tokenize_text(text: str) -> List[int]:
    """Tokenize text using the embedding model's tokenizer."""
    model = _get_embedding_model()
    return model.tokenizer.encode(text, add_special_tokens=False)


def _detokenize_tokens(tokens: List[int]) -> str:
    """Convert tokens back to text."""
    model = _get_embedding_model()
    return model.tokenizer.decode(tokens, skip_special_tokens=True)


def _chunk_text(text: str) -> List[str]:
    """
    Split text into chunks of CHUNK_SIZE_TOKENS tokens with CHUNK_OVERLAP_TOKENS overlap.
    Returns list of text chunks.
    """
    if not text.strip():
        return []

    tokens = _tokenize_text(text)
    if len(tokens) == 0:
        return []

    chunks = []
    start = 0
    while start < len(tokens):
        end = start + CHUNK_SIZE_TOKENS
        chunk_tokens = tokens[start:end]
        chunk_text = _detokenize_tokens(chunk_tokens)
        chunks.append(chunk_text)
        start += CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS
        if start >= len(tokens):
            break
    return chunks


def _extract_text_from_file(file_path: Path) -> Optional[str]:
    """Extract text from a file using appropriate libraries."""
    try:
        suffix = file_path.suffix.lower()
        if suffix in ['.txt', '.md', '.rst', '.log']:
            return file_path.read_text(encoding='utf-8', errors='ignore')
        elif suffix == '.pdf':
            # Try pdfplumber first, then PyPDF2
            text = ""
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text += (page.extract_text() or "") + "\n"
            except ImportError:
                try:
                    import PyPDF2
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        for page in reader.pages:
                            text += page.extract_text() or ""
                except ImportError:
                    pass
            return text.strip() if text else None
        elif suffix in ['.docx', '.doc']:
            try:
                from docx import Document
                doc = Document(file_path)
                return "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                pass
        # Add more types if needed
        return None
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return None


def _index_file(file_path: Path) -> int:
    """
    Index a single file: extract text, chunk, embed, and store in ChromaDB.
    Returns number of chunks indexed.
    """
    # Check if the file is allowed
    ok, msg = check_path_access(file_path)
    if not ok:
        print(f"Skipping {file_path}: {msg}")
        return 0

    # Extract text
    text = _extract_text_from_file(file_path)
    if text is None or not text.strip():
        print(f"No text extracted from {file_path}")
        return 0

    # Chunk the text
    chunks = _chunk_text(text)
    if not chunks:
        print(f"No chunks generated from {file_path}")
        return 0

    # Get embedding model and compute embeddings
    model = _get_embedding_model()
    embeddings = model.encode(chunks, show_progress_bar=False)

    # Prepare data for ChromaDB
    collection = _get_chroma_collection()
    ids = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{file_path}_{i}"
        ids.append(chunk_id)
        metadatas.append({
            "source": str(file_path),
            "chunk_index": i,
            "text": chunk  # Store the text for retrieval? ChromaDB can store metadata, but text is large.
                         # We'll store the text in metadata so we can return it directly.
                         # Alternatively, we can store the text in the document and embeddings separately.
                         # ChromaDB stores the document text and embeddings. We'll set the document to the chunk.
                         # Then we don't need to store text in metadata.
        })

    # Add to collection
    # ChromaDB's add method: ids, embeddings, metadatas, documents
    # We'll set documents=chunks
    try:
        collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            documents=chunks  # store the chunk text as the document
        )
        print(f"Indexed {file_path}: {len(chunks)} chunks")
        return len(chunks)
    except Exception as e:
        print(f"Error adding to ChromaDB for {file_path}: {e}")
        return 0


def _should_index_file(file_path: Path) -> bool:
    """Determine if a file should be indexed based on extension and size."""
    # Skip binary/executable files and large files
    # We'll check extension and size
    skip_extensions = {
        '.exe', '.dll', '.so', '.bin', '.image', '.iso', '.zip', '.rar', '.7z', '.tar', '.gz',
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg', '.ico',
        '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.wav', '.ogg', '.flac', '.aac',
        '.pdf',  # we actually want to index PDFs, so remove from skip
        # We'll handle PDFs separately
    }
    # Actually, we want to index PDFs, TXT, MD, DOCX
    # Let's define allowed extensions
    allowed_extensions = {'.txt', '.md', '.pdf', '.docx', '.doc'}
    if file_path.suffix.lower() not in allowed_extensions:
        return False

    # Check file size (skip if > 25MB)
    try:
        file_size = file_path.stat().st_size
        if file_size > 25 * 1024 * 1024:  # 25MB
            return False
    except Exception:
        return False

    return True


def crawl_and_index():
    """Crawl the allowed Desktop and Documents directories and index all files."""
    print("Starting crawl and index of Desktop and Documents...")
    allowed_roots = get_allowed_c_roots()
    total_files = 0
    total_chunks = 0
    for root in allowed_roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip heavenly restricted directories
            # We'll check each directory to see if it's under heavenly restriction
            # We can modify dirnames in-place to skip restricted dirs
            # But we'll just check each file
            for fname in filenames:
                file_path = Path(dirpath) / fname
                if _should_index_file(file_path):
                    chunks = _index_file(file_path)
                    if chunks > 0:
                        total_files += 1
                        total_chunks += chunks
    print(f"Indexing complete. Indexed {total_files} files, {total_chunks} chunks.")
    return total_files, total_chunks


class _ChangeHandler(FileSystemEventHandler if FileSystemEventHandler else object):
    """Handle file system events for auto-update."""
    def on_created(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            if _should_index_file(file_path):
                print(f"File created: {file_path}")
                _index_file(file_path)

    def on_modified(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            if _should_index_file(file_path):
                print(f"File modified: {file_path}")
                # We need to update the index: remove old chunks and add new ones
                # For simplicity, we'll delete by source and re-index
                _delete_file_chunks(file_path)
                _index_file(file_path)

    def on_deleted(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            print(f"File deleted: {file_path}")
            _delete_file_chunks(file_path)


def _delete_file_chunks(file_path: Path):
    """Delete all chunks associated with a file from the collection."""
    try:
        collection = _get_chroma_collection()
        # Query for all chunks with this source
        results = collection.get(where={"source": str(file_path)})
        if results['ids']:
            collection.delete(ids=results['ids'])
            print(f"Deleted {len(results['ids'])} chunks for {file_path}")
    except Exception as e:
        print(f"Error deleting chunks for {file_path}: {e}")


def start_watchdog():
    """Start watching the Desktop and Documents directories for changes."""
    global _observer, Observer, FileSystemEventHandler
    if Observer is None:
        try:
            from watchdog.observers import Observer as _Obs
            from watchdog.events import FileSystemEventHandler as _FSEH
            Observer = _Obs
            FileSystemEventHandler = _FSEH
        except ImportError:
            print("Watchdog not installed. Skipping auto-update.")
            return
    _observer = Observer()
    handler = _ChangeHandler()
    allowed_roots = get_allowed_c_roots()
    for root in allowed_roots:
        if root.exists():
            _observer.schedule(handler, str(root), recursive=True)
    _observer.start()
    print("Watchdog started for auto-update.")


def stop_watchdog():
    """Stop the watchdog observer."""
    global _observer
    if _observer is not None:
        _observer.stop()
        _observer.join()
        _observer = None
        print("Watchdog stopped.")


def search_local_docs(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Search for local documents similar to the query.
    Returns a list of dictionaries with keys: 'text', 'source', 'score'.
    """
    try:
        collection = _get_chroma_collection()
        model = _get_embedding_model()
        query_embedding = model.encode([query])[0]
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k
        )
        # Format results
        formatted = []
        if results['ids'] and len(results['ids']) > 0:
            for i in range(len(results['ids'][0])):
                formatted.append({
                    "text": results['documents'][0][i],
                    "source": results['metadatas'][0][i]['source'],
                    "score": results['distances'][0][i]  # ChromaDB returns distance, lower is better
                })
        return formatted
    except Exception as e:
        print(f"Error searching local docs: {e}")
        return []


# If this script is run directly, perform indexing and start watchdog
if __name__ == "__main__":
    # Initialize
    try:
        _init_chroma()
        _init_embedding_model()
    except ImportError as e:
        print(f"Failed to initialize: {e}")
        sys.exit(1)

    # Index existing files
    crawl_and_index()

    # Start watchdog for auto-update
    start_watchdog()

    try:
        # Keep the script running
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_watchdog()