# HSK Phase 2 Integration Tests

Manual smoke tests for HSK seeding and progression logic. Run against a local server (`uvicorn daily_dragon.daily_dragon_app:app --reload`) with a valid Cognito token.

## Prerequisites

```bash
export TOKEN="<your-cognito-id-token>"
export BASE="http://127.0.0.1:8000"
```

---

## 1. Seed HSK 1 words (via Python shell)

The placement test (Phase 3) normally seeds the first batch. For manual testing, run this directly:

```python
# In a Python REPL with the venv active and S3_BUCKET set
from daily_dragon.repository.hsk_repository import HskRepository
from daily_dragon.repository.vocabulary_repository import VocabularyRepository
from daily_dragon.repository.settings_repository import SettingsRepository
from daily_dragon.service.hsk_service import HskService

hsk_repo = HskRepository()
vocab_repo = VocabularyRepository()
settings_repo = SettingsRepository()
svc = HskService(hsk_repo, vocab_repo, settings_repo)

svc.seed_next_batch("<your-user-id>", level=1, batch_size=20)
```

---

## 2. Verify seeded words appear in due words

```bash
curl -s "$BASE/daily-dragon/vocabulary/due" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

Expected: 5 due words, each with `hsk_level: 1` and `source: "hsk"` in their metadata.

---

## 3. Check initial HSK progress

```bash
curl -s "$BASE/daily-dragon/hsk/progress" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

Expected:
- `current_level: 1`
- `levels[0]` (HSK 1): `total: 20`, `new: 20`, `mastered: 0`, `in_progress: 0`
- All other levels: `total: 0`

---

## 4. Trigger promotion by submitting high-quality reviews

To reach 80% mastery (interval >= 21), you need to submit successful reviews multiple times.
For a fast test, directly set intervals in S3 to 21 for 80%+ of the seeded words, then submit one review to trigger the check:

```bash
# Submit a review batch for the due words
curl -s -X POST "$BASE/daily-dragon/vocabulary/reviews" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reviews": [{"word": "一", "quality": 10}]}' | python -m json.tool
```

---

## 5. Verify promotion occurred

```bash
# Check settings — hsk_level should have incremented
curl -s "$BASE/daily-dragon/settings" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Check progress — HSK 2 should now have new seeded words
curl -s "$BASE/daily-dragon/hsk/progress" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

Expected:
- `settings.hsk_level: 2`
- `levels[1]` (HSK 2): `total: 20`, `new: 20`

---

## 6. Verify no double-promotion (idempotency)

Submit another review batch without changing any intervals.

```bash
curl -s -X POST "$BASE/daily-dragon/vocabulary/reviews" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reviews": [{"word": "一", "quality": 5}]}' | python -m json.tool
```

Expected: `settings.hsk_level` stays at 2 (not promoted to 3).

---

## 7. Verify level 7 cap

Set `hsk_level: 7` in settings (via PATCH), ensure 100% mastery for level 7, then submit a review. `hsk_level` must remain 7.

```bash
curl -s -X PATCH "$BASE/daily-dragon/settings" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hsk_level": 7}' | python -m json.tool
```
