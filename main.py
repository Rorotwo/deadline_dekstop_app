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

class TaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Task]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        tasks: list[Task] = []
        for item in raw:
            try:
                tasks.append(Task.from_dict(item))
            except Exception:
                continue
        return tasks

    def save(self, tasks: list[Task]) -> None:
        payload = [task.to_dict() for task in tasks]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def filter_tasks(tasks: list[Task], filter_key: str) -> list[Task]:
    if filter_key == "active":
        return [task for task in tasks if not task.completed]
    if filter_key == "important":
        return [task for task in tasks if task.important and not task.completed]
    if filter_key == "overdue":
        return [task for task in tasks if task.is_overdue]
    if filter_key == "completed":
        return [task for task in tasks if task.completed]
    return list(tasks)


def sort_tasks(tasks: list[Task], sort_key: str) -> list[Task]:
    if sort_key == "due":
        return sorted(tasks, key=lambda task: (task.completed, task.due, not task.important, task.title.casefold()))
    if sort_key == "important":
        return sorted(tasks, key=lambda task: (task.completed, not task.important, task.due, task.title.casefold()))
    if sort_key == "created":
        return sorted(tasks, key=lambda task: task.created_at, reverse=True)
    if sort_key == "title":
        return sorted(tasks, key=lambda task: (task.completed, task.title.casefold(), task.due))
    return sorted(tasks, key=lambda task: (task.smart_score, task.due, task.title.casefold()))


def focus_task(tasks: list[Task]) -> Task | None:
    active = [task for task in tasks if not task.completed]
    if not active:
        return None
    return sort_tasks(active, "urgency")[0]


class DatePickerDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, initial: date, on_pick) -> None:
        super().__init__(master)
        self.title("Выбор даты")
        self.resizable(False, False)
        self.configure(bg="#C5D6DC")
        self.transient(master)
        self.grab_set()

        self.on_pick = on_pick
        self.current_year = initial.year
        self.current_month = initial.month

        self.header = tk.Frame(self, bg="#C5D6DC")
        self.header.pack(fill="x", padx=16, pady=(16, 8))

        tk.Button(
            self.header,
            text="<",
            command=self.prev_month,
            bg="#5E7682",
            fg="#FFFFFF",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            width=3,
            cursor="hand2",
        ).pack(side="left")

        self.month_label = tk.Label(
            self.header,
            bg="#C5D6DC",
            fg="#2D3B44",
            font=("Georgia", 14, "bold"),
        )
        self.month_label.pack(side="left", expand=True)

        tk.Button(
            self.header,
            text=">",
            command=self.next_month,
            bg="#5E7682",
            fg="#FFFFFF",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            width=3,
            cursor="hand2",
        ).pack(side="right")

        self.calendar_frame = tk.Frame(self, bg="#C5D6DC")
        self.calendar_frame.pack(padx=16, pady=(0, 16))

        self.render_calendar()
        self.center_relative(master)

    def center_relative(self, master: tk.Misc) -> None:
        self.update_idletasks()
        x = master.winfo_rootx() + max((master.winfo_width() - self.winfo_width()) // 2, 20)
        y = master.winfo_rooty() + max((master.winfo_height() - self.winfo_height()) // 2, 20)
        self.geometry(f"+{x}+{y}")

    def prev_month(self) -> None:
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.render_calendar()

    def next_month(self) -> None:
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.render_calendar()

    def render_calendar(self) -> None:
        for child in self.calendar_frame.winfo_children():
            child.destroy()

        self.month_label.config(text=f"{RU_MONTHS[self.current_month - 1]} {self.current_year}")

        weekday_names = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
        for index, weekday_name in enumerate(weekday_names):
            tk.Label(
                self.calendar_frame,
                text=weekday_name,
                bg="#C5D6DC",
                fg="#4B5C66",
                font=("Segoe UI", 10, "bold"),
                width=4,
            ).grid(row=0, column=index, pady=(0, 6))

        month_matrix = calendar.Calendar(firstweekday=0).monthdayscalendar(self.current_year, self.current_month)
        for row_index, week in enumerate(month_matrix, start=1):
            for column_index, day in enumerate(week):
                if day == 0:
                    tk.Label(self.calendar_frame, text=" ", bg="#C5D6DC", width=4).grid(
                        row=row_index,
                        column=column_index,
                        padx=2,
                        pady=2,
                    )
                    continue

                selected = date(self.current_year, self.current_month, day)
                tk.Button(
                    self.calendar_frame,
                    text=str(day),
                    width=4,
                    bg="#F6F3EF" if selected != date.today() else "#F7C3B8",
                    fg="#2F3A43",
                    activebackground="#F9D1C8",
                    relief="flat",
                    cursor="hand2",
                    command=lambda chosen=selected: self.pick_date(chosen),
                ).grid(row=row_index, column=column_index, padx=2, pady=2)

    def pick_date(self, chosen: date) -> None:
        self.on_pick(chosen)
        self.destroy()


class TaskDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, on_submit, task: Task | None = None) -> None:
        super().__init__(master)
        self.task = task
        self.on_submit = on_submit
        self.title("Новая задача" if task is None else "Редактирование задачи")
        self.configure(bg="#8AA4AF")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        default_start = task.start if task else date.today()
        default_due = task.due if task else date.today() + timedelta(days=3)

        self.title_var = tk.StringVar(value=task.title if task else "")
        self.start_var = tk.StringVar(value=default_start.isoformat())
        self.due_var = tk.StringVar(value=default_due.isoformat())
        self.important_var = tk.BooleanVar(value=task.important if task else False)

        self.card = tk.Frame(self, bg="#8AA4AF", padx=30, pady=24)
        self.card.pack(fill="both", expand=True)

        title_text = "Новая задача" if task is None else "Редактирование задачи"
        tk.Label(
            self.card,
            text=title_text,
            bg="#8AA4AF",
            fg="#F7F5F1",
            font=("Georgia", 24, "italic"),
        ).pack(pady=(0, 6))

        tk.Frame(self.card, bg="#4CB0FF", height=3, width=180).pack(pady=(0, 22))

        self.title_entry = tk.Entry(
            self.card,
            textvariable=self.title_var,
            font=("Segoe UI", 14),
            bg="#EFECEC",
            fg="#243038",
            relief="flat",
            width=38,
            insertbackground="#243038",
        )
        self.title_entry.pack(ipady=10, fill="x")

        tk.Label(
            self.card,
            text="Описание",
            bg="#8AA4AF",
            fg="#F7F5F1",
            font=("Segoe UI", 12, "italic"),
        ).pack(pady=(18, 8))

        self.description_text = tk.Text(
            self.card,
            height=5,
            font=("Segoe UI", 11),
            bg="#EFECEC",
            fg="#243038",
            relief="flat",
            wrap="word",
        )
        self.description_text.pack(fill="x")
        if task and task.description:
            self.description_text.insert("1.0", task.description)

        tk.Label(
            self.card,
            text="Период",
            bg="#8AA4AF",
            fg="#F7F5F1",
            font=("Segoe UI", 14, "italic"),
        ).pack(pady=(18, 10))

        date_row = tk.Frame(self.card, bg="#8AA4AF")
        date_row.pack()

        self.build_date_field(date_row, "От", self.start_var).pack(side="left", padx=(0, 12))
        self.build_date_field(date_row, "До", self.due_var).pack(side="left")

        check_row = tk.Frame(self.card, bg="#8AA4AF")
        check_row.pack(pady=18)

        self.importance_on_image, self.importance_off_image = self.resolve_importance_images()
        self.importance_button = tk.Button(
            check_row,
            text=" Важность задачи",
            image=self.importance_on_image if self.important_var.get() else self.importance_off_image,
            compound="left",
            command=self.toggle_importance,
            bg="#8AA4AF",
            fg="#F7F5F1",
            activebackground="#8AA4AF",
            activeforeground="#F7F5F1",
            font=("Segoe UI", 12, "italic"),
            cursor="hand2",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=0,
        )
        self.importance_button.pack()

        actions = tk.Frame(self.card, bg="#8AA4AF")
        actions.pack(pady=(8, 0))

        tk.Button(
            actions,
            text="Отмена",
            command=self.destroy,
            bg="#6E8791",
            fg="#F8F7F3",
            activebackground="#7B949D",
            relief="flat",
            padx=22,
            pady=8,
            font=("Segoe UI", 11),
            cursor="hand2",
        ).pack(side="left", padx=(0, 12))

        tk.Button(
            actions,
            text="Готово",
            command=self.submit,
            bg="#5E7682",
            fg="#F8F7F3",
            activebackground="#718995",
            relief="flat",
            padx=30,
            pady=8,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
        ).pack(side="left")

        self.bind("<Return>", lambda _event: self.submit())
        self.title_entry.focus_set()
        self.center_relative(master)