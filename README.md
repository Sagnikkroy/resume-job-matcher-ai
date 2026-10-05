# 📄 AI Resume – Job Matcher (NLP + Google Gemini)

A Streamlit web app that uses the **Google Gemini API** to compare a resume against a job description and returns:

- Overall **match score** (0–100) with a breakdown: skills, experience, education, keywords
- **Matched / missing / extra skills** extracted from both documents
- **Strengths, gaps** and concrete **resume improvement tips**
- **ATS keywords** to add to the resume
- A tailored **cover letter** (one click)
- **Interview questions** with tips on how to answer (one click)

## How the LLM is used

| Feature | Technique |
|---|---|
| Match analysis | Zero-shot structured information extraction + scoring, Gemini **JSON mode** (`response_mime_type="application/json"`) |
| Cover letter | Controlled text generation grounded only in resume facts |
| Interview prep | Targeted question generation from detected skill gaps |

Engineering details that make it robust and efficient:

- **Prompt file** (`prompts.yaml`): all prompts are separated from code, with role, rules, schema, scoring rubric and prompt-injection guard (resume and job text are wrapped in tags and treated as data).
- **Config file** (`config.yaml`): model, temperature, token limits, retries, input limits.
- **Retries with exponential backoff** on API errors; clear error messages in the UI.
- **Output validation** (`matcher.validate_result`): clamps scores, fixes missing fields, so malformed model output never crashes the UI.
- **Caching**: identical resume + job pairs are not sent to the API twice.
- **Input truncation** to control token cost; PDF / DOCX / TXT parsing.
- **Unit tests** with the API mocked (no key required).

## Project structure

```
app.py              Streamlit UI
matcher.py          Core NLP logic, validation, caching, history
llm_client.py       Gemini API wrapper (retries, JSON mode, safe parsing)
file_utils.py       PDF / DOCX / TXT text extraction
config_loader.py    Loads config.yaml and prompts.yaml
prompts.yaml        Prompt file
config.yaml         Configuration file
test_matcher.py     Unit tests
sample_resume.txt   Sample input
sample_job.txt      Sample input
requirements.txt    Dependencies
.env.example        Template for API key
```

## Setup and run

1. **Python 3.10+** required.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Get a free Gemini API key at https://aistudio.google.com/apikey
4. Create your env file:
   ```bash
   cp .env.example .env
   ```
   Then open `.env` and set `GEMINI_API_KEY=your_key`.
5. Start the app:
   ```bash
   streamlit run app.py
   ```
6. Upload your resume and a job description (or paste text). You can try `sample_resume.txt` and `sample_job.txt`.

## Run tests

```bash
pytest -q
```

## Configuration

Edit `config.yaml` to change the model (e.g. `gemini-2.5-pro`), temperature, retries or input limits. Edit `prompts.yaml` to tune the prompts without touching code.

## Limitations

- Scanned (image-only) PDFs are not supported; use a text-based PDF.
- Scores are AI estimates meant to guide improvement, not a hiring decision.

## Author

Solo project – NLP course submission.
