from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.deps import get_current_user
from app.models import Flashcard, Quiz, QuizAttempt, StudySession, User
from app.schemas import FlashcardReviewIn, QuizGenerateIn, QuizSubmitIn
from app.services.quiz import generate_quiz, review_flashcard, submit_quiz


router = APIRouter(prefix='/quiz', tags=['quiz'])


@router.post('/sessions/{session_id}/generate')
async def create_quiz(session_id: int, payload: QuizGenerateIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    session_result = await db.execute(select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user.id))
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail='Session not found')
    quiz = await generate_quiz(db, session_id, user.id, payload.mode)
    return {'id': quiz.id, 'mode': quiz.mode, 'questions': quiz.questions}


@router.post('/{quiz_id}/submit')
async def submit(quiz_id: int, payload: QuizSubmitIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id, Quiz.user_id == user.id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')
    attempt, review = await submit_quiz(db, quiz, user.id, payload.answers)
    return {'attempt_id': attempt.id, 'score': attempt.score, 'total': attempt.total, 'review': review}


@router.get('/sessions/{session_id}/scores')
async def score_history(session_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(QuizAttempt).join(Quiz, Quiz.id == QuizAttempt.quiz_id).where(
            Quiz.session_id == session_id,
            QuizAttempt.user_id == user.id,
        ).order_by(QuizAttempt.id.desc())
    )
    attempts = result.scalars().all()
    return [{'id': a.id, 'score': a.score, 'total': a.total, 'created_at': a.created_at} for a in attempts]


@router.get('/flashcards/due')
async def flashcards_due(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Flashcard).where(Flashcard.user_id == user.id).order_by(Flashcard.next_review_at.asc()))
    cards = result.scalars().all()
    return [
        {
            'id': c.id,
            'session_id': c.session_id,
            'front': c.front,
            'back': c.back,
            'next_review_at': c.next_review_at,
            'interval_days': c.interval_days,
            'ease_factor': c.ease_factor,
        }
        for c in cards
    ]


@router.post('/flashcards/{flashcard_id}/review')
async def review(flashcard_id: int, payload: FlashcardReviewIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Flashcard).where(Flashcard.id == flashcard_id, Flashcard.user_id == user.id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail='Flashcard not found')
    updated = await review_flashcard(db, card, payload.quality)
    return {'id': updated.id, 'next_review_at': updated.next_review_at, 'interval_days': updated.interval_days, 'ease_factor': updated.ease_factor}
