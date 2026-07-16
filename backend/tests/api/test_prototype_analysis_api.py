"""API tests for the prototype scoring endpoint."""
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.analysis import OpenCVPoolPrototypeAnalyzer
from app.core.auth import get_current_profile_id
from app.main import app
from app.models.database import Event, Foul, Session, Shot
from app.services.prototype_scoring import (
    PrototypeAnalysisResult,
    PrototypeDetectedEvent,
    PrototypeDetectedShot,
)


@pytest.fixture
def prototype_auth_override():
    async def override_profile_id() -> str:
        return "test-profile"

    app.dependency_overrides[get_current_profile_id] = override_profile_id
    yield
    app.dependency_overrides.pop(get_current_profile_id, None)


@pytest.mark.asyncio
async def test_run_prototype_analysis_persists_detected_data(
    client: AsyncClient,
    test_db: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prototype_auth_override,
):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"prototype")

    session = Session(
        id="prototype-session",
        profile_id="test-profile",
        name="Prototype Session",
        source_type="video_file",
        source_path=str(video_path),
        status="completed",
    )
    test_db.add(session)
    await test_db.commit()

    fake_result = PrototypeAnalysisResult(
        analyzed_frames=18,
        sample_fps=6,
        duration_ms=4200,
        notes=["Synthetic result"],
        frame_width=800,
        frame_height=400,
        shots=[
            PrototypeDetectedShot(
                shot_number=1,
                timestamp_start_ms=100,
                timestamp_end_ms=600,
                duration_ms=500,
                balls_pocketed=["ball_2"],
                foul_types=["scratch"],
                confidence_overall=0.81,
                table_state_before={"balls": [{"name": "cue_ball"}]},
                table_state_after={"balls": [{"name": "ball_3"}]},
                analysis_data={"motion_frames": 3},
            )
        ],
        events=[
            PrototypeDetectedEvent(
                timestamp_ms=300,
                event_type="pocket",
                event_data={"ball": "ball_2", "pocket": "top_left", "shot_number": 1},
            ),
            PrototypeDetectedEvent(
                timestamp_ms=310,
                event_type="foul",
                event_data={
                    "foul_type": "scratch",
                    "shot_number": 1,
                    "details": {"ball": "cue_ball", "pocket": "bottom_left"},
                },
            ),
            PrototypeDetectedEvent(
                timestamp_ms=600,
                event_type="shot",
                event_data={"shot_number": 1, "balls_pocketed": ["ball_2"], "confidence_overall": 0.81},
            ),
        ],
    )

    monkeypatch.setattr(OpenCVPoolPrototypeAnalyzer, "analyze", lambda self, path: fake_result)

    response = await client.post(
        "/api/analysis/prototype-session/prototype",
        json={"replace_existing": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["shots_detected"] == 1
    assert payload["pockets_detected"] == 1
    assert payload["fouls_detected"] == 1
    assert payload["session"]["total_shots"] == 1
    assert payload["session"]["total_pocketed"] == 1
    assert payload["session"]["total_fouls"] == 1

    shot_count = await test_db.scalar(select(func.count()).select_from(Shot))
    event_count = await test_db.scalar(select(func.count()).select_from(Event))
    foul_count = await test_db.scalar(select(func.count()).select_from(Foul))

    assert shot_count == 1
    assert event_count == 3
    assert foul_count == 1

    await test_db.refresh(session)
    assert session.extra_data["prototype_analysis"]["source"] == "opencv_prototype"