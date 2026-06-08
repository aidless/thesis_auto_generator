"""
文件管理工具

提供文件保存、临时文件清理、路径管理等基础功能。
"""

import os
import shutil
import tempfile
from datetime import datetime
from typing import Optional

# 项目根目录（config.py 导入前可用）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_dir(dir_path: str) -> str:
    """确保目录存在，如不存在则创建

    Args:
        dir_path: 目录路径

    Returns:
        str: 目录路径
    """
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def get_output_dir() -> str:
    """获取输出目录路径，不存在则自动创建

    Returns:
        str: 输出目录绝对路径
    """
    out_dir = os.path.join(_PROJECT_ROOT, "data", "output")
    return ensure_dir(out_dir)


def get_template_dir() -> str:
    """获取预置模板目录路径，不存在则自动创建

    Returns:
        str: 模板目录绝对路径
    """
    tpl_dir = os.path.join(_PROJECT_ROOT, "data", "templates")
    return ensure_dir(tpl_dir)


def generate_output_filename(prefix: str, ext: str) -> str:
    """生成带时间戳的输出文件名

    格式：{prefix}_{YYYYMMDD_HHMMSS}.{ext}

    Args:
        prefix: 文件名前缀（如 "thesis", "outline"）
        ext: 文件扩展名（如 "docx", "md", "bib"）

    Returns:
        str: 完整输出路径
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.{ext}"
    return os.path.join(get_output_dir(), filename)


def save_uploaded_file(uploaded_file, target_dir: Optional[str] = None) -> str:
    """保存 Gradio 上传的文件到指定目录

    处理 Gradio 的临时文件路径，将其复制到持久化目录。

    Args:
        uploaded_file: Gradio 上传的文件对象或路径字符串
        target_dir: 目标目录，默认为 template 目录

    Returns:
        str: 保存后的文件路径
    """
    target_dir = target_dir or get_template_dir()
    ensure_dir(target_dir)

    # 处理 Gradio 上传文件的不同格式
    if isinstance(uploaded_file, str):
        source_path = uploaded_file
    elif hasattr(uploaded_file, 'name'):
        source_path = uploaded_file.name
    else:
        source_path = str(uploaded_file)

    # 生成目标文件名
    base_name = os.path.basename(source_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_name = f"{timestamp}_{base_name}"
    dest_path = os.path.join(target_dir, dest_name)

    # 复制文件
    shutil.copy2(source_path, dest_path)
    return dest_path


def cleanup_temp_files(pattern: str = "*.tmp", directory: Optional[str] = None) -> int:
    """清理临时文件

    Args:
        pattern: 文件匹配模式
        directory: 目标目录，默认为系统临时目录

    Returns:
        int: 清理的文件数量
    """
    import glob
    target_dir = directory or tempfile.gettempdir()
    count = 0
    for filepath in glob.glob(os.path.join(target_dir, pattern)):
        try:
            os.remove(filepath)
            count += 1
        except OSError:
            pass
    return count


def get_file_size_mb(file_path: str) -> float:
    """获取文件大小（MB）

    Args:
        file_path: 文件路径

    Returns:
        float: 文件大小，单位为 MB
    """
    if not os.path.isfile(file_path):
        return 0.0
    return os.path.getsize(file_path) / (1024 * 1024)
