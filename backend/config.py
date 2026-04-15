import os
from dotenv import load_dotenv

load_dotenv()

def get_secret(secret_name, default=None):
    try:
        with open(f"/run/secrets/{secret_name}", "r") as f:
            return f.read().strip()
    except IOError:
        return os.getenv(secret_name, default)

DATA_DIR = get_secret("DATA_DIR", "./backend/data")
os.makedirs(DATA_DIR, exist_ok=True)

# =============================================================================
# APP LEVEL AUTH
# =============================================================================
APP_PASSWORD = get_secret("APP_PASSWORD", None)

# =============================================================================
# AI INFERENCE & INFRASTRUCTURE
# =============================================================================
AI_URL = get_secret("AI_URL")
AI_API_KEY = get_secret("AI_API_KEY", "")
EMBEDDING_URL = get_secret("EMBEDDING_URL", None)
EMBEDDING_API_KEY = get_secret("EMBEDDING_API_KEY", None)

# Strict Validation: Fail if EMBEDDING_URL is missing
if not EMBEDDING_URL:
    raise ValueError(
        "FATAL: EMBEDDING_URL is missing from secrets. "
        "Falling back to AI_URL is deprecated and strictly forbidden for security and isolation."
    )

PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "True").lower() == "true"
CHROMA_PATH = get_secret("CHROMA_PATH", os.path.abspath(os.path.join(DATA_DIR, "chroma_db")))

# Ensure persistence directories exist
os.makedirs(CHROMA_PATH, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "logs", "general"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "tasks"), exist_ok=True)

# =============================================================================
# SEARCH (Tavily API)
# =============================================================================
# TAVILY_API_KEY is loaded from environment/secrets for documentation compliance
TAVILY_API_KEY = get_secret("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

SEARCH_DEPTH = "basic"
MAX_SEARCH_RESULTS = 5
MIN_SEARCH_RESULTS = 3
INCLUDE_ANSWER = "advanced"
INCLUDE_RAW_CONTENT = True
RELEVANCE_THRESHOLD = 0.6          # Below this, trim results (keep MIN_SEARCH_RESULTS)
SEARCH_CACHE_TTL = 3600            # Seconds before cached search expires

# =============================================================================
# NETWORK & INTEGRATION TIMEOUTS (seconds)
# =============================================================================
TIMEOUT_LLM_BLOCKING = None        # Standard chat completions (None = infinite for local queue)
TIMEOUT_LLM_ASYNC = None           # Parallel AI generation tasks
TIMEOUT_TAVILY_SEARCH = 15         # Sync search
TIMEOUT_TAVILY_SEARCH_ASYNC = 60   # Async search
TIMEOUT_TAVILY_MAP = 150           # Deep link discovery (slow because recursive)
TIMEOUT_TAVILY_EXTRACT = 60        # JS-rendered page scraping fallback
TIMEOUT_WEB_SCRAPE = 15            # Standard HTTP GET for markdown extraction
TIMEOUT_IMAGE_FETCH = 15           # Base64-encoding images for VLM
TIMEOUT_URLHAUS = 5                # URLhaus malware check

# =============================================================================
# WEB EXTRACTION & PARSING
# =============================================================================
URL_FETCH_RETRIES = 5              # Max redirects to follow
MAX_CHARS_VISIT_PAGE = 8000        # Character cap for standard visit_page tool

# Minimum content length thresholds (chars) to accept extraction as valid
RESEARCH_EXTRACT_MIN_RAW_CONTENT = 50       # Raw content from Tavily search results
RESEARCH_EXTRACT_MIN_PDF_CONTENT = 100      # PDF extraction via pymupdf
RESEARCH_EXTRACT_MIN_TAVILY_CONTENT = 100   # Tavily Extract API fallback
RESEARCH_MAP_MIN_CONTENT = 100              # Deep-mode mapped sub-pages
RESEARCH_CONTENT_MIN_LENGTH_REGULAR = 50    # Direct HTTP GET (regular mode)
RESEARCH_CONTENT_MIN_LENGTH_DEEP = 200      # Direct HTTP GET (deep mode, higher bar)

# Per-source content limit passed to the LLM (chars, applied per URL's content)
RESEARCH_CONTENT_CHUNK_LIMIT = 15000

# =============================================================================
# RAG & EMBEDDINGS
# =============================================================================
RAG_CHUNK_MAX_CHARS = 2200         # Max chars per embedding chunk
RAG_MIN_SEMANTIC_SCORE = 0.40      # Minimum cosine similarity for retrieval (post-RRF)
RAG_DEDUP_THRESHOLD = 0.80         # Similarity above this = duplicate chunk
RAG_FETCH_MULTIPLIER = 2           # Overfetch ratio for re-ranking
RAG_DECAY_RATE = 0.30              # Time-decay weight for older memories
RAG_RETRIEVAL_LIMIT = 500          # Hard cap on total retrieved chunks
RAG_GRID_WORKERS = int(os.getenv("RAG_GRID_WORKERS", 16))  # Parallel workers for optimization

# =============================================================================
# RAG MIGRATION SETTINGS
# =============================================================================
RAG_MIGRATION_BATCH_SIZE = int(os.getenv("RAG_MIGRATION_BATCH_SIZE", 50))

# =============================================================================
# EMBEDDING TOKEN LIMITS
# Maximum tokens per embedding request (to stay within tokenizer context window)
# Using 1000 tokens per chunk: embeddinggemma-300m has 2048 context window,
# allowing ~2 chunks per LLM context window for retrieval with better context
# =============================================================================
EMBEDDING_MAX_TOKENS_CORE = int(os.getenv("EMBEDDING_MAX_TOKENS_CORE", 1000))       # Core memory embeddings
EMBEDDING_MAX_TOKENS_RESEARCH = int(os.getenv("EMBEDDING_MAX_TOKENS_RESEARCH", 1000))  # Research RAG embeddings
EMBEDDING_MAX_TOKENS_FILE = int(os.getenv("EMBEDDING_MAX_TOKENS_FILE", 1000))       # File RAG embeddings
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", 1024))               # Number of chunks per request

# =============================================================================
# FILE RAG ENHANCEMENTS
# =============================================================================
HYBRID_SEARCH_ENABLED = True          # Enable BM25 + vector fusion for File RAG
CODE_CHUNKING_ENABLED = True          # Enable syntax-aware chunking for code files
# =============================================================================
# FILE TYPE CLASSIFIER
# =============================================================================
FILE_TYPE_DETECTION_ENABLED = True    # Enable content-based file type detection
CLASSIFIER_CODE_THRESHOLD = float(os.getenv("CLASSIFIER_CODE_THRESHOLD", 20.0))
CLASSIFIER_DOC_THRESHOLD = float(os.getenv("CLASSIFIER_DOC_THRESHOLD", 0.35))

# =============================================================================
# CORE MEMORY MANAGEMENT
# =============================================================================
MEMORY_MAX_INJECT_CHARS = int(os.getenv("MEMORY_MAX_INJECT_CHARS", 10000))
MEMORY_MAX_ADD_PER_TURN = int(os.getenv("MEMORY_MAX_ADD_PER_TURN", 5))
MEMORY_MAX_EDIT_PER_TURN = int(os.getenv("MEMORY_MAX_EDIT_PER_TURN", 5))
MEMORY_MAX_DELETE_PER_TURN = int(os.getenv("MEMORY_MAX_DELETE_PER_TURN", 5))

# =============================================================================
# UI & STREAMING
# =============================================================================
RESEARCH_UI_THOUGHT_MIN_LENGTH = 15       # Min chars to show reasoning snippet
RESEARCH_UI_THOUGHT_SNIPPET_LENGTH = 120  # Max chars shown in real-time thought preview
RESEARCH_UI_STREAM_UPDATE_INTERVAL = 40   # Characters between stream flush events
RESEARCH_VISION_MIN_RESPONSE_LENGTH = 20  # Min VLM response to consider valid

# =============================================================================
# RESEARCH: LLM MAX TOKENS
# =============================================================================
RESEARCH_MAX_TOKENS_SCOUT = int(os.getenv("RESEARCH_MAX_TOKENS_SCOUT", 8192))
RESEARCH_MAX_TOKENS_PLANNING = int(os.getenv("RESEARCH_MAX_TOKENS_PLANNING", 8192))
RESEARCH_MAX_TOKENS_REFLECTION = int(os.getenv("RESEARCH_MAX_TOKENS_REFLECTION", 8192))
RESEARCH_MAX_TOKENS_STEP_WRITER = int(os.getenv("RESEARCH_MAX_TOKENS_STEP_WRITER", 16384))
RESEARCH_MAX_TOKENS_SUMMARY = int(os.getenv("RESEARCH_MAX_TOKENS_SUMMARY", 8192))
RESEARCH_MAX_TOKENS_SYNTHESIS = int(os.getenv("RESEARCH_MAX_TOKENS_SYNTHESIS", 16384))
RESEARCH_MAX_TOKENS_TRIAGE = int(os.getenv("RESEARCH_MAX_TOKENS_TRIAGE", 16384))
RESEARCH_MAX_TOKENS_VISION = int(os.getenv("RESEARCH_MAX_TOKENS_VISION", 8192))
RESEARCH_MAX_TOKENS_RAG_CONTEXT = int(os.getenv("RESEARCH_MAX_TOKENS_RAG_CONTEXT", 30000))

# Audit max tokens = same as step writer (surgeon patches one section at a time)
RESEARCH_MAX_TOKENS_AUDIT = int(os.getenv("RESEARCH_MAX_TOKENS_AUDIT", RESEARCH_MAX_TOKENS_STEP_WRITER))

# =============================================================================
# RESEARCH: SECTION-BASED PLANNING & EXECUTION
# =============================================================================
RESEARCH_MAX_RETRIES = int(os.getenv("RESEARCH_MAX_RETRIES", 3))        # General research retry limit
RESEARCH_MAX_PLAN_RETRIES = 3              # Planner retries on validation failure
RESEARCH_MAX_QUERIES_PER_SECTION = 2       # Max search queries per report section
RESEARCH_MAX_TOTAL_QUERIES = 10            # Cap across all sections in a plan
RESEARCH_MAX_GAPS_PER_SECTION = int(os.getenv("RESEARCH_MAX_GAPS_PER_SECTION", 2))
RESEARCH_TRIAGE_MAX_FACTS = int(os.getenv("RESEARCH_TRIAGE_MAX_FACTS", 25))
RESEARCH_MIN_SECTION_LEN = 300             # Min chars for a written section to be accepted

# Per-query content budget (actual token counting via token_counter.py)
RESEARCH_CONTENT_BUDGET_REGULAR = 50000    # Tokens per query, regular mode
RESEARCH_CONTENT_BUDGET_DEEP = 80000       # Tokens per query, deep mode

# =============================================================================
# RESEARCH: MEANDER DETECTION
# Limits on <think> block length (TOKENS). If reasoning exceeds the limit AND
# content output is below CONTENT_THRESHOLD, the response is considered
# "meandering" and gets retried or truncated.
# =============================================================================
RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS = 125

RESEARCH_MEANDER_THOUGHT_LIMIT_SCOUT_TOKENS = 1500
RESEARCH_MEANDER_THOUGHT_LIMIT_PLANNING_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_TRIAGE_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER_TOKENS = 5000
RESEARCH_MEANDER_THOUGHT_LIMIT_SUMMARY_TOKENS = 1500
RESEARCH_MEANDER_THOUGHT_LIMIT_SYNTHESIS_TOKENS = 3750
RESEARCH_MEANDER_THOUGHT_LIMIT_VISION_TOKENS = 1000

# Audit meander limit = same as step writer (surgeon produces one section)
RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT_TOKENS = RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER_TOKENS

# =============================================================================
# RESEARCH: SEARCH & SOURCE SELECTION
# =============================================================================
RESEARCH_TAVILY_MAX_RESULTS_INITIAL = int(os.getenv("RESEARCH_TAVILY_MAX_RESULTS_INITIAL", 20))
RESEARCH_TAVILY_MAX_RESULTS_FOLLOWUP = int(os.getenv("RESEARCH_TAVILY_MAX_RESULTS_FOLLOWUP", 10))
RESEARCH_SELECT_TOP_URLS_COUNT = int(os.getenv("RESEARCH_SELECT_TOP_URLS_COUNT", 4))
RESEARCH_SELECT_TOP_URLS_FOLLOWUP_COUNT = int(os.getenv("RESEARCH_SELECT_TOP_URLS_FOLLOWUP_COUNT", 2))
RESEARCH_SCOUT_PRELIM_RESULTS_COUNT = 5    # Scout phase preliminary search count
RESEARCH_DEEP_MAP_MAX_URLS = 5             # Max sub-pages to crawl per source (deep mode)
TAVILY_MAP_MAX_DEPTH = 3                   # Crawl depth for Tavily Map
TAVILY_MAP_MAX_BREADTH = 10                # Crawl breadth for Tavily Map

# =============================================================================
# RESEARCH: LLM TEMPERATURE & SAMPLING (Reasoning Optimized)
# =============================================================================
RESEARCH_SAMPLING_TEMPERATURE = 0.7
RESEARCH_SAMPLING_MIN_P = 0.1
RESEARCH_SAMPLING_DRY_MULTIPLIER = 0.8
RESEARCH_SAMPLING_DRY_BASE = 1.75
RESEARCH_SAMPLING_DRY_ALLOWED_LENGTH = 3
RESEARCH_SAMPLING_XTC_PROBABILITY = 0.1
RESEARCH_SAMPLING_REPEAT_PENALTY = 1.1

# Fallback temperature used on retry attempts (reflection, writer, surgeon)
RESEARCH_TEMPERATURE_RETRY_FALLBACK = 0.1
RESEARCH_SAMPLING_DRY_RETRIAL_BOOST = 0.2

# =============================================================================
# RESEARCH: FINAL AUDIT & REFINEMENT
# =============================================================================
RESEARCH_AUDIT_ENABLED = True
RESEARCH_AUDIT_MAX_HIGH_SEVERITY = 999     # Fix all citation/contradiction issues
RESEARCH_AUDIT_MAX_MEDIUM_SEVERITY = 5     # Cap rewrites for medium issues
RESEARCH_AUDIT_MAX_LOW_SEVERITY = 3        # Cap rewrites for low issues
RESEARCH_SURGEON_MAX_RETRIES = 2           # Max attempts per section before structured fallback

# =============================================================================
# RESEARCH: VISION & IMAGE PROCESSING
# =============================================================================
RESEARCH_MAX_IMAGES_PER_PAGE = 3           # Max inline images to VLM-process per page
RESEARCH_MAX_SEARCH_IMAGES = 10            # Max Tavily search result images to process
RESEARCH_IMAGE_FETCH_RETRIES = 5           # Retries for fetching image bytes
RESEARCH_VISION_RETRIES = 3               # Retries for VLM inference calls

# =============================================================================
# RESEARCH: CONVERSATION HISTORY CONTEXT
# =============================================================================
RESEARCH_CONTEXT_HISTORY_SCOUT = 5         # Messages passed to scout
RESEARCH_CONTEXT_HISTORY_PLANNING = 10     # Messages passed to planner
# =============================================================================
# LOCALIZATION & TIME
# =============================================================================
USER_TIMEZONE = os.getenv("TZ", "Asia/Kolkata")

# =============================================================================
# CANVAS SYSTEM
# =============================================================================
# Max characters of canvas content injected into the system prompt as active
# canvas context. Large research reports easily exceed 20k chars; 32k covers
# most reports while keeping the system prompt manageable.
CANVAS_ACTIVE_CONTEXT_CHAR_LIMIT = 32000

# =============================================================================
# CACHE TTL CONFIGURATION
# =============================================================================
CACHE_ENTRY_TTL_SECONDS = int(os.getenv("CACHE_ENTRY_TTL_SECONDS", 3600))      # 1 hour default
DEFAULT_TTL_SECONDS = CACHE_ENTRY_TTL_SECONDS  # Alias for config_directives.md compliance
CACHE_CLEANUP_INTERVAL = int(os.getenv("CACHE_CLEANUP_INTERVAL", 300))         # 5 min
CACHE_RETRY_COUNT = int(os.getenv("CACHE_RETRY_COUNT", 2))                     # Retry attempts

# =============================================================================
# ERROR HANDLING CONFIGURATION
# =============================================================================
ERROR_RETRY_BASE_DELAY = float(os.getenv("ERROR_RETRY_BASE_DELAY", 0.1))       # Base delay for retry backoff
CIRCUIT_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", 5))     # Failures before opening circuit
CIRCUIT_RECOVERY_TIMEOUT = float(os.getenv("CIRCUIT_RECOVERY_TIMEOUT", 30))    # Seconds before attempting recovery

# =============================================================================
# RETRY CONFIGURATION
# =============================================================================
RETRY_COUNT = int(os.getenv("RETRY_COUNT", 2))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", 1))

# =============================================================================
# TOOL CONFIGURATION
# =============================================================================
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", 8))

# =============================================================================
# FILE UPLOAD SETTINGS
# =============================================================================
# Maximum file size for uploads (default 100MB for text-only models)
FILE_UPLOAD_MAX_SIZE = int(os.getenv("FILE_UPLOAD_MAX_SIZE", 100 * 1024 * 1024))  # 100MB
FILE_STORAGE_PATH = os.path.join(DATA_DIR, 'files')
os.makedirs(FILE_STORAGE_PATH, exist_ok=True)

# Allowed MIME types for file uploads
FILE_UPLOAD_ALLOWED_TYPES = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'image/png',
    'image/jpeg',
    'image/gif',
    'video/mp4',
    'audio/mpeg',
    'audio/wav'
]

# File processing options
# FILE_RAG_ENABLED: Enable RAG storage for uploaded files
# FILE_VISION_ENABLED: Enable vision processing for image/video files
# For text-only models: RAG enabled, vision disabled
FILE_RAG_ENABLED = True
FILE_VISION_ENABLED = True  # Maximum tool rounds per conversation

# Text-only model file upload settings
# TEXT_ONLY_MODEL_MAX_FILES: Maximum number of files per chat for text-only models
# Set to None for no limit, or a positive integer to enforce a limit
TEXT_ONLY_MODEL_MAX_FILES = None  # No limit by default

# =============================================================================
# FILE UPLOAD - ADDITIONAL SETTINGS
# =============================================================================
# Maximum characters to return from read_file tool
READ_FILE_CONTENT_LIMIT = int(os.getenv("READ_FILE_CONTENT_LIMIT", 10000))
# Maximum pages to extract from PDF for vision analysis
PDF_PAGE_LIMIT = int(os.getenv("PDF_PAGE_LIMIT", 5))

# =============================================================================
# PDF EXTRACTION SETTINGS
# =============================================================================
# Enable PDF text extraction
PDF_EXTRACTOR_ENABLED = True
# Enable OCR fallback for scanned PDFs
PDF_OCR_ENABLED = True
# OCR languages to use (easyocr supported languages)
PDF_OCR_LANGUAGES = ['en']
# Minimum content length required after extraction
PDF_EXTRACTION_MIN_CONTENT = 50
