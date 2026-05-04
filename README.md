# HORROCRUXES

HORROCRUXES es un sistema de preguntas y respuestas sobre el universo de Harry Potter. Usa recuperacion semantica sobre los 7 libros en PDF, datos estructurados en CSV, memoria conversacional y respuestas con fuentes auditables.

El proyecto esta dividido en:

- `backend/`: API FastAPI con pipeline RAG/multiagente usando LangGraph, Pinecone, Gemini, S3 y CSVs.
- `Frontend/`: cliente web React + Vite.
- `docker-compose.yaml`: ejecucion local de backend y frontend.
- `infrastructure/`: plantilla CloudFormation para despliegue en AWS.

## Funcionalidades

- Chat web para hacer preguntas en lenguaje natural.
- Busqueda en los 7 libros PDF indexados en Pinecone.
- Uso de CSVs como fuente estructurada desde S3.
- Citas separadas en el panel `Sources`.
- Memoria conversacional por sesion.
- Timeline automatica para preguntas cronologicas.
- Reporte Markdown auditable por respuesta.
- Fallback cuando el LLM falla por cuota o disponibilidad.

## Requisitos

Para ejecutar con Docker:

- Git
- Docker Desktop
- Docker Compose, disponible como `docker compose` o `docker-compose`

Para ejecutar sin Docker:

- Python 3.11 o superior
- Node.js 20 o superior
- npm

Tambien necesitas credenciales/API keys para usar el sistema completo:

- Google Gemini API key
- Pinecone API key
- Acceso a S3 si vas a consultar CSVs o reindexar datos

## 1. Clonar El Proyecto

```bash
git clone <URL_DEL_REPOSITORIO>
cd horrocruxes
```

Si ya tienes el proyecto descargado, solo entra a la carpeta raiz:

```bash
cd horrocruxes
```

## 2. Configurar Variables De Entorno

### Backend

Crea el archivo `backend/.env`.

Ejemplo:

```env
GOOGLE_API_KEY=tu_google_api_key
PINECONE_API_KEY=tu_pinecone_api_key
PINECONE_INDEX=horrocruxes-index

GOOGLE_LLM_MODEL=gemini-2.5-flash-lite
GOOGLE_FALLBACK_LLM_MODELS=gemini-2.0-flash-lite,gemini-2.0-flash

EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu

AWS_REGION=us-east-1
S3_BUCKET=horrocruxes-data
S3_PDF_PREFIX=data/books
S3_CSV_PREFIX=data/structured
S3_REPORTS_PREFIX=reports

LANGSMITH_API_KEY=
LANGSMITH_PROJECT=horrocruxes
```

Notas:

- `GOOGLE_API_KEY` se usa para generar respuestas con Gemini.
- `PINECONE_API_KEY` y `PINECONE_INDEX` se usan para buscar en los libros.
- `LANGSMITH_API_KEY` es opcional.
- No subas archivos `.env` al repositorio.

### Frontend

Crea el archivo `Frontend/.env`.

Ejemplo:

```env
VITE_API_URL=http://localhost:8080
```

## 3. Ejecutar Con Docker

Desde la raiz del proyecto:

```bash
docker compose up --build
```

Si tu instalacion usa el comando antiguo:

```bash
docker-compose up --build
```

Cuando termine de levantar:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8080`
- Health check: `http://localhost:8080/health`

Para detener los servicios:

```bash
docker compose down
```

Para ejecutar en segundo plano:

```bash
docker compose up -d --build
```

Para ver logs:

```bash
docker compose logs -f
```

Para reconstruir despues de cambios en dependencias:

```bash
docker compose build
```

## 4. Ejecutar Sin Docker

### Backend

Desde la raiz:

```bash
cd backend
python -m venv .venv
```

Activar entorno virtual en Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Activar entorno virtual en macOS/Linux:

```bash
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
pip install -r dev-requirements.txt
```

Ejecutar API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Frontend

En otra terminal, desde la raiz:

```bash
cd Frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Abrir:

```text
http://localhost:5173
```

## 5. Probar Que Todo Funciona

Backend:

```bash
curl http://localhost:8080/health
```

Respuesta esperada:

```json
{"status":"healthy"}
```

Chat por API:

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"quien es Harry Potter?\"}"
```

En PowerShell:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8080/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"quien es Harry Potter?"}'
```

Preguntas recomendadas para demo:

- `quien es Harry Potter?`
- `Haz una linea de tiempo de Voldemort`
- `Cuales son los Horrocruxes de Voldemort?`
- `Compara la evolucion de Snape y Draco Malfoy`
- `Que hechizos usa Hermione?`

## 6. Endpoints Principales

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/` | Estado basico de la API |
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Pregunta al sistema y devuelve respuesta, citas, timeline y reporte |
| `GET` | `/session/{session_id}` | Consulta historial de una sesion |
| `DELETE` | `/session/{session_id}` | Limpia historial de una sesion |
| `POST` | `/session/cleanup` | Limpia sesiones antiguas |
| `WS` | `/ws/chat` | WebSocket para streaming de eventos |

## 7. Como Funciona El Pipeline

1. El usuario hace una pregunta desde el frontend.
2. El backend crea o recupera una sesion de conversacion.
3. El coordinador decide si la pregunta va a busqueda textual o datos estructurados.
4. El recuperador consulta Pinecone para traer fragmentos relevantes de los libros.
5. Si aplica, el agente estructurado carga CSVs desde S3.
6. El verificador/redactor genera la respuesta con Gemini o usa fallback extractivo.
7. El agente de reporte genera timeline, confianza y reporte Markdown.
8. El frontend muestra la respuesta y las fuentes en secciones separadas.

## 8. Datos E Ingestion

Los PDFs y CSVs viven en S3. Pinecone debe tener el indice creado y cargado previamente.

Para reindexar desde S3:

```bash
cd backend
python scripts/ingest_pinecone.py
```

Variables importantes para ingestion:

| Variable | Default | Descripcion |
|---|---|---|
| `PINECONE_API_KEY` | requerido | API key de Pinecone |
| `PINECONE_INDEX` | `horrocruxes-index` | Nombre del indice |
| `S3_BUCKET` | `horrocruxes-data` | Bucket con PDFs/CSVs |
| `S3_PDF_PREFIX` | `data/books` | Carpeta S3 de PDFs |
| `S3_CSV_PREFIX` | `data/structured` | Carpeta S3 de CSVs |
| `EMBEDDING_PROVIDER` | `sentence-transformers` | Proveedor de embeddings |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Modelo de embeddings |
| `CHUNK_SIZE` | `1200` | Tamano de fragmento |
| `CHUNK_OVERLAP` | `200` | Solapamiento entre fragmentos |

## 9. Solucion De Problemas

### El frontend no conecta con el backend

Verifica `Frontend/.env`:

```env
VITE_API_URL=http://localhost:8080
```

Y confirma que el backend este activo:

```bash
curl http://localhost:8080/health
```

### Gemini no responde o aparece error de cuota

Puede ocurrir si se agota la cuota del modelo. Cambia a un modelo mas economico:

```env
GOOGLE_LLM_MODEL=gemini-2.5-flash-lite
```

El sistema tiene fallback, pero la calidad mejora cuando Gemini esta disponible.

### Pinecone no devuelve resultados

Revisa:

- `PINECONE_API_KEY`
- `PINECONE_INDEX`
- Que el indice ya tenga registros cargados
- Que el modelo de embeddings coincida con el usado durante la ingestion

### Docker no encuentra el frontend

La carpeta correcta es `Frontend` con F mayuscula. El `docker-compose.yaml` ya usa esa ruta.

## 10. Despliegue

La carpeta `infrastructure/` incluye una plantilla CloudFormation para AWS.

El flujo esperado es:

1. Crear infraestructura con CloudFormation.
2. Construir imagen Docker del backend.
3. Subir imagen a ECR.
4. Desplegar en AWS App Runner.

Consulta `infrastructure/setup.yaml` para parametros como repositorio, rama, ECR y rol OIDC.

## 11. Resumen Para Evaluadores

HORROCRUXES combina:

- RAG sobre los 7 libros PDF.
- Fuente estructurada en CSV.
- Orquestacion con LangGraph.
- API FastAPI.
- Frontend React.
- Memoria conversacional.
- Citas auditables.
- Timeline y reporte Markdown como funciones diferenciales.

La idea central es que el sistema no memoriza respuestas: recupera evidencia real, razona sobre ella y responde con fuentes verificables.
