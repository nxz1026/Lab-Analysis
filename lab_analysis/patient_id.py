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
import hashlib
import hmac
import os
import secrets
import stat
import sys
from pathlib import Path
from typing import Optional

# cryptography 提供 AES-GCM (AEAD)；标准库无 AEAD，必须声明依赖
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 仅在文件直接运行时才 import 正则校验，避免模块加载阶段的循环依赖
# （utils.py 会反过来用到 patient_id 的 encode）
try:
    from lab_analysis.utils import validate_chinese_id as _is_valid_id_card
except Exception:  # pragma: no cover - utils 不可用时降级为本地正则
    import re

    def _is_valid_id_card(s: str) -> bool:  # type: ignore[no-redef]
        if not s:
            return False
        return bool(
            re.match(r"^\d{17}[\dXx]$", s) or re.match(r"^\d{15}$", s)
        )


# ── master_key 解析 ──────────────────────────────────────────────────

_KEY_FILE = Path(os.environ.get("WORK_ROOT", Path.cwd())) / ".hermes" / "master.key"
_NONCE_LEN = 12  # AES-GCM 推荐 nonce 长度


def _load_or_create_master_key() -> bytes:
    """加载 master key（32 字节）。不存在则安全生成并落盘到 .hermes/master.key。"""
    env_val = os.environ.get("LAB_DEID_KEY", "").strip()
    if env_val:
        key = _decode_key(env_val)
        if len(key) != 32:
            raise ValueError(
                "LAB_DEID_KEY 解码后必须为 32 字节（base64 编码）。"
            )
        return key

    if _KEY_FILE.is_file():
        key = _decode_key(_KEY_FILE.read_text(encoding="utf-8").strip())
        if len(key) != 32:
            raise ValueError(f"{_KEY_FILE} 内容解码后必须为 32 字节。")
        return key

    # 首次运行：自动生成
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    new_key = secrets.token_bytes(32)
    _KEY_FILE.write_text(
        base64.urlsafe_b64encode(new_key).decode("ascii"), encoding="utf-8"
    )
    try:
        os.chmod(_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0600，Windows 上为 no-op
    except OSError:
        pass
    print(
        f"[WARN] 已生成新的脱敏主密钥: {_KEY_FILE}\n"
        "       该文件包含还原身份证号的唯一凭证，切勿提交或外传。\n"
        "       生产环境建议改用环境变量 LAB_DEID_KEY 注入。",
        file=sys.stderr,
    )
    return new_key


def _decode_key(s: str) -> bytes:
    """容错地解码 base64 key（兼容 urlsafe/标准、是否带 padding）。"""
    s = s.strip()
    pad = "=" * (-len(s) % 4)
    try:
        return base64.urlsafe_b64decode(s + pad)
    except Exception:
        return base64.b64decode(s + pad)


# ── 脱敏 / 还原 ──────────────────────────────────────────────────────

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
    nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")


# ── 身份证号统一校验 ──────────────────────────────────────────────────

def validate_id_card(
    id_card: Optional[str],
    extracted_id: Optional[str] = None,
    interactive: bool = True,
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

    # 情况 1：合法且一致（或无 OCR 参照）
    if id_ok and (not ext_ok or id_card == extracted_id):
        return id_card

    # 情况 2：id_card 与 OCR 不一致
    if id_ok and ext_ok and id_card != extracted_id:
        print("[WARNING] 命令行身份证号与图片识别结果不一致：")
        print(f"  命令行传入: {id_card}")
        print(f"  图片识别:   {extracted_id}")
        if not interactive:
            print("[ERROR] 非交互模式且身份证号不一致，放弃此数据")
            return None
        return _choose_id_card(
            options=[("使用命令行身份证号", id_card),
                     ("使用图片识别身份证号", extracted_id)]
        )

    # 情况 3：仅 OCR 合法
    if not id_ok and ext_ok:
        print(f"[INFO] 提供的身份证号无效，将采用 OCR 识别值: {extracted_id}")
        return extracted_id

    # 情况 4：均非法/为空
    if id_card and not id_ok:
        print(f"[WARNING] 身份证号 '{id_card}' 不是有效的 15/18 位格式")
    if extracted_id and not ext_ok:
        print(f"[WARNING] OCR 识别值 '{extracted_id}' 也非有效身份证号")
    if not interactive:
        print("[ERROR] 非交互模式下必须提供有效身份证号，放弃此数据")
        return None
    return _prompt_manual_input()


def _choose_id_card(options: list) -> Optional[str]:
    """打印多选项菜单；options = [(label, value), ...]，末尾自动追加「手动输入/放弃」。"""
    print("\n请选择使用哪个身份证号：")
    for i, (label, _) in enumerate(options, 1):
        print(f"  {i}. {label}")
    print(f"  {len(options) + 1}. 手动输入其他身份证号")
    print(f"  {len(options) + 2}. 放弃此数据")
    try:
        choice = input(f"请输入选择 (1-{len(options) + 2}): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[ERROR] 无法读取输入，放弃此数据")
        return None

    idx = int(choice) - 1 if choice.isdigit() else -1
    if 0 <= idx < len(options):
        return options[idx][1]
    if idx == len(options):
        return _prompt_manual_input()
    print("[INFO] 用户选择放弃此数据")
    return None


def _prompt_manual_input() -> Optional[str]:
    """交互式要求用户手动输入一个合法身份证号（最多 3 次）。"""
    for attempt in range(3):
        try:
            val = input(
                f"请输入正确的身份证号（18 位或 15 位，第 {attempt + 1}/3 次）: "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[ERROR] 无法读取输入，放弃此数据")
            return None
        if val and _is_valid_id_card(val):
            return val
        print(f"[ERROR] '{val}' 不是有效身份证号")
    print("[ERROR] 连续 3 次输入无效，放弃此数据")
    return None


# ── 自测 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = "110101199003078888"  # 18 位示例（非真实号段）
    obf = encode(sample)
    restored = decode(obf)
    print(f"原始:   {sample}")
    print(f"脱敏:   {obf}")
    print(f"还原:   {restored}")
    print(f"确定性: {'[OK] 两次 encode 一致' if encode(sample) == obf else '[FAIL] 不一致'}")
    print(f"验证:   {'[OK] 往返一致' if sample == restored else '[FAIL] 往返失败'}")
