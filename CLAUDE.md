# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

FastAPI vocabulary API deployed as AWS Lambda, storing per-user data in S3.

## Commands

```bash
pip install -r requirements.txt
uvicorn daily_dragon.daily_dragon_app:app --reload   # http://localhost:8000/docs
pytest --cov=.                                        # 80% coverage required, fails fast
pytest tests/test_daily_dragon_app.py::test_name     # single test
```

## Architecture

```
daily_dragon_app.py → service/vocabulary_service.py → repository/vocabulary_repository.py → S3
                    → service/settings_service.py    → repository/settings_repository.py   → S3
                    → service/hsk_service.py         → repository/hsk_repository.py        → S3 (hsk/)
                                                     → repository/vocabulary_repository.py → S3
                                                     → repository/settings_repository.py   → S3
```

All services and repositories are wired via FastAPI `Depends()` — no explicit DI setup needed.

- **Auth**: Cognito via `cognito_auth.auth_required`; `auth.sub` is the user ID
- **Storage**: Two JSON files per user in S3: `{user_id}_vocabulary.json` and `{user_id}_settings.json`
- **HSK static data**: Shared read-only files at `s3://daily-dragon-bucket/hsk/hsk1.json` … `hsk7.json`
- **Spaced repetition**: SM-2 algorithm in `service/spaced_repetition.py`; `SpacedRepetitionService` is stateless (all `@staticmethod`). `MASTERY_INTERVAL = 21` days defines a mature card.

Repositories read the full S3 file on every operation and write it back on mutations. No caching or concurrency control — concurrent requests for the same user can cause lost updates.

## Vocabulary data structure

```json
{
  "word": {
    "created_on": 1234567890,
    "interval": 0,
    "repetition": 0,
    "ease_factor": 2.5,
    "next_review_date": null,
    "last_review_date": null
  }
}
```

Old files with `adoption` field are lazily migrated on read (`ensure_spaced_repetition_fields()`).

## Testing

Three test layers, each with a different mocking strategy:

1. **Endpoint tests** (`tests/test_daily_dragon_app.py`, `tests/test_settings_endpoints.py`): `TestClient` with `app.dependency_overrides` replacing `VocabularyService`, `SettingsService`, and `cognito_auth.auth_required`. See `tests/conftest.py` for shared fixtures.
2. **Service unit tests** (`tests/service/`): Service classes instantiated directly with a `MagicMock` repository.
3. **Repository unit tests** (`tests/repository/`): `monkeypatch` for `S3_BUCKET` env var; `unittest.mock.patch("boto3.client", ...)` to inject a mock S3 client.

## HSK Vocabulary

Static Chinese vocabulary lists parsed from official HSK PDFs.

```
hsk/pdf/          — source PDFs (hsk-1 through hsk-7-vocabulary.pdf)
hsk/code/         — parse_hsk_pdfs.py: extracts words and regenerates JSONs
hsk/json/         — hsk1.json … hsk7.json (committed, deployed to S3)
```

Each JSON contains only the words **unique to that level** (deduplicated across levels). To regenerate JSONs after updating PDFs:
```bash
pip install pdfplumber
python hsk/code/parse_hsk_pdfs.py
```

JSON files are deployed to `s3://daily-dragon-bucket/hsk/` via CDK on every push to `main`.

## CDK

`cdk/app.py` deploys `hsk/json/` to `s3://daily-dragon-bucket/hsk/` using `BucketDeployment`. Skips re-upload if files are unchanged (CloudFormation asset hash check). Only HSK static data is CDK-managed — Lambda, API Gateway, and Cognito were created manually.

One-time setup — run locally with admin credentials before first CI deploy:
```bash
./scripts/setup_cdk_permissions.sh <ci-iam-username>
```

## Deployment

GitHub Actions deploys to Lambda on push to `main`. The app is packaged as a **Lambda Layer** (deps + `daily_dragon/` zipped into `daily_dragon_layer.zip`, uploaded to `s3://daily-dragon-layer/`). The Lambda function `daily-dragon` is updated to reference the new layer ARN. Entry point is `daily_dragon_handler.daily_dragon_handler` (Mangum wrapper). Manual deployment not needed.

## Environment

`.env` file: `S3_BUCKET=daily-dragon-bucket`

Cognito pool ID, app client ID, and CORS origins are hardcoded in `auth/cognito.py` and `daily_dragon_app.py` respectively.

## HTTP examples

`requests/` — `vocabulary_local.http`, `vocabulary_aws.http`, `settings_local.http`, `settings_aws.http`, `spaced_repetition_test_local.http`, `spaced_repetition_test_aws.http`
