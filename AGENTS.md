# Project Context: Kokoro-82M Podcast Generator

## Project Overview
This project turns source documents into two-person podcast scripts and generated audio. It combines a FastAPI backend, a Google ADK multi-agent workflow, SQLite persistence, Kokoro-82M text-to-speech, Arize Phoenix tracing, and a Vue 3 frontend.

The main user flow is:
1. Create a project.
2. Add documents to the project.
3. Build a knowledge base by extracting facts from those documents.
4. Generate personas and a refined two-speaker script from the fact set and a user prompt.
5. Optionally edit the script.
6. Generate a concatenated WAV file for the final script.

## Tech Stack
- **Backend:** FastAPI, Python 3.13, SQLAlchemy async ORM, SQLite via `aiosqlite`.
- **Agents:** Google Agent Development Kit (ADK), configured with `GEMINI_MODEL` and defaulting to `gemini-1.5-flash`.
- **TTS:** Kokoro-82M, SoundFile, PyDub, ffmpeg, espeak-ng.
- **Frontend:** Vue 3, Vue Router, Vite, Tailwind CSS, Axios, lucide-vue-next.
- **Observability:** Arize Phoenix and OpenTelemetry FastAPI instrumentation.
- **Runtime:** Docker and Docker Compose; `uv` manages Python dependencies.

## Key Files and Directories
- `main.py`: FastAPI app, CORS setup, Phoenix tracing registration, root `/generate` TTS endpoint, and router registration.
- `database.py`: Async SQLite engine and session dependency. The default DB file is `audio_chat.db`.
- `models.py`: SQLAlchemy models for `Project`, `Document`, `Fact`, `Script`, and `Audio`.
- `routers/projects.py`: Project, document, fact, script, knowledge-base, and script-generation endpoints. Knowledge-base and script-generation operations stream Server-Sent Events.
- `routers/podcast.py`: Direct non-project endpoints for fact extraction and script generation.
- `routers/audio.py`: Project script audio generation and audio download endpoints.
- `utils/sse.py`: Helper for formatting SSE payloads.
- `agents/`: ADK agent definitions and orchestration.
- `frontend/src/views/Dashboard.vue`: Project list and creation UI.
- `frontend/src/views/ProjectDetail.vue`: Document, fact, script, and audio workspace UI.
- `generate_final_podcast.py`: CLI automation for the direct `/podcast` and `/generate` path using the sample document.

## Agent Directory Structure
```text
agents/
├── fact_extractor/
│   ├── agent.py       # fact_extractor
│   └── README.md
├── persona_generator/
│   ├── agent.py       # persona_generator
│   └── README.md
├── script_writer/
│   ├── agent.py       # script_writer
│   └── README.md
├── script_critic/
│   ├── agent.py       # script_critic
│   └── README.md
└── podcast_flow.py    # PodcastFlow orchestration and global flow singleton
```

## Agent Roles
### Fact Extractor (`fact_extractor`)
- Uses `google.adk.Agent` with a Pydantic `DocumentSummary` output schema.
- Extracts a concise summary and `key_facts` from user-provided source text.
- Each key fact contains a `point` and `context`.

### Persona Generator (`persona_generator`)
- Uses a Pydantic `PodcastPersonas` output schema.
- Creates exactly two podcast personas from the supplied facts and conversation history.

### Script Writer (`script_writer`)
- Uses a Pydantic `PodcastScript` output schema.
- Produces a title and dialogue lines with `speaker` and `text`.
- The project prompt requires spoken dialogue only, with no stage directions, music cues, or sound effects.

### Script Critic (`script_critic`)
- Uses a Pydantic `Critique` output schema.
- Reviews the latest script draft against the facts and personas.
- Returns feedback, a 1-10 score, and suggestions.

## Agent Orchestration
`agents/podcast_flow.py` exposes a global `flow = PodcastFlow()` singleton so the ADK agents and in-memory session service are not repeatedly recreated.

The project workflow is:
- `build_knowledge_base(project_id, db)`: loads project documents, runs `fact_extractor` once per document, and stores extracted facts in SQLite.
- `generate_script_stream(project_id, prompt, db, max_loops=3)`: loads stored facts, generates personas, runs an iterative writer/critic loop, stores the final script and personas, and streams status events.
- `extract_facts(text)` and `generate_script(facts, max_loops=3)`: direct API helpers used by `routers/podcast.py` and the CLI script.

The ADK composition is:
- `generation_workflow`: `SequentialAgent` containing `persona_generator` followed by `refinement_loop`.
- `refinement_loop`: `LoopAgent` containing a `SequentialAgent` of `script_writer` then `script_critic`.
- The loop defaults to 3 iterations but can be changed per request.

Session state uses ADK `InMemorySessionService`, so generated agent event history is process-local. Durable project data is stored in SQLite.

## API Surface
- `GET /`: health-style root response for the TTS API.
- `POST /generate`: direct text-to-WAV Kokoro generation.
- `POST /podcast/extract-facts`: direct fact extraction from raw text.
- `POST /podcast/generate-script`: direct persona and script generation from supplied facts.
- `POST /projects/`, `GET /projects/`, `GET /projects/{project_id}`: project CRUD basics.
- `POST /projects/{project_id}/documents`, `GET /projects/{project_id}/documents`: document management.
- `POST /projects/{project_id}/build-kb`: SSE endpoint for fact extraction into the project knowledge base.
- `GET /projects/{project_id}/facts`: list stored facts.
- `POST /projects/{project_id}/generate-script`: SSE endpoint for project script generation.
- `GET /projects/{project_id}/scripts`: list generated scripts.
- `GET /projects/scripts/{script_id}`, `PUT /projects/scripts/{script_id}`: read and edit a generated script.
- `POST /projects/scripts/{script_id}/generate-audio`: synthesize final script audio.
- `GET /projects/audio/{audio_id}`: download generated WAV audio.

## Frontend
The frontend is a Vite/Vue application in `frontend/`.

Current implemented views:
- Dashboard: fetches projects, creates projects, and links to project detail pages.
- Project detail: manages documents, runs knowledge-base extraction over SSE, searches facts, generates scripts over SSE, edits script lines, and triggers audio synthesis.

The UI currently talks to the backend at `http://localhost:8000`.

## Execution
Create a root `.env` with at least:
```text
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
PHOENIX_PROJECT_NAME=audio-chat
```

Run the backend and Phoenix with:
```bash
docker compose up -d --build
```

Expected service URLs:
- FastAPI: `http://localhost:8000`
- FastAPI docs: `http://localhost:8000/docs`
- Phoenix UI: `http://localhost:3000`
- Phoenix collector inside Docker: `http://phoenix:3000/v1/traces`

Run the Vue frontend from `frontend/` with the package manager used by the lockfile:
```bash
pnpm install
pnpm run dev
```

Expected frontend URL: `http://localhost:5173`.

## Generated and Local State
The following are local/generated artifacts and should not be committed:
- `.env`
- `.venv/`
- `audio_chat.db`
- `audio_outputs/`
- generated audio files such as `output.wav` and `podcast_output.wav`
- Python caches and frontend `node_modules/` / `dist/`

## Notes for Future Agents
- Prefer updating this `AGENTS.md` file for project-level agent guidance. `CLAUDE.md` and `GEMINI.md` are symlinks to it.
- Keep documentation aligned with actual code; `IMPLEMENTATION_PLAN.md` may lag behind the implementation.
- The direct CLI script uses American Kokoro voices through `/generate`; the project audio endpoint uses British Kokoro voices through `routers/audio.py`.
- The backend currently allows all CORS origins for local development.
- The frontend has hard-coded `API_BASE = 'http://localhost:8000'` in its views.
