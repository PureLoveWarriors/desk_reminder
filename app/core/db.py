"""SQLite 数据层：任务的增删改查。"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from app.config import DB_PATH

# 首次使用的演示任务，只在空库时插入一次
SAMPLE_TITLES = (
    "点左侧圆圈，完成这条任务",
    "点时钟图标，设置倒计时提醒",
    "按住标题拖动，可以调整顺序",
)


@dataclass
class Task:
    id: int
    title: str
    done: bool
    duration: int          # 倒计时时长（秒），0 表示无
    remind_at: float       # 到点提醒的时间戳，0 表示无
    created_at: float
    sort_order: int
    highlighted: bool = False   # 是否高亮标记（正在进行）
    pinned: bool = False        # 是否置顶


class Database:
    def __init__(self, path=DB_PATH):
        # check_same_thread=False：允许在计时回调等场景跨线程使用
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                done        INTEGER NOT NULL DEFAULT 0,
                duration    INTEGER NOT NULL DEFAULT 0,
                remind_at   REAL NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                highlighted INTEGER NOT NULL DEFAULT 0,
                pinned      INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.commit()
        self._migrate_add_columns()

    def _migrate_add_columns(self):
        """给老数据库补充新字段，兼容升级前建的库。"""
        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(tasks)")}
        if "highlighted" not in cols:
            self.conn.execute(
                "ALTER TABLE tasks ADD COLUMN highlighted INTEGER NOT NULL DEFAULT 0"
            )
            self.conn.commit()
        if "pinned" not in cols:
            self.conn.execute(
                "ALTER TABLE tasks ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"
            )
            self.conn.commit()

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            done=bool(row["done"]),
            duration=row["duration"],
            remind_at=row["remind_at"],
            created_at=row["created_at"],
            sort_order=row["sort_order"],
            highlighted=bool(row["highlighted"]),
            pinned=bool(row["pinned"]),
        )

    def seed_sample_tasks(self) -> list[Task]:
        """空库时插入三条样例，已有任务则不动。"""
        row = self.conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()
        if row["n"]:
            return []
        created = []
        n = len(SAMPLE_TITLES)
        for i, title in enumerate(SAMPLE_TITLES):
            task = self.add_task(title)
            # 待办列表按 sort_order DESC 显示，第一条样例要在最上面
            order = n - i
            self.set_sort_order(task.id, order)
            task.sort_order = order
            created.append(task)
        return created

    def list_tasks(self, done: bool | None = None) -> list[Task]:
        if done is None:
            rows = self.conn.execute(
                "SELECT * FROM tasks ORDER BY pinned DESC, sort_order ASC, id ASC"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE done = ? "
                "ORDER BY pinned DESC, sort_order DESC, id DESC",
                (1 if done else 0,),
            ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def add_task(self, title: str) -> Task:
        now = time.time()
        cur = self.conn.execute(
            "INSERT INTO tasks (title, created_at, sort_order) VALUES (?, ?, ?)",
            (title, now, int(now * 1000)),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return self._row_to_task(row)

    def set_done(self, task_id: int, done: bool):
        self.conn.execute(
            "UPDATE tasks SET done = ? WHERE id = ?", (1 if done else 0, task_id)
        )
        self.conn.commit()

    def set_title(self, task_id: int, title: str):
        self.conn.execute(
            "UPDATE tasks SET title = ? WHERE id = ?", (title, task_id)
        )
        self.conn.commit()

    def set_timer(self, task_id: int, duration: int, remind_at: float):
        self.conn.execute(
            "UPDATE tasks SET duration = ?, remind_at = ? WHERE id = ?",
            (duration, remind_at, task_id),
        )
        self.conn.commit()

    def set_highlighted(self, task_id: int, highlighted: bool):
        self.conn.execute(
            "UPDATE tasks SET highlighted = ? WHERE id = ?",
            (1 if highlighted else 0, task_id),
        )
        self.conn.commit()

    def set_pinned(self, task_id: int, pinned: bool):
        if pinned:
            # 置顶时把 sort_order 刷新到最新，确保排在所有置顶项的最上面
            now_order = int(time.time() * 1000)
            self.conn.execute(
                "UPDATE tasks SET pinned = 1, sort_order = ? WHERE id = ?",
                (now_order, task_id),
            )
        else:
            self.conn.execute(
                "UPDATE tasks SET pinned = 0 WHERE id = ?", (task_id,)
            )
        self.conn.commit()

    def set_sort_order(self, task_id: int, order: int):
        self.conn.execute(
            "UPDATE tasks SET sort_order = ? WHERE id = ?", (order, task_id)
        )
        self.conn.commit()

    def delete_task(self, task_id: int):
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def clear_completed(self):
        self.conn.execute("DELETE FROM tasks WHERE done = 1")
        self.conn.commit()
