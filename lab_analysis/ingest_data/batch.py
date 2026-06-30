"""ingest_data.batch — 批量处理辅助函数。"""

from __future__ import annotations

from collections.abc import Callable

from ._log import INGEST_LOG, append_log, logger


def process_batch(
    items: list,
    process_func: Callable,
    batch_mode: bool,
    item_name: str = "项",
) -> tuple[int, int]:
    """通用批量处理函数。

    Args:
        items: 要处理的项目列表
        process_func: 处理单个项目的函数，接收一个项目作为参数
        batch_mode: 是否批量模式
        item_name: 项目名称（用于显示）

    Returns:
        (success_count, fail_count) 元组
    """
    total = len(items)
    success_count = 0
    fail_count = 0
    for idx, item in enumerate(items, 1):
        if batch_mode:
            display_item = item[0] if isinstance(item, tuple) else item
            logger.info(f"\n{'=' * 60}")
            logger.info(
                f"[{idx}/{total}] 处理: {(display_item.name if hasattr(display_item, 'name') else display_item)}"
            )
            logger.info(f"{'=' * 60}")
        try:
            result = process_func(item)
            if result:
                append_log(result)
                success_count += 1
                if not batch_mode:
                    logger.info(f"[OK] {item_name}摄入成功")
            else:
                fail_count += 1
                if not batch_mode:
                    return (success_count, fail_count)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.error(f"摄入失败 {item}: {e}")
            logger.info(f"[ERROR] 摄入失败: {e}")
            fail_count += 1
            if not batch_mode:
                raise
    return (success_count, fail_count)


def print_batch_summary(success_count: int, fail_count: int, extra_info: str = "") -> None:
    """打印批量处理汇总信息。"""
    import json

    logger.info(f"\n{'=' * 60}")
    logger.info(f"批量处理完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    if extra_info:
        logger.info(extra_info)
    logger.info(f"{'=' * 60}")
    log = json.loads(INGEST_LOG.read_text(encoding="utf-8"))
    logger.info(f"总记录数: {len(log['ingested'])} 条")
