"""Database tables.

Survey content lives in one JSON document per survey (the bundle); responses are
stored in relational tables so that exports are plain queries. No table stores a
network address or a browser description.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JSONMixin:
    @staticmethod
    def _load(value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _dump(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="researcher")
    active = db.Column(db.Boolean, nullable=False, default=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)
    ui_language = db.Column(db.String(8), nullable=True)
    session_version = db.Column(db.Integer, nullable=False, default=1)

    surveys = db.relationship("Survey", back_populates="owner")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
        self.session_version = (self.session_version or 0) + 1

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def verified(self) -> bool:
        return self.verified_at is not None


class RateEvent(db.Model):
    __tablename__ = "rate_events"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(200), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


class Survey(JSONMixin, db.Model):
    __tablename__ = "surveys"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    slug = db.Column(db.String(32), nullable=False, unique=True, index=True)
    status = db.Column(db.String(12), nullable=False, default="draft")
    definition_json = db.Column(db.Text, nullable=False, default="{}")
    revision = db.Column(db.Integer, nullable=False, default=1)
    allocation_seed = db.Column(db.String(64), nullable=False)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    published_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    owner = db.relationship("User", back_populates="surveys")
    responses = db.relationship("Response", back_populates="survey", cascade="all, delete-orphan")

    @property
    def definition(self) -> dict[str, Any]:
        return self._load(self.definition_json, {"survey": {}, "modules": []})

    @definition.setter
    def definition(self, value: dict[str, Any]) -> None:
        self.definition_json = self._dump(value)

    @property
    def settings(self) -> dict[str, Any]:
        return self.definition.get("survey", {})

    @property
    def modules(self) -> list[dict[str, Any]]:
        return self.definition.get("modules", [])

    @property
    def languages(self) -> list[str]:
        return list(self.settings.get("languages") or ["pl", "en"])

    @property
    def default_language(self) -> str:
        return self.settings.get("default_language") or self.languages[0]


class Response(JSONMixin, db.Model):
    __tablename__ = "responses"
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    uuid = db.Column(db.String(40), nullable=False, unique=True, index=True)
    language = db.Column(db.String(8), nullable=False)
    status = db.Column(db.String(12), nullable=False, default="started")
    preview = db.Column(db.Boolean, nullable=False, default=False)
    consented = db.Column(db.Boolean, nullable=False, default=False)
    revision = db.Column(db.Integer, nullable=False, default=1)
    state_json = db.Column(db.Text, nullable=False, default="{}")
    assignments_json = db.Column(db.Text, nullable=False, default="{}")
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)
    retest_submitted_at = db.Column(db.DateTime, nullable=True)

    survey = db.relationship("Survey", back_populates="responses")

    @property
    def state(self) -> dict[str, Any]:
        return self._load(self.state_json, {})

    @state.setter
    def state(self, value: dict[str, Any]) -> None:
        self.state_json = self._dump(value)

    @property
    def assignments(self) -> dict[str, Any]:
        return self._load(self.assignments_json, {})

    @assignments.setter
    def assignments(self, value: dict[str, Any]) -> None:
        self.assignments_json = self._dump(value)


class Answer(db.Model):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("response_id", "module_key", "name", "occasion"),)
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    occasion = db.Column(db.Integer, nullable=False, default=1)
    value = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Arrangement(db.Model):
    __tablename__ = "arrangements"
    __table_args__ = (UniqueConstraint("response_id", "module_key", "occasion"),)
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = db.Column(db.String(64), nullable=False)
    occasion = db.Column(db.Integer, nullable=False, default=1)
    board_kind = db.Column(db.String(16), nullable=False)
    placements_json = db.Column(db.Text, nullable=False, default="{}")
    reading_json = db.Column(db.Text, nullable=False, default="[]")
    coherent = db.Column(db.Boolean, nullable=False, default=True)
    paradata_json = db.Column(db.Text, nullable=False, default="{}")
    completed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Judgment(db.Model):
    __tablename__ = "judgments"
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = db.Column(db.String(64), nullable=False)
    occasion = db.Column(db.Integer, nullable=False, default=1)
    element_a = db.Column(db.String(64), nullable=False)
    element_b = db.Column(db.String(64), nullable=False)
    state = db.Column(db.String(16), nullable=False)


class Confirmation(db.Model):
    __tablename__ = "confirmations"
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = db.Column(db.String(64), nullable=False)
    occasion = db.Column(db.Integer, nullable=False, default=1)
    element_a = db.Column(db.String(64), nullable=False)
    element_b = db.Column(db.String(64), nullable=False)
    answer = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class BlockResponse(db.Model):
    __tablename__ = "block_responses"
    __table_args__ = (UniqueConstraint("response_id", "module_key", "occasion", "position"),)
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = db.Column(db.String(64), nullable=False)
    occasion = db.Column(db.Integer, nullable=False, default=1)
    position = db.Column(db.Integer, nullable=False)
    technique = db.Column(db.String(8), nullable=False)
    variant = db.Column(db.String(64), nullable=False, default="")
    design_block = db.Column(db.Integer, nullable=True)
    repeat_of = db.Column(db.Integer, nullable=True)
    criterion = db.Column(db.Integer, nullable=True)
    attention = db.Column(db.Boolean, nullable=False, default=False)
    attention_passed = db.Column(db.Boolean, nullable=True)
    cards_json = db.Column(db.Text, nullable=False, default="[]")
    result_json = db.Column(db.Text, nullable=False, default="{}")
    gate_value = db.Column(db.String(64), nullable=True)
    events_json = db.Column(db.Text, nullable=False, default="[]")
    duration_ms = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class PairObservation(db.Model):
    __tablename__ = "pair_observations"
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = db.Column(db.String(64), nullable=False)
    occasion = db.Column(db.Integer, nullable=False, default=1)
    position = db.Column(db.Integer, nullable=False)
    item_a = db.Column(db.String(64), nullable=False)
    item_b = db.Column(db.String(64), nullable=False)
    relation = db.Column(db.String(16), nullable=False)


class ScreenTime(db.Model):
    __tablename__ = "screen_times"
    __table_args__ = (UniqueConstraint("response_id", "screen_key"),)
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True)
    screen_key = db.Column(db.String(120), nullable=False)
    module_key = db.Column(db.String(64), nullable=False)
    occasion = db.Column(db.Integer, nullable=False, default=1)
    first_shown_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)
    client_ms = db.Column(db.Integer, nullable=True)
    visits = db.Column(db.Integer, nullable=False, default=1)
    question_order_json = db.Column(db.Text, nullable=True)
    leaves = db.Column(db.Integer, nullable=True)
    away_ms = db.Column(db.Integer, nullable=True)
    links_json = db.Column(db.Text, nullable=True)
    revisions = db.Column(db.Integer, nullable=False, default=0)


class Allocation(db.Model):
    __tablename__ = "allocations"
    __table_args__ = (UniqueConstraint("survey_id", "randomizer_key", "stratum", "seq_no"),)
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    randomizer_key = db.Column(db.String(64), nullable=False)
    stratum = db.Column(db.String(200), nullable=False)
    seq_no = db.Column(db.Integer, nullable=False)
    arm = db.Column(db.String(32), nullable=False)
    response_id = db.Column(db.Integer, db.ForeignKey("responses.id", ondelete="SET NULL"), nullable=True, index=True)
    preview = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
