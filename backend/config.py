import os
from dotenv import load_dotenv

load_dotenv()

# --- Search Configuration ---
# API Key
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

# Search settings
SEARCH_DEPTH = "basic"
MAX_SEARCH_RESULTS = 5
MIN_SEARCH_RESULTS = 3
INCLUDE_ANSWER = "advanced"
INCLUDE_RAW_CONTENT = True
# If relevance score is below this threshold, try to trim results, while keeping MIN_SEARCH_RESULTS
RELEVANCE_THRESHOLD = 0.6

# Cache settings
SEARCH_CACHE_TTL = 3600  # 1 hour in seconds

# --- Network & Integration Timeouts (Seconds) ---
TIMEOUT_LLM_BLOCKING = None         # Standard Chat completions (None = wait infinitely for local queue)
TIMEOUT_LLM_ASYNC = None            # Parallel AI generation tasks
TIMEOUT_TAVILY_SEARCH = 15          # Sync broad search 
TIMEOUT_TAVILY_SEARCH_ASYNC = 60    # Async broad search
TIMEOUT_TAVILY_MAP = 150            # Deep link discovery
TIMEOUT_TAVILY_EXTRACT = 60         # Deep scraping fallbacks
TIMEOUT_WEB_SCRAPE = 15             # Standard webpage text/markdown pulling
TIMEOUT_IMAGE_FETCH = 15            # Encoding images directly into base64
