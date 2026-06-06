"""log_utils.py — 统一日志框架

v38.0: 替代散落在各模块中的 print() 调用，提供分级日志。

用法：
    from log_utils import get_logger
    log = get_logger(__name__)

    log.info("构建完成: %d 个文件", count)
    log.warning("占位符残留: %s", placeholders)
    log.error("校验失败: %s", errors)
    log.success("验证通过")      # 自定义 SUCCESS 级别
    log.fail("构建中断")         # 自定义 FAIL 级别

向后兼容：
    已有 print() 调用不必全部替换，新代码优先使用 log。
    set_legacy_print(True) 可将 log 输出同时镜像到 print()。
"""

import logging
import sys

# ── 自定义日志级别 ───────────────────────────────────────
SUCCESS = 25  # 介于 INFO(20) 和 WARNING(30) 之间
FAIL = 35  # 介于 WARNING(30) 和 ERROR(40) 之间

logging.addLevelName(SUCCESS, "SUCCESS")
logging.addLevelName(FAIL, "FAIL")

# ── Emoji 前缀映射 ──────────────────────────────────────
_EMOJI = {
    "DEBUG": "🔍",
    "INFO": "📋",
    "SUCCESS": "✅",
    "WARNING": "⚠️",
    "FAIL": "❌",
    "ERROR": "💥",
    "CRITICAL": "🔥",
}

# ── 格式化器 ────────────────────────────────────────────


class EmojiFormatter(logging.Formatter):
    """带 emoji 前缀的格式化器"""

    def __init__(self, fmt: str = "%(message)s", use_emoji: bool = True):
        super().__init__(fmt)
        self.use_emoji = use_emoji

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        if self.use_emoji:
            emoji = _EMOJI.get(record.levelname, "")
            if emoji and not msg.startswith(emoji):
                msg = f"{emoji} {msg}"
        return msg


# ── Logger 工厂 ─────────────────────────────────────────

_loggers: dict = {}
_legacy_print: bool = False


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """获取或创建命名 Logger。

    Args:
        name: 通常为 __name__，如 'build_kb_files'
        level: 最低日志级别，默认 DEBUG

    Returns:
        配置好的 Logger 实例
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False  # 防止重复输出

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(EmojiFormatter())
        logger.addHandler(handler)

    # 添加便捷方法
    if not hasattr(logger, "success"):

        def success(msg, *args, **kwargs):
            logger.log(SUCCESS, msg, *args, **kwargs)

        logger.success = success  # type: ignore[attr-defined]

    if not hasattr(logger, "fail"):

        def fail(msg, *args, **kwargs):
            logger.log(FAIL, msg, *args, **kwargs)

        logger.fail = fail  # type: ignore[attr-defined]

    _loggers[name] = logger
    return logger


def set_level(level: int) -> None:
    """全局设置所有已创建 Logger 的日志级别"""
    for logger in _loggers.values():
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)


def set_legacy_print(enabled: bool) -> None:
    """启用/禁用 legacy print 模式（log 同时输出到 print）"""
    global _legacy_print
    _legacy_print = enabled


def set_quiet() -> None:
    """静默模式：只显示 WARNING 及以上"""
    set_level(logging.WARNING)


def set_verbose() -> None:
    """详细模式：显示 DEBUG 及以上"""
    set_level(logging.DEBUG)
