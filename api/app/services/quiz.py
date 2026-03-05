from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Chunk, Flashcard, Quiz, QuizAttempt, StudySession
from app.services.spaced import update_sm2
from app.services.text_cleaning import clean_text, is_quality_chunk


def _build_questions(texts: list[str], mode: str) -> list[dict]:
    questions = []
    for idx, t in enumerate(texts[:5]):
        sentence = clean_text(t.split('.')[0])[:160].strip()
        ok, _ = is_quality_chunk(sentence + ' context words for quality')
        if not ok:
            continue
        if mode == 'mcq':
            questions.append(
                {
                    'id': idx + 1,
                    'type': 'mcq',
                    'question': f'Which statement best matches: {sentence}?',
                    'options': [sentence, 'None of the above', 'Opposite meaning', 'Unrelated fact'],
                    'answer': 0,
                }
            )
        elif mode == 'short':
            questions.append(
                {
                    'id': idx + 1,
                    'type': 'short',
                    'question': f'Summarize the key idea: {sentence}',
                    'answer': sentence.lower(),
                }
            )
        else:
            questions.append(
                {
                    'id': idx + 1,
                    'type': 'flashcard',
                    'front': sentence,
                    'back': f'Explanation: {sentence}',
                }
            )
    return questions


async def generate_quiz(db: AsyncSession, session_id: int, user_id: int, mode: str) -> Quiz:
    session_result = await db.execute(select(StudySession).where(StudySession.id == session_id))
    session = session_result.scalar_one_or_none()

    if session and isinstance(session.education_quiz, list) and mode == 'mcq' and session.education_quiz:
        questions = []
        for idx, q in enumerate(session.education_quiz[:5], start=1):
            if not isinstance(q, dict):
                continue
            question = clean_text(str(q.get('question', '')))
            options = q.get('options', [])
            if len(options) < 2:
                continue
            options = [clean_text(str(opt)) for opt in options[:4]]
            answer_index = q.get('answer_index', 0)
            if not isinstance(answer_index, int) or answer_index < 0 or answer_index >= len(options):
                answer_index = 0
            questions.append(
                {
                    'id': idx,
                    'type': 'mcq',
                    'question': question,
                    'options': options,
                    'answer': answer_index,
                    'explanation': clean_text(str(q.get('explanation', ''))),
                }
            )
    else:
        result = await db.execute(select(Chunk.content).where(Chunk.session_id == session_id).limit(20))
        raw_texts = [clean_text(r[0]) for r in result.all()]
        texts = []
        for text in raw_texts:
            ok, _ = is_quality_chunk(text)
            if ok:
                texts.append(text)
        questions = _build_questions(texts, mode)

    quiz = Quiz(session_id=session_id, user_id=user_id, mode=mode, questions=questions)
    db.add(quiz)

    if mode == 'flashcards':
        for q in questions:
            db.add(
                Flashcard(
                    session_id=session_id,
                    user_id=user_id,
                    front=q['front'],
                    back=q['back'],
                    next_review_at=datetime.utcnow(),
                )
            )

    await db.commit()
    await db.refresh(quiz)
    return quiz


async def submit_quiz(db: AsyncSession, quiz: Quiz, user_id: int, answers: list) -> tuple[QuizAttempt, list[dict]]:
    total = len(quiz.questions)
    correct = 0
    review: list[dict] = []

    for idx, q in enumerate(quiz.questions):
        ans = answers[idx] if idx < len(answers) else None
        is_correct = False
        if q['type'] == 'mcq' and ans == q['answer']:
            correct += 1
            is_correct = True
        elif q['type'] == 'short' and isinstance(ans, str):
            if q['answer'][:30] in ans.lower():
                correct += 1
                is_correct = True
        elif q['type'] == 'flashcard':
            correct += 1
            is_correct = True
        review.append(
            {
                'question_id': q.get('id', idx + 1),
                'question': q.get('question') or q.get('front', ''),
                'selected': ans,
                'correct_answer': q.get('answer'),
                'options': q.get('options', []),
                'is_correct': is_correct,
                'explanation': q.get('explanation', ''),
            }
        )

    score = (correct / total) * 100 if total else 0
    attempt = QuizAttempt(quiz_id=quiz.id, user_id=user_id, score=score, total=total, answers=review)
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt, review


async def review_flashcard(db: AsyncSession, flashcard: Flashcard, quality: int) -> Flashcard:
    interval, ef, rep = update_sm2(
        flashcard.interval_days,
        flashcard.ease_factor,
        flashcard.repetition,
        quality,
    )
    flashcard.interval_days = interval
    flashcard.ease_factor = ef
    flashcard.repetition = rep
    flashcard.next_review_at = datetime.utcnow() + timedelta(days=interval)
    flashcard.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(flashcard)
    return flashcard
