#!/usr/bin/env python3
"""
Generate a random passphrase from GB2312 Level 1 (一级) Chinese characters.
Usage: python scripts/random_passphrase.py [length]
Default length: 10  (≈119 bits entropy from 3755 chars).
"""

import secrets
import sys


def _gb2312_level1_chars() -> list[str]:
    """GB2312 一级汉字：16–55 区，每区 94 位。解码得到约 3755 个字。"""
    chars = []
    for b1 in range(0xB0, 0xD8):  # 区码 16–55
        for b2 in range(0xA1, 0xFF):  # 位码 1–94
            try:
                c = bytes([b1, b2]).decode("gb2312")
                chars.append(c)
            except UnicodeDecodeError:
                pass
    return chars


# 模块加载时生成一次，避免重复计算
_LEVEL1 = _gb2312_level1_chars()


def random_gb2312_level1(length: int) -> str:
    """随机生成指定长度的一级汉字序列。"""
    if length <= 0:
        return ""
    return "".join(secrets.choice(_LEVEL1) for _ in range(length))


def main() -> None:
    length = 10
    if len(sys.argv) > 1:
        try:
            length = int(sys.argv[1])
        except ValueError:
            print("Usage: python scripts/random_passphrase.py [length]", file=sys.stderr)
            sys.exit(1)
    if length <= 0:
        print("Length must be positive.", file=sys.stderr)
        sys.exit(1)
    print(random_gb2312_level1(length))


if __name__ == "__main__":
    main()
