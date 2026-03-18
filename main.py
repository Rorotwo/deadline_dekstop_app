from __future__ import annotations

import argparse
import calendar
import json
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


DATA_FILE = Path(__file__).with_name("tasks_data.json")
IMAGE_DIR = Path(__file__).with_name("images")

RU_MONTHS = (
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)

FILTER_OPTIONS = {
    "all": "Все",
    "active": "Активные",
    "important": "Важные",
    "overdue": "Просрочено",
    "completed": "Выполнено",
}

SORT_OPTIONS = {
    "urgency": "Сначала срочные",
    "due": "По дедлайну",
    "important": "По важности",
    "created": "Сначала новые",
    "title": "По названию",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def format_date_short(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def truncate_text(value: str, width: int = 120) -> str:
    clean = " ".join(value.split())
    if not clean:
        return "Без описания"
    return textwrap.shorten(clean, width=width, placeholder="...")


def current_week_range(reference: date | None = None) -> tuple[date, date]:
    today = reference or date.today()
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


@dataclass(slots=True)
class Task:
    task_id: str
    title: str
    description: str
    start_date: str
    due_date: str
    important: bool = False
    completed: bool = False
    created_at: str = field(default_factory=now_iso)
    completed_at: str | None = None

    @property
    def start(self) -> date:
        return parse_date(self.start_date)

    @property
    def due(self) -> date:
        return parse_date(self.due_date)

    @property
    def days_left(self) -> int:
        return (self.due - date.today()).days

    @property
    def progress_ratio(self) -> float:
        if self.completed:
            return 1.0
        if self.start >= self.due:
            return 1.0 if date.today() >= self.due else 0.0
        elapsed = (date.today() - self.start).days
        total = (self.due - self.start).days
        return min(max(elapsed / total, 0.0), 1.0)

    @property
    def is_overdue(self) -> bool:
        return not self.completed and self.days_left < 0

    @property
    def urgency_label(self) -> str:
        if self.completed:
            return "Выполнено"
        if self.days_left < 0:
            return f"Просрочено на {abs(self.days_left)} д."
        if self.days_left == 0:
            return "Дедлайн сегодня"
        if self.days_left == 1:
            return "1 день в запасе"
        if self.days_left <= 3:
            return f"{self.days_left} дня в запасе"
        if self.days_left <= 7:
            return "Срок скоро"
        return "Есть запас"

    @property
    def urgency_color(self) -> str:
        if self.completed:
            return "#8CD3A8"
        if self.days_left < 0:
            return "#FF8A80"
        if self.days_left <= 1:
            return "#FFC27A"
        if self.days_left <= 3:
            return "#FFD98E"
        return "#BFD7EA"

    @property
    def smart_score(self) -> int:
        score = 100
        if self.completed:
            score += 1000
        score += max(self.days_left, -30) * 10
        if self.important:
            score -= 35
        if self.is_overdue:
            score -= 120
        return score

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        start: date,
        due: date,
        important: bool,
    ) -> "Task":
        return cls(
            task_id=f"task-{int(datetime.now().timestamp() * 1000)}",
            title=title.strip(),
            description=description.strip(),
            start_date=start.isoformat(),
            due_date=due.isoformat(),
            important=important,
        )

    @classmethod
    def from_dict(cls, payload: dict) -> "Task":
        return cls(
            task_id=payload["task_id"],
            title=payload["title"],
            description=payload.get("description", ""),
            start_date=payload["start_date"],
            due_date=payload["due_date"],
            important=payload.get("important", False),
            completed=payload.get("completed", False),
            created_at=payload.get("created_at", now_iso()),
            completed_at=payload.get("completed_at"),
        )

    def to_dict(self) -> dict:
        return asdict(self)
