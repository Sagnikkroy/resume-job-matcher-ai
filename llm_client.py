"""Thin wrapper around the Google Gemini API (google-genai SDK).

Handles: API key loading, retries with exponential backoff, JSON-mode output
and robust JSON parsing.
"""
import json
import logging
import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from config_loader import load_config

load_dotenv()
logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM call fails or returns unusable output."""


class GeminiClient:
    def __init__(self, api_key: str | None = None):
        cfg = load_config()["llm"]
        self.model = cfg["model"]
        self.temperature = cfg["temperature"]
        self.max_tokens = cfg["max_output_tokens"]
        self.max_retries = cfg["max_retries"]
        self.backoff = cfg["retry_backoff_seconds"]

        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY not found. Add it to your .env file.")
        self.client = genai.Client(api_key=key)

    def generate(self, system: str, user: str, json_mode: bool = False) -> str:
        """Call Gemini with retries. Returns raw text."""
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=user, config=config
                )
                text = (response.text or "").strip()
                if not text:
                    raise LLMError("Empty response from model.")
                return text
            except Exception as e:  # network, quota, 5xx, empty output
                last_err = e
                logger.warning("Gemini call failed (attempt %d/%d): %s", attempt, self.max_retries, e)
                if attempt < self.max_retries:
                    time.sleep(self.backoff ** attempt)
        raise LLMError(f"Gemini API failed after {self.max_retries} attempts: {last_err}")

    def generate_json(self, system: str, user: str) -> dict:
        """Call Gemini in JSON mode and parse the result into a dict."""
        raw = self.generate(system, user, json_mode=True)
        return parse_json(raw)


def parse_json(raw: str) -> dict:
    """Parse JSON even if the model wrapped it in markdown fences or added text."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise LLMError("Model did not return valid JSON.")
