"""mcp_server.recompile — trigger_dspy_recompile tool"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import mcp

# 项目根 = mcp_server/ 的父目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@mcp.tool()
def trigger_dspy_recompile(force: bool = False, timeout_sec: int = 600) -> str:
    """触发 DSPy 4 module recompile (subprocess 调 examples/compile_all_dspy_modules_v2.py)。

    Args:
        force: True = 强制全量重 compile (跳过 mtime 检测); False = 增量 (默认).
        timeout_sec: subprocess 超时秒数, 默认 600s (10 min).

    Returns:
        JSON 字符串:
        {
          "started_at": str,
          "finished_at": str,
          "elapsed_sec": float,
          "returncode": int,
          "force": bool,
          "stdout_tail": str (最后 50 行),
          "stderr_tail": str (最后 20 行),
          "ok": bool
        }
    """
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.time()
    try:
        cmd = [sys.executable, str(_PROJECT_ROOT / "examples" / "compile_all_dspy_modules_v2.py")]
        if force:
            cmd.append("--force")
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(_PROJECT_ROOT),
            check=False,
            env={**os.environ},  # 传递当前 env (含 DEEPSEEK_API_KEY)
        )
        elapsed = round(time.time() - t0, 2)
        return json.dumps(
            {
                "started_at": started,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "elapsed_sec": elapsed,
                "returncode": proc.returncode,
                "force": force,
                "ok": proc.returncode == 0,
                "stdout_tail": "\n".join(proc.stdout.splitlines()[-50:]),
                "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
            },
            ensure_ascii=False,
            indent=2,
        )
    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - t0, 2)
        return json.dumps(
            {
                "started_at": started,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "elapsed_sec": elapsed,
                "returncode": -1,
                "ok": False,
                "error": f"timeout after {timeout_sec}s",
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        return json.dumps(
            {
                "started_at": started,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "elapsed_sec": elapsed,
                "returncode": -1,
                "ok": False,
                "error": str(e),
                "type": type(e).__name__,
            },
            ensure_ascii=False,
            indent=2,
        )
