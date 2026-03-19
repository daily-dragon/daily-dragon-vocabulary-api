# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Daily Dragon Vocabulary API is a FastAPI-based REST API for managing user vocabulary. It is deployed as an AWS Lambda function and stores per-user vocabulary data in S3.

## Development Commands

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run the app locally
```bash
uvicorn daily_dragon.daily_dragon_app:app --reload
```
Access the API at `http://localhost:8000` and docs at `http://localhost:8000/docs`.

### Run tests
```bash
pytest --cov=.
```
Tests fail fast (stop after first failure) and require minimum 80% code coverage.

### Run a single test
```bash
pytest tests/test_daily_dragon_app.py::test_add_word_success
```

## Architecture

The codebase follows a layered architecture:

**FastAPI Application** (`daily_dragon_app.py`)
→ **Service Layer** (`service/vocabulary_service.py`)
→ **Repository Layer** (`repository/vocabulary_repository.py`)
→ **AWS S3** (storage)

### Key Design Patterns

- **FastAPI Dependency Injection**: Services and repositories are injected via `Depends()`. This enables easy mocking in tests.
- **Repository Pattern**: `VocabularyRepository` encapsulates all S3 interactions. Each user's vocabulary is stored as `{user_id}_vocabulary.json` in the configured S3 bucket.
- **Cognito Authentication**: All endpoints require authentication via AWS Cognito. The `auth.sub` field contains the user ID.
- **Per-User Data Isolation**: Each user has their own vocabulary file in S3, keyed by their Cognito sub (user ID).

### Vocabulary Data Structure

Each word in the vocabulary has the following structure:
```json
{
  "word": {
    "adoption": 0,
    "created_on": 1234567890
  }
}
```

## Testing Patterns

Tests use FastAPI's `dependency_overrides` to mock dependencies:

1. **Mock VocabularyService**: Replace the service with a `MagicMock` for app-level tests
2. **Mock Cognito Auth**: Override `cognito_auth.auth_required` with a dummy token for testing without real authentication
3. **TestClient**: Use FastAPI's `TestClient` for integration tests

See `tests/conftest.py` for the fixture setup pattern.

## AWS Lambda Deployment

The app is deployed to AWS Lambda via the `daily_dragon_handler.py` entry point using Mangum (FastAPI → Lambda adapter).

GitHub Actions automatically deploys on push to `main`:
1. Creates a Lambda Layer with dependencies and application code
2. Updates the `daily-dragon` Lambda function configuration to use the new layer

Manual deployment is not typically needed.

## Environment Variables

Required for local development (`.env` file):
- `S3_BUCKET`: S3 bucket name for storing vocabulary files

## HTTP Request Examples

The `requests/` directory contains `.http` files with example API requests:
- `vocabulary_local.http` - for local development
- `vocabulary_aws.http` - for AWS environment