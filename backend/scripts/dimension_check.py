import os
from typing import Tuple

from dotenv import load_dotenv
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def _normalize_provider(value: str) -> str:
    return value.strip().lower()


def _build_embeddings(
    provider: str,
    model_name: str | None,
    google_api_key: str | None,
) -> Tuple[Embeddings, str]:
    if provider in {"sentence-transformers", "sentence_transformers", "st"}:
        resolved = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        return SentenceTransformerEmbeddings(model_name=resolved), resolved
    if provider == "gemini":
        if not google_api_key:
            raise SystemExit("GOOGLE_API_KEY is required for Gemini embeddings")
        resolved = model_name or os.getenv(
            "GOOGLE_EMBEDDING_MODEL", "models/embedding-001"
        )
        return (
            GoogleGenerativeAIEmbeddings(
                model=resolved,
                google_api_key=google_api_key,
            ),
            resolved,
        )
    raise SystemExit(f"Unsupported embedding provider: {provider}")


def main() -> None:
    load_dotenv()
    provider = _normalize_provider(
        os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
    )
    model_name = os.getenv("EMBEDDING_MODEL")
    google_api_key = os.getenv("GOOGLE_API_KEY")
    embeddings, resolved = _build_embeddings(provider, model_name, google_api_key)
    vector = embeddings.embed_query("dimension check")
    print(f"Embedding provider: {provider}")
    print(f"Selected model: {resolved}")
    print(f"Dimension: {len(vector)}")


if __name__ == "__main__":
    main()
