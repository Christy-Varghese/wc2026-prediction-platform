"""Database schema (SQLAlchemy ORM) — the production data model.

Tables
------
teams                national teams (code, name, confederation, flag, elo, manager)
players              squad players (team, position, club, goals/assists/xG/xA, fitness)
matches              fixtures + results (group/knockout, venue, kickoff, weather)
predictions          cached ensemble output per match (probs, scores, explanation)
team_news            injuries / suspensions / availability snapshots
model_runs           retraining history + accuracy metrics (freshness)
users                admin accounts (hashed password)
kis_simulations      KIS vector-decomposition run log (KIS_SPEC.md §6.1, Phase 3)
team_pressure_inputs KIS curated Pressure Score inputs (KIS_SPEC.md §6.1, Phase 3;
                     not yet populated — ml/player_condition.KNOCKOUT_PEDIGREE
                     remains the source of truth)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, JSON,
                        String, Text, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(3), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    confederation: Mapped[str] = mapped_column(String(16), default="")
    flag_url: Mapped[str] = mapped_column(String(256), default="")
    elo: Mapped[float] = mapped_column(Float, default=1500.0)
    fifa_rank: Mapped[int] = mapped_column(Integer, default=0)
    manager: Mapped[str] = mapped_column(String(64), default="")
    manager_winrate: Mapped[float] = mapped_column(Float, default=0.0)
    group: Mapped[str] = mapped_column(String(2), default="")
    players: Mapped[list["Player"]] = relationship(back_populates="team")


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    position: Mapped[str] = mapped_column(String(4), default="")   # GK/DF/MF/FW
    club: Mapped[str] = mapped_column(String(64), default="")
    photo_url: Mapped[str] = mapped_column(String(256), default="")
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    xg: Mapped[float] = mapped_column(Float, default=0.0)
    xa: Mapped[float] = mapped_column(Float, default=0.0)
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    impact: Mapped[float] = mapped_column(Float, default=0.0)       # 0-100
    fitness: Mapped[str] = mapped_column(String(16), default="fit")  # fit/doubt/out
    team: Mapped[Team] = relationship(back_populates="players")


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    stage: Mapped[str] = mapped_column(String(16), default="group")  # group/R32...
    group: Mapped[str] = mapped_column(String(2), default="")
    home_team: Mapped[str] = mapped_column(String(64), index=True)
    away_team: Mapped[str] = mapped_column(String(64), index=True)
    venue: Mapped[str] = mapped_column(String(80), default="")
    city: Mapped[str] = mapped_column(String(64), default="")
    kickoff: Mapped[datetime] = mapped_column(DateTime, index=True)
    neutral: Mapped[bool] = mapped_column(Boolean, default=True)
    weather: Mapped[str] = mapped_column(String(32), default="")
    home_rest_days: Mapped[int] = mapped_column(Integer, default=4)
    away_rest_days: Mapped[int] = mapped_column(Integer, default=4)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prediction: Mapped["Prediction"] = relationship(back_populates="match",
                                                    uselist=False)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), unique=True)
    p_home: Mapped[float] = mapped_column(Float)
    p_draw: Mapped[float] = mapped_column(Float)
    p_away: Mapped[float] = mapped_column(Float)
    xg_home: Mapped[float] = mapped_column(Float, default=0.0)
    xg_away: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    upset_prob: Mapped[float] = mapped_column(Float, default=0.0)
    top_scores: Mapped[list] = mapped_column(JSON, default=list)
    members: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime,
                                                 server_default=func.now())
    match: Mapped[Match] = relationship(back_populates="prediction")


class TeamNews(Base):
    __tablename__ = "team_news"
    id: Mapped[int] = mapped_column(primary_key=True)
    team: Mapped[str] = mapped_column(String(64), index=True)
    player: Mapped[str] = mapped_column(String(80), default="")
    kind: Mapped[str] = mapped_column(String(16), default="injury")  # injury/suspension
    status: Mapped[str] = mapped_column(String(16), default="out")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime,
                                                 server_default=func.now())


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started: Mapped[datetime] = mapped_column(DateTime)
    finished: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    n_matches: Mapped[int] = mapped_column(Integer, default=0)
    latest_match: Mapped[str] = mapped_column(String(16), default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    log: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)


class KISSimulation(Base):
    """Audit log + cache of a KIS vector-decomposition run (KIS_SPEC.md §6.1).

    `match_id` is nullable — D4 (§10) resolved by precedent: `services.predict()`
    has no "must be a real scheduled fixture" gate, so KIS follows the same
    pattern and allows a hypothetical matchup with no corresponding `Match` row.
    Purely additive: nothing in the existing schema references this table, so
    dropping it has zero impact elsewhere (§13 Rollback Plan).
    """
    __tablename__ = "kis_simulations"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"),
                                                  nullable=True, index=True)
    home_team: Mapped[str] = mapped_column(String(64))
    away_team: Mapped[str] = mapped_column(String(64))
    sim_runs_executed: Mapped[int] = mapped_column(Integer, default=50000)
    weather_condition: Mapped[str] = mapped_column(String(32), default="Clear")
    referee_strictness: Mapped[float] = mapped_column(Float, default=0.50)

    p_home_win: Mapped[float] = mapped_column(Float)
    p_away_win: Mapped[float] = mapped_column(Float)
    p_draw_90: Mapped[float] = mapped_column(Float)
    p_extra_time: Mapped[float] = mapped_column(Float)
    p_shootout: Mapped[float] = mapped_column(Float)

    home_skill_score: Mapped[float] = mapped_column(Float)
    away_skill_score: Mapped[float] = mapped_column(Float)
    home_luck_mu_bias: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_luck_mu_bias: Mapped[float | None] = mapped_column(Float, nullable=True)
    luck_sigma_chaos: Mapped[float] = mapped_column(Float)

    chaos_events: Mapped[dict] = mapped_column(JSON, default=dict)  # {run_count, run_rate, ...}
    pressure_score_home: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_score_away: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("match_id", "weather_condition", "referee_strictness",
                         name="uq_kis_sim_fixture_inputs"),
    )


class TeamPressureInput(Base):
    """Curated per-team Pressure Score inputs (KIS_SPEC.md §4[6]/§6.1).

    Phase 1/2 shipped these as the `KNOCKOUT_PEDIGREE` Python dict in
    `ml/player_condition.py` (same precedent as MANAGER_WINRATE/GK_QUALITY) —
    this table is the eventual DB-backed home for that data once/if it needs
    to be queryable/editable without a code change. Not yet populated or read
    by the ML pipeline; `knockout_pedigree()` remains the source of truth
    until a Phase 3+ migration script backfills this table.
    """
    __tablename__ = "team_pressure_inputs"
    team_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    knockout_experience: Mapped[int] = mapped_column(Integer, default=0)
    shootout_win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    captain_caps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captain_tournament_apps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sub_aggression: Mapped[str | None] = mapped_column(String(8), nullable=True)  # early/average/late
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
