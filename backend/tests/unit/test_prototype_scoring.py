"""Unit tests for the local prototype scoring state machine."""
from app.services.prototype_scoring import BallTrack, FrameState, PrototypeEventBuilder


def _track(name: str, x: float, y: float, *, cue: bool = False) -> BallTrack:
    return BallTrack(
        name=name,
        x=x,
        y=y,
        radius=8.0,
        confidence=0.8,
        brightness=190.0 if cue else 110.0,
        saturation=20.0 if cue else 120.0,
        is_cue_ball=cue,
    )


def _frame(index: int, timestamp_ms: int, tracks: list[BallTrack], moving: list[str]) -> FrameState:
    return FrameState(
        frame_index=index,
        timestamp_ms=timestamp_ms,
        frame_width=400,
        frame_height=200,
        tracks=tracks,
        moving_names=moving,
    )


def test_builder_detects_object_ball_pocket_and_shot() -> None:
    builder = PrototypeEventBuilder(stationary_start_frames=1, settle_frames=2, pocket_missing_frames=2)

    builder.process_frame(_frame(0, 0, [_track("cue_ball", 140, 120, cue=True), _track("ball_2", 120, 30)], []))
    builder.process_frame(_frame(1, 100, [_track("cue_ball", 148, 118, cue=True), _track("ball_2", 18, 18)], ["cue_ball", "ball_2"]))
    builder.process_frame(_frame(2, 200, [_track("cue_ball", 160, 118, cue=True)], ["cue_ball"]))
    builder.process_frame(_frame(3, 300, [_track("cue_ball", 160, 118, cue=True)], []))
    builder.process_frame(_frame(4, 400, [_track("cue_ball", 160, 118, cue=True)], []))
    builder.finish()

    event_types = [event.event_type for event in builder.events]
    assert "pocket" in event_types
    assert "shot" in event_types

    pocket_event = next(event for event in builder.events if event.event_type == "pocket")
    assert pocket_event.event_data["ball"] == "ball_2"
    assert pocket_event.event_data["pocket"] == "top_left"

    assert len(builder.shots) == 1
    assert builder.shots[0].balls_pocketed == ["ball_2"]
    assert builder.shots[0].foul_types == []


def test_builder_detects_scratch_foul() -> None:
    builder = PrototypeEventBuilder(stationary_start_frames=1, settle_frames=2, pocket_missing_frames=2)

    builder.process_frame(_frame(0, 0, [_track("cue_ball", 30, 180, cue=True), _track("ball_2", 200, 90)], []))
    builder.process_frame(_frame(1, 100, [_track("cue_ball", 16, 188, cue=True), _track("ball_2", 200, 90)], ["cue_ball"]))
    builder.process_frame(_frame(2, 200, [_track("ball_2", 200, 90)], []))
    builder.process_frame(_frame(3, 300, [_track("ball_2", 200, 90)], []))
    builder.process_frame(_frame(4, 400, [_track("ball_2", 200, 90)], []))
    builder.finish()

    foul_event = next(event for event in builder.events if event.event_type == "foul")
    assert foul_event.event_data["foul_type"] == "scratch"
    assert foul_event.event_data["details"]["ball"] == "cue_ball"

    assert len(builder.shots) == 1
    assert builder.shots[0].foul_types == ["scratch"]