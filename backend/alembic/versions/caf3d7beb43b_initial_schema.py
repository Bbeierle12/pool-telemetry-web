"""Initial schema

Revision ID: caf3d7beb43b
Revises:
Create Date: 2026-01-14 18:24:14.515025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'caf3d7beb43b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create profiles table
    op.create_table(
        'profiles',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('pin_hash', sa.String(255), nullable=False),
        sa.Column('avatar', sa.String(50), default='default'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('is_admin', sa.Boolean, default=False),
    )

    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('profile_id', sa.String(32), sa.ForeignKey('profiles.id'), nullable=True),
        sa.Column('name', sa.String(255)),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('ended_at', sa.DateTime, nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('source_type', sa.String(50)),
        sa.Column('source_path', sa.Text),
        sa.Column('video_duration_ms', sa.Integer, default=0),
        sa.Column('video_resolution', sa.String(20)),
        sa.Column('video_framerate', sa.Integer),
        sa.Column('total_shots', sa.Integer, default=0),
        sa.Column('total_pocketed', sa.Integer, default=0),
        sa.Column('total_fouls', sa.Integer, default=0),
        sa.Column('gemini_cost_usd', sa.Float, default=0.0),
        sa.Column('notes', sa.Text),
    )
    op.create_index('idx_sessions_created', 'sessions', ['created_at'])
    op.create_index('idx_sessions_status', 'sessions', ['status'])

    # Create shots table
    op.create_table(
        'shots',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(32), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shot_number', sa.Integer, nullable=False),
        sa.Column('game_number', sa.Integer, default=1),
        sa.Column('timestamp_ms', sa.Integer),
        sa.Column('player', sa.String(50)),
        sa.Column('cue_ball_position', sa.JSON),
        sa.Column('target_ball', sa.Integer),
        sa.Column('target_ball_position', sa.JSON),
        sa.Column('shot_type', sa.String(50)),
        sa.Column('intended_pocket', sa.Integer),
        sa.Column('pocketed_balls', sa.JSON),
        sa.Column('is_foul', sa.Boolean, default=False),
        sa.Column('foul_type', sa.String(50)),
        sa.Column('table_state_before', sa.JSON),
        sa.Column('table_state_after', sa.JSON),
        sa.Column('cue_stick_data', sa.JSON),
        sa.Column('confidence_overall', sa.Float),
        sa.Column('confidence_ball_detection', sa.Float),
        sa.Column('confidence_trajectory', sa.Float),
        sa.Column('ai_analysis', sa.JSON),
        sa.Column('frame_before_path', sa.String(255)),
        sa.Column('frame_after_path', sa.String(255)),
    )
    op.create_index('idx_shots_session', 'shots', ['session_id'])
    op.create_index('idx_shots_number', 'shots', ['session_id', 'shot_number'])

    # Create events table
    op.create_table(
        'events',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(32), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp_ms', sa.Integer, nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('data', sa.JSON),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_events_session', 'events', ['session_id'])
    op.create_index('idx_events_timestamp', 'events', ['session_id', 'timestamp_ms'])

    # Create games table
    op.create_table(
        'games',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(32), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('game_number', sa.Integer, nullable=False),
        sa.Column('game_type', sa.String(50)),
        sa.Column('started_at', sa.DateTime),
        sa.Column('ended_at', sa.DateTime),
        sa.Column('winner', sa.String(50)),
        sa.Column('final_score', sa.JSON),
    )
    op.create_index('idx_games_session', 'games', ['session_id'])

    # Create fouls table
    op.create_table(
        'fouls',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(32), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shot_id', sa.Integer, sa.ForeignKey('shots.id', ondelete='CASCADE'), nullable=True),
        sa.Column('timestamp_ms', sa.Integer),
        sa.Column('foul_type', sa.String(50), nullable=False),
        sa.Column('player', sa.String(50)),
        sa.Column('description', sa.Text),
    )
    op.create_index('idx_fouls_session', 'fouls', ['session_id'])

    # Create key_frames table
    op.create_table(
        'key_frames',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(32), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shot_id', sa.Integer, sa.ForeignKey('shots.id', ondelete='CASCADE'), nullable=True),
        sa.Column('timestamp_ms', sa.Integer, nullable=False),
        sa.Column('frame_type', sa.String(50)),
        sa.Column('file_path', sa.String(255), nullable=False),
        sa.Column('ball_positions', sa.JSON),
    )
    op.create_index('idx_keyframes_session', 'key_frames', ['session_id'])

    # Create trajectories table
    op.create_table(
        'trajectories',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('shot_id', sa.Integer, sa.ForeignKey('shots.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ball_id', sa.Integer, nullable=False),
        sa.Column('path_points', sa.JSON, nullable=False),
        sa.Column('initial_velocity', sa.Float),
        sa.Column('final_velocity', sa.Float),
        sa.Column('spin_type', sa.String(50)),
    )
    op.create_index('idx_trajectories_shot', 'trajectories', ['shot_id'])

    # Create ball_collisions table
    op.create_table(
        'ball_collisions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('shot_id', sa.Integer, sa.ForeignKey('shots.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp_ms', sa.Integer, nullable=False),
        sa.Column('ball1_id', sa.Integer, nullable=False),
        sa.Column('ball2_id', sa.Integer),
        sa.Column('collision_type', sa.String(50), nullable=False),
        sa.Column('position', sa.JSON),
        sa.Column('ball1_velocity_before', sa.JSON),
        sa.Column('ball1_velocity_after', sa.JSON),
        sa.Column('ball2_velocity_before', sa.JSON),
        sa.Column('ball2_velocity_after', sa.JSON),
        sa.Column('energy_transfer', sa.Float),
    )
    op.create_index('idx_collisions_shot', 'ball_collisions', ['shot_id'])

    # Create physics_analysis table
    op.create_table(
        'physics_analysis',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('shot_id', sa.Integer, sa.ForeignKey('shots.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('cue_speed_mph', sa.Float),
        sa.Column('impact_angle', sa.Float),
        sa.Column('spin_rpm', sa.Float),
        sa.Column('spin_axis', sa.JSON),
        sa.Column('deflection_angle', sa.Float),
        sa.Column('throw_angle', sa.Float),
        sa.Column('squirt_angle', sa.Float),
        sa.Column('energy_efficiency', sa.Float),
        sa.Column('physics_valid', sa.Boolean, default=True),
        sa.Column('simulation_match_score', sa.Float),
        sa.Column('anomalies', sa.JSON),
    )
    op.create_index('idx_physics_shot', 'physics_analysis', ['shot_id'])

    # Create calibrations table
    op.create_table(
        'calibrations',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(32), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('corner_points', sa.JSON, nullable=False),
        sa.Column('pocket_positions', sa.JSON),
        sa.Column('table_width_inches', sa.Float),
        sa.Column('table_length_inches', sa.Float),
        sa.Column('pixels_per_inch', sa.Float),
        sa.Column('transform_matrix', sa.JSON),
    )
    op.create_index('idx_calibrations_session', 'calibrations', ['session_id'])


def downgrade() -> None:
    op.drop_table('calibrations')
    op.drop_table('physics_analysis')
    op.drop_table('ball_collisions')
    op.drop_table('trajectories')
    op.drop_table('key_frames')
    op.drop_table('fouls')
    op.drop_table('games')
    op.drop_table('events')
    op.drop_table('shots')
    op.drop_table('sessions')
    op.drop_table('profiles')
