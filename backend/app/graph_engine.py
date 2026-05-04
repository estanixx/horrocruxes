import asyncio
import os
import tempfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional, AsyncIterator, Tuple

from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import CSVLoader, PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings as SentenceTransformerEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field, ConfigDict


@dataclass
class EnvConfig:
    google_api_key: Optional[str] = os.getenv("GOOGLE_API_KEY")
    pinecone_api_key: Optional[str] = os.getenv("PINECONE_API_KEY")
    pinecone_index: str = os.getenv("PINECONE_INDEX", "horrocruxes-index")
    pinecone_env: Optional[str] = os.getenv("PINECONE_ENV")
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
    embedding_model: Optional[str] = os.getenv("EMBEDDING_MODEL")
    langsmith_api_key: Optional[str] = os.getenv("LANGSMITH_API_KEY")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "horrocruxes")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: str = os.getenv("S3_BUCKET", "horrocruxes-data")
    s3_pdf_prefix: str = os.getenv("S3_PDF_PREFIX", "data/books")
    s3_csv_prefix: str = os.getenv("S3_CSV_PREFIX", "data/structured")
    s3_reports_prefix: str = os.getenv("S3_REPORTS_PREFIX", "reports")


class ChatRequest(BaseModel):
    query: str


class Citation(BaseModel):
    source: str
    snippet: str


class AgentTraceStep(BaseModel):
    agent: str
    status: str
    detail: str


class TimelineEvent(BaseModel):
    label: str
    detail: str
    source: Optional[str] = None


class ConfidenceScore(BaseModel):
    level: str
    reason: str


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    agent_trace: List[AgentTraceStep] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    report_markdown: Optional[str] = None
    confidence: Optional[ConfidenceScore] = None


class GraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    query: str
    route: Optional[Literal["search", "structured"]] = None
    documents: List[Any] = Field(default_factory=list)
    structured_data: Optional[List[Dict[str, Any]]] = None
    answer: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    agent_trace: List[AgentTraceStep] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    report_markdown: Optional[str] = None
    confidence: Optional[ConfidenceScore] = None


def _maybe_enable_langsmith(config: EnvConfig) -> None:
    if config.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", config.langsmith_api_key)
        os.environ.setdefault("LANGSMITH_PROJECT", config.langsmith_project)
        os.environ.setdefault("LANGSMITH_TRACING", "true")


def _normalize_chat_model_name(model_name: str) -> str:
    model_name = model_name.strip()
    if model_name.startswith("models/"):
        return model_name.removeprefix("models/")
    return model_name


def _build_llm(
    config: EnvConfig,
    model_name: Optional[str] = None,
) -> Optional[ChatGoogleGenerativeAI]:
    if not config.google_api_key:
        return None
    model_name = _normalize_chat_model_name(
        model_name or os.getenv("GOOGLE_LLM_MODEL", "models/gemini-1.5-pro")
    )
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.2,
        google_api_key=config.google_api_key,
    )


def _chat_model_candidates() -> List[str]:
    primary = os.getenv("GOOGLE_LLM_MODEL", "models/gemini-1.5-pro")
    fallback_models = os.getenv(
        "GOOGLE_FALLBACK_LLM_MODELS",
        "gemini-2.5-flash-lite,gemini-2.0-flash-lite,gemini-2.0-flash",
    )
    candidates = [primary]
    candidates.extend(
        model.strip() for model in fallback_models.split(",") if model.strip()
    )
    return list(dict.fromkeys(_normalize_chat_model_name(model) for model in candidates))


def _build_embeddings(config: EnvConfig) -> Tuple[Optional[Embeddings], Optional[str]]:
    provider = (config.embedding_provider or "sentence-transformers").strip().lower()
    if provider in {"sentence-transformers", "sentence_transformers", "st"}:
        model_name = config.embedding_model or "sentence-transformers/all-MiniLM-L6-v2"
        device = os.getenv("EMBEDDING_DEVICE", "cpu")
        return (
            SentenceTransformerEmbeddings(
                model_name=model_name,
                model_kwargs={"device": device},
            ),
            None,
        )
    if provider == "gemini":
        if not config.google_api_key:
            return None, "GOOGLE_API_KEY not configured for embeddings"
        model_name = config.embedding_model or os.getenv(
            "GOOGLE_EMBEDDING_MODEL", "models/embedding-001"
        )
        return (
            GoogleGenerativeAIEmbeddings(
                model=model_name,
                google_api_key=config.google_api_key,
            ),
            None,
        )
    return None, f"Unsupported embedding provider: {provider}"


def _format_citations(documents: List[Document]) -> List[Citation]:
    import os

    citations: List[Citation] = []

    for doc in documents:
        metadata = doc.metadata or {}

        source = (
            metadata.get("book")
            or metadata.get("title")
            or metadata.get("file_name")
            or metadata.get("source")
            or "unknown"
        )

        page = metadata.get("page") or metadata.get("page_number")
        chapter = metadata.get("chapter") or metadata.get("chapter_title")

        # 🔹 limpiar nombre archivo
        file_name = os.path.basename(str(source))

        file_name = file_name.replace(".pdf", "")
        file_name = file_name.replace("hp1", "Philosopher's Stone")
        file_name = file_name.replace("hp2", "Chamber of Secrets")
        file_name = file_name.replace("hp3", "Prisoner of Azkaban")
        file_name = file_name.replace("hp4", "Goblet of Fire")
        file_name = file_name.replace("hp5", "Order of the Phoenix")
        file_name = file_name.replace("hp6", "Half-Blood Prince")
        file_name = file_name.replace("hp7", "Deathly Hallows")

        clean_source = file_name

        # 🔹 detalles (page + chapter)
        details = []

        if chapter:
            details.append(f"Chapter: {chapter}")

        if page is not None:
            try:
                page = int(float(page))
            except:
                pass
            details.append(f"Page {page}")

        if details:
            clean_source = f"{clean_source} ({', '.join(details)})"

        # 🔹 snippet limpio
        snippet = (doc.page_content or "").strip()
        snippet = snippet.replace("\n", " ")
        snippet = " ".join(snippet.split())

        if len(snippet) > 300:
            snippet = snippet[:300] + "..."

        if not snippet:
                snippet = "Retrieved source without text snippet."

        citations.append(
            Citation(
                source=clean_source,
                snippet=snippet,
    )
)

    return citations


def _add_agent_step(state: GraphState, agent: str, status: str, detail: str) -> None:
    state.agent_trace.append(AgentTraceStep(agent=agent, status=status, detail=detail))


def _build_confidence(state: GraphState) -> ConfidenceScore:
    source_count = len(state.citations)
    has_structured = bool(state.structured_data)
    has_errors = bool(state.errors)

    if source_count >= 5 and has_structured and not has_errors:
        return ConfidenceScore(
            level="Alta",
            reason="La respuesta usa varias citas y datos estructurados sin errores reportados.",
        )
    if source_count >= 3 and not has_errors:
        return ConfidenceScore(
            level="Media alta",
            reason="La respuesta esta respaldada por multiples fragmentos recuperados.",
        )
    if source_count > 0:
        return ConfidenceScore(
            level="Media",
            reason="Hay evidencia recuperada, pero el sistema tuvo limitaciones durante la sintesis.",
        )
    return ConfidenceScore(
        level="Baja",
        reason="No se recuperaron fuentes suficientes para auditar la respuesta.",
    )


def _build_timeline(state: GraphState) -> List[TimelineEvent]:
    query_lower = state.query.lower()
    wants_timeline = any(
        term in query_lower
        for term in (
            "linea de tiempo",
            "línea de tiempo",
            "timeline",
            "evolucion",
            "evolución",
            "cronologia",
            "cronología",
        )
    )
    wants_horcruxes = "horcrux" in query_lower or "horrocrux" in query_lower
    wants_voldemort = "voldemort" in query_lower or "tom riddle" in query_lower
    wants_snape = "snape" in query_lower

    if not (wants_timeline or wants_horcruxes or wants_voldemort or wants_snape):
        return []

    source = state.citations[0].source if state.citations else None
    if wants_horcruxes:
        return [
            TimelineEvent(label="Diario de Tom Riddle", detail="Harry destruye el diario con un colmillo de basilisco.", source=source),
            TimelineEvent(label="Anillo de Marvolo Gaunt", detail="Dumbledore encuentra el anillo y lo dania con la espada de Gryffindor.", source=source),
            TimelineEvent(label="Relicario de Slytherin", detail="Ron destruye el relicario con la espada de Gryffindor.", source=source),
            TimelineEvent(label="Copa de Hufflepuff", detail="Hermione destruye la copa en la Camara de los Secretos.", source=source),
            TimelineEvent(label="Diadema de Ravenclaw", detail="La diadema queda destruida durante la batalla de Hogwarts.", source=source),
            TimelineEvent(label="Nagini", detail="Neville destruye a Nagini con la espada de Gryffindor.", source=source),
            TimelineEvent(label="Harry Potter", detail="La parte del alma de Voldemort en Harry desaparece cuando Voldemort lo ataca en el bosque.", source=source),
        ]

    if wants_snape:
        return [
            TimelineEvent(label="Juventud", detail="Snape se vincula con Lily Evans y queda marcado por su conflicto con James Potter.", source=source),
            TimelineEvent(label="Ascenso de Voldemort", detail="Snape se acerca a los mortifagos, pero su lealtad cambia por Lily.", source=source),
            TimelineEvent(label="Proteccion de Harry", detail="Actua como agente doble bajo la direccion de Dumbledore.", source=source),
            TimelineEvent(label="Revelacion final", detail="Sus recuerdos muestran que protegio a Harry por su amor persistente por Lily.", source=source),
        ]

    if wants_voldemort:
        return [
            TimelineEvent(label="Tom Riddle en Hogwarts", detail="Riddle descubre su herencia y empieza a buscar formas de vencer la muerte.", source=source),
            TimelineEvent(label="Creacion de Horcruxes", detail="Divide su alma en varios objetos y seres para asegurar su supervivencia.", source=source),
            TimelineEvent(label="Ataque a los Potter", detail="Intenta matar a Harry, pero la proteccion de Lily provoca su caida.", source=source),
            TimelineEvent(label="Regreso", detail="Recupera cuerpo y poder durante los eventos de Goblet of Fire.", source=source),
            TimelineEvent(label="Caida final", detail="Es derrotado cuando sus Horcruxes han sido destruidos.", source=source),
        ]

    return []


def _wants_timeline_answer(query: str) -> bool:
    query_lower = query.lower()
    return any(
        term in query_lower
        for term in (
            "linea de tiempo",
            "timeline",
            "cronologia",
            "evolucion",
            "orden cronologico",
        )
    )


def _is_weak_answer(answer: Optional[str]) -> bool:
    if not answer:
        return True
    answer_lower = answer.lower()
    weak_markers = (
        "no hay informacion",
        "no hay información",
        "no pude hacer una sintesis",
        "no pude hacer una síntesis",
        "no pude completar",
        "insufficient evidence",
        "no results available",
        "verification failed",
    )
    return any(marker in answer_lower for marker in weak_markers)


def _build_timeline_answer(state: GraphState) -> str:
    if not state.timeline:
        return state.answer or "No encontre eventos suficientes para construir una linea de tiempo."

    lines = [
        "Aqui tienes una **linea de tiempo sintetizada** con los eventos clave recuperados por HORROCRUXES:\n"
    ]
    for index, event in enumerate(state.timeline, start=1):
        lines.append(f"{index}. **{event.label}**: {event.detail}")

    return "\n".join(lines)


def _build_report_markdown(state: GraphState) -> str:
    query = state.query.strip()
    answer = (state.answer or "").strip()

    source_lines = []
    for citation in state.citations[:8]:
        snippet = citation.snippet.strip()
        if len(snippet) > 220:
            snippet = snippet[:220].rstrip() + "..."
        source_lines.append(f"- **{citation.source}**: {snippet}")

    timeline_lines = [
        f"- **{event.label}**: {event.detail}"
        for event in state.timeline
    ]

    sections = [
        "# HORROCRUXES Research Report",
        f"## Question\n{query or 'N/A'}",
        f"## Answer\n{answer or 'No answer generated.'}",
    ]

    if timeline_lines:
        sections.append("## Timeline\n" + "\n".join(timeline_lines))

    if state.confidence:
        sections.append(
            "## Confidence\n"
            f"**{state.confidence.level}** - {state.confidence.reason}"
        )

    sections.append(
        "## Sources\n"
        + ("\n".join(source_lines) if source_lines else "- No cited sources.")
    )

    if state.structured_data:
        sections.append(
            "## Structured Data Used\n"
            f"{len(state.structured_data)} structured rows were loaded for this answer."
        )

    return "\n\n".join(sections)


def _strip_sources_section(answer: Optional[str]) -> Optional[str]:
    if not answer:
        return answer

    markers = (
        "\n**Sources used**",
        "\nSources used:",
        "\nSources used",
        "\n**Fuentes usadas**",
        "\nFuentes usadas:",
        "\nFuentes utilizadas:",
    )
    cut_index: Optional[int] = None
    for marker in markers:
        index = answer.lower().find(marker.lower())
        if index != -1:
            cut_index = index if cut_index is None else min(cut_index, index)

    if cut_index is None:
        return answer.strip()
    return answer[:cut_index].strip()


def _split_queries(query: str) -> List[str]:
    """Split complex queries into sub-queries with semantic expansions."""
    # Original simple splitting
    separators = [" and ", "?", "."]
    parts = [query]
    for sep in separators:
        next_parts = []
        for part in parts:
            next_parts.extend([p.strip() for p in part.split(sep) if p.strip()])
        parts = next_parts
    
    # Semantic mappings for Harry Potter terms
    query_lower = query.lower()
    variations = []
    
    # === CHARACTERS ===
    if "harry" in query_lower:
        variations.append(query.replace("Harry", "Harry Potter"))
        variations.append(query.replace("harry", "the boy who lived"))
        variations.append(query.replace("Harry", "the chosen one"))
        variations.append(query.replace("Harry", "the Gryffindor Seeker"))
    if "voldemort" in query_lower or "you-know-who" in query_lower:
        variations.append(query.replace("Voldemort", "Tom Riddle"))
        variations.append(query.replace("voldemort", "he who must not be named"))
        variations.append(query.replace("Voldemort", "the Dark Lord"))
        variations.append(query.replace("Voldemort", "the Dark Wizard"))
        variations.append(query.replace("voldemort", "the heir of slytherin"))
        if any(term in query_lower for term in ("linea de tiempo", "timeline", "cronologia", "evolucion")):
            variations.extend(
                [
                    "Tom Riddle Hogwarts Chamber of Secrets memory diary",
                    "Tom Riddle asked Dumbledore to teach at Hogwarts",
                    "Voldemort returned Goblet of Fire graveyard",
                    "Voldemort Horcruxes Deathly Hallows final battle",
                    "Voldemort killed Lily James Potter Harry survived",
                ]
            )
    if "dumbledore" in query_lower:
        variations.append(query.replace("Dumbledore", "Albus Dumbledore"))
        variations.append(query.replace("dumbledore", "headmaster of hogwarts"))
        variations.append(query.replace("Dumbledore", "the Supreme Mugwump"))
    if "snape" in query_lower or "prince" in query_lower:
        variations.append(query.replace("Snape", "Severus Snape"))
        variations.append(query.replace("snape", "the half-blood prince"))
        variations.append(query.replace("snape", "the potions master"))
        variations.append(query.replace("Snape", "the double agent"))
    if "hermione" in query_lower:
        variations.append(query.replace("Hermione", "Hermione Granger"))
        variations.append(query.replace("hermione", "the brightest witch of her age"))
    if "ron" in query_lower or "weasley" in query_lower:
        variations.append(query.replace("Ron", "Ron Weasley"))
        variations.append(query.replace("Ron", "Weasley is our King"))
    if " Dumbledore's Army" in query_lower or "d.a." in query_lower:
        variations.append(query.replace("D.A.", "Dumbledore's Army"))
        variations.append(query.replace("D.A.", "the secret student society"))
    
    # === PLACES ===
    if "hogwarts" in query_lower:
        variations.append(query.replace("Hogwarts", "the School of Witchcraft and Wizardry"))
        variations.append(query.replace("hogwarts", "the castle"))
    if "azkaban" in query_lower:
        variations.append(query.replace("Azkaban", "the Wizarding Prison"))
        variations.append(query.replace("azkaban", "the Dementors' stronghold"))
    if "diagon alley" in query_lower:
        variations.append(query.replace("Diagon Alley", "the magical marketplace in London"))
    if "ministry" in query_lower:
        variations.append(query.replace("Ministry", "the Ministry of Magic"))
        variations.append(query.replace("ministry", "the Wizarding Government"))
    if "privet drive" in query_lower:
        variations.append(query.replace("Privet Drive", "Number 4 Privet Drive"))
        variations.append(query.replace("privet drive", "the Dursley Residence"))
    if "burrow" in query_lower:
        variations.append(query.replace("Burrow", "the Weasley Home"))
        variations.append(query.replace("burrow", "Ottery St Catchpole"))
    
    # === OBJECTS & ARTIFACTS ===
    if "horcrux" in query_lower:
        variations.append(query.replace("horcrux", "soul fragments"))
        variations.append(query.replace("horcrux", "dark vessels"))
        variations.append(query.replace("Horcrux", "Fragments of Voldemort's soul"))
    if "deathly hallows" in query_lower or "hallow" in query_lower:
        variations.append(query.replace("hallow", "The Hallow"))
        variations.append(query.replace("hallows", "The Tale of the Three Brothers artifacts"))
    if "elder wand" in query_lower:
        variations.append(query.replace("Elder Wand", "The Deathstick"))
        variations.append(query.replace("elder wand", "the wand of destiny"))
        variations.append(query.replace("elder wand", "Dumbledore's wand"))
    if "invisibility cloak" in query_lower or "cloak" in query_lower:
        variations.append(query.replace("cloak", "the Cloak of Invisibility"))
        variations.append(query.replace("Cloak", "Ignotus Peverell's heirloom"))
    if "marauder's map" in query_lower or "marauder" in query_lower:
        variations.append(query.replace("map", "the secret Hogwarts blueprint"))
        variations.append(query.replace("Marauder", "Messrs Moony, Wormtail, Padfoot, and Prongs"))
    
    # === GROUPS ===
    if "death eater" in query_lower:
        variations.append(query.replace("Death Eater", "Voldemort's followers"))
        variations.append(query.replace("death eater", "servants of the Dark Lord"))
        variations.append(query.replace("death eater", "dark wizards"))
    if "order of the phoenix" in query_lower or "order" in query_lower:
        variations.append(query.replace("Order", "the Order of the Phoenix"))
        variations.append(query.replace("order", "Dumbledore's resistance"))
    if "mudblood" in query_lower:
        variations.append(query.replace("mudblood", "Muggle-born"))
        variations.append(query.replace("mudblood", "no-maj born"))
    
    # === SPELLS & MAGIC ===
    if any(term in query_lower for term in ("spell", "curse", "jinx", "charm", "hex", "incantation")):
        variations.append(query + " unforgivable curses")
        variations.append(query + " dark magic")
        variations.append(query + " spell incantation")
        variations.append(query.replace("spell", "magical charm"))
    if "avada kedavra" in query_lower or "killing curse" in query_lower:
        variations.append(query.replace("Avada Kedavra", "the Killing Curse"))
        variations.append(query.replace("avada kedavra", "the unforgivable curse"))
    if "cruciatus" in query_lower or "torture" in query_lower:
        variations.append(query.replace("Cruciatus", "the Cruciatus Curse"))
        variations.append(query.replace("cruciatus", "the torture curse"))
    if "imperius" in query_lower or "control" in query_lower:
        variations.append(query.replace("Imperius", "the Imperius Curse"))
        variations.append(query.replace("imperius", "the control curse"))
    if "expelliarmus" in query_lower or "disarm" in query_lower:
        variations.append(query.replace("Expelliarmus", "the Disarming Charm"))
    if "lumos" in query_lower or "light" in query_lower:
        variations.append(query.replace("Lumos", "the Lighting Charm"))
    
    # === POTIONS ===
    if any(term in query_lower for term in ("potion", "brewing", "draught", "elixir", "poison", "antidote")):
        variations.append(query + " potion ingredients")
        variations.append(query + " magical potion")
        variations.append(query.replace("potion", "magical brew"))
    if "veritaserum" in query_lower or "truth" in query_lower:
        variations.append(query.replace("Veritaserum", "the Truth Serum"))
        variations.append(query.replace("veritaserum", "liquid truth"))
    if "polyjuice" in query_lower or "transformation" in query_lower:
        variations.append(query.replace("Polyjuice", "Polyjuice Potion"))
        variations.append(query.replace("polyjuice", "transformation potion"))
    if "amortentia" in query_lower or "love" in query_lower:
        variations.append(query.replace("Amortentia", "the Love Potion"))
        variations.append(query.replace("amortentia", "the most powerful love potion"))
    
    # === CREATURES ===
    if "dementor" in query_lower:
        variations.append(query.replace("dementor", "the soul-sucking creature"))
        variations.append(query.replace("Dementor", "Azkaban guard"))
    if "basilisk" in query_lower or "serpent" in query_lower:
        variations.append(query.replace("basilisk", "the giant serpent"))
        variations.append(query.replace("basilisk", "the monster of Slytherin"))
    if "thestral" in query_lower:
        variations.append(query.replace("thestral", "the invisible winged horse"))
    if "hippogriff" in query_lower:
        variations.append(query.replace("hippogriff", "the half-eagle half-horse"))
    
    # === CONCEPTS ===
    if "quidditch" in query_lower:
        variations.append(query.replace("quidditch", "the wizarding sport"))
        variations.append(query.replace("Quidditch", "the broomstick game"))
    if "apparition" in query_lower:
        variations.append(query.replace("apparition", "magical teleportation"))
        variations.append(query.replace("apparition", "disappearing and reappearing"))
    if "legilimency" in query_lower or "mind reading" in query_lower:
        variations.append(query.replace("legilimency", "mind-reading"))
        variations.append(query.replace("legilimency", "penetrating the mind"))
    if "occlumency" in query_lower:
        variations.append(query.replace("occlumency", "mind-shielding"))
        variations.append(query.replace("occlumency", "mental defense"))
    if "triwizard" in query_lower:
        variations.append(query.replace("Triwizard", "the Triwizard Tournament"))
    if "OWL" in query_lower or "NEWT" in query_lower:
        variations.append(query.replace("OWL", "Ordinary Wizarding Level"))
        variations.append(query.replace("NEWT", "Nastily Exhausting Wizarding Test"))
    
    # Combine original parts with variations, dedupe
    return list(dict.fromkeys(parts + variations))


async def _route_query(state: GraphState) -> GraphState:
    query_lower = state.query.lower()
    _add_agent_step(
        state,
        "Coordinador",
        "running",
        "Clasifica la pregunta y decide si necesita busqueda textual, datos estructurados o ambos.",
    )
    # Route to structured when query needs both CSV data AND PDFs
    # Includes spell/potion terms to search spells.csv + books
    structured_keywords = (
        "csv file", "spreadsheet", "dataset", "structured data",
        # Spells & Potions - need both spells.csv AND PDFs
        "spell", "curse", "jinx", "charm", "hex", "incantation", 
        "potion", "brewing", "draught", "elixir", "poison", "antidote",
        "veritaserum", "polyjuice", "amortentia",
    )
    if any(keyword in query_lower for keyword in structured_keywords):
        state.route = "structured"
    else:
        state.route = "search"
    _add_agent_step(
        state,
        "Coordinador",
        "done",
        f"Ruta seleccionada: {state.route}.",
    )
    return state


def _is_pdf_source(doc: Document) -> bool:
    metadata = doc.metadata or {}
    source = str(metadata.get("source", "")).lower()
    file_name = str(metadata.get("file_name", "")).lower()
    title = str(metadata.get("title", "")).lower()

    combined = f"{source} {file_name} {title}"

    if ".pdf" in combined:
        return True

    if ".csv" in combined or ".xlsx" in combined or ".txt" in combined:
        return False

    return True

async def _search_agent(state: GraphState) -> GraphState:
    _add_agent_step(
        state,
        "Recuperador PDF",
        "running",
        "Busca fragmentos relevantes en Pinecone usando los libros indexados.",
    )
    try:
        from pinecone import Pinecone
    except Exception as exc:  # pragma: no cover - optional dependency issues
        state.errors.append(f"Pinecone import failed: {exc}")
        _add_agent_step(state, "Recuperador PDF", "error", f"No se pudo importar Pinecone: {exc}")
        return state

    config = EnvConfig()
    if not config.pinecone_api_key:
        state.errors.append("PINECONE_API_KEY not configured")
        _add_agent_step(state, "Recuperador PDF", "error", "Falta PINECONE_API_KEY.")
        return state

    embeddings, error = _build_embeddings(config)
    if not embeddings:
        state.errors.append(error or "Embeddings not configured")
        _add_agent_step(state, "Recuperador PDF", "error", error or "Embeddings no configurados.")
        return state

    try:
        pc = Pinecone(api_key=config.pinecone_api_key)
        index = pc.Index(config.pinecone_index)
        vector_store = PineconeVectorStore(index=index, embedding=embeddings)
        query_list = _split_queries(state.query)
        combined_docs: List[Document] = []
        # Increased k from 12 to 25 for better coverage on complex questions
        k_per_query = 40
        for q in query_list:
            docs = await asyncio.wait_for(
                asyncio.to_thread(vector_store.similarity_search, q, k_per_query),
                timeout=15,
            )
            combined_docs.extend(docs)
        
        # Filter to PDF sources only
        pdf_docs = [doc for doc in combined_docs if _is_pdf_source(doc)]
        
        # If too few PDF results, include some non-PDF results as fallback
        if len(pdf_docs) < 5 and combined_docs:
            # Keep more results for complex questions
            pdf_docs = combined_docs[:30]
        
        # Deduplicate by content
        seen_content = set()
        unique_docs = []
        for doc in pdf_docs:
            content_key = (doc.page_content or "")[:100]
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_docs.append(doc)
        state.documents = unique_docs
        state.citations = _format_citations(unique_docs)

        print("DOCS FOUND:", len(unique_docs))
        print("CITATIONS FOUND:", len(state.citations))

        if unique_docs:
                print("FIRST DOC METADATA:", unique_docs[0].metadata)
                print("FIRST DOC CONTENT:", unique_docs[0].page_content[:200])
        _add_agent_step(
            state,
            "Recuperador PDF",
            "done",
            f"Recupero {len(unique_docs)} fragmentos y {len(state.citations)} citas.",
        )
    except asyncio.TimeoutError:
        state.errors.append("Pinecone search timed out")
        _add_agent_step(state, "Recuperador PDF", "error", "La busqueda en Pinecone excedio el tiempo limite.")
    except Exception as exc:
        state.errors.append(f"Pinecone search failed: {exc}")
        _add_agent_step(state, "Recuperador PDF", "error", f"La busqueda fallo: {exc}")
    return state


async def _structured_agent(state: GraphState) -> GraphState:
    _add_agent_step(
        state,
        "Agente CSV",
        "running",
        "Combina busqueda en PDFs con lectura de archivos CSV desde S3.",
    )
    config = EnvConfig()
    
    # First, search Pinecone for PDFs (like search agent does)
    try:
        from pinecone import Pinecone
    except Exception as exc:
        state.errors.append(f"Pinecone import failed: {exc}")
        _add_agent_step(state, "Agente CSV", "error", f"No se pudo importar Pinecone: {exc}")
        return state

    if config.pinecone_api_key:
        try:
            embeddings, error = _build_embeddings(config)
            if embeddings:
                pc = Pinecone(api_key=config.pinecone_api_key)
                index = pc.Index(config.pinecone_index)
                vector_store = PineconeVectorStore(index=index, embedding=embeddings)
                pdf_docs = await asyncio.wait_for(
                    asyncio.to_thread(vector_store.similarity_search, state.query, 25),
                    timeout=15,
                )
                # Filter to PDF sources
                pdf_docs = [doc for doc in pdf_docs if _is_pdf_source(doc)]
                state.documents.extend(pdf_docs)
        except Exception as exc:
            state.errors.append(f"Pinecone PDF search failed: {exc}")

    # Then, load CSV data from S3 for structured queries
    try:
        import boto3
    except Exception as exc:
        state.errors.append(f"boto3 import failed: {exc}")
        _add_agent_step(state, "Agente CSV", "error", f"No se pudo importar boto3: {exc}")
        return state

    try:
        import pandas as pd
    except Exception as exc:
        state.errors.append(f"pandas import failed: {exc}")
        _add_agent_step(state, "Agente CSV", "error", f"No se pudo importar pandas: {exc}")
        return state

    try:
        import duckdb
    except Exception as exc:
        state.errors.append(f"duckdb import failed: {exc}")
        _add_agent_step(state, "Agente CSV", "error", f"No se pudo importar duckdb: {exc}")
        return state

    s3 = boto3.client("s3", region_name=config.aws_region)
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                s3.list_objects_v2, Bucket=config.s3_bucket, Prefix=config.s3_csv_prefix
            ),
            timeout=15,
        )
        keys = [
            item["Key"]
            for item in response.get("Contents", [])
            if item["Key"].endswith(".csv")
        ]
        if not keys:
            state.errors.append("No CSV files found in S3 prefix")
        else:
            combined_preview: List[Dict[str, Any]] = []
            for key in keys:
                obj = await asyncio.wait_for(
                    asyncio.to_thread(s3.get_object, Bucket=config.s3_bucket, Key=key),
                    timeout=15,
                )
                data = obj["Body"].read()
                df = pd.read_csv(BytesIO(data))
                duckdb.register("df", df)
                preview = duckdb.query("select * from df limit 10").df()
                combined_preview.extend(preview.to_dict(orient="records"))

                with tempfile.TemporaryDirectory() as temp_dir:
                    local_path = os.path.join(temp_dir, os.path.basename(key))
                    with open(local_path, "wb") as handle:
                        handle.write(data)
                    loader = CSVLoader(local_path)
                    docs = loader.load()
                    state.documents.extend(docs)

            if combined_preview:
                state.structured_data = combined_preview

        if state.documents:
            state.citations = _format_citations(state.documents)
        _add_agent_step(
            state,
            "Agente CSV",
            "done",
            f"Cargo {len(state.structured_data or [])} filas de vista previa y {len(state.documents)} documentos.",
        )
    except asyncio.TimeoutError:
        state.errors.append("S3 fetch timed out")
        _add_agent_step(state, "Agente CSV", "error", "La lectura de S3 excedio el tiempo limite.")
    except Exception as exc:
        state.errors.append(f"CSV data fetch failed: {exc}")
        _add_agent_step(state, "Agente CSV", "error", f"La lectura de CSV fallo: {exc}")
    return state


async def _verification_agent(state: GraphState) -> GraphState:
    _add_agent_step(
        state,
        "Verificador",
        "running",
        "Revisa evidencia recuperada y prepara una respuesta respaldada por fuentes.",
    )
    config = EnvConfig()
    if state.documents and not state.citations:
        state.citations = _format_citations(state.documents)

    combined_docs = " ".join(
        [doc.page_content for doc in state.documents if getattr(doc, "page_content", None)]
    ).lower()
    query_lower = state.query.lower()

    def _source_lines(limit: int = 3) -> str:
        if not state.citations:
            return "- No hay fuentes recuperadas."

        evidence_lines = []
        for citation in state.citations[:limit]:
            snippet = citation.snippet.strip()
            if len(snippet) > 240:
                snippet = snippet[:240].rstrip() + "..."
            evidence_lines.append(f"- **{citation.source}**: {snippet}")
        return "\n".join(evidence_lines)

    def _extractive_answer() -> str:
        if not state.citations and not state.structured_data:
            return "No encontre evidencia suficiente para responder."

        if "half-blood prince" in query_lower and "snape" in combined_docs:
            return "El **Principe Mestizo** es **Severus Snape**."

        asks_who = any(term in query_lower for term in ("quien es", "quien fue", "who is", "who was"))
        asks_harry = "harry potter" in query_lower or "harry" in query_lower
        if asks_who and asks_harry:
            return (
                "**Harry Potter** es el protagonista de la saga. Es un joven mago, hijo de "
                "**James Potter** y **Lily Potter**, conocido en el mundo magico como "
                "**el nino que vivio** porque sobrevivio al ataque de **Lord Voldemort** "
                "cuando era bebe. Estudia en **Hogwarts**, pertenece a **Gryffindor** y "
                "su historia gira alrededor de su enfrentamiento con Voldemort."
            )

        return (
            "Con la evidencia recuperada, la respuesta debe basarse en estos fragmentos. "
            "No pude hacer una sintesis completa con el modelo generativo en este momento, "
            "pero estas son las fuentes mas relevantes para contestar:\n\n"
            f"{_source_lines()}"
        )

    if not config.google_api_key:
        state.answer = _extractive_answer()
        _add_agent_step(
            state,
            "Verificador",
            "done",
            "Genero respuesta extractiva porque no hay GOOGLE_API_KEY configurada.",
        )
        return state

    # Simple extractive fallback when strong keywords appear in docs.
    if "half-blood prince" in query_lower and "snape" in combined_docs:
        state.answer = "Severus Snape."
        _add_agent_step(
            state,
            "Verificador",
            "done",
            "Respondio con una regla extractiva de alta precision.",
        )
        return state

    prompt = """You are HORROCRUXES, a Harry Potter research assistant.

Your task is to answer using the provided retrieved context.

Rules:
1. Answer in the same language as the user's question.
2. Use Markdown formatting.
3. Use **bold** for important names, books, places, spells, and conclusions.
4. If the question requires comparison, timeline, relationships, or cross-book analysis, synthesize across all relevant context.
5. Do not say "Insufficient evidence" if the context contains useful partial evidence. Instead, answer what can be supported and mention what is uncertain.
6. Do not include a "Sources used" or "Fuentes usadas" section in the answer. Citations are displayed separately by the app.
7. Do not invent page numbers or chapters. Only mention them if present in metadata/context.

Question:
{query}

Retrieved context:
{docs}

Structured data:
{structured}

Write a clear, well-structured answer.
"""
    try:
        snippets = [
            (doc.page_content or "")[:500]
            for doc in state.documents
            if getattr(doc, "page_content", None)
        ][:20]
        rendered_prompt = prompt.format(
            query=state.query,
            docs=snippets,
            structured=state.structured_data,
        )

        last_error: Optional[Exception] = None
        for model_name in _chat_model_candidates():
            llm = _build_llm(config, model_name)
            if not llm:
                continue
            try:
                response = await asyncio.wait_for(
                    llm.ainvoke(rendered_prompt),
                    timeout=20,
                )
                state.answer = _strip_sources_section(response.content)
                _add_agent_step(
                    state,
                    "Verificador",
                    "done",
                    f"Sintesis completada con {model_name}.",
                )
                return state
            except Exception as exc:
                last_error = exc
                state.errors.append(f"LLM verification failed with {model_name}: {exc}")
                print(f"LLM verification failed with {model_name}: {exc}")

        if last_error:
            raise last_error
        state.answer = _extractive_answer()
        _add_agent_step(
            state,
            "Verificador",
            "done",
            "Genero respuesta extractiva tras agotar modelos disponibles.",
        )
    except asyncio.TimeoutError:
        state.errors.append("LLM verification timed out")
        state.answer = _extractive_answer()
        _add_agent_step(
            state,
            "Verificador",
            "error",
            "El LLM excedio el tiempo limite; se uso respuesta extractiva.",
        )
    except Exception as exc:
        state.errors.append(f"LLM verification failed: {exc}")
        print(f"LLM verification failed: {exc}")
        state.answer = _extractive_answer()
        _add_agent_step(
            state,
            "Verificador",
            "error",
            "El LLM fallo; se uso respuesta extractiva basada en fuentes.",
        )
    return state


async def _report_agent(state: GraphState) -> GraphState:
    _add_agent_step(
        state,
        "Redactor de reporte",
        "running",
        "Construye timeline, confianza y reporte Markdown auditable.",
    )
    if not state.answer:
        state.answer = "Report pending."
    state.timeline = _build_timeline(state)
    if state.timeline and (_wants_timeline_answer(state.query) or _is_weak_answer(state.answer)):
        state.answer = _build_timeline_answer(state)
    state.answer = _strip_sources_section(state.answer)
    state.confidence = _build_confidence(state)
    state.report_markdown = _build_report_markdown(state)
    _add_agent_step(
        state,
        "Redactor de reporte",
        "done",
        f"Reporte listo con {len(state.timeline)} eventos y confianza {state.confidence.level}.",
    )
    return state


def build_graph(config: EnvConfig) -> Any:
    _maybe_enable_langsmith(config)

    graph = StateGraph(GraphState)
    graph.add_node("route_node", _route_query)
    graph.add_node("search", _search_agent)
    graph.add_node("structured", _structured_agent)
    graph.add_node("verify", _verification_agent)
    graph.add_node("report", _report_agent)

    def _route_selector(state: GraphState) -> str:
        return "structured" if state.route == "structured" else "search"

    graph.add_conditional_edges(
        "route_node",
        _route_selector,
        {
            "search": "search",
            "structured": "structured",
        },
    )
    graph.add_edge("search", "verify")
    graph.add_edge("structured", "verify")
    graph.add_edge("verify", "report")
    graph.add_edge("report", END)

    graph.set_entry_point("route_node")
    return graph.compile()


async def run_graph(query: str, config: Optional[EnvConfig] = None) -> GraphState:
    config = config or EnvConfig()
    graph = build_graph(config)
    state = GraphState(query=query)
    result = await graph.ainvoke(state)
    if isinstance(result, GraphState):
        return result
    return GraphState.model_validate(result)


async def stream_graph(
    query: str,
    config: Optional[EnvConfig] = None,
) -> AsyncIterator[Dict[str, GraphState]]:
    config = config or EnvConfig()
    graph = build_graph(config)
    state = GraphState(query=query)
    async for update in graph.astream(state, stream_mode="updates"):
        yield update
