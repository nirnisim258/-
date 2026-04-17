"""
סוכן חיפוש עבודה אוטומטי - מבוסס Claude Agent SDK
חיפוש ב: LinkedIn, Drushim, AllJobs, Jobs.il, GotFriends
"""

import anyio
import os
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus

# תמיכה ב-Unicode בטרמינל Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        ResultMessage,
        AssistantMessage,
        TextBlock,
    )
except ImportError:
    print("❌ חסר חבילת claude-agent-sdk")
    print("   הרץ: pip install claude-agent-sdk")
    sys.exit(1)

from config import SEARCH_CONFIG, CV_FILE, OUTPUT_DIR


# ──────────────────────────────────────────
# פונקציות עזר
# ──────────────────────────────────────────

def load_cv() -> str:
    cv_path = Path(__file__).parent / CV_FILE
    if cv_path.exists() and cv_path.stat().st_size > 100:
        content = cv_path.read_text(encoding="utf-8")
        if "[שם מלא]" not in content:
            return content
    return ""


def build_direct_fetch_urls() -> dict[str, list[str]]:
    """בנה URLs ישירים לדפי חיפוש בכל אתר עבודה."""
    templates = SEARCH_CONFIG.get("search_url_templates", {})
    short_queries = SEARCH_CONFIG.get("short_queries", {})
    all_terms = short_queries.get("hebrew", []) + short_queries.get("english", [])

    urls: dict[str, list[str]] = {}
    for site, template in templates.items():
        if not SEARCH_CONFIG["sites"].get(site, False):
            continue
        urls[site] = [template.format(query=quote_plus(term)) for term in all_terms]
    return urls


def build_linkedin_queries() -> list[str]:
    """בנה שאילתות WebSearch ממוקדות ל-LinkedIn."""
    queries = []
    for term in SEARCH_CONFIG["short_queries"]["english"]:
        queries.append(f'site:linkedin.com/jobs "{term}" Israel')
    for term in SEARCH_CONFIG["short_queries"]["hebrew"]:
        queries.append(f'site:linkedin.com/jobs "{term}"')
    return queries


def build_prompt(cv_content: str, output_file: str) -> str:
    direct_urls = build_direct_fetch_urls()
    linkedin_queries = build_linkedin_queries()

    cv_section = (
        f"\n**קורות חיים של המועמד:**\n{cv_content}\n"
        if cv_content
        else "\n**לא סופקו קורות חיים** - ציון התאמה יבוסס על הגדרות החיפוש בלבד.\n"
    )

    # בנה בלוק URLs לכל אתר
    fetch_blocks = ""
    for site, urls in direct_urls.items():
        fetch_blocks += f"\n**{site}** — אסוף כל URL בנפרד עם WebFetch:\n"
        for url in urls:
            fetch_blocks += f"  • {url}\n"

    linkedin_block = "\n".join(f"  • {q}" for q in linkedin_queries)

    return f"""
אתה סוכן חיפוש עבודה מקצועי. בצע את כל השלבים הבאים בדייקנות מרבית.
{cv_section}
**פרופיל יעד של ניר:**
- תפקיד: הובלת תחום AI/דיגיטל בארגון גדול (כמו מוביל AI / ראש תחום AI / מנהל חדשנות)
- ניסיון: 7+ שנים | לאומית שירותי בריאות | GenAI, Voice AI, WhatsApp Bots, IVR
- הישגים: IT Awards 2024+2025, VocaLeumit (ראשון בישראל), נחום, פרסום Cambridge
- חוזקות: GenAI בפועל, ניהול 25 עובדים, עבודה מול C-Level, ניהול ספקים ותקציבים
- מיקום: רמת גן (עדיפות מרכז, גמישות סביר)

**דוגמת משרה אידיאלית (רמת התאמה = 10):**
"מוביל/ת AI – הובלת אסטרטגיית AI וטרנספורמציה דיגיטלית, ניהול פרויקטים E2E מול הנהלה+פיתוח+דאטה, ארגון גדול (Enterprise)"

════════════════════════════════════════
שלב 1 – LinkedIn (WebSearch)
════════════════════════════════════════
הפעל WebSearch עבור כל אחת מהשאילתות הבאות (כל שאילתה בנפרד):
{linkedin_block}

לכל תוצאה שמור: כותרת, חברה, מיקום, URL מלא.

════════════════════════════════════════
שלב 2 – אתרים ישראלים (WebFetch ישיר)
════════════════════════════════════════
אסוף משרות מאתרי העבודה הישראלים ישירות.
לכל URL: הפעל WebFetch, חלץ את כל המשרות שמופיעות בדף.
{fetch_blocks}
**חשוב:** אם דף מסוים מחזיר שגיאה, המשך לדף הבא. אל תעצור.
מכל דף, חלץ את: כותרת המשרה, שם החברה, מיקום, URL המשרה.

════════════════════════════════════════
שלב 3 – איסוף פרטי משרות (WebFetch)
════════════════════════════════════════
לכל URL של משרה שנמצאה בשלב 1+2:
• אסוף עם WebFetch את דרישות התפקיד המלאות
• אם הדף דורש התחברות – רשום "דף נעול"
• אם כבר יש מספיק פרטים מהחיפוש – דלג

════════════════════════════════════════
שלב 4 – סינון ורלוונטיות
════════════════════════════════════════
**כלול** רק משרות שעומדות בכל התנאים:
✓ תפקיד ניהולי/בכיר (לא ביצועי-טכני בלבד)
✓ קשור לדיגיטל, AI, IT, חדשנות, טרנספורמציה
✓ ניסיון נדרש ≤ 10 שנים
✓ מיקום: ישראל (עדיפות למרכז)

**אל תכלול:**
✗ תפקידי תוכן/מדיה/שיווק ללא רכיב טכנולוגי
✗ תפקידים ביטחוניים/הגנה ללא רקע מתאים
✗ Supply Chain / פיננסים / ERP-only ללא טרנספורמציה

════════════════════════════════════════
שלב 5 – ציון התאמה לפרופיל ניר
════════════════════════════════════════
**חוזקות ייחודיות של ניר — תחשב אותן:**
- הוביל פרויקטי GenAI/Conversational AI בפועל (נחום, VocaLeumit — ראשון בישראל)
- IT Awards 2024 + 2025 (הכרה מקצועית לאומית)
- ניסיון HealthTech בארגון של אלפי עובדים (לאומית)
- פרסום אקדמי Cambridge (אמינות מחקרית)
- Commbox, WhatsApp Business API, Voice AI, IVR — ניסיון מעשי

לכל משרה, חשב ציון 1-10 לפי:
• GenAI / Conversational AI / Voice AI – ניסיון ישיר (+3)
• ניהול צוותים טכנולוגיים – ניסיון מוכח (+2)
• טרנספורמציה דיגיטלית בארגון גדול (+2)
• עבודה מול C-Level (+1)
• ניהול ספקים ותקציבים (+1)
• HealthTech / ארגון ממשלתי / רגולציה — bonus (+0.5)

ציון 8-10 = התאמה מצוינת
ציון 5-7  = התאמה טובה
ציון 1-4  = לא מתאים (אל תכלול בתוצאות)

════════════════════════════════════════
שלב 6 – שמירת CSV
════════════════════════════════════════
שמור קובץ CSV בנתיב: {output_file}

**כותרות חובה:**
Title,Company,Location,Site,URL,Match_Score,Key_Requirements,Notes

כללים:
- עטוף שדות עם פסיקות או מרכאות בתוך גרשיים כפולים
- הוסף שורה לכל משרה שציונה ≥ 5
- Notes: כתוב בעברית מה חזק ומה חסר לניר ספציפית
- אם חסר מידע, כתוב "N/A"

דוגמה:
"Head of Digital","Bank Hapoalim","Tel Aviv","LinkedIn","https://...","9","AI; ניהול 20+ עובדים; תקציב; C-Level","התאמה מצוינת - AI ו-Digital Transformation מדויק לפרופיל"

════════════════════════════════════════
שלב 7 – סיכום
════════════════════════════════════════
לאחר שמירת הקובץ הצג:
1. סך המשרות לפי אתר (כמה נמצאו, כמה עברו סינון)
2. TOP 5 המשרות המומלצות עם הסבר קצר לכל אחת
3. אתרים/קטגוריות שלא נחפשו עדיין
4. מיומנויות שנדרשות הרבה אך לא מופיעות מספיק בקורות החיים

התחל עכשיו – שלב 1 ראשון!
"""


# ──────────────────────────────────────────
# הרצה ראשית
# ──────────────────────────────────────────

async def run():
    cv_content = load_cv()

    output_dir = Path(__file__).parent / OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = str(output_dir / f"jobs_{timestamp}.csv")

    active_sites = [s for s, on in SEARCH_CONFIG["sites"].items() if on]

    print("=" * 55)
    print("       🔍  סוכן חיפוש עבודה אוטומטי")
    print("=" * 55)
    print(f"  📍 מיקום   : {SEARCH_CONFIG['location']}")
    print(f"  🌐 אתרים   : {', '.join(active_sites)}")
    print(f"  💾 שומר ב  : {output_file}")

    if cv_content:
        print(f"  ✅ קורות חיים נטענו ({len(cv_content):,} תווים)")
    else:
        print("  ⚠️  my_cv.txt ריק – מלא אותו לניתוח התאמה מדויק")

    print("=" * 55)
    print()

    prompt = build_prompt(cv_content, output_file)

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["WebSearch", "WebFetch", "Write", "Read"],
            permission_mode="acceptEdits",
            max_turns=120,
            cwd=str(Path(__file__).parent),
        ),
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print(f"\n\n{'=' * 55}")
            print("  ✅  החיפוש הושלם!")
            print(f"  📊  תוצאות: {output_file}")
            print("=" * 55)


if __name__ == "__main__":
    anyio.run(run)
