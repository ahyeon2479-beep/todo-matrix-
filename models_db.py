from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.String(128), primary_key=True)  # Google ID
    email = db.Column(db.String(256), unique=True, nullable=False)
    name = db.Column(db.String(256), nullable=False)
    picture = db.Column(db.String(512), default="")

    todos = db.relationship("Todo", backref="user", lazy=True, cascade="all,delete")
    memos = db.relationship("Memo", backref="user", lazy=True, cascade="all,delete")
    habits = db.relationship("Habit", backref="user", lazy=True, cascade="all,delete")
    bucket_items = db.relationship("BucketItem", backref="user", lazy=True, cascade="all,delete")
    diaries = db.relationship("Diary", backref="user", lazy=True, cascade="all,delete")
    free_memos = db.relationship("FreeMemo", backref="user", lazy=True, cascade="all,delete")


class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    note = db.Column(db.Text, default="")
    completed = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(100), default="개인")
    urgent = db.Column(db.Boolean, default=False)
    important = db.Column(db.Boolean, default=True)
    repeat = db.Column(db.Boolean, default=False)
    repeat_weekdays = db.Column(db.Text, default="[]")  # JSON: [0,1,2...]
    repeat_days = db.Column(db.Text, default="[]")       # JSON: [1,15,...]
    due_date = db.Column(db.String(10), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "title": self.title,
            "note": self.note,
            "completed": self.completed,
            "category": self.category,
            "urgent": self.urgent,
            "important": self.important,
            "repeat": self.repeat,
            "repeat_weekdays": json.loads(self.repeat_weekdays or "[]"),
            "repeat_days": json.loads(self.repeat_days or "[]"),
            "due_date": self.due_date or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }


class Memo(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    date_str = db.Column(db.String(10), nullable=False)
    text = db.Column(db.Text, default="")

    __table_args__ = (db.UniqueConstraint("user_id", "date_str"),)


class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    order = db.Column(db.Integer, default=0)

    checks = db.relationship("HabitCheck", backref="habit", lazy=True, cascade="all,delete")


class HabitCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    habit_id = db.Column(db.Integer, db.ForeignKey("habit.id"), nullable=False)
    date_str = db.Column(db.String(10), nullable=False)

    __table_args__ = (db.UniqueConstraint("habit_id", "date_str"),)


class BucketItem(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    year = db.Column(db.Integer, nullable=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id, "text": self.text, "completed": self.completed,
            "year": self.year, "order": self.order,
        }


class Diary(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    date_str = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(300), default="")
    content = db.Column(db.Text, default="")
    mood = db.Column(db.String(10), default="")
    event = db.Column(db.Text, default="")
    deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (db.UniqueConstraint("user_id", "date_str"),)

    def to_dict(self):
        return {
            "id": self.id, "date_str": self.date_str,
            "title": self.title, "content": self.content, "mood": self.mood,
            "event": self.event or "", "deleted": self.deleted or False,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }


class StickyNote(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    done = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {"id": self.id, "text": self.text, "done": self.done, "order": self.order}


class FreeMemo(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(300), default="")
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }
