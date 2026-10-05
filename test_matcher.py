"""Unit tests. The Gemini API is mocked, so no API key or internet is needed.

Run with:  pytest -q
"""
import pytest

from config_loader import load_config, load_prompts, render
from file_utils import clean_text, extract_text
from llm_client import LLMError, parse_json
from matcher import ResumeMatcher, validate_result, verdict_for

RESUME = "Python developer with 2 years of experience in machine learning and SQL. " * 3
JOB = "Looking for an NLP engineer skilled in Python, PyTorch and Docker. " * 3

GOOD_RESPONSE = {
    "match_score": 72,
    "verdict": "Good Match",
    "score_breakdown": {"skills": 70, "experience": 75, "education": 80, "keywords": 60},
    "candidate_name": "Test User",
    "job_title": "NLP Engineer",
    "matched_skills": ["Python"],
    "missing_skills": ["PyTorch", "Docker"],
    "strengths": ["Strong Python"],
    "gaps": ["No PyTorch"],
    "ats_keywords_to_add": ["PyTorch"],
    "improvement_tips": ["Add a PyTorch project"],
    "summary": "Decent fit.",
}


class FakeClient:
    def __init__(self, response=None):
        self.response = response if response is not None else GOOD_RESPONSE
        self.calls = 0

    def generate_json(self, system, user):
        self.calls += 1
        return self.response

    def generate(self, system, user, json_mode=False):
        self.calls += 1
        return "Dear [Hiring Manager], ..."


def test_config_and_prompts_load():
    assert load_config()["llm"]["model"].startswith("gemini")
    prompts = load_prompts()
    for key in ("match_system", "match_user", "cover_letter_user", "interview_user"):
        assert key in prompts


def test_render_keeps_json_braces():
    out = render(load_prompts()["match_user"], resume="R", job_description="J")
    assert "<resume>\nR\n</resume>" in out
    assert '"match_score"' in out  # JSON schema braces untouched


def test_parse_json_handles_fences_and_noise():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here you go: {"a": 2} thanks') == {"a": 2}
    with pytest.raises(LLMError):
        parse_json("not json at all")


def test_verdict_thresholds():
    assert verdict_for(90) == "Strong Match"
    assert verdict_for(70) == "Good Match"
    assert verdict_for(50) == "Partial Match"
    assert verdict_for(10) == "Weak Match"


def test_validate_result_clamps_and_defaults():
    r = validate_result({"match_score": 150, "score_breakdown": {"skills": -5}})
    assert r["match_score"] == 100
    assert r["score_breakdown"]["skills"] == 0
    assert r["matched_skills"] == []
    assert r["candidate_name"] == "Unknown"


def test_validate_result_rejects_bad_payload():
    with pytest.raises(LLMError):
        validate_result({"foo": "bar"})


def test_analyze_and_cache():
    fake = FakeClient()
    m = ResumeMatcher(client=fake)
    r1 = m.analyze(RESUME, JOB)
    r2 = m.analyze(RESUME, JOB)
    assert r1["match_score"] == 72
    assert r1 is r2
    assert fake.calls == 1  # second call served from cache


def test_analyze_rejects_short_input():
    m = ResumeMatcher(client=FakeClient())
    with pytest.raises(ValueError):
        m.analyze("too short", JOB)


def test_cover_letter_and_questions():
    fake = FakeClient({"questions": [{"question": "Why NLP?", "why_asked": "x", "tip": "y"}]})
    m = ResumeMatcher(client=fake)
    analysis = validate_result(GOOD_RESPONSE)
    assert "Hiring Manager" in m.cover_letter(RESUME, JOB, analysis)
    assert len(m.interview_questions(RESUME, JOB)) == 1


def test_extract_text_txt_and_validation():
    assert extract_text("a.txt", b"hello   world\n\n\n\nbye") == "hello world\n\nbye"
    with pytest.raises(ValueError):
        extract_text("a.exe", b"x")
    with pytest.raises(ValueError):
        extract_text("a.txt", b"   ")


def test_clean_text():
    assert clean_text("a \t b\n\n\n\nc") == "a b\n\nc"
