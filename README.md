# Triage Assist

Triage Assist is a **preliminary health-screening and specialist-recommendation application** that provides triage-and-navigation guidance (how soon, and where), **not a diagnosis**.

## Design

The system is designed as a safety-first screening workflow. It processes structured symptoms, optional free text, and optional modifiers, then returns urgency, point-of-care guidance, and discussion prompts with explicit disclaimer text. It does not produce diagnostic verdicts.

High-level runtime design:

1. **Deterministic safety layer (runs first):** scans structured and free-text input for red flags/danger phrases and routes emergencies immediately, independent of model output.
2. **NLP symptom-matching cascade:** normalizes text, applies synonym and fuzzy matching, handles local negation, and surfaces unsure/unmatched items for confirmation.
3. **Classical ML classifier (runtime has no LLM):** uses a bundled scikit-learn model (`predict_proba`) as an internal routing signal.
4. **Confidence/uncertainty gate:** sends low-confidence or unrecognized input to an explicit uncertainty path rather than forcing confident output.
5. **Deterministic urgency layer:** computes low/moderate/high urgency from severity tier, duration band, self-severity, and symptom-combination rules.
6. **Result assembly:** maps routed categories to safe phrasing and specialist point of care, then persists screening history in SQLite.

## Setup (Local)

### Prerequisites

- Python **3.12**
- `pip`

### Install

```bash
python3.12 -m venv .python_env
source .python_env/bin/activate
python3.12 -m pip install --upgrade pip
python3.12 -m pip install -r requirements.txt
```

Dependencies are pinned intentionally. The bundled model artifact is serialized with `joblib`/scikit-learn, so runtime loading must use compatible versions (especially `scikit-learn==1.5.2`).

## Running It (Locally)

### Web application

```bash
source .python_env/bin/activate
flask --app app.web.app:create_app run --debug
```

Open: `http://127.0.0.1:5000`

### Rebuild curated data artifacts

```bash
source .python_env/bin/activate
python3.12 app/data/build_data_artifacts.py
```

### Retrain and bundle the model

```bash
source .python_env/bin/activate
python3.12 app/model/train_and_bundle.py
```

### Run tests

```bash
source .python_env/bin/activate
python3.12 -m pytest
```

## Directory Structure

```text
app
|-- __init__.py
|-- data
|-- evidence
|-- model
|-- nlp
|-- pyproject.toml
|-- tests
`-- web
design_reference
|-- decision-log.md
|-- design-bible.md
`-- terminology.md
```

| Path | Purpose |
|---|---|
| `app/web` | Flask routes, safety/inference wiring, templates, static assets, and persistence logic. |
| `app/nlp` | Classical free-text symptom-mapping cascade (normalization, synonyms, fuzzy matching, negation handling). |
| `app/model` | Model training/bundling code and bundled model artifacts. |
| `app/data` | Curated datasets, vocabulary/order artifacts, lookup tables, and data build scripts. |
| `app/tests` | Automated tests for safety, NLP cascade, inference, and integration behavior. |
| `app/evidence` | Captured runtime artifacts and validation evidence for the application. |
| `design_reference` | Frozen design source of truth (design bible, terminology, decision log). |

## Pitfalls / Notes

- This system is a **screening aid**, not a diagnosis engine.
- Keep training and runtime scikit-learn versions aligned; pickle/joblib compatibility is strict.
- Do not alter one-hot symptom order manually; training and inference must share the same frozen column order.
- Safety checks must execute before any model inference.
- Low-confidence and unrecognized inputs must route to uncertainty explicitly (do not force confident labels).
