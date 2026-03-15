import re
import sqlite3
import logging

logger = logging.getLogger(__name__)

DB_PATH = "seen_items.db"

# Buffer for notifications to send in the current cycle
_pending_notifications = []

# GPU patterns (order matters — more specific first)
_GPU_PATTERNS = [
    r'\brtx\s+a\d{4}\b',
    r'\bquadro\s+(?:rtx\s+)?\d{4}\b',
    r'\brtx\s+\d{4}(?:\s+(?:ti|super))?\b',
    r'\bgtx\s+\d{4}(?:\s+ti)?\b',
    r'\bradeon\s+rx\s+\d{4}[a-z]{0,2}\b',
    r'\brx\s+\d{4}[a-z]{0,2}\b',
]

# CPU patterns (order matters — more specific first)
_CPU_PATTERNS = [
    r'\bcore\s+ultra\s+[579]\s+\d{3}[a-z]{0,3}\b',
    r'\bi[3579]-\d{4,5}[a-z]{0,3}\b',
    r'\bi[3579]\s+\d{4,5}[a-z]{0,3}\b',
    r'\bm[1-5]\s+(?:pro|max|ultra)\b',
    r'\bm[1-5]\b',
    r'\bryzen\s+[3579]\s+\d{4}[a-z]{0,3}\b',
    r'\bryzen\s+[3579]\b',
]


def extract_model(title: str):
    """
    Extracts CPU or GPU model name from a listing title using regex.
    Returns (model_string, 'cpu' or 'gpu') or (None, None).
    """
    t = title.lower()

    for pattern in _GPU_PATTERNS:
        m = re.search(pattern, t)
        if m:
            return m.group(0).strip(), 'gpu'

    for pattern in _CPU_PATTERNS:
        m = re.search(pattern, t)
        if m:
            return m.group(0).strip(), 'cpu'

    return None, None


def init_table():
    """Creates unknown_models table if it does not exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS unknown_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                model_type TEXT NOT NULL,
                title TEXT NOT NULL,
                price_usd REAL NOT NULL,
                item_url TEXT DEFAULT '',
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                count INTEGER DEFAULT 1
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_unknown_model ON unknown_models(model)')
        conn.commit()


def _was_notified_today(model: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM unknown_models WHERE model = ? AND date(first_seen) = date('now')",
            (model,)
        ).fetchone()
        return row is not None


def _save_or_update(model: str, model_type: str, title: str, price_usd: float, item_url: str):
    with sqlite3.connect(DB_PATH) as conn:
        existing = conn.execute(
            "SELECT id FROM unknown_models WHERE model = ?", (model,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE unknown_models SET count = count + 1, last_seen = CURRENT_TIMESTAMP WHERE model = ?",
                (model,)
            )
        else:
            conn.execute(
                "INSERT INTO unknown_models (model, model_type, title, price_usd, item_url) VALUES (?,?,?,?,?)",
                (model, model_type, title, price_usd, item_url)
            )
        conn.commit()


def track_unknown(title: str, price_usd: float, item_url: str = ""):
    """
    Called when a listing passes all filters but matches no criterion in limits.json.
    Extracts the model, saves to DB, and queues a Telegram notification if it's new today.
    """
    model, model_type = extract_model(title)
    if not model:
        return

    already_notified = _was_notified_today(model)
    _save_or_update(model, model_type, title, price_usd, item_url)

    if not already_notified:
        _pending_notifications.append({
            'model': model,
            'model_type': model_type,
            'title': title,
            'price_usd': price_usd,
            'item_url': item_url,
        })
        logger.info(f"Unknown model queued for notification: {model.upper()}")


def pop_pending():
    """Returns all pending notifications and clears the buffer."""
    items = list(_pending_notifications)
    _pending_notifications.clear()
    return items


def get_unknown_report(days: int = 7) -> str:
    """Returns a formatted Telegram-ready report of unknown models seen in the last N days."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT model, model_type, count, price_usd
            FROM unknown_models
            WHERE first_seen >= datetime('now', ?)
            ORDER BY count DESC
            LIMIT 30
            """,
            (f'-{days} days',)
        ).fetchall()

    if not rows:
        return f"За останні {days} днів невідомих моделей не знайдено."

    gpu_rows = [(m, c, p) for m, mt, c, p in rows if mt == 'gpu']
    cpu_rows = [(m, c, p) for m, mt, c, p in rows if mt == 'cpu']

    lines = [f"🔍 <b>Невідомі моделі (останні {days} днів):</b>\n"]

    if gpu_rows:
        lines.append("🎮 <b>GPU:</b>")
        for model, count, price in gpu_rows:
            lines.append(
                f"• <code>{model.upper()}</code> — {count} лот(ів), від ~${price:.0f}\n"
                f"  → <code>/addgpu {model} [грн]</code>"
            )
        lines.append("")

    if cpu_rows:
        lines.append("💻 <b>CPU:</b>")
        for model, count, price in cpu_rows:
            lines.append(
                f"• <code>{model.upper()}</code> — {count} лот(ів), від ~${price:.0f}\n"
                f"  → <code>/addcpu {model} [грн]</code>"
            )

    return "\n".join(lines)
