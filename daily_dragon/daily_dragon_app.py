import logging
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Response, Query
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.cors import CORSMiddleware

from daily_dragon.auth.cognito import cognito_auth, DailyDragonCognitoToken
from daily_dragon.exceptions import WordAlreadyExistsError
from daily_dragon.service.vocabulary_service import VocabularyService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

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


class WordEntry(BaseModel):
    word: str


class Review(BaseModel):
    """A single word review with quality rating."""
    word: str
    quality: int = Field(..., ge=0, le=5, description="Quality rating from 0 (complete blackout) to 5 (perfect recall)")

    @field_validator('quality')
    @classmethod
    def validate_quality(cls, v):
        if not isinstance(v, int) or v < 0 or v > 5:
            raise ValueError('Quality must be an integer between 0 and 5')
        return v


class BatchReviewRequest(BaseModel):
    """Request body for batch review submission."""
    reviews: List[Review] = Field(..., min_length=1, description="List of word reviews")

    @field_validator('reviews')
    @classmethod
    def validate_reviews_not_empty(cls, v):
        if len(v) == 0:
            raise ValueError('Reviews list must contain at least one review')
        return v


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
                   auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required)):
    """
    Submit quality ratings for multiple words at once.
    Each review updates the word's spaced repetition schedule using the SM-2 algorithm.

    Quality ratings (0-5):
    - 0: Complete blackout
    - 1: Incorrect, but word felt familiar
    - 2: Incorrect, but seemed easy to recall
    - 3: Correct with serious difficulty
    - 4: Correct after hesitation
    - 5: Perfect recall
    """
    user_id = auth.sub
    reviews = [{'word': r.word, 'quality': r.quality} for r in request.reviews]
    return vocabulary_service.record_reviews(user_id, reviews)
