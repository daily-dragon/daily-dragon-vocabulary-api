# CLAUDE.md

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
```

- **Auth**: Cognito via `cognito_auth.auth_required`; `auth.sub` is the user ID
- **Storage**: One JSON file per user in S3: `{user_id}_vocabulary.json`
- **Spaced repetition**: SM-2 algorithm in `service/spaced_repetition.py`; `SpacedRepetitionService` is stateless

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

Uses `dependency_overrides` to mock `VocabularyService` and `cognito_auth.auth_required`. See `tests/conftest.py`.

## HSK Vocabulary

Static Chinese vocabulary lists parsed from official HSK PDFs.

```
hsk/pdf/          — source PDFs (hsk-1 through hsk-7-vocabulary.pdf)
hsk/code/         — parse_hsk_pdfs.py: extracts words and regenerates JSONs
hsk/json/         — hsk1.json … hsk7.json (committed, deployed to S3)
```

Each JSON is a **cumulative** word list — `hsk3.json` contains all words from HSK 1–3. Word counts: 300 / 497 / 990 / 1980 / 3559 / 5336 / 10898.

To regenerate JSONs after updating PDFs:
```bash
pip install pdfplumber
python hsk/code/parse_hsk_pdfs.py
```

JSON files are deployed to `s3://daily-dragon-bucket/hsk/` via CDK on every push to `main`.

## CDK

`cdk/app.py` deploys `hsk/json/` to `s3://daily-dragon-bucket/hsk/` using `BucketDeployment`. Skips re-upload if files are unchanged (CloudFormation asset hash check).

One-time setup — run locally with admin credentials before first CI deploy:
```bash
./scripts/setup_cdk_permissions.sh <ci-iam-username>
```

## Deployment

GitHub Actions deploys to Lambda on push to `main` (via Mangum adapter in `daily_dragon_handler.py`). Also runs `cdk bootstrap` + `cdk deploy` for HSK files. Manual deployment not needed.

## Environment

`.env` file: `S3_BUCKET=daily-dragon-bucket`

## HTTP examples

`requests/` — `vocabulary_local.http`, `vocabulary_aws.http`, `spaced_repetition_test_local.http`, `spaced_repetition_test_aws.http`