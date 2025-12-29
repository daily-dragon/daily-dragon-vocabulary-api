import logging
from typing import Optional
from urllib.request import Request

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Response, Query
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

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

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://d36kc4lmm7sv5n.cloudfront.net"
]


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        headers = {}
        if origin in ALLOWED_ORIGINS:
            headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS,DELETE",
                "Access-Control-Allow-Headers": "Authorization,Content-Type",
            }

        if request.method == "OPTIONS":
            return Response(status_code=200, headers=headers)

        response = await call_next(request)
        response.headers.update(headers)
        return response

app.add_middleware(DynamicCORSMiddleware)


class WordEntry(BaseModel):
    word: str


@app.post("/daily-dragon/vocabulary", status_code=201)
def add_word(word_entry: WordEntry, vocabulary_service: VocabularyService = Depends(),
             auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required)):
    word = word_entry.word
    try:
        vocabulary_service.add_word(word_entry.word)
        return {"message": f"Word {word} added to vocabulary"}
    except WordAlreadyExistsError:
        raise HTTPException(status_code=409, detail=f"Word {word} already exists")


@app.get("/daily-dragon/vocabulary")
def get_vocabulary(vocabulary_service: VocabularyService = Depends(), count: Optional[int] = Query(None, gt=0),
                   auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required)):
    if count is not None:
        vocabulary = vocabulary_service.get_random_vocabulary(count)
    else:
        vocabulary = vocabulary_service.get_vocabulary()
    return vocabulary


@app.delete("/daily-dragon/vocabulary/{word}")
def delete_word(word: str, vocabulary_service: VocabularyService = Depends(),
                auth: DailyDragonCognitoToken = Depends(cognito_auth.auth_required)):
    vocabulary_service.delete_word(word)
    return {"message": f"Word {word} deleted"}


@app.options("/daily-dragon/vocabulary")
def options_vocabulary():
    return Response(status_code=200)
