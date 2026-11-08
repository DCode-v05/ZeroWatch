import json
from groq import AsyncGroq
from backend.config import GROQ_API_KEY

client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
MODEL = "llama-3.3-70b-versatile"


async def synthesise_baseline(role: str, department: str, access_permissions: str) -> dict:
    """Ask LLM to generate a behavioral baseline for a new user. Returns JSON dict."""
    if not client:
        return _fallback_baseline()

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a security analytics engine. A new employee just joined.\n"
                    f"Role: {role}\nDepartment: {department}\nAccess: {access_permissions}\n\n"
                    f"Generate a JSON behavioral baseline profile with these exact keys:\n"
                    f'{{"expected_hours_start": <int 0-23>, "expected_hours_end": <int 0-23>, '
                    f'"data_mb_range": [<min>, <max>], "expected_endpoints": [<list of API paths>], '
                    f'"device_type": "<laptop|desktop|mobile>", '
                    f'"api_calls_per_min_range": [<min>, <max>]}}\n\n'
                    f"Return ONLY valid JSON, no explanation."
                ),
            }],
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)
    except Exception as e:
        print(f"LLM baseline error: {e}")
        return _fallback_baseline()


async def narrate_incident(user_id: str, z_scores: dict, baseline: dict, flags: list[str]) -> str:
    """Ask LLM to narrate a security incident. Returns plain-English report <150 words."""
    if not client:
        return _fallback_narrative(user_id, z_scores, flags)

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a security incident narrator for ZeroWatch.\n"
                    f"User ID: {user_id}\n"
                    f"Anomaly z-scores: {json.dumps(z_scores)}\n"
                    f"Baseline profile: {json.dumps(baseline)}\n"
                    f"Triggered flags: {flags}\n\n"
                    f"Write a plain-English incident report under 150 words.\n"
                    f"Include: what happened, why it's suspicious, recommended action.\n"
                    f"Be specific about the anomalies. Write as a security analyst."
                ),
            }],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM narration error: {e}")
        return _fallback_narrative(user_id, z_scores, flags)


async def classify_intent(user_id: str, api_sequence: list[str]) -> str:
    """Ask LLM to classify user intent. Returns one word."""
    if not client:
        return "normal"

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": (
                    f"Classify this API access pattern for user {user_id}.\n"
                    f"API sequence: {api_sequence}\n\n"
                    f"Return ONLY one word: normal, reconnaissance, staging, or exfiltration."
                ),
            }],
        )
        word = response.choices[0].message.content.strip().lower()
        if word in ("normal", "reconnaissance", "staging", "exfiltration"):
            return word
        return "normal"
    except Exception as e:
        print(f"LLM intent error: {e}")
        return "normal"


def _fallback_baseline() -> dict:
    return {
        "expected_hours_start": 9,
        "expected_hours_end": 18,
        "data_mb_range": [1, 10],
        "expected_endpoints": ["/app/dashboard", "/app/reports"],
        "device_type": "laptop",
        "api_calls_per_min_range": [5, 15],
    }


def _fallback_narrative(user_id: str, z_scores: dict, flags: list[str]) -> str:
    flag_str = ", ".join(flags) if flags else "multiple behavioral signals"
    return (
        f"Security Incident Report — User {user_id}\n\n"
        f"ZeroWatch detected anomalous behavior across {flag_str}. "
        f"The session's risk score exceeded the termination threshold. "
        f"Key anomalies: {', '.join(f'{k}={v:.1f}' for k, v in z_scores.items() if v > 1.5)}. "
        f"Recommended action: Review session logs, verify user identity, and consider enforcing MFA re-authentication."
    )
