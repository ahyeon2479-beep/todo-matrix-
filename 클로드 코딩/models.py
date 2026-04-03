from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


_DEFAULT_STORAGE = Path(__file__).parent / "todos.json"


@dataclass
class TodoItem:
    title: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    note: str = ""
    completed: bool = False
    category: str = "개인"
    tags: list = field(default_factory=list)
    urgent: bool = False    # 긴급함 여부
    important: bool = True  # 중요함 여부
    repeat: bool = False    # 반복 할 일 여부
    repeat_weekdays: list = field(default_factory=list)  # 반복 요일 [0=월,1=화,...6=일]
    repeat_days: list = field(default_factory=list)      # 반복 일자 [1,15,...] (매월)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    due_date: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> TodoItem:
        known = set(cls.__dataclass_fields__)
        filtered = {k: v for k, v in d.items() if k in known}
        # 구버전 데이터 마이그레이션 (priority → urgent/important)
        if "urgent" not in filtered and "important" not in filtered:
            priority = d.get("priority", "medium")
            filtered["urgent"] = priority == "high"
            filtered["important"] = priority != "low"
        return cls(**filtered)


class MemoManager:
    """날짜별 메모를 memos.json에 저장/로드."""
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(__file__).parent / "memos.json"

    def load(self, date_str: str) -> str:
        if not self.path.exists():
            return ""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data.get(date_str, "")
        except Exception:
            return ""

    def save(self, date_str: str, text: str) -> None:
        data: dict = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        data[date_str] = text
        tmp = self.path.parent / (self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)


class HabitManager:
    """습관 목록 + 주차별 체크 기록을 habits.json에 저장/로드."""

    def __init__(self, path=None):
        self.path = Path(path) if path else Path(__file__).parent / "habits.json"

    def _read(self) -> dict:
        if not self.path.exists():
            return {"habits": [], "checks": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"habits": [], "checks": {}}

    def _write(self, data: dict) -> None:
        tmp = self.path.parent / (self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get_habits(self) -> list[str]:
        return self._read().get("habits", [])

    def add_habit(self, name: str) -> None:
        data = self._read()
        if name not in data["habits"]:
            data["habits"].append(name)
            self._write(data)

    def remove_habit(self, name: str) -> None:
        data = self._read()
        if name in data["habits"]:
            data["habits"].remove(name)
            # 관련 체크 기록도 삭제
            data["checks"] = {k: v for k, v in data["checks"].items()
                              if not k.startswith(name + "|")}
            self._write(data)

    def is_checked(self, habit: str, date_str: str) -> bool:
        data = self._read()
        return data["checks"].get(f"{habit}|{date_str}", False)

    def toggle_check(self, habit: str, date_str: str) -> bool:
        """토글 후 새 상태를 반환."""
        data = self._read()
        key = f"{habit}|{date_str}"
        current = data["checks"].get(key, False)
        data["checks"][key] = not current
        self._write(data)
        return not current

    def get_week_checks(self, habit: str, week_dates: list[str]) -> dict[str, bool]:
        data = self._read()
        return {d: data["checks"].get(f"{habit}|{d}", False) for d in week_dates}


class StorageManager:
    def __init__(self, path=None):
        self.path = Path(path) if path else _DEFAULT_STORAGE
        self._tmp = self.path.parent / (self.path.name + ".tmp")

    def load(self) -> list[TodoItem]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [TodoItem.from_dict(item) for item in data.get("items", [])]
        except Exception:
            return []

    def save(self, items: list[TodoItem]) -> None:
        payload = {
            "version": "1.1",
            "last_saved": _now(),
            "items": [item.to_dict() for item in items],
        }
        self._tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._tmp.replace(self.path)
