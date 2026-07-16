"""Physics validation and shot analysis using pooltool."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .shot_detector import ShotData, TableState

logger = logging.getLogger(__name__)

# Physical constants
BALL_RADIUS = 0.02625  # Standard pool ball radius in meters (2.625 cm / 52.5mm diameter)
BALL_MASS = 0.17  # Standard pool ball mass in kg
TABLE_LENGTH = 2.24  # 7-foot table length in meters
TABLE_WIDTH = 1.12  # 7-foot table width in meters

# Coordinate scaling (table units to meters)
SCALE_X = TABLE_LENGTH / 1000  # table x (0-1000) to meters
SCALE_Y = TABLE_WIDTH / 500    # table y (0-500) to meters


@dataclass
class CollisionData:
    """Data about a collision event."""

    ball1_name: str
    ball2_name: str
    position: tuple[float, float]  # Table coordinates
    ball1_velocity_before: tuple[float, float]
    ball1_velocity_after: tuple[float, float]
    ball2_velocity_before: tuple[float, float]
    ball2_velocity_after: tuple[float, float]
    energy_transferred: float
    collision_angle: float  # Degrees


@dataclass
class ShotAnalysis:
    """Comprehensive analysis of a shot."""

    shot_number: int
    duration_seconds: float

    # Cue ball analysis
    cue_initial_speed: float  # Table units per second
    cue_initial_speed_mph: float  # Miles per hour
    cue_initial_angle: float  # Degrees from horizontal
    cue_distance_traveled: float  # Table units
    cue_final_position: tuple[float, float]

    # Physics analysis
    total_collisions: int
    collision_data: list[CollisionData] = field(default_factory=list)
    energy_efficiency: float = 0.0  # Ratio of useful energy transfer

    # Pocketing analysis
    balls_pocketed: list[str] = field(default_factory=list)
    pockets_used: list[str] = field(default_factory=list)

    # Validation
    physics_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)

    # Simulated vs observed comparison (if available)
    simulation_match_score: float | None = None
    position_errors: dict[str, float] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        """Get human-readable summary."""
        lines = [
            f"Shot {self.shot_number} Analysis:",
            f"  Duration: {self.duration_seconds:.2f}s",
            f"  Cue ball speed: {self.cue_initial_speed_mph:.1f} mph",
            f"  Shot angle: {self.cue_initial_angle:.1f}°",
            f"  Distance traveled: {self.cue_distance_traveled:.1f} units",
            f"  Collisions: {self.total_collisions}",
        ]
        if self.balls_pocketed:
            lines.append(f"  Pocketed: {', '.join(self.balls_pocketed)}")
        if not self.physics_valid:
            lines.append(f"  Validation errors: {', '.join(self.validation_errors)}")
        return "\n".join(lines)


class PhysicsValidator:
    """Validates and analyzes shot physics."""

    def __init__(
        self,
        use_pooltool: bool = True,
        frame_rate: float = 30.0,
    ) -> None:
        """Initialize physics validator.

        Args:
            use_pooltool: Whether to use pooltool for simulation.
            frame_rate: Video frame rate for velocity calculation.
        """
        self._use_pooltool = use_pooltool
        self._frame_rate = frame_rate
        self._pooltool_available = False

        if use_pooltool:
            self._init_pooltool()

    def _init_pooltool(self) -> None:
        """Initialize pooltool if available."""
        try:
            import pooltool as pt

            self._pooltool_available = True
            logger.info("pooltool initialized successfully")
        except ImportError:
            logger.warning("pooltool not available, using simplified physics")
            self._pooltool_available = False

    def analyze_shot(
        self,
        shot_data: ShotData,
        events: list | None = None,
    ) -> ShotAnalysis:
        """Analyze a completed shot.

        Args:
            shot_data: Shot data from shot detector.
            events: Optional list of game events during shot.

        Returns:
            Comprehensive shot analysis.
        """
        # Calculate cue ball metrics
        cue_speed = shot_data.cue_initial_speed
        cue_speed_per_second = cue_speed * self._frame_rate

        # Convert to mph (table units are approximately mm, need scaling)
        # Assuming 1000 table units = 2.24 meters
        speed_meters_per_second = cue_speed_per_second * SCALE_X
        cue_speed_mph = speed_meters_per_second * 2.237  # m/s to mph

        # Calculate shot angle
        if shot_data.cue_initial_vx != 0 or shot_data.cue_initial_vy != 0:
            angle = np.degrees(np.arctan2(
                shot_data.cue_initial_vy,
                shot_data.cue_initial_vx
            ))
        else:
            angle = 0.0

        # Calculate distance traveled
        cue_distance = self._calculate_trajectory_distance(shot_data.cue_trajectory)

        # Get final position
        if shot_data.cue_trajectory:
            final_x, final_y = shot_data.cue_trajectory[-1][:2]
        else:
            final_x, final_y = shot_data.cue_start_x, shot_data.cue_start_y

        # Count collisions from events
        collision_count = 0
        collision_data = []
        balls_pocketed = []
        pockets_used = []

        if events:
            from .event_detector import EventType

            for event in events:
                if event.event_type == EventType.COLLISION:
                    collision_count += 1
                elif event.event_type == EventType.POCKET:
                    balls_pocketed.extend(event.ball_names)
                    if event.pocket_name:
                        pockets_used.append(event.pocket_name)
                elif event.event_type == EventType.SCRATCH:
                    balls_pocketed.append("cue")
                    if event.pocket_name:
                        pockets_used.append(event.pocket_name)

        # Validate physics
        valid, errors = self._validate_physics(shot_data, cue_speed_mph)

        analysis = ShotAnalysis(
            shot_number=shot_data.shot_number,
            duration_seconds=shot_data.duration_seconds,
            cue_initial_speed=cue_speed,
            cue_initial_speed_mph=cue_speed_mph,
            cue_initial_angle=angle,
            cue_distance_traveled=cue_distance,
            cue_final_position=(final_x, final_y),
            total_collisions=collision_count,
            collision_data=collision_data,
            balls_pocketed=balls_pocketed,
            pockets_used=pockets_used,
            physics_valid=valid,
            validation_errors=errors,
        )

        # Run simulation comparison if pooltool available
        if self._pooltool_available and self._use_pooltool:
            self._run_simulation_comparison(shot_data, analysis)

        return analysis

    def _calculate_trajectory_distance(
        self,
        trajectory: list[tuple[float, float, int, int]],
    ) -> float:
        """Calculate total distance traveled along trajectory."""
        if len(trajectory) < 2:
            return 0.0

        total_distance = 0.0
        for i in range(1, len(trajectory)):
            x1, y1 = trajectory[i - 1][:2]
            x2, y2 = trajectory[i][:2]
            total_distance += np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        return total_distance

    def _validate_physics(
        self,
        shot_data: ShotData,
        cue_speed_mph: float,
    ) -> tuple[bool, list[str]]:
        """Validate shot physics for anomalies.

        Returns:
            (is_valid, list of error messages)
        """
        errors = []

        # Check for unrealistic cue ball speed
        if cue_speed_mph > 30:  # Pro players rarely exceed 25 mph
            errors.append(f"Unrealistic cue speed: {cue_speed_mph:.1f} mph")

        if cue_speed_mph < 0.5:  # Too slow to be a real shot
            errors.append(f"Shot speed too low: {cue_speed_mph:.1f} mph")

        # Check for teleporting balls (position jumps)
        for track_id, trajectory in shot_data.all_trajectories.items():
            if len(trajectory) < 2:
                continue

            for i in range(1, len(trajectory)):
                x1, y1 = trajectory[i - 1][:2]
                x2, y2 = trajectory[i][:2]
                distance = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                # Max reasonable distance per frame (assuming 30 fps, ~30 mph max)
                # 30 mph = ~13.4 m/s = ~6 table units per frame at 30fps
                max_distance = 50  # Allow some margin for tracking noise

                if distance > max_distance:
                    errors.append(
                        f"Ball {track_id} position jump: {distance:.1f} units in one frame"
                    )

        # Check shot duration
        if shot_data.duration_seconds > 30:
            errors.append(f"Shot duration too long: {shot_data.duration_seconds:.1f}s")

        if shot_data.duration_seconds < 0.3:
            errors.append(f"Shot duration too short: {shot_data.duration_seconds:.1f}s")

        return len(errors) == 0, errors

    def _run_simulation_comparison(
        self,
        shot_data: ShotData,
        analysis: ShotAnalysis,
    ) -> None:
        """Run pooltool simulation and compare to observed trajectory."""
        try:
            import pooltool as pt

            # Create table
            table = pt.Table.default("7_foot")

            # Create balls from initial state
            balls = {}
            for ball_data in shot_data.table_state_before.balls:
                # Convert table coordinates to pooltool coordinates
                x_m = ball_data["x"] * SCALE_X
                y_m = ball_data["y"] * SCALE_Y

                ball_id = ball_data["class_name"]
                balls[ball_id] = pt.Ball.create(
                    ball_id,
                    xy=(x_m, y_m),
                )

            # Set cue ball velocity
            if "cue" in balls:
                vx_m = shot_data.cue_initial_vx * SCALE_X * self._frame_rate
                vy_m = shot_data.cue_initial_vy * SCALE_Y * self._frame_rate
                balls["cue"].state.rvw[1] = [vx_m, vy_m, 0]

            # Create and run system
            system = pt.System(
                table=table,
                balls=balls,
                cue=pt.Cue.default(),
            )

            # Simulate
            pt.simulate(system, inplace=True)

            # Compare final positions
            position_errors = {}
            for ball_id, ball in system.balls.items():
                # Get simulated final position
                sim_x = ball.state.rvw[0][0] / SCALE_X
                sim_y = ball.state.rvw[0][1] / SCALE_Y

                # Find observed final position
                for ball_data in shot_data.table_state_after.balls:
                    if ball_data["class_name"] == ball_id:
                        obs_x = ball_data["x"]
                        obs_y = ball_data["y"]
                        error = np.sqrt((sim_x - obs_x) ** 2 + (sim_y - obs_y) ** 2)
                        position_errors[ball_id] = error
                        break

            analysis.position_errors = position_errors

            # Calculate match score (inverse of average error)
            if position_errors:
                avg_error = np.mean(list(position_errors.values()))
                # Normalize: 0 error = 1.0 score, 100 units error = 0.0 score
                analysis.simulation_match_score = max(0.0, 1.0 - avg_error / 100)

            logger.debug("Simulation comparison complete, match score: %.2f", analysis.simulation_match_score)

        except Exception as e:
            logger.warning("Simulation comparison failed: %s", e)

    def estimate_impact_velocity(
        self,
        ball1_trajectory: list[tuple[float, float, int, int]],
        ball2_trajectory: list[tuple[float, float, int, int]],
        collision_frame: int,
    ) -> tuple[tuple[float, float], tuple[float, float]] | None:
        """Estimate ball velocities at collision point.

        Args:
            ball1_trajectory: First ball's trajectory.
            ball2_trajectory: Second ball's trajectory.
            collision_frame: Frame number of collision.

        Returns:
            ((vx1, vy1), (vx2, vy2)) or None if cannot estimate.
        """
        # Find trajectory points around collision
        def get_velocity_at_frame(trajectory, frame):
            # Find points before and after frame
            before = None
            after = None

            for i, (x, y, ts, f) in enumerate(trajectory):
                if f <= frame:
                    before = (x, y, f)
                if f >= frame and after is None:
                    after = (x, y, f)
                    break

            if before is None or after is None or before[2] == after[2]:
                return None

            dt = (after[2] - before[2]) / self._frame_rate
            if dt == 0:
                return None

            vx = (after[0] - before[0]) / dt
            vy = (after[1] - before[1]) / dt
            return (vx, vy)

        v1 = get_velocity_at_frame(ball1_trajectory, collision_frame)
        v2 = get_velocity_at_frame(ball2_trajectory, collision_frame)

        if v1 is None or v2 is None:
            return None

        return (v1, v2)

    def calculate_deflection_angle(
        self,
        incoming_velocity: tuple[float, float],
        outgoing_velocity: tuple[float, float],
    ) -> float:
        """Calculate deflection angle in degrees.

        Args:
            incoming_velocity: (vx, vy) before collision.
            outgoing_velocity: (vx, vy) after collision.

        Returns:
            Deflection angle in degrees.
        """
        # Calculate angles
        angle_in = np.arctan2(incoming_velocity[1], incoming_velocity[0])
        angle_out = np.arctan2(outgoing_velocity[1], outgoing_velocity[0])

        # Deflection is difference
        deflection = np.degrees(angle_out - angle_in)

        # Normalize to -180 to 180
        while deflection > 180:
            deflection -= 360
        while deflection < -180:
            deflection += 360

        return deflection

    def predict_shot_outcome(
        self,
        cue_position: tuple[float, float],
        cue_velocity: tuple[float, float],
        ball_positions: dict[str, tuple[float, float]],
    ) -> dict:
        """Predict shot outcome using physics simulation.

        Args:
            cue_position: Cue ball (x, y) in table coordinates.
            cue_velocity: Initial velocity (vx, vy).
            ball_positions: Dict of ball_name -> (x, y).

        Returns:
            Prediction dict with likely outcomes.
        """
        if not self._pooltool_available:
            return {"error": "pooltool not available for prediction"}

        try:
            import pooltool as pt

            # Create table
            table = pt.Table.default("7_foot")

            # Create balls
            balls = {}
            for ball_name, (x, y) in ball_positions.items():
                x_m = x * SCALE_X
                y_m = y * SCALE_Y
                balls[ball_name] = pt.Ball.create(ball_name, xy=(x_m, y_m))

            # Add cue ball if not in positions
            if "cue" not in balls:
                x_m = cue_position[0] * SCALE_X
                y_m = cue_position[1] * SCALE_Y
                balls["cue"] = pt.Ball.create("cue", xy=(x_m, y_m))

            # Set cue velocity
            vx_m = cue_velocity[0] * SCALE_X * self._frame_rate
            vy_m = cue_velocity[1] * SCALE_Y * self._frame_rate
            balls["cue"].state.rvw[1] = [vx_m, vy_m, 0]

            # Create and simulate
            system = pt.System(
                table=table,
                balls=balls,
                cue=pt.Cue.default(),
            )
            pt.simulate(system, inplace=True)

            # Analyze results
            pocketed = []
            final_positions = {}

            for ball_id, ball in system.balls.items():
                final_x = ball.state.rvw[0][0] / SCALE_X
                final_y = ball.state.rvw[0][1] / SCALE_Y

                # Check if pocketed (position outside table)
                if final_x < 0 or final_x > 1000 or final_y < 0 or final_y > 500:
                    pocketed.append(ball_id)
                else:
                    final_positions[ball_id] = (final_x, final_y)

            return {
                "pocketed": pocketed,
                "final_positions": final_positions,
                "scratch": "cue" in pocketed,
            }

        except Exception as e:
            logger.error("Shot prediction failed: %s", e)
            return {"error": str(e)}
