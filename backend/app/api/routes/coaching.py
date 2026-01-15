"""Coaching routes - AI-powered feedback using Claude."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter, RATE_LIMIT_AI
from app.models.database import Session, Shot

router = APIRouter()


@router.post("/{session_id}/analyze")
@limiter.limit(RATE_LIMIT_AI)
async def analyze_session(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get AI analysis of a complete session."""
    if not settings.anthropic_api_key:
        return {
            "status": "unavailable",
            "message": "Claude API key not configured",
            "fallback_feedback": _get_fallback_session_feedback(session_id)
        }

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    shots_result = await db.execute(
        select(Shot).where(Shot.session_id == session_id).order_by(Shot.shot_number)
    )
    shots = shots_result.scalars().all()

    # Build prompt for Claude
    prompt = _build_session_analysis_prompt(session, shots)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            "status": "success",
            "analysis": response.content[0].text,
            "session_id": session_id,
            "shots_analyzed": len(shots),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "fallback_feedback": _get_fallback_session_feedback(session_id)
        }


@router.post("/{session_id}/shots/{shot_number}/feedback")
@limiter.limit(RATE_LIMIT_AI)
async def get_shot_feedback(
    request: Request,
    session_id: str,
    shot_number: int,
    db: AsyncSession = Depends(get_db)
):
    """Get AI feedback on a specific shot."""
    if not settings.anthropic_api_key:
        return {
            "status": "unavailable",
            "message": "Claude API key not configured",
            "fallback_feedback": _get_fallback_shot_feedback()
        }

    shot_result = await db.execute(
        select(Shot)
        .where(Shot.session_id == session_id)
        .where(Shot.shot_number == shot_number)
    )
    shot = shot_result.scalar_one_or_none()

    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    prompt = _build_shot_analysis_prompt(shot)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            "status": "success",
            "feedback": response.content[0].text,
            "shot_number": shot_number,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "fallback_feedback": _get_fallback_shot_feedback()
        }


@router.get("/{session_id}/drills")
async def suggest_drills(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get drill suggestions based on session performance."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Calculate weak areas
    accuracy = session.total_pocketed / max(session.total_shots, 1)
    foul_rate = session.total_fouls / max(session.total_shots, 1)

    drills = []

    if accuracy < 0.3:
        drills.append({
            "name": "Straight-In Shots",
            "description": "Practice basic straight-in shots from various distances",
            "focus": "accuracy",
            "difficulty": "beginner",
        })

    if foul_rate > 0.2:
        drills.append({
            "name": "Cue Ball Control",
            "description": "Work on controlling the cue ball to avoid scratches",
            "focus": "control",
            "difficulty": "intermediate",
        })

    if accuracy >= 0.3 and accuracy < 0.6:
        drills.append({
            "name": "Cut Shots",
            "description": "Practice angled shots at 30, 45, and 60 degrees",
            "focus": "angles",
            "difficulty": "intermediate",
        })

    if accuracy >= 0.6:
        drills.append({
            "name": "Position Play",
            "description": "Focus on leaving the cue ball in good position",
            "focus": "strategy",
            "difficulty": "advanced",
        })

    return {
        "session_id": session_id,
        "accuracy_rate": accuracy,
        "foul_rate": foul_rate,
        "suggested_drills": drills,
    }


def _build_session_analysis_prompt(session, shots) -> str:
    """Build Claude prompt for session analysis."""
    return f"""Analyze this pool/billiards session and provide constructive feedback:

Session Statistics:
- Total Shots: {session.total_shots}
- Balls Pocketed: {session.total_pocketed}
- Fouls: {session.total_fouls}
- Accuracy Rate: {session.total_pocketed / max(session.total_shots, 1):.1%}

Shot Summary:
{chr(10).join(f"- Shot {s.shot_number}: Pocketed {len(s.balls_pocketed or [])} balls" for s in shots[:10])}
{"..." if len(shots) > 10 else ""}

Please provide:
1. Overall performance assessment
2. Key strengths observed
3. Areas for improvement
4. 2-3 specific practice recommendations

Keep the feedback encouraging and actionable for a recreational player."""


def _build_shot_analysis_prompt(shot) -> str:
    """Build Claude prompt for shot analysis."""
    pocketed = len(shot.balls_pocketed or [])
    return f"""Analyze this pool shot and provide brief feedback:

Shot #{shot.shot_number}:
- Duration: {shot.duration_ms or 0}ms
- Balls Pocketed: {pocketed}
- Table State Before: {shot.table_state_before}
- Table State After: {shot.table_state_after}

Provide 2-3 sentences of constructive feedback on this shot."""


def _get_fallback_session_feedback(session_id: str) -> str:
    """Fallback feedback when AI is unavailable."""
    return """Great practice session! Here are some general tips:

1. Focus on your pre-shot routine for consistency
2. Keep your bridge hand stable during the stroke
3. Follow through smoothly after contact

Keep practicing and tracking your progress!"""


def _get_fallback_shot_feedback() -> str:
    """Fallback shot feedback when AI is unavailable."""
    return "Nice effort! Remember to stay down on the shot and follow through."
