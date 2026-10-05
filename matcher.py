"""Core NLP logic: resume vs job description analysis using Gemini."""
import hashlib
import json
from pathlib import Path

from config_loader import BASE_DIR, load_config, load_prompts, render
from file_utils import truncate
from llm_client import GeminiClient, LLMError

VERDICTS = ["Strong Match", "Good Match", "Partial Match", "Weak Match"]


def verdict_for(score: int) -> str:
    if score >= 80:
        return VERDICTS[0]
    if score >= 65:
        return VERDICTS[1]
    if score >= 45:
        return VERDICTS[2]
    return VERDICTS[3]


def _clamp(value, default=0) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _as_list(value) -> list:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def validate_result(data: dict) -> dict:
    """Normalise and sanity-check the model's JSON so the UI never breaks."""
    if not isinstance(data, dict) or "match_score" not in data:
        raise LLMError("Model response is missing 'match_score'.")

    score = _clamp(data.get("match_score"))
    breakdown = data.get("score_breakdown") or {}
    return {
        "match_score": score,
        "verdict": data.get("verdict") if data.get("verdict") in VERDICTS else verdict_for(score),
        "score_breakdown": {
            k: _clamp(breakdown.get(k)) for k in ("skills", "experience", "education", "keywords")
        },
        "candidate_name": str(data.get("candidate_name") or "Unknown"),
        "job_title": str(data.get("job_title") or "Unknown"),
        "matched_skills": _as_list(data.get("matched_skills")),
        "missing_skills": _as_list(data.get("missing_skills")),
        "extra_skills": _as_list(data.get("extra_skills")),
        "strengths": _as_list(data.get("strengths")),
        "gaps": _as_list(data.get("gaps")),
        "ats_keywords_to_add": _as_list(data.get("ats_keywords_to_add")),
        "improvement_tips": _as_list(data.get("improvement_tips")),
        "summary": str(data.get("summary") or ""),
    }


class ResumeMatcher:
    def __init__(self, client: GeminiClient | None = None):
        self.client = client or GeminiClient()
        self.prompts = load_prompts()
        self._cache: dict[str, dict] = {}

    @staticmethod
    def _key(*parts: str) -> str:
        return hashlib.sha256("||".join(parts).encode()).hexdigest()

    def analyze(self, resume: str, job_description: str) -> dict:
        """Return a validated match analysis. Identical inputs are served from cache."""
        resume, job_description = truncate(resume), truncate(job_description)
        if len(resume) < 50 or len(job_description) < 50:
            raise ValueError("Resume and job description must each have at least 50 characters.")

        key = self._key("match", resume, job_description)
        if key in self._cache:
            return self._cache[key]

        user = render(self.prompts["match_user"], resume=resume, job_description=job_description)
        raw = self.client.generate_json(self.prompts["match_system"], user)
        result = validate_result(raw)
        self._cache[key] = result
        return result

    def cover_letter(self, resume: str, job_description: str, analysis: dict) -> str:
        user = render(
            self.prompts["cover_letter_user"],
            resume=truncate(resume),
            job_description=truncate(job_description),
            matched_skills=", ".join(analysis["matched_skills"][:8]) or "none identified",
            missing_skills=", ".join(analysis["missing_skills"][:4]) or "none",
        )
        return self.client.generate(self.prompts["cover_letter_system"], user)

    def interview_questions(self, resume: str, job_description: str) -> list[dict]:
        user = render(
            self.prompts["interview_user"],
            resume=truncate(resume),
            job_description=truncate(job_description),
        )
        data = self.client.generate_json(self.prompts["interview_system"], user)
        questions = data.get("questions", []) if isinstance(data, dict) else []
        return [q for q in questions if isinstance(q, dict) and q.get("question")]


# ---- simple persistent history (optional) ----
def _history_path() -> Path:
    return BASE_DIR / load_config()["paths"]["history_file"]


def load_history() -> list[dict]:
    path = _history_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def save_history(entry: dict, limit: int = 20) -> None:
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    history = load_history()
    history.insert(0, entry)
    path.write_text(json.dumps(history[:limit], indent=2), encoding="utf-8")
