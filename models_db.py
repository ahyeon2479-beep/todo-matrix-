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


class MemoFolder(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "order": self.order}


class FreeMemo(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey("memo_folder.id"), nullable=True)
    title = db.Column(db.String(300), default="")
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id, "folder_id": self.folder_id, "title": self.title, "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }


class FinanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    date_str = db.Column(db.String(10), nullable=False)
    record_type = db.Column(db.String(10), nullable=False)  # income / expense
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id, "date_str": self.date_str, "record_type": self.record_type,
            "category": self.category, "amount": self.amount,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


class FixedExpense(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(100), default="기타")
    day_of_month = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    pay_method = db.Column(db.String(200), default="")
    note = db.Column(db.String(500), default="")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "amount": self.amount,
            "category": self.category, "day_of_month": self.day_of_month,
            "is_active": self.is_active, "pay_method": self.pay_method or "",
            "note": self.note or "",
        }


class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    bank = db.Column(db.String(200), default="")
    remaining_amount = db.Column(db.Integer, default=0)
    interest_rate = db.Column(db.Float, default=0)
    due_date = db.Column(db.String(10), default="")
    repay_type = db.Column(db.String(50), default="")
    prepay_fee = db.Column(db.String(300), default="")
    monthly_interest = db.Column(db.Integer, default=0)
    account = db.Column(db.String(200), default="")
    pay_day = db.Column(db.Integer, default=0)  # 매월 상환일
    # 기존 호환
    total_amount = db.Column(db.Integer, default=0)
    monthly_payment = db.Column(db.Integer, default=0)
    start_date = db.Column(db.String(10), default="")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "bank": self.bank or "",
            "remaining_amount": self.remaining_amount, "interest_rate": self.interest_rate,
            "due_date": self.due_date or "", "repay_type": self.repay_type or "",
            "prepay_fee": self.prepay_fee or "", "monthly_interest": self.monthly_interest,
            "account": self.account or "", "pay_day": self.pay_day or 0,
            "total_amount": self.total_amount, "monthly_payment": self.monthly_payment,
            "start_date": self.start_date,
        }

