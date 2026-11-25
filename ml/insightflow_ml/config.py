import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    """Tiny .env reader (no extra package). Existing environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), val)


_load_dotenv(ROOT / ".env")
ARTIFACT_DIR = Path(os.getenv("ML_ARTIFACT_DIR", ROOT / "artifacts"))
DATA_DIR = ROOT / "data"

# ---- Label / feature definitions (change ONLY via team agreement; see README) ----
LABEL_WINDOW_DAYS = 7      # "retained" = came back on a later calendar day within 7 days
SESSION_GAP_MIN = 30       # inactivity gap that starts a new session
LOOKBACK_DAYS = int(os.getenv("ML_LOOKBACK_DAYS", 90))
MIN_TRAIN_ROWS = 200       # refuse to train on fewer labelled visitors than this
RANDOM_SEED = 42

# ---- Event vocabulary (matches names used by the SDK and demoData.service.js) ----
CLICK_EVENTS = {"click", "button_click", "cta_click"}
SCROLL_EVENTS = {"scroll", "scroll_depth"}
CONVERSION_EVENTS = {
    "purchase", "signup", "lead_capture", "demo_request",
    "form_submit", "newsletter_signup", "upgrade_plan",
}
INTENT_EVENTS = {
    "add_to_cart", "checkout", "exam_start", "invite_member",
    "feature_used", "article_read",
}
FRICTION_PATTERN = r"quit|retry|error|fail|abandon"
BOT_UA_PATTERN = r"bot|crawler|spider|headless|lighthouse|python-requests|curl/|wget|axios/|postman"

# ---- Model input columns ----
LOG_COLS = [
    "n_events", "n_page_views", "n_clicks", "n_scroll_events", "n_intent_events",
    "n_friction_events", "n_unique_pages", "n_event_types", "duration_sec", "events_per_min",
]
LIN_COLS = ["max_scroll_depth", "hour_sin", "hour_cos"]
BIN_COLS = ["has_conversion", "is_identified", "is_mobile", "is_weekend", "bounced"]
CAT_COLS = ["referrer_type"]
FEATURE_COLUMNS = LOG_COLS + LIN_COLS + BIN_COLS + CAT_COLS
TARGET = "returned_7d"
