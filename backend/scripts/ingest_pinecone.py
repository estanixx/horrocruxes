import hashlib
import os
import tempfile
import time
from typing import Iterable, Tuple

import boto3
from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted
from langchain_community.document_loaders import CSVLoader, PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings as SentenceTransformerEmbeddings
import torch
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai._common import GoogleGenerativeAIError
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from tqdm import tqdm

load_dotenv()

def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _normalize_provider(value: str) -> str:
    return value.strip().lower()


def _build_embeddings(
    provider: str,
    model_name: str | None,
    google_api_key: str | None,
) -> Tuple[Embeddings, str]:
    if provider in {"sentence-transformers", "sentence_transformers", "st"}:
        resolved = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        device = os.getenv("EMBEDDING_DEVICE", "cpu")
        return (
            SentenceTransformerEmbeddings(
                model_name=resolved,
                model_kwargs={"device": device},
            ),
            resolved,
        )
    if provider == "gemini":
        if not google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is required for Gemini embeddings")
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
    raise RuntimeError(f"Unsupported embedding provider: {provider}")


def _filter_documents(documents: Iterable[Document]) -> list[Document]:
    filtered: list[Document] = []
    for doc in documents:
        content = (doc.page_content or "").strip()
        if not content:
            continue
        doc.page_content = content
        filtered.append(doc)
    return filtered


def main() -> None:
    pinecone_api_key = _env("PINECONE_API_KEY")
    pinecone_index = _env("PINECONE_INDEX", "horrocruxes-index")
    aws_region = _env("AWS_REGION", "us-east-1")
    s3_bucket = _env("S3_BUCKET", "horrocruxes-data")
    s3_pdf_prefix = _env("S3_PDF_PREFIX", "data/books")
    s3_csv_prefix = _env("S3_CSV_PREFIX", "data/structured")
    embedding_provider = _normalize_provider(
        os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
    )
    embedding_model = os.getenv("EMBEDDING_MODEL")
    batch_size = int(os.getenv("INGEST_BATCH_SIZE", "25"))
    retry_max = int(os.getenv("INGEST_RETRY_MAX", "5"))
    retry_base_seconds = float(os.getenv("INGEST_RETRY_BASE_SECONDS", "5"))

    google_api_key = os.getenv("GOOGLE_API_KEY")
    embeddings, resolved_model = _build_embeddings(
        embedding_provider,
        embedding_model,
        google_api_key,
    )
    pc = Pinecone(api_key=pinecone_api_key)
    index = pc.Index(pinecone_index)
    vector_store = PineconeVectorStore(index=index, embedding=embeddings)

    s3 = boto3.client("s3", region_name=aws_region)

    def _load_pdf_documents() -> list:
        response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=s3_pdf_prefix)
        keys = [
            item["Key"]
            for item in response.get("Contents", [])
            if item["Key"].endswith(".pdf")
        ]
        documents = []
        for key in keys:
            obj = s3.get_object(Bucket=s3_bucket, Key=key)
            data = obj["Body"].read()
            with tempfile.TemporaryDirectory() as temp_dir:
                local_path = os.path.join(temp_dir, os.path.basename(key))
                with open(local_path, "wb") as handle:
                    handle.write(data)
                loader = PyPDFLoader(local_path)
                documents.extend(loader.load())
        return documents

    def _load_csv_documents() -> list:
        response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=s3_csv_prefix)
        keys = [
            item["Key"]
            for item in response.get("Contents", [])
            if item["Key"].endswith(".csv")
        ]
        documents = []
        for key in keys:
            obj = s3.get_object(Bucket=s3_bucket, Key=key)
            data = obj["Body"].read()
            with tempfile.TemporaryDirectory() as temp_dir:
                local_path = os.path.join(temp_dir, os.path.basename(key))
                with open(local_path, "wb") as handle:
                    handle.write(data)
                loader = CSVLoader(local_path)
                documents.extend(loader.load())
        return documents

    documents = _filter_documents(_load_pdf_documents() + _load_csv_documents())
    if not documents:
        raise RuntimeError("No documents found in S3 prefixes")

    print(f"Embedding provider: {embedding_provider}")
    print(f"Embedding model: {resolved_model}")

    def _doc_id(doc: Document) -> str:
        metadata = doc.metadata or {}
        source = metadata.get("source", "unknown")
        page = metadata.get("page", "unknown")
        content = (doc.page_content or "").strip()
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        return f"{source}:{page}:{digest}"

    doc_ids = [_doc_id(doc) for doc in documents]

    indexed = 0
    skipped = 0
    for i in tqdm(range(0, len(documents), batch_size), desc="Indexing batches"):
        batch_docs = documents[i : i + batch_size]
        batch_ids = doc_ids[i : i + batch_size]
        existing = index.fetch(ids=batch_ids).get("vectors", {})
        to_add_docs = []
        to_add_ids = []
        for doc, doc_id in zip(batch_docs, batch_ids, strict=True):
            if doc_id in existing:
                skipped += 1
                continue
            to_add_docs.append(doc)
            to_add_ids.append(doc_id)
        if to_add_docs:
            attempts = 0
            while True:
                try:
                    vector_store.add_documents(to_add_docs, ids=to_add_ids)
                    indexed += len(to_add_docs)
                    break
                except (ResourceExhausted, GoogleGenerativeAIError) as exc:
                    attempts += 1
                    if attempts > retry_max:
                        raise
                    if isinstance(exc, GoogleGenerativeAIError) and "429" not in str(exc):
                        raise
                    sleep_for = retry_base_seconds * (2 ** (attempts - 1))
                    print(
                        f"Rate limit hit. Sleeping {sleep_for:.1f}s before retry "
                        f"({attempts}/{retry_max})."
                    )
                    time.sleep(sleep_for)

    print(
        f"Indexed {indexed} documents into Pinecone index {pinecone_index}. "
        f"Skipped {skipped} existing documents."
    )


if __name__ == "__main__":
    main()
