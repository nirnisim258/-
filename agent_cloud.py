"""
Cloud-compatible job search agent.
Uses anthropic SDK (web_search built-in + httpx for direct fetching).
No dependency on claude_agent_sdk or local Claude CLI.
"""

import csv
import io
import os
import time
from datetime import datetime
from pathlib import Path

import anthropic
import httpx

from config import SEARCH_CONFIG, CV_FILE, OUTPUT_DIR

# ── Constants ────────────────────────────────────────────────────────────────
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
MAX_TURNS = 80
FETCH_TIMEOUT = 20
FETCH_MAX_BYTES = 12_000  # ~3,000 tokens per fetch — stays under rate limit

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

# ── Tool definitions ─────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 50,
    },
    {
        "name": "web_fetch",
        "description": (
            "Fetch the HTML/text content of a URL directly. "
            "Use this for Israeli job boards (Drushim, AllJobs, JobsIL, GotFriends) "
            "and specific job posting pages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to fetch"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "save_results",
        "description": "Save the final job results as a CSV file. Call this after scoring all jobs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "csv_content": {
                    "type": "string",
                    "description": "Full CSV content with headers: Title,Company,Location,Site,URL,Match_Score,Key_Requirements,Notes",
                }
            },
            "required": ["csv_content"],
        },
    },
]

SYSTEM_PROMPT = (
    "אתה סוכן חיפוש עבודה מקצועי הפועל בעברית. "
    "בצע את כל השלבים שנדרשים ממך בדייקנות ובשיטתיות. "
    "כאשר אתה מחפש משרות, בצע חיפושים מרובים. "
    "אל תחזור על אותו URL פעמיים."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_cv() -> str:
    cv_path = Path(__file__).parent / CV_FILE
    if cv_path.exists() and cv_path.stat().st_size > 100:
        content = cv_path.read_text(encoding="utf-8")
        if "[שם מלא]" not in content:
            return content
    return ""


def _fetch_url(url: str) -> str:
    try:
        resp = httpx.get(
            url,
            headers=HEADERS,
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
        )
        text = resp.text[:FETCH_MAX_BYTES]
        return f"[HTTP {resp.status_code}]\n{text}"
    except httpx.TimeoutException:
        return f"[TIMEOUT] הדף לא הגיב תוך {FETCH_TIMEOUT} שניות"
    except Exception as e:
        return f"[ERROR] {e}"


def _save_csv(csv_content: str, output_file: Path) -> str:
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(csv_content, encoding="utf-8-sig")
        # Count rows
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        count = max(0, len(rows) - 1)  # minus header
        return f"✅ נשמר: {output_file} ({count} משרות)"
    except Exception as e:
        return f"❌ שגיאה בשמירה: {e}"


def _build_all_search_queries() -> list[str]:
    """
    Build a mixed query list that surfaces results from ALL job sites naturally.
    Broad queries + LinkedIn-specific queries.
    """
    queries = []

    # ── Broad Hebrew searches (catch Drushim, AllJobs, JobsIL, GotFriends, LinkedIn)
    hebrew_terms = SEARCH_CONFIG["short_queries"]["hebrew"]
    for term in hebrew_terms:
        queries.append(f'"{term}" משרה ישראל 2025')

    # ── Broad English searches
    english_terms = SEARCH_CONFIG["short_queries"]["english"]
    for term in english_terms:
        queries.append(f'"{term}" Israel job 2025')

    # ── LinkedIn-specific for depth
    for term in english_terms[:4]:
        queries.append(f'site:linkedin.com/jobs "{term}" Israel')

    # ── Explicit Israeli-board searches (domain mention, not site:)
    il_boards = ["drushim.co.il", "alljobs.co.il", "jobs.il", "gotfriends.co.il"]
    for term in hebrew_terms[:3]:
        for board in il_boards:
            queries.append(f'"{term}" {board}')

    return queries


def _build_prompt(cv_content: str, output_file: Path) -> str:
    all_queries = _build_all_search_queries()

    cv_section = (
        f"\n**קורות חיים של המועמד:**\n{cv_content}\n"
        if cv_content
        else "\n**לא סופקו קורות חיים** — ציון יבוסס על הגדרות החיפוש בלבד.\n"
    )

    queries_block = "\n".join(f"  • {q}" for q in all_queries)

    return f"""
אתה סוכן חיפוש עבודה מקצועי. בצע את כל השלבים הבאים בדייקנות מרבית.
{cv_section}
**פרופיל יעד של ניר:**
- תפקיד: הובלת תחום AI/דיגיטל בארגון גדול (מוביל AI / ראש תחום AI / מנהל חדשנות)
- ניסיון: 7+ שנים | לאומית שירותי בריאות | GenAI, Voice AI, WhatsApp Bots, IVR
- הישגים: IT Awards 2024+2025, VocaLeumit (ראשון בישראל), נחום, פרסום Cambridge
- חוזקות: GenAI בפועל, ניהול 25 עובדים, C-Level, ניהול ספקים ותקציבים
- מיקום: רמת גן (עדיפות מרכז, גמישות סביר)

════════════════════════════════════════
שלב 1 – חיפוש משרות (web_search)
════════════════════════════════════════
בצע web_search עבור כל אחת מהשאילתות הבאות בנפרד.
השאילתות מכסות LinkedIn, Drushim, AllJobs, JobsIL, GotFriends ועוד.
חובה לבצע את כולן — אל תדלג על שאילתה:

{queries_block}

לכל תוצאה שמור: כותרת, חברה, מיקום, URL, שם האתר (LinkedIn / Drushim / AllJobs וכו').

════════════════════════════════════════
שלב 3 – פרטי משרות
════════════════════════════════════════
לכל URL משרה שנמצא: אסוף פרטים עם web_fetch.
אם הדף נעול — רשום "דף נעול".

════════════════════════════════════════
שלב 4 – סינון
════════════════════════════════════════
כלול רק: תפקיד ניהולי/בכיר, קשור ל-AI/דיגיטל/IT, ניסיון ≤10 שנים, ישראל.
אל תכלול: תוכן/שיווק ללא רכיב טכנולוגי, ביטחוני, ERP-only.

════════════════════════════════════════
שלב 5 – ציון התאמה
════════════════════════════════════════
לכל משרה (1-10):
• GenAI/Conversational AI/Voice AI – ניסיון ישיר (+3)
• ניהול צוות טכנולוגי (+2)
• טרנספורמציה דיגיטלית בארגון גדול (+2)
• עבודה מול C-Level (+1)
• ניהול ספקים ותקציבים (+1)
• HealthTech/ממשלה/רגולציה – bonus (+0.5)
ציון ≥5 בלבד.

════════════════════════════════════════
שלב 6 – שמירה
════════════════════════════════════════
קרא לכלי save_results עם CSV מלא.

כותרות חובה:
Title,Company,Location,Site,URL,Match_Score,Key_Requirements,Notes

דוגמה:
"Head of Digital","Bank Hapoalim","Tel Aviv","LinkedIn","https://...","9","AI; ניהול; C-Level","התאמה מצוינת"

════════════════════════════════════════
שלב 7 – סיכום
════════════════════════════════════════
לאחר השמירה:
1. סך משרות לפי אתר
2. TOP 5 משרות מומלצות עם הסבר
3. מיומנויות שנדרשות הרבה ולא מופיעות מספיק בקורות החיים

התחל עכשיו — שלב 1!
"""


# ── Main search runner ────────────────────────────────────────────────────────

def run_search(log_callback, data_dir: Path | None = None) -> str:
    """
    Run the job search using anthropic SDK.
    log_callback(line: str) is called for each output line.
    Returns the path to the saved CSV file, or empty string on failure.
    """
    if data_dir is None:
        data_dir = Path(__file__).parent / OUTPUT_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = data_dir / f"jobs_{timestamp}.csv"

    cv_content = load_cv()
    prompt = _build_prompt(cv_content, output_file)

    log_callback(f"{'='*50}")
    log_callback(f"  🔍  סוכן חיפוש עבודה (Cloud)")
    log_callback(f"  💾  שומר ב: {output_file}")
    if cv_content:
        log_callback(f"  ✅  קורות חיים נטענו ({len(cv_content):,} תווים)")
    log_callback(f"{'='*50}")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log_callback("❌ חסר ANTHROPIC_API_KEY בסביבה!")
        return ""

    client = anthropic.Anthropic(api_key=api_key)

    messages: list[dict] = [
        {
            "role": "user",
            "content": [
                # cache the long prompt — saves cost on retries
                {"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}},
            ],
        }
    ]

    saved_file = ""
    turn = 0

    while turn < MAX_TURNS:
        turn += 1
        log_callback(f"\n[תור {turn}]")

        response = None
        for attempt in range(4):
            try:
                response = client.beta.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=[{"type": "text", "text": SYSTEM_PROMPT,
                              "cache_control": {"type": "ephemeral"}}],
                    tools=TOOLS,
                    messages=messages,
                    betas=["web-search-2025-03-05"],
                )
                break
            except anthropic.RateLimitError:
                wait = 60 * (attempt + 1)
                log_callback(f"⏳ Rate limit — ממתין {wait} שניות...")
                time.sleep(wait)
            except anthropic.APIError as e:
                log_callback(f"❌ API שגיאה: {e}")
                break
        if response is None:
            log_callback("❌ נכשל אחרי 4 ניסיונות")
            break

        # Log text output
        for block in response.content:
            if hasattr(block, "text") and block.text:
                log_callback(block.text)

        if response.stop_reason == "end_turn":
            log_callback("\n✅ הסוכן סיים!")
            break

        # Handle tool_use blocks
        tool_results = []
        has_custom_tool = False

        for block in response.content:
            if not hasattr(block, "type") or block.type != "tool_use":
                continue

            name = block.name
            inp = block.input if hasattr(block, "input") else {}

            if name == "web_search":
                # web_search is handled server-side in the beta API
                # We still need to add a placeholder tool_result so the loop continues
                query_str = inp.get("query", "")
                log_callback(f"🔍 web_search: {query_str[:80]}")
                # Server handles results; we don't add tool_result here
                # (the API already injected results into response content)

            elif name == "web_fetch":
                url = inp.get("url", "")
                log_callback(f"🌐 web_fetch: {url[:80]}")
                result = _fetch_url(url)
                log_callback(f"   → {len(result)} תווים")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
                has_custom_tool = True

            elif name == "save_results":
                csv_content = inp.get("csv_content", "")
                log_callback(f"💾 שומר תוצאות...")
                result = _save_csv(csv_content, output_file)
                log_callback(result)
                if "✅" in result:
                    saved_file = str(output_file)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
                has_custom_tool = True

        # Add assistant turn
        messages.append({"role": "assistant", "content": response.content})

        # Add tool results if any
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        elif not has_custom_tool and response.stop_reason == "tool_use":
            # web_search only — server handled it, results are in the response
            # No extra user message needed; loop will call model again to continue
            pass
        else:
            # Nothing left to do
            break

    log_callback(f"\n{'='*50}")
    log_callback(f"  ✅  החיפוש הושלם!")
    if saved_file:
        log_callback(f"  📊  תוצאות: {saved_file}")
    log_callback(f"{'='*50}")

    return saved_file
