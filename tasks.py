"""
异步任务管理模块（P1-R12）

支持双模式：
- 轻量模式（默认）：multiprocessing + queue.Queue，零额外依赖
- Celery 模式（可选）：celery + redis，适合多用户生产环境

命名规范：类名 PascalCase，函数 snake_case
"""

import uuid
import time
import threading
import multiprocessing
import queue
import logging
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)


class TaskMode(Enum):
    """异步任务运行模式"""
    LIGHTWEIGHT = "lightweight"  # multiprocessing + queue
    CELERY = "celery"            # Celery + Redis（预留）


class TaskStatus(Enum):
    """任务生命周期状态"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    """异步任务查询结果"""
    task_id: str
    status: TaskStatus
    progress: float = 0.0       # 0.0 ~ 1.0
    message: str = ""           # 当前阶段描述
    output_path: Optional[str] = None  # 完成后输出文件路径
    error: Optional[str] = None


class AsyncTaskManager:
    """异步任务管理器

    统一管理轻量模式和 Celery 模式的任务生命周期。

    Attributes:
        mode: 运行模式
        _tasks: 任务状态字典 {task_id: TaskResult}
        _queue: 轻量模式任务队列
        _lock: 线程锁，保护 _tasks 并发访问
    """

    def __init__(self, mode: TaskMode = TaskMode.LIGHTWEIGHT):
        """初始化异步任务管理器

        Args:
            mode: 运行模式，默认轻量
        """
        self.mode = mode
        self._tasks: Dict[str, TaskResult] = {}
        self._queue: multiprocessing.Queue = multiprocessing.Queue()
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

        if mode == TaskMode.LIGHTWEIGHT:
            self._start_worker()
        logger.info(f"AsyncTaskManager 已启动，模式: {mode.value}")

    # ── 任务提交流程 ────────────────────────────────────

    def submit(self, thesis_data: dict, config_data: dict) -> str:
        """提交异步生成任务

        Args:
            thesis_data: Thesis 对象序列化后的字典
            config_data: GenerationConfig 序列化后的字典

        Returns:
            str: 任务 ID
        """
        task_id = self._generate_task_id()

        with self._lock:
            self._tasks[task_id] = TaskResult(
                task_id=task_id,
                status=TaskStatus.QUEUED,
                progress=0.0,
                message="任务已加入队列",
            )

        self._queue.put({
            "task_id": task_id,
            "thesis_data": thesis_data,
            "config_data": config_data,
        })

        logger.info(f"任务已提交: {task_id}")
        return task_id

    def get_status(self, task_id: str) -> TaskResult:
        """查询任务状态

        Args:
            task_id: 任务 ID

        Returns:
            TaskResult: 包含进度和状态的查询结果
        """
        with self._lock:
            if task_id in self._tasks:
                return self._tasks[task_id]
        return TaskResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error=f"任务不存在: {task_id}",
        )

    def get_output(self, task_id: str) -> Optional[str]:
        """获取已完成任务的输出文件路径

        Args:
            task_id: 任务 ID

        Returns:
            Optional[str]: 输出文件路径，未完成则返回 None
        """
        with self._lock:
            if task_id in self._tasks:
                result = self._tasks[task_id]
                if result.status == TaskStatus.COMPLETED:
                    return result.output_path
        return None

    def cleanup(self, task_id: str) -> None:
        """清理已完成的任务记录

        Args:
            task_id: 任务 ID
        """
        with self._lock:
            self._tasks.pop(task_id, None)
        logger.debug(f"任务已清理: {task_id}")

    # ── 内部方法 ────────────────────────────────────────

    def _generate_task_id(self) -> str:
        """生成唯一任务 ID

        Returns:
            str: 格式为 {uuid8}_{timestamp}
        """
        short_uuid = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        return f"{short_uuid}_{timestamp}"

    def _start_worker(self) -> None:
        """启动轻量模式的后台 worker 线程

        Worker 从队列取任务，异步执行生成流程。
        """
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="async-task-worker",
        )
        self._worker_thread.start()
        logger.info("轻量 Worker 线程已启动")

    def _worker_loop(self) -> None:
        """Worker 主循环：取任务 → 执行 → 更新状态"""
        while self._running:
            try:
                task_data = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            task_id = task_data["task_id"]
            thesis_data = task_data["thesis_data"]
            config_data = task_data["config_data"]

            try:
                self._update_task(task_id, TaskStatus.RUNNING, 0.05, "正在初始化...")
                self._execute_task(task_id, thesis_data, config_data)
            except Exception as e:
                error_msg = f"任务执行失败: {str(e)}\n{traceback.format_exc()}"
                logger.error(f"任务 {task_id} 失败: {error_msg}")
                self._update_task(task_id, TaskStatus.FAILED, 0.0, "任务失败", error=error_msg)

    def _execute_task(self, task_id: str, thesis_data: dict, config_data: dict) -> None:
        """执行论文生成流程（复用同步逻辑）

        步骤：解析模板 → 生成大纲 → 逐章生成 → 文献检索 → 格式化 → 水印

        Args:
            task_id: 任务 ID
            thesis_data: Thesis 序列化数据
            config_data: GenerationConfig 序列化数据
        """
        import os
        import sys

        # 确保项目根在 sys.path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from core.models import Thesis, GenerationConfig, Chapter
        from core.outline_generator import OutlineGenerator
        from core.chapter_generator import ChapterGenerator
        from core.reference_fetcher import ReferenceFetcher
        from core.template_parser import TemplateParser
        from core.docx_formatter import DocxFormatter
        from llm.base import create_llm_client
        from utils.watermark import add_watermark_and_disclaimer
        from config import OUTPUT_DIR

        # 反序列化
        config = GenerationConfig(**config_data)
        thesis = Thesis(**thesis_data)

        # 创建 LLM 客户端
        llm = create_llm_client(config.llm_provider, config)
        self._update_task(task_id, TaskStatus.RUNNING, 0.05, "LLM 客户端已就绪")

        # 阶段 1: 生成大纲
        self._update_task(task_id, TaskStatus.RUNNING, 0.10, "正在生成大纲...")
        og = OutlineGenerator(llm)
        thesis.outline = og.generate(thesis.topic, thesis.keywords, config.discipline)
        self._update_task(task_id, TaskStatus.RUNNING, 0.20, "大纲生成完成")

        # 阶段 2: 创建章节对象
        chapters = []
        if thesis.outline:
            for node in thesis.outline.get_chapters():
                ch = Chapter(node=node, status="pending")
                chapters.append(ch)
        thesis.chapters = chapters
        total_chapters = len(chapters)
        self._update_task(task_id, TaskStatus.RUNNING, 0.25, f"章节结构就绪: {total_chapters} 章")

        # 阶段 3: 逐章生成
        cg = ChapterGenerator(llm)
        rf = ReferenceFetcher()
        thesis.references = rf.fetch_by_keywords(thesis.keywords, limit=20)

        for i, ch in enumerate(thesis.chapters):
            progress = 0.25 + 0.40 * (i / max(total_chapters, 1))
            self._update_task(task_id, TaskStatus.RUNNING, progress,
                            f"正在生成第 {i+1}/{total_chapters} 章: {ch.node.title}")

            # 获取参考文献 prompt
            if thesis.references:
                _, refs_text = rf.fetch_with_citations(
                    thesis.keywords,
                    thesis.chapters[i-1].content_markdown if i > 0 else ""
                )
            else:
                refs_text = ""

            generated = cg.generate_chapter(
                thesis.outline, ch.node,
                thesis.chapters[:i],
                user_data=thesis.user_data.get("prompt_text"),
                references_text=refs_text,
            )
            thesis.chapters[i] = generated

        self._update_task(task_id, TaskStatus.RUNNING, 0.70, "章节生成完成")

        # 阶段 4: 文献格式化
        self._update_task(task_id, TaskStatus.RUNNING, 0.75, "正在格式化参考文献...")
        for ref in thesis.references:
            if not ref.citation_text:
                ref.citation_text = ref.to_gb7714()

        # 阶段 5: DOCX 输出
        self._update_task(task_id, TaskStatus.RUNNING, 0.82, "正在生成 DOCX 文件...")
        output_dir = os.path.join(os.path.dirname(project_root), "data", "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"thesis_{task_id}.docx")

        formatter = DocxFormatter()
        formatter.create_document(thesis, output_path)

        # 阶段 6: 水印 + 免责声明
        self._update_task(task_id, TaskStatus.RUNNING, 0.95, "正在添加水印和免责声明...")
        final_path = output_path
        try:
            final_path = add_watermark_and_disclaimer(output_path, output_path)
        except Exception as e:
            logger.warning(f"水印添加失败（非致命）: {e}")

        # 完成
        self._update_task(
            task_id, TaskStatus.COMPLETED, 1.0,
            "生成完成！",
            output_path=final_path,
        )
        logger.info(f"任务 {task_id} 完成: {final_path}")

    def _update_task(
        self,
        task_id: str,
        status: TaskStatus,
        progress: float,
        message: str,
        output_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """更新任务状态

        Args:
            task_id: 任务 ID
            status: 新状态
            progress: 进度 [0, 1]
            message: 状态描述
            output_path: 输出文件路径
            error: 错误信息
        """
        with self._lock:
            if task_id in self._tasks:
                result = self._tasks[task_id]
                result.status = status
                result.progress = progress
                result.message = message
                if output_path:
                    result.output_path = output_path
                if error:
                    result.error = error

    def shutdown(self) -> None:
        """关闭 worker，释放资源"""
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        logger.info("AsyncTaskManager 已关闭")


# 全局单例（轻量模式）
_task_manager: Optional[AsyncTaskManager] = None


def get_task_manager(mode: TaskMode = TaskMode.LIGHTWEIGHT) -> AsyncTaskManager:
    """获取全局 AsyncTaskManager 单例

    Args:
        mode: 任务模式，仅首次调用时生效

    Returns:
        AsyncTaskManager: 全局实例
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = AsyncTaskManager(mode=mode)
    return _task_manager
