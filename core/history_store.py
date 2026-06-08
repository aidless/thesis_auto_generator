"""
历史记录存储（P2-R17）

使用 sqlite3 持久化生成历史，替代 P1 的内存 _history_store。

表结构：
- id: TEXT PRIMARY KEY (uuid hex)
- topic: TEXT
- keywords: TEXT (JSON array)
- word_count: INTEGER
- chapter_count: INTEGER
- ref_count: INTEGER
- output_path: TEXT
- created_at: TEXT (ISO 8601)
"""

import os
import json
import sqlite3
import logging
import threading
from typing import List, Dict, Optional
from datetime import datetime
from contextlib import contextmanager

from core.models import HistoryRecord

logger = logging.getLogger(__name__)


# 数据库路径
DB_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "history.db",
)


class HistoryStore:
    """SQLite 历史记录存储

    线程安全，自动建表，支持 CRUD。

    Attributes:
        db_path: SQLite 数据库文件路径
    """

    def __init__(self, db_path: str = DB_PATH):
        """初始化存储，自动建表

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        logger.info(f"HistoryStore 已初始化: {db_path}")

    def save(self, record: HistoryRecord) -> str:
        """保存一条历史记录

        Args:
            record: HistoryRecord 对象

        Returns:
            str: 记录 ID
        """
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO history (id, topic, keywords, word_count,
                       chapter_count, ref_count, output_path, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.id,
                        record.topic,
                        json.dumps(record.keywords, ensure_ascii=False),
                        record.word_count,
                        record.chapter_count,
                        record.ref_count,
                        record.output_path,
                        record.created_at or datetime.now().isoformat(),
                    ),
                )
                conn.commit()
        logger.debug(f"历史记录已保存: {record.id[:8]}")
        return record.id

    def list_all(self, limit: int = 50, offset: int = 0) -> List[HistoryRecord]:
        """分页查询所有历史记录

        Args:
            limit: 最大返回数
            offset: 偏移量

        Returns:
            List[HistoryRecord]: 历史记录列表
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM history ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            records = []
            for row in cursor.fetchall():
                try:
                    keywords = json.loads(row[2]) if row[2] else []
                except json.JSONDecodeError:
                    keywords = []
                records.append(HistoryRecord(
                    id=row[0],
                    topic=row[1],
                    keywords=keywords,
                    word_count=row[3] or 0,
                    chapter_count=row[4] or 0,
                    ref_count=row[5] or 0,
                    output_path=row[6] or "",
                    created_at=row[7] or "",
                ))
            return records

    def get(self, record_id: str) -> Optional[HistoryRecord]:
        """按 ID 查询单条记录

        Args:
            record_id: 记录 ID

        Returns:
            Optional[HistoryRecord]: 记录或 None
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM history WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            try:
                keywords = json.loads(row[2]) if row[2] else []
            except json.JSONDecodeError:
                keywords = []
            return HistoryRecord(
                id=row[0],
                topic=row[1],
                keywords=keywords,
                word_count=row[3] or 0,
                chapter_count=row[4] or 0,
                ref_count=row[5] or 0,
                output_path=row[6] or "",
                created_at=row[7] or "",
            )

    def delete(self, record_id: str) -> bool:
        """删除指定记录

        Args:
            record_id: 记录 ID

        Returns:
            bool: 是否成功删除
        """
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM history WHERE id = ?",
                    (record_id,),
                )
                conn.commit()
                return cursor.rowcount > 0

    def clear_all(self) -> int:
        """清空所有历史记录

        Returns:
            int: 删除的记录数
        """
        with self._lock:
            with self._get_conn() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM history"
                ).fetchone()[0]
                conn.execute("DELETE FROM history")
                conn.commit()
                logger.info(f"已清空 {count} 条历史记录")
                return count

    def count(self) -> int:
        """获取记录总数"""
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]

    def as_dataframe_rows(self) -> List:
        """返回 Gradio DataFrame 兼容的行列表

        Returns:
            List: 用于 gr.DataFrame 的行数据
        """
        records = self.list_all()
        return [
            [
                r.id[:8] + "...",
                r.topic[:30],
                r.chapter_count,
                r.word_count,
                r.ref_count,
                r.output_path[:50] if r.output_path else "-",
                r.created_at[:19] if r.created_at else "-",
            ]
            for r in records
        ]

    # ── 内部方法 ────────────────────────────────────────

    def _init_db(self) -> None:
        """初始化表结构（幂等）"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    keywords TEXT DEFAULT '[]',
                    word_count INTEGER DEFAULT 0,
                    chapter_count INTEGER DEFAULT 0,
                    ref_count INTEGER DEFAULT 0,
                    output_path TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.commit()

    @contextmanager
    def _get_conn(self):
        """获取数据库连接（上下文管理器，自动关闭）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


# 全局单例
_store: Optional[HistoryStore] = None


def get_history_store() -> HistoryStore:
    """获取全局 HistoryStore 单例"""
    global _store
    if _store is None:
        _store = HistoryStore()
    return _store
