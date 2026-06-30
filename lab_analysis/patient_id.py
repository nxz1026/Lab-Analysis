"""
patient_id.py — 患者身份证号脱敏与校验

脱敏算法：确定性 AES-256-GCM 对称加密
===========================================
- 同一身份证号每次产出同一 deid（确定性），保证数据始终落入同一目录。
- deid 形如 ``9f3a...c2e1``（URL 安全 base64，可作目录名）。
- 仅凭 master_key 即可还原（无需明文映射文件，杜绝 PHI 落盘）。
- master_key 不进仓库：优先级
    1. 环境变量 ``LAB_DEID_KEY``（base64）
    2. ``.hermes/master.key``（base64，已 gitignore）
    3. 首次运行自动生成并写入 ``.hermes/master.key``（权限 0600），打印警告

⚠️ ``decode()`` 仅供本地数据回溯，禁止分发，仅 ``.hermes/`` 有权访问。
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import os
import secrets
import stat
import sys
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import _log
from ._exceptions import SAFE_EXCEPTIONS

logger = _log.get_logger(__name__)
from lab_analysis.utils import validate_chinese_id as _is_valid_id_card


_KEY_FILE = Path(os.environ.get("WORK_ROOT", Path.cwd())) / ".hermes" / "master.key"
_NONCE_LEN = 12


def _load_or_create_master_key() -> bytes:
    """加载 master key（32 字节）。不存在则安全生成并落盘到 .hermes/master.key。"""
    env_val = os.environ.get("LAB_DEID_KEY", "").strip()
    if env_val:
        key = _decode_key(env_val)
        if len(key) != 32:
            raise ValueError("LAB_DEID_KEY 解码后必须为 32 字节（base64 编码）。")
        return key
    if _KEY_FILE.is_file():
        key = _decode_key(_KEY_FILE.read_text(encoding="utf-8").strip())
        if len(key) != 32:
            raise ValueError(f"{_KEY_FILE} 内容解码后必须为 32 字节。")
        return key
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    new_key = secrets.token_bytes(32)
    _KEY_FILE.write_text(base64.urlsafe_b64encode(new_key).decode("ascii"), encoding="utf-8")
    with contextlib.suppress(OSError):
        os.chmod(_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)
    logger.warning(
        f"[WARN] 已生成新的脱敏主密钥: {_KEY_FILE}\n       该文件包含还原身份证号的唯一凭证，切勿提交或外传。\n       生产环境建议改用环境变量 LAB_DEID_KEY 注入。"
    )
    return new_key


def _decode_key(s: str) -> bytes:
    """容错地解码 base64 key（兼容 urlsafe/标准、是否带 padding）。"""
    s = s.strip()
    pad = "=" * (-len(s) % 4)
    try:
        return base64.urlsafe_b64decode(s + pad)
    except Exception:
        pass
    try:
        return base64.b64decode(s + pad)
    except Exception as e:
        raise ValueError(f"无法解码 master key（{len(s)} 字节）：数据已损坏或使用了不同的 key") from e


def encode(id_card: str) -> str:
    """原始身份证号 → 脱敏 ID（确定性、可逆）。

    - 合成 nonce = HMAC-SHA256(master_key, id_card)[:12]，保证确定性。
    - deid = base64url(nonce || ciphertext_with_tag)，仅含 URL 安全字符。
    """
    if not id_card:
        raise ValueError("encode() 拒绝空字符串")
    key = _load_or_create_master_key()
    data = id_card.encode("utf-8")
    nonce = hmac.new(key, data, hashlib.sha256).digest()[:_NONCE_LEN]
    ct = AESGCM(key).encrypt(nonce, data, None)
    return base64.urlsafe_b64encode(nonce + ct).rstrip(b"=").decode("ascii")


def decode(deid: str) -> str:
    """脱敏 ID → 原始身份证号（仅供本地数据回溯）。

    ⚠️ 仅需 master_key 即可还原。该函数用于内部审计，禁止随数据/日志分发。
    """
    if not deid:
        raise ValueError("decode() 拒绝空字符串")
    key = _load_or_create_master_key()
    raw = base64.urlsafe_b64decode(deid + "=" * (-len(deid) % 4))
    nonce, ct = (raw[:_NONCE_LEN], raw[_NONCE_LEN:])
    return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")


def _deid_log(val: str) -> str:
    """日志安全版脱敏：返回脱敏 ID 或占位符，避免明文 PHI 写日志。"""
    try:
        return encode(val)
    except SAFE_EXCEPTIONS:
        return "(脱敏失败)"


def validate_id_card(
    id_card: Optional[str], extracted_id: Optional[str] = None, interactive: bool = True
) -> Optional[str]:
    """强制校验身份证号格式；无效则交互确认或放弃。

    Args:
        id_card:      命令行/调用方提供的身份证号（可能为空或非法）。
        extracted_id: OCR 从图片中识别到的身份证号（可选，用于比对一致性）。
        interactive:  非法时是否进入交互确认；False 则直接放弃（返回 None）。

    Returns:
        验证通过的身份证号；放弃时返回 None。

    优先级：
      1. id_card 合法且（无 extracted_id 或与 extracted_id 一致）→ 直接通过
      2. id_card 合法但与 extracted_id 不一致 → 交互选择用哪一个 / 手输 / 放弃
      3. id_card 非法但 extracted_id 合法 → 询问是否采用 extracted_id
      4. 二者均非法 → 交互要求手输，或放弃
    """
    id_ok = bool(id_card and _is_valid_id_card(id_card))
    ext_ok = bool(extracted_id and _is_valid_id_card(extracted_id))
    if id_ok and (not ext_ok or id_card == extracted_id):
        return id_card
    if id_ok and ext_ok and (id_card != extracted_id):
        logger.warning("[WARNING] 命令行身份证号与图片识别结果不一致：")
        logger.info(f"  命令行传入(脱敏): {_deid_log(id_card)}")
        logger.info(f"  图片识别(脱敏):   {_deid_log(extracted_id)}")
        if not interactive:
            logger.error("[ERROR] 非交互模式且身份证号不一致，放弃此数据")
            return None
        return _choose_id_card(
            options=[("使用命令行身份证号", id_card), ("使用图片识别身份证号", extracted_id)]
        )
    if not id_ok and ext_ok:
        logger.info(f"[INFO] 将采用 OCR 识别值(脱敏): {_deid_log(extracted_id)}")
        return extracted_id
    if id_card and (not id_ok):
        logger.info(f"[WARNING] 提供的身份证号不是有效的 15/18 位格式")
    if extracted_id and (not ext_ok):
        logger.info(f"[WARNING] OCR 识别值也非有效身份证号")
    if not interactive:
        logger.error("[ERROR] 非交互模式下必须提供有效身份证号，放弃此数据")
        return None
    return _prompt_manual_input()


def _choose_id_card(options: list) -> Optional[str]:
    """打印多选项菜单；options = [(label, value), ...]，末尾自动追加「手动输入/放弃」。"""
    logger.info("\n请选择使用哪个身份证号：")
    for i, (label, _) in enumerate(options, 1):
        logger.info(f"  {i}. {label}")
    logger.info(f"  {len(options) + 1}. 手动输入其他身份证号")
    logger.info(f"  {len(options) + 2}. 放弃此数据")
    try:
        choice = input(f"请输入选择 (1-{len(options) + 2}): ").strip()
    except (EOFError, KeyboardInterrupt):
        logger.error("\n[ERROR] 无法读取输入，放弃此数据")
        return None
    idx = int(choice) - 1 if choice.isdigit() else -1
    if 0 <= idx < len(options):
        return options[idx][1]
    if idx == len(options):
        return _prompt_manual_input()
    logger.info("[INFO] 用户选择放弃此数据")
    return None


def _prompt_manual_input() -> Optional[str]:
    """交互式要求用户手动输入一个合法身份证号（最多 3 次）。"""
    for attempt in range(3):
        try:
            val = input(f"请输入正确的身份证号（18 位或 15 位，第 {attempt + 1}/3 次）: ").strip()
        except (EOFError, KeyboardInterrupt):
            logger.error("\n[ERROR] 无法读取输入，放弃此数据")
            return None
        if val and _is_valid_id_card(val):
            return val
        logger.info(f"[ERROR] '{val}' 不是有效身份证号")
    logger.error("[ERROR] 连续 3 次输入无效，放弃此数据")
    return None


if __name__ == "__main__":
    sample = os.environ.get("LAB_DEID_TEST_ID", "110101199003078888")
    obf = encode(sample)
    restored = decode(obf)
    logger.info(f"原始:   {_deid_log(sample)}")
    logger.info(f"脱敏:   {obf}")
    logger.info(f"验证:   {('[OK] 往返一致' if sample == restored else '[FAIL] 往返失败')}")
