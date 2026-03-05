from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.deps import get_current_user
from app.models import Chunk, StudySession, User
from app.schemas import SearchIn
from app.services.embeddings import cosine_similarity, embed_text


router = APIRouter(prefix='/search', tags=['search'])


@router.post('/semantic')
async def semantic_search(payload: SearchIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    q_vec = embed_text(payload.query)
    result = await db.execute(
        select(Chunk)
        .join(StudySession, StudySession.id == Chunk.session_id)
        .where(StudySession.user_id == user.id)
    )
    chunks = result.scalars().all()

    scored = []
    for c in chunks:
        score = cosine_similarity(q_vec, c.embedding)
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: payload.top_k]

    return [
        {
            'chunk_id': c.id,
            'score': float(s),
            'content': c.content,
            'citation': {
                'url': c.citation_url,
                'title': c.citation_title,
                'header': c.citation_header,
                'snippet': c.citation_snippet,
            },
        }
        for s, c in top
    ]
