"""pytest 全局配置 — 设置测试环境变量，避免模块加载时触发副作用"""

import base64
import os
import secrets

# 预生成测试用脱敏密钥，避免测试中自动写入 .hermes/master.key
_TEST_KEY = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
os.environ.setdefault("LAB_DEID_KEY", _TEST_KEY)

# 设置 WORK_ROOT 指向仓库根，确保路径一致
os.environ.setdefault("WORK_ROOT", os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")
))
