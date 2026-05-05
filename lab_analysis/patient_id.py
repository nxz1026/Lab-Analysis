"""
patient_id.py
患者ID脱敏算法：数字偏移 (d + k) mod 10，字母不变
k=3，写在此处供逆向运算参考
"""

K = 3  # 偏移量


def encode(patient_id: str) -> str:
    """原始ID → 脱敏ID（正运算）"""
    result = ""
    for ch in patient_id:
        if ch.isdigit():
            result += str((int(ch) + K) % 10)
        else:
            result += ch
    return result


def decode(obfuscated_id: str) -> str:
    """脱敏ID → 原始ID（逆运算，(d - k + 10) mod 10）"""
    result = ""
    for ch in obfuscated_id:
        if ch.isdigit():
            result += str((int(ch) - K + 10) % 10)
        else:
            result += ch
    return result


if __name__ == "__main__":
    # 示例
    raw = "513229198801040014"
    obf = encode(raw)
    restored = decode(obf)
    print(f"原始:  {raw}")
    print(f"脱敏:  {obf}")
    print(f"还原:  {restored}")
    print(f"验证:  {'✅ 一致' if raw == restored else '❌ 失败'}")
