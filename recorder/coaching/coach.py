"""AI-powered pool coaching using Claude API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Sequence

from ..analysis.shot_detector import ShotData
from ..analysis.event_detector import GameEvent, EventType
from ..analysis.physics import ShotAnalysis

logger = logging.getLogger(__name__)

# Coaching prompts
SHOT_ANALYSIS_PROMPT = """You are an expert pool/billiards coach. Analyze this shot and provide actionable feedback.

Shot Data:
- Shot #{shot_number}
- Duration: {duration:.2f} seconds
- Cue ball initial speed: {speed_mph:.1f} mph
- Shot angle: {angle:.1f}° from horizontal
- Distance traveled: {distance:.1f} table units

Events during shot:
{events_summary}

Physics validation: {physics_status}
{physics_errors}

Table state before:
{table_before}

Table state after:
{table_after}

Provide:
1. Brief assessment of shot execution (1-2 sentences)
2. What went well
3. Area for improvement
4. Specific tip for next similar shot

Keep response concise and actionable. Focus on technique, not luck."""

SESSION_SUMMARY_PROMPT = """You are an expert pool/billiards coach. Summarize this practice session.

Session Statistics:
- Total shots: {total_shots}
- Balls pocketed: {balls_pocketed}
- Scratches: {scratches}
- Fouls: {fouls}
- Average shot speed: {avg_speed:.1f} mph
- Session duration: {duration_minutes:.1f} minutes

Shot breakdown by outcome:
{shot_outcomes}

Provide:
1. Overall assessment (2-3 sentences)
2. Strengths demonstrated
3. Areas needing work
4. 2-3 specific drills to improve weak areas
5. Encouragement and motivation

Be supportive but honest. Focus on improvement opportunities."""

DRILL_SUGGESTION_PROMPT = """You are an expert pool/billiards coach. Based on the player's recent performance, suggest targeted practice drills.

Recent performance data:
- Pocket success rate: {pocket_rate:.1%}
- Most missed pocket: {missed_pocket}
- Average cue ball speed: {avg_speed:.1f} mph
- Common errors: {common_errors}

Player skill indicators:
- Position play: {position_skill}
- Speed control: {speed_skill}
- Cut shot accuracy: {cut_skill}

Suggest 3 specific drills with:
1. Drill name
2. Setup description
3. Goal/success criteria
4. How it addresses their weakness
5. Progression to make it harder

Keep drills practical for home/bar table practice."""


class FeedbackType(Enum):
    """Types of coaching feedback."""

    SHOT_ANALYSIS = auto()      # Analysis of single shot
    SESSION_SUMMARY = auto()    # Summary of practice session
    DRILL_SUGGESTION = auto()   # Suggested practice drills
    MISTAKE_CORRECTION = auto() # Correction for specific mistake
    ENCOURAGEMENT = auto()      # Positive reinforcement
    TIP = auto()               # General tip


@dataclass
class CoachingFeedback:
    """Coaching feedback from AI analysis."""

    feedback_type: FeedbackType
    content: str
    shot_number: int | None = None
    timestamp_ms: int | None = None
    confidence: float = 1.0
    suggestions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def summary(self) -> str:
        """Get short summary of feedback."""
        # Return first sentence or first 100 chars
        first_line = self.content.split("\n")[0]
        if len(first_line) > 100:
            return first_line[:97] + "..."
        return first_line


class PoolCoach:
    """AI-powered pool coach using Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
    ) -> None:
        """Initialize pool coach.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
            model: Claude model to use.
            max_tokens: Maximum response tokens.
        """
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._client = None
        self._anthropic_available = False

        self._init_client()

    def _init_client(self) -> None:
        """Initialize Anthropic client."""
        try:
            import anthropic

            if self._api_key:
                self._client = anthropic.Anthropic(api_key=self._api_key)
            else:
                # Will use ANTHROPIC_API_KEY env var
                self._client = anthropic.Anthropic()

            self._anthropic_available = True
            logger.info("Claude API initialized with model %s", self._model)

        except ImportError:
            logger.warning("anthropic package not installed, coaching disabled")
            self._anthropic_available = False
        except Exception as e:
            logger.error("Failed to initialize Claude API: %s", e)
            self._anthropic_available = False

    @property
    def is_available(self) -> bool:
        """Check if coaching is available."""
        return self._anthropic_available and self._client is not None

    def analyze_shot(
        self,
        shot_data: ShotData,
        analysis: ShotAnalysis | None = None,
        events: Sequence[GameEvent] | None = None,
    ) -> CoachingFeedback:
        """Get coaching feedback for a single shot.

        Args:
            shot_data: Shot data from detector.
            analysis: Optional physics analysis.
            events: Optional list of events during shot.

        Returns:
            Coaching feedback for the shot.
        """
        if not self.is_available:
            return self._fallback_shot_feedback(shot_data, analysis, events)

        # Build events summary
        events_summary = "None recorded"
        if events:
            event_lines = []
            for event in events:
                event_lines.append(f"  - {event.description}")
            events_summary = "\n".join(event_lines) if event_lines else "None recorded"

        # Physics status
        physics_status = "Not validated"
        physics_errors = ""
        if analysis:
            physics_status = "Valid" if analysis.physics_valid else "Issues detected"
            if analysis.validation_errors:
                physics_errors = "Errors: " + ", ".join(analysis.validation_errors)

        # Format table states
        table_before = self._format_table_state(shot_data.table_state_before)
        table_after = self._format_table_state(shot_data.table_state_after)

        # Build prompt
        prompt = SHOT_ANALYSIS_PROMPT.format(
            shot_number=shot_data.shot_number,
            duration=shot_data.duration_seconds,
            speed_mph=analysis.cue_initial_speed_mph if analysis else 0,
            angle=analysis.cue_initial_angle if analysis else 0,
            distance=analysis.cue_distance_traveled if analysis else 0,
            events_summary=events_summary,
            physics_status=physics_status,
            physics_errors=physics_errors,
            table_before=table_before,
            table_after=table_after,
        )

        # Call Claude API
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            content = response.content[0].text

            return CoachingFeedback(
                feedback_type=FeedbackType.SHOT_ANALYSIS,
                content=content,
                shot_number=shot_data.shot_number,
                timestamp_ms=shot_data.end_timestamp_ms,
                metadata={
                    "model": self._model,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

        except Exception as e:
            logger.error("Claude API call failed: %s", e)
            return self._fallback_shot_feedback(shot_data, analysis, events)

    def summarize_session(
        self,
        shots: Sequence[ShotData],
        analyses: Sequence[ShotAnalysis] | None = None,
        events: Sequence[GameEvent] | None = None,
        session_duration_ms: int = 0,
    ) -> CoachingFeedback:
        """Get summary feedback for a practice session.

        Args:
            shots: All shots in the session.
            analyses: Optional physics analyses for shots.
            events: Optional all events in session.
            session_duration_ms: Total session duration.

        Returns:
            Session summary feedback.
        """
        if not self.is_available:
            return self._fallback_session_summary(shots)

        # Calculate statistics
        total_shots = len(shots)
        balls_pocketed = 0
        scratches = 0
        fouls = 0
        speeds = []

        if events:
            for event in events:
                if event.event_type == EventType.POCKET:
                    balls_pocketed += 1
                elif event.event_type == EventType.SCRATCH:
                    scratches += 1
                elif event.event_type in (EventType.FOUL_NO_RAIL, EventType.FOUL_WRONG_BALL):
                    fouls += 1

        if analyses:
            speeds = [a.cue_initial_speed_mph for a in analyses if a.cue_initial_speed_mph > 0]

        avg_speed = sum(speeds) / len(speeds) if speeds else 0
        duration_minutes = session_duration_ms / 60000

        # Shot outcomes
        outcomes = {
            "Successful pockets": balls_pocketed,
            "Scratches": scratches,
            "Fouls": fouls,
            "Safety/position shots": max(0, total_shots - balls_pocketed - scratches),
        }
        shot_outcomes = "\n".join(f"  - {k}: {v}" for k, v in outcomes.items())

        prompt = SESSION_SUMMARY_PROMPT.format(
            total_shots=total_shots,
            balls_pocketed=balls_pocketed,
            scratches=scratches,
            fouls=fouls,
            avg_speed=avg_speed,
            duration_minutes=duration_minutes,
            shot_outcomes=shot_outcomes,
        )

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            return CoachingFeedback(
                feedback_type=FeedbackType.SESSION_SUMMARY,
                content=response.content[0].text,
                metadata={
                    "total_shots": total_shots,
                    "balls_pocketed": balls_pocketed,
                    "model": self._model,
                },
            )

        except Exception as e:
            logger.error("Claude API call failed: %s", e)
            return self._fallback_session_summary(shots)

    def suggest_drills(
        self,
        recent_analyses: Sequence[ShotAnalysis],
        recent_events: Sequence[GameEvent] | None = None,
    ) -> CoachingFeedback:
        """Suggest practice drills based on recent performance.

        Args:
            recent_analyses: Recent shot analyses.
            recent_events: Recent game events.

        Returns:
            Drill suggestions feedback.
        """
        if not self.is_available or not recent_analyses:
            return CoachingFeedback(
                feedback_type=FeedbackType.DRILL_SUGGESTION,
                content="Practice the stop shot: Hit the cue ball center to make it stop on contact.",
                suggestions=["Stop shot drill", "Line-up drill", "Position play basics"],
            )

        # Calculate metrics
        pocket_events = [e for e in (recent_events or []) if e.event_type == EventType.POCKET]
        scratch_events = [e for e in (recent_events or []) if e.event_type == EventType.SCRATCH]

        total_attempts = len(recent_analyses)
        pocket_rate = len(pocket_events) / total_attempts if total_attempts > 0 else 0

        # Find most missed pocket (simplified - would need more data in real impl)
        missed_pocket = "corner pockets"

        # Average speed
        speeds = [a.cue_initial_speed_mph for a in recent_analyses]
        avg_speed = sum(speeds) / len(speeds) if speeds else 10

        # Common errors
        errors = []
        if scratch_events:
            errors.append("scratches")
        if any(not a.physics_valid for a in recent_analyses):
            errors.append("inconsistent stroke")
        common_errors = ", ".join(errors) if errors else "none identified"

        # Skill assessments (simplified)
        position_skill = "developing" if pocket_rate < 0.5 else "intermediate"
        speed_skill = "needs work" if avg_speed > 15 or avg_speed < 5 else "good"
        cut_skill = "developing"

        prompt = DRILL_SUGGESTION_PROMPT.format(
            pocket_rate=pocket_rate,
            missed_pocket=missed_pocket,
            avg_speed=avg_speed,
            common_errors=common_errors,
            position_skill=position_skill,
            speed_skill=speed_skill,
            cut_skill=cut_skill,
        )

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            return CoachingFeedback(
                feedback_type=FeedbackType.DRILL_SUGGESTION,
                content=response.content[0].text,
                metadata={
                    "pocket_rate": pocket_rate,
                    "avg_speed": avg_speed,
                },
            )

        except Exception as e:
            logger.error("Claude API call failed: %s", e)
            return CoachingFeedback(
                feedback_type=FeedbackType.DRILL_SUGGESTION,
                content="Focus on fundamentals: stance, grip, and smooth stroke.",
                suggestions=["Stance check", "Pendulum stroke drill"],
            )

    def get_tip(self, context: str = "general") -> CoachingFeedback:
        """Get a quick tip based on context.

        Args:
            context: Context for the tip (e.g., "after_scratch", "good_shot").

        Returns:
            Quick tip feedback.
        """
        tips = {
            "after_scratch": "After a scratch, take your time setting up. Position the cue ball to give yourself the best angle on your target ball.",
            "after_foul": "Focus on hitting the correct ball first. Visualize the shot line before shooting.",
            "good_shot": "Nice shot! Remember what that felt like - the stance, the stroke, the follow-through.",
            "slow_shot": "Don't be afraid to hit the ball with authority. A confident stroke is often more accurate than a tentative one.",
            "fast_shot": "Speed control is key. Try to hit the ball just hard enough to pocket it and position for the next shot.",
            "general": "Keep your bridge hand stable and your back arm loose. Let the cue do the work.",
            "opening": "On the break, hit the head ball full and follow through completely. Power comes from your legs and core.",
            "safety": "When playing safe, think two shots ahead. Where do you want to leave your opponent?",
        }

        content = tips.get(context, tips["general"])

        return CoachingFeedback(
            feedback_type=FeedbackType.TIP,
            content=content,
            metadata={"context": context},
        )

    def _format_table_state(self, state) -> str:
        """Format table state for prompt."""
        if not state or not state.balls:
            return "No balls recorded"

        lines = []
        for ball in state.balls:
            name = ball.get("class_name", "unknown")
            x = ball.get("x", 0)
            y = ball.get("y", 0)
            lines.append(f"  - {name}: ({x:.0f}, {y:.0f})")

        return "\n".join(lines)

    def _fallback_shot_feedback(
        self,
        shot_data: ShotData,
        analysis: ShotAnalysis | None,
        events: Sequence[GameEvent] | None,
    ) -> CoachingFeedback:
        """Generate fallback feedback without API."""
        # Check if anything was pocketed
        pocketed = []
        scratched = False

        if events:
            for event in events:
                if event.event_type == EventType.POCKET:
                    pocketed.extend(event.ball_names)
                elif event.event_type == EventType.SCRATCH:
                    scratched = True

        if scratched:
            content = "Scratch! Focus on cue ball control. Try to hit the cue ball lower to reduce forward roll after contact."
        elif pocketed:
            content = f"Good shot! Pocketed: {', '.join(pocketed)}. Work on positioning the cue ball for your next shot."
        else:
            content = "Keep practicing! Focus on a smooth, level stroke and follow through towards your target."

        return CoachingFeedback(
            feedback_type=FeedbackType.SHOT_ANALYSIS,
            content=content,
            shot_number=shot_data.shot_number,
            timestamp_ms=shot_data.end_timestamp_ms,
            metadata={"fallback": True},
        )

    def _fallback_session_summary(self, shots: Sequence[ShotData]) -> CoachingFeedback:
        """Generate fallback session summary without API."""
        total = len(shots)

        content = f"""Session complete! You took {total} shots.

Key points to remember:
- Maintain a consistent pre-shot routine
- Keep your head down through the shot
- Follow through towards your target

Keep practicing and track your progress over time!"""

        return CoachingFeedback(
            feedback_type=FeedbackType.SESSION_SUMMARY,
            content=content,
            metadata={"fallback": True, "total_shots": total},
        )
