# ==========================================
# הגדרות חיפוש עבודה - ניר ניסים
# ==========================================

SEARCH_CONFIG = {
    # תפקידים לחיפוש - מותאמים לפרופיל ניר
    # דוגמת משרה רלוונטית: "מוביל/ת AI" בבזק – הובלת אסטרטגיית AI, פרויקטים מקצה לקצה, עבודה מול הנהלה
    "job_titles": [
        "Head of AI",
        "AI Lead",
        "Head of Digital",
        "Digital Transformation Manager",
        "AI Innovation Manager",
        "Generative AI Manager",
        "Head of Conversational AI",
        "Digital Products Manager",
        "VP Digital",
        "מוביל AI",
        "ראש תחום AI",
        "מנהל AI",
        "מנהל חדשנות",
        "מנהל דיגיטל",
        "ראש תחום דיגיטל",
        "מנהל טרנספורמציה דיגיטלית",
    ],

    # מיקום
    "location": "Israel",

    # ניסיון
    "experience_years": "7+",

    # סוג משרה
    "job_type": "full-time",

    # אתרים לחיפוש
    "sites": {
        "LinkedIn":    True,
        "Drushim":     True,
        "AllJobs":     True,
        "JobsIL":      True,
        "GotFriends":  True,
        "Facebook":    False,   # בדרך כלל חסום
    },

    # מקסימום משרות לאתר
    "max_jobs_per_site": 15,

    # מילות מפתח נוספות
    "extra_keywords": ["GenAI", "AI", "Digital Transformation", "חדשנות"],

    # URL חיפוש ישיר לכל אתר (WebFetch)
    "search_url_templates": {
        "Drushim":    "https://www.drushim.co.il/jobs/?q={query}",
        "AllJobs":    "https://www.alljobs.co.il/SearchResults.aspx?type=1&q={query}",
        "JobsIL":     "https://www.jobs.il/jobs/?q={query}",
        "GotFriends": "https://www.gotfriends.co.il/jobs/?query={query}",
    },

    # שאילתות חיפוש קצרות ויעילות לכל אתר
    # מבוססות על ניתוח משרת בזק (מוביל AI) + פרופיל ניר
    "short_queries": {
        "hebrew": [
            "מוביל AI",
            "מנהל AI",
            "ראש תחום AI",
            "מנהל חדשנות",
            "מנהל דיגיטל",
            "מנהל טרנספורמציה דיגיטלית",
            "ראש תחום דיגיטל",
        ],
        "english": [
            "Head of AI",
            "AI Lead",
            "Generative AI Manager",
            "Head of Digital",
            "Digital Transformation Manager",
            "AI Innovation Manager",
            "Conversational AI",
        ],
    },

    # מאפייני המשרה האידיאלית (בהתאם לדוגמת בזק)
    "ideal_job_profile": {
        "must_have": [
            "ניהול פרויקטי AI/GenAI",
            "עבודה מול הנהלה + צוותי פיתוח",
            "ארגון גדול (Enterprise)",
        ],
        "nice_to_have": [
            "HealthTech / Telecom / Finance / Insurance",
            "Conversational AI / Voice AI / WhatsApp Bots",
            "LLMs / GPT / Generative AI",
        ],
        "exclude": [
            "תוכן דיגיטל / מדיה / שיווק בלבד",
            "Supply Chain",
            "תפקיד ביצועי טכני בלבד (ללא ניהול)",
        ],
    },
}

# נתיב לקובץ קורות חיים
CV_FILE = "my_cv.txt"

# תיקיית תוצאות
OUTPUT_DIR = "results"
