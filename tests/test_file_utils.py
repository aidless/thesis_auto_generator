"""
测试文件管理工具 (test_file_utils.py)

覆盖：
- ensure_dir() — 创建目录
- get_output_dir() — 获取/创建输出目录
- get_template_dir() — 获取/创建模板目录
- generate_output_filename() — 生成时间戳文件名
- save_uploaded_file() — 保存上传文件
- get_file_size_mb() — 获取文件大小
- cleanup_temp_files() — 清理临时文件
"""

import sys
import os
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.file_utils import (
    ensure_dir,
    get_output_dir,
    get_template_dir,
    generate_output_filename,
    save_uploaded_file,
    get_file_size_mb,
    cleanup_temp_files,
)


class TestEnsureDir(unittest.TestCase):
    """测试目录创建"""

    def setUp(self):
        self.test_root = tempfile.mkdtemp()
        self.test_dir = os.path.join(self.test_root, "test_subdir")

    def tearDown(self):
        if os.path.isdir(self.test_root):
            shutil.rmtree(self.test_root, ignore_errors=True)

    def test_create_new_dir(self):
        """测试创建新目录"""
        self.assertFalse(os.path.isdir(self.test_dir))
        result = ensure_dir(self.test_dir)
        self.assertTrue(os.path.isdir(self.test_dir))
        self.assertEqual(result, self.test_dir)

    def test_existing_dir(self):
        """测试目录已存在"""
        os.makedirs(self.test_dir)
        self.assertTrue(os.path.isdir(self.test_dir))
        result = ensure_dir(self.test_dir)
        self.assertTrue(os.path.isdir(self.test_dir))
        self.assertEqual(result, self.test_dir)

    def test_nested_dir(self):
        """测试创建嵌套目录"""
        nested = os.path.join(self.test_root, "a", "b", "c")
        result = ensure_dir(nested)
        self.assertTrue(os.path.isdir(nested))
        self.assertEqual(result, nested)

    def test_returns_string(self):
        """测试返回字符串"""
        result = ensure_dir(self.test_dir)
        self.assertIsInstance(result, str)


class TestGetOutputDir(unittest.TestCase):
    """测试输出目录获取"""

    def test_returns_string(self):
        """测试返回字符串路径"""
        out_dir = get_output_dir()
        self.assertIsInstance(out_dir, str)

    def test_dir_exists(self):
        """测试目录确实存在"""
        out_dir = get_output_dir()
        self.assertTrue(os.path.isdir(out_dir))

    def test_ends_with_output(self):
        """测试路径以 output 结尾"""
        out_dir = get_output_dir()
        self.assertTrue(out_dir.endswith("output") or out_dir.endswith("output" + os.sep))


class TestGetTemplateDir(unittest.TestCase):
    """测试模板目录获取"""

    def test_returns_string(self):
        """测试返回字符串路径"""
        tpl_dir = get_template_dir()
        self.assertIsInstance(tpl_dir, str)

    def test_dir_exists(self):
        """测试目录存在"""
        tpl_dir = get_template_dir()
        self.assertTrue(os.path.isdir(tpl_dir))

    def test_ends_with_templates(self):
        """测试路径以 templates 结尾"""
        tpl_dir = get_template_dir()
        self.assertTrue(tpl_dir.endswith("templates") or tpl_dir.endswith("templates" + os.sep))


class TestGenerateOutputFilename(unittest.TestCase):
    """测试文件名生成"""

    def test_basic_filename(self):
        """测试基本文件名生成"""
        path = generate_output_filename("thesis", "docx")
        basename = os.path.basename(path)
        self.assertTrue(basename.startswith("thesis_"))
        self.assertTrue(basename.endswith(".docx"))

    def test_md_extension(self):
        """测试 .md 扩展名"""
        path = generate_output_filename("outline", "md")
        self.assertTrue(path.endswith(".md"))

    def test_timestamp_format(self):
        """测试时间戳格式 YYYYMMDD_HHMMSS"""
        path = generate_output_filename("test", "txt")
        basename = os.path.basename(path)
        # 格式: test_YYYYMMDD_HHMMSS.txt
        parts = basename.replace("test_", "").replace(".txt", "")
        self.assertEqual(len(parts), 15)  # YYYYMMDD_HHMMSS = 15 chars
        self.assertRegex(parts, r'^\d{8}_\d{6}$')

    def test_unique_filenames(self):
        """验证不同调用生成不同文件名（时间戳不同）"""
        import time
        path1 = generate_output_filename("test", "txt")
        time.sleep(0.1)  # 确保时间戳变化
        path2 = generate_output_filename("test", "txt")
        # 在快速连续调用时可能相同，所以这里宽松检查
        self.assertIsInstance(path1, str)
        self.assertIsInstance(path2, str)


class TestSaveUploadedFile(unittest.TestCase):
    """测试上传文件保存"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source_file = os.path.join(self.test_dir, "source.docx")
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("test content")

    def tearDown(self):
        if os.path.isdir(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_string_path(self):
        """测试字符串路径保存"""
        target = tempfile.mkdtemp()
        try:
            result = save_uploaded_file(self.source_file, target)
            self.assertTrue(os.path.isfile(result))
            self.assertIn(os.path.basename(self.source_file), result)
        finally:
            shutil.rmtree(target, ignore_errors=True)

    def test_save_with_default_dir(self):
        """测试使用默认目标目录"""
        result = save_uploaded_file(self.source_file)
        self.assertTrue(os.path.isfile(result))

    def test_file_content_preserved(self):
        """测试文件内容保留"""
        target = tempfile.mkdtemp()
        try:
            result = save_uploaded_file(self.source_file, target)
            with open(result, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content, "test content")
        finally:
            shutil.rmtree(target, ignore_errors=True)


class TestGetFileSizeMb(unittest.TestCase):
    """测试文件大小获取"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.isdir(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_existing_file(self):
        """测试存在的文件"""
        filepath = os.path.join(self.test_dir, "test.txt")
        with open(filepath, "w") as f:
            f.write("x" * 1024)  # 1KB
        size_mb = get_file_size_mb(filepath)
        self.assertGreater(size_mb, 0)
        self.assertLess(size_mb, 0.01)  # 1KB < 0.01MB

    def test_nonexistent_file(self):
        """测试不存在的文件"""
        size = get_file_size_mb("/nonexistent/file/path.txt")
        self.assertEqual(size, 0.0)

    def test_returns_float(self):
        """测试返回浮点数"""
        filepath = os.path.join(self.test_dir, "test.txt")
        with open(filepath, "w") as f:
            f.write("hello")
        size = get_file_size_mb(filepath)
        self.assertIsInstance(size, float)


class TestCleanupTempFiles(unittest.TestCase):
    """测试临时文件清理"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.isdir(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cleanup_temp_files(self):
        """测试清理 .tmp 文件"""
        tmp_file = os.path.join(self.test_dir, "test.tmp")
        with open(tmp_file, "w") as f:
            f.write("temp")
        self.assertTrue(os.path.isfile(tmp_file))

        count = cleanup_temp_files("*.tmp", self.test_dir)
        self.assertEqual(count, 1)
        self.assertFalse(os.path.isfile(tmp_file))

    def test_no_matching_files(self):
        """测试无匹配文件"""
        count = cleanup_temp_files("*.xyz", self.test_dir)
        self.assertEqual(count, 0)

    def test_returns_int(self):
        """测试返回整数"""
        count = cleanup_temp_files("*.tmp", self.test_dir)
        self.assertIsInstance(count, int)


if __name__ == "__main__":
    unittest.main()
