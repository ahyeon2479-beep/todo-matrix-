from __future__ import annotations

from datetime import datetime, date as _Date
from models import TodoItem, StorageManager


class TodoController:
    def __init__(self, storage: StorageManager | None = None):
        self._storage = storage or StorageManager()
        self._items: list[TodoItem] = self._storage.load()

    # ── CRUD ──────────────────────────────────────────────

    def add_item(
        self,
        title: str,
        category: str = "개인",
        tags: list | None = None,
        urgent: bool = False,
        important: bool = True,
        note: str = "",
        due_date: str = "",
        repeat: bool = False,
        repeat_weekdays: list | None = None,
        repeat_days: list | None = None,
    ) -> TodoItem:
        item = TodoItem(
            title=title.strip(),
            category=category,
            tags=tags or [],
            urgent=urgent,
            important=important,
            note=note.strip(),
            due_date=due_date,
            repeat=repeat,
            repeat_weekdays=repeat_weekdays or [],
            repeat_days=repeat_days or [],
        )
        self._items.append(item)
        self._save()
        return item

    def update_item(self, item_id: str, **kwargs) -> TodoItem | None:
        item = self._find(item_id)
        if item is None:
            return None
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        item.updated_at = datetime.now().isoformat(timespec="seconds")
        self._save()
        return item

    def delete_item(self, item_id: str) -> bool:
        item = self._find(item_id)
        if item is None:
            return False
        self._items.remove(item)
        self._save()
        return True

    def toggle_complete(self, item_id: str) -> TodoItem | None:
        item = self._find(item_id)
        if item is None:
            return None
        item.completed = not item.completed
        # 반복 할 일은 완료 처리해도 바로 미완료로 리셋
        if item.repeat and item.completed:
            item.completed = False
        item.updated_at = datetime.now().isoformat(timespec="seconds")
        self._save()
        return item

    # ── 조회 ──────────────────────────────────────────────

    def get_all(self) -> list[TodoItem]:
        return list(self._items)

    def filter_by_quadrant(self, urgent: bool, important: bool, show_completed: bool = True, date_filter: str | None = None) -> list[TodoItem]:
        items = [i for i in self._items if i.urgent == urgent and i.important == important]
        if date_filter is not None:
            items = [i for i in items
                     if i.due_date == date_filter
                     or (i.repeat and self._matches_repeat(i, date_filter))]
        if not show_completed:
            items = [i for i in items if not i.completed]
        return items

    @staticmethod
    def _matches_repeat(item: TodoItem, date_str: str) -> bool:
        """반복 할일이 해당 날짜에 표시되어야 하는지 확인."""
        try:
            d = _Date.fromisoformat(date_str)
        except ValueError:
            return True  # 날짜 파싱 실패 시 표시
        weekdays = getattr(item, "repeat_weekdays", [])
        days = getattr(item, "repeat_days", [])
        # 둘 다 비어있으면 매일 반복
        if not weekdays and not days:
            return True
        # 요일 체크 (weekday: 0=월 ~ 6=일)
        if weekdays and d.weekday() in weekdays:
            return True
        # 일자 체크
        if days and d.day in days:
            return True
        return False

    def get_repeat_items(self) -> list[TodoItem]:
        return [i for i in self._items if i.repeat]

    def get_categories(self, defaults: list[str] | None = None) -> list[str]:
        base = list(defaults) if defaults else []
        for item in self._items:
            if item.category not in base:
                base.append(item.category)
        return base

    def stats(self) -> dict:
        total = len(self._items)
        done = sum(1 for i in self._items if i.completed)
        return {"total": total, "completed": done, "pending": total - done}

    # ── 내부 ──────────────────────────────────────────────

    def _find(self, item_id: str) -> TodoItem | None:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def _save(self) -> None:
        self._storage.save(self._items)
