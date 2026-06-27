APP_NAME = "LaserRAG"
API_V1_PREFIX = "/api/v1"

STAGE_NAMES: dict[int, str] = {
    1: "extract",
    2: "analyze",
    3: "metadata",
    4: "split",
    5: "index",
    6: "persist",
}
FIRST_STAGE = 1
LAST_STAGE = 6

UPLOAD_READ_CHUNK_BYTES = 1024 * 1024  # 1 MiB

# --- Auth / JWT ---
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# --- Chat / SSE protocol (spec §5, §7) ---
SSE_EVENT_STATUS = "status"
SSE_EVENT_TOKEN = "token"
SSE_EVENT_CITATIONS = "citations"
SSE_EVENT_DONE = "done"
SSE_STAGE_RETRIEVING = "retrieving"
SSE_STAGE_GENERATING = "generating"

# --- LLM task labels (select the model tier; see LangChainLLMClient) ---
LLM_TASK_CONDENSE = "condense"
LLM_TASK_TRANSLATION = "translation"
LLM_TASK_GENERATION = "generation"
LLM_TASK_SUMMARY = "summary"
