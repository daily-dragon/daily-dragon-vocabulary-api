import logging
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Response, Query
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from daily_dragon.auth.cognito import cognito_auth, DailyDragonCognitoToken
from daily_dragon.exceptions import WordAlreadyExistsError
from daily_dragon.service.hsk_service import HskService
from daily_dragon.service.settings_service import SettingsService
from daily_dragon.service.vocabulary_service import VocabularyService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://d36kc4lmm7sv5n.cloudfront.net",
        "https://daily-dragon.havryliuk.com",
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SettingsResponse(BaseModel):
    hsk_level: int
    placement_completed: bool


class SettingsUpdateRequest(BaseModel):
    hsk_level: Optional[int] = None
    placement_completed: Optional[bool] = None


class WordEntry(BaseModel):
    word: str


class Review(BaseModel):
    """A single word review with quality rating."""
    word: str
    quality: int = Field(..., ge=0, le=10, description="Quality rating from 0 (complete blackout) to 10 (perfect recall)")


class BatchReviewRequest(BaseModel):
    """Request body for batch review submission."""
    reviews: List[Review] = Field(..., min_length=1, description="List of word reviews")


class LevelProgress(BaseModel):
    level: int
    total: int
    mastered: int
    in_progress: int
    new: int


class HskProgressResponse(BaseModel):
    current_level: int
    levels: List[LevelProgress]


@app.get("/daily-dragon/settings", status_code=200)
def get_settings(
        auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required),
        settings_service: SettingsService = Depends()
) -> SettingsResponse:
    return SettingsResponse(**settings_service.get_settings(auth.sub))


@app.patch("/daily-dragon/settings", status_code=200)
def update_settings(
        request: SettingsUpdateRequest,
        auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required),
        settings_service: SettingsService = Depends()
) -> SettingsResponse:
    return SettingsResponse(**settings_service.update_settings(auth.sub, request.model_dump()))


@app.get("/daily-dragon/hsk/progress", response_model=HskProgressResponse)
def get_hsk_progress(
        auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required),
        settings_service: SettingsService = Depends(),
        hsk_service: HskService = Depends(),
) -> HskProgressResponse:
    user_id = auth.sub
    settings = settings_service.get_settings(user_id)
    levels = [hsk_service.get_level_progress(user_id, lvl) for lvl in range(1, 8)]
    return HskProgressResponse(current_level=settings['hsk_level'], levels=[LevelProgress(**l) for l in levels])


@app.post("/daily-dragon/vocabulary", status_code=201)
def add_word(word_entry: WordEntry, vocabulary_service: VocabularyService = Depends(),
             auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required)):
    word = word_entry.word
    try:
        user_id = auth.sub
        vocabulary_service.add_word(user_id, word_entry.word)
        return {"message": f"Word {word} added to vocabulary"}
    except WordAlreadyExistsError:
        raise HTTPException(status_code=409, detail=f"Word {word} already exists")


@app.get("/daily-dragon/vocabulary")
def get_vocabulary(vocabulary_service: VocabularyService = Depends(), count: Optional[int] = Query(None, gt=0),
                   auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required)):
    user_id = auth.sub
    if count is not None:
        vocabulary = vocabulary_service.get_random_vocabulary(user_id, count)
    else:
        vocabulary = vocabulary_service.get_vocabulary(user_id)
    return vocabulary


@app.delete("/daily-dragon/vocabulary/{word}")
def delete_word(word: str, vocabulary_service: VocabularyService = Depends(),
                auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required)):
    user_id = auth.sub
    vocabulary_service.delete_word(user_id, word)
    return {"message": f"Word {word} deleted"}


@app.options("/daily-dragon/vocabulary")
def options_vocabulary():
    return Response(status_code=200)


@app.get("/daily-dragon/vocabulary/due")
def get_due_words(vocabulary_service: VocabularyService = Depends(),
                  auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required)):
    """
    Get words that are due for review based on spaced repetition schedule.
    Returns up to 5 words, sorted by most overdue first.
    """
    user_id = auth.sub
    return vocabulary_service.get_due_words(user_id)


@app.post("/daily-dragon/vocabulary/reviews")
def submit_reviews(request: BatchReviewRequest,
                   vocabulary_service: VocabularyService = Depends(),
                   hsk_service: HskService = Depends(),
                   auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required)):
    """
    Submit quality ratings for multiple words at once.
    Each review updates the word's spaced repetition schedule using the SM-2 algorithm.

    Quality ratings (0-10):
    - 0-1: Complete blackout
    - 2-3: Incorrect, but word felt familiar
    - 4: Incorrect, but seemed easy to recall
    - 5: Correct with serious difficulty
    - 6-7: Correct with some difficulty
    - 8: Correct after hesitation
    - 9: Good recall
    - 10: Perfect recall
    """
    user_id = auth.sub
    logger.info("submit_reviews: processing %d reviews for user %s", len(request.reviews), user_id)
    reviews = [{'word': r.word, 'quality': r.quality} for r in request.reviews]
    result = vocabulary_service.record_reviews(user_id, reviews)
    logger.info("submit_reviews: record_reviews complete, calling check_and_promote")
    hsk_service.check_and_promote(user_id)
    logger.info("submit_reviews: complete")
    return result
