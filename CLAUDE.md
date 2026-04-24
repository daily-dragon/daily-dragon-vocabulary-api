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
- **Spaced Repetition**: SM-2 algorithm for optimized review scheduling. Batch reviews for efficiency (single S3 save per batch).

### Vocabulary Data Structure

Each word in the vocabulary has the following structure with spaced repetition fields:
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

**Fields:**
- `created_on`: Unix timestamp when word was added
- `interval`: Days until next review (starts at 0)
- `repetition`: Consecutive successful reviews (starts at 0)
- `ease_factor`: SM-2 ease factor (starts at 2.5, minimum 1.3)
- `next_review_date`: Unix timestamp of next review (null = immediately due)
- `last_review_date`: Unix timestamp of last review (null = never reviewed)

**Note:** The `adoption` field from older versions has been removed. Existing vocabulary files are automatically migrated when accessed (lazy migration).

## Spaced Repetition System

The API implements the SuperMemo-2 (SM-2) spaced repetition algorithm for optimized vocabulary learning.

### SM-2 Algorithm

**Quality Ratings (0-10):**
- 0-1: Complete blackout, didn't remember at all
- 2-3: Incorrect, but word felt familiar
- 4: Incorrect, but seemed easy to recall
- 5: Correct with serious difficulty
- 6-7: Correct with some difficulty
- 8: Correct after hesitation
- 9: Good recall
- 10: Perfect recall

**Interval Progression:**
- Failed review (quality < 5): Reset to immediate review (interval = 0, repetition = 0)
- First successful review: 1 day
- Second successful review: 6 days
- Subsequent reviews: previous_interval × ease_factor

**Ease Factor:**
- Starts at 2.5 for new words
- Adjusted based on quality rating: `EF' = EF + (0.1 - (10 - q) * (0.04 + (10 - q) * 0.005))`
- Minimum value: 1.3

### Spaced Repetition Endpoints

**GET /daily-dragon/vocabulary/due**
- Returns up to 5 words that are due for review
- Sorted by most overdue first
- New words (never reviewed) are immediately due

**POST /daily-dragon/vocabulary/reviews**
- Submit batch reviews for multiple words
- Request body: `{"reviews": [{"word": "你好", "quality": 10}, ...]}`
- Returns individual results for each word (success/failure)
- Single S3 save for entire batch (efficient)

### Implementation Details

**Service Layer:**
- `SpacedRepetitionService` (`service/spaced_repetition.py`): Stateless utility implementing SM-2 algorithm
- `VocabularyService` (`service/vocabulary_service.py`): Orchestrates review operations

**Repository Layer:**
- `ensure_spaced_repetition_fields()`: Lazy migration from old data format
- `get_due_words()`: Filters and sorts due words

**Lazy Migration:**
- Old vocabulary files (with `adoption` field) are automatically migrated when accessed
- No batch migration required - happens transparently on read operations
- Migration removes `adoption` field and adds SM-2 fields with default values

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