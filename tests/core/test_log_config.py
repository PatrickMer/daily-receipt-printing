"""Tests for core.log_config — setup_logging and get_logger."""

import logging

import pytest

from core.log_config import LOG_FORMAT, get_logger, setup_logging


@pytest.fixture(autouse=True)
def _clean_root_logger():
    """Remove handlers added during tests so they don't leak across tests."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.level = original_level


class TestSetupLogging:
    """Test setup_logging configuration."""

    def test_creates_log_file(self, tmp_path):
        log_file = tmp_path / "app.log"
        setup_logging({"level": "DEBUG", "file": str(log_file)})
        assert log_file.exists()

    def test_creates_nested_log_directory(self, tmp_path):
        log_file = tmp_path / "subdir" / "nested" / "app.log"
        setup_logging({"file": str(log_file)})
        assert log_file.parent.exists()
        assert log_file.exists()

    def test_sets_root_logger_level_debug(self, tmp_path):
        log_file = tmp_path / "app.log"
        setup_logging({"level": "DEBUG", "file": str(log_file)})
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_sets_root_logger_level_warning(self, tmp_path):
        log_file = tmp_path / "app.log"
        setup_logging({"level": "WARNING", "file": str(log_file)})
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_default_level_is_info(self, tmp_path):
        log_file = tmp_path / "app.log"
        setup_logging({"file": str(log_file)})
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_case_insensitive_level(self, tmp_path):
        log_file = tmp_path / "app.log"
        setup_logging({"level": "debug", "file": str(log_file)})
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_invalid_level_falls_back_to_info(self, tmp_path):
        log_file = tmp_path / "app.log"
        setup_logging({"level": "NONEXISTENT", "file": str(log_file)})
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_adds_stream_and_file_handlers(self, tmp_path):
        log_file = tmp_path / "app.log"
        root = logging.getLogger()
        handlers_before = len(root.handlers)
        setup_logging({"file": str(log_file)})
        # Should add exactly 2 handlers (stream + file)
        assert len(root.handlers) == handlers_before + 2

    def test_handlers_use_correct_format(self, tmp_path):
        log_file = tmp_path / "app.log"
        setup_logging({"file": str(log_file)})
        root = logging.getLogger()
        # Check the last two handlers (the ones we just added)
        for handler in root.handlers[-2:]:
            assert handler.formatter is not None
            assert handler.formatter._fmt == LOG_FORMAT

    def test_writes_to_log_file(self, tmp_path):
        log_file = tmp_path / "app.log"
        setup_logging({"level": "INFO", "file": str(log_file)})
        logger = logging.getLogger("test.file_write")
        logger.info("Test message for file")
        # Flush handlers
        for handler in logging.getLogger().handlers:
            handler.flush()
        content = log_file.read_text()
        assert "Test message for file" in content

    def test_default_file_path(self, tmp_path, monkeypatch):
        """When no file key is provided, defaults to logs/daily-receipt.log."""
        # Change cwd to tmp_path so we don't pollute the real project
        monkeypatch.chdir(tmp_path)
        setup_logging({})
        expected = tmp_path / "logs" / "daily-receipt.log"
        assert expected.exists()


class TestGetLogger:
    """Test get_logger utility."""

    def test_returns_logger_instance(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_correct_name(self):
        logger = get_logger("my.custom.logger")
        assert logger.name == "my.custom.logger"

    def test_same_name_returns_same_logger(self):
        logger1 = get_logger("shared.name")
        logger2 = get_logger("shared.name")
        assert logger1 is logger2

    def test_different_names_return_different_loggers(self):
        logger1 = get_logger("name.one")
        logger2 = get_logger("name.two")
        assert logger1 is not logger2
