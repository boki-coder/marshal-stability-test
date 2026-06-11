#!/usr/bin/env python3
# flake8: noqa: C901
# -*- coding: utf-8 -*-

"""
test_fuzzer_engine.py  <-- 注意：文件名必须以此开头
角色2: 复杂结构与模糊测试（黑盒）

功能：
1. 生成随机深度嵌套的 Python 对象（list/dict/set/tuple + 基本类型）
2. 对 marshal.dumps 进行模糊测试
3. 提供自引用/循环引用的专用测试用例
"""

import marshal
import random
import time
import pytest
from typing import Any, List, Tuple

# ---------- 随机对象生成器配置 ----------
RANDOM_SEED = 42  # 固定种子，确保 CI 环境完全可复现
MAX_DEPTH = 6
MAX_CONTAINER_SIZE = 20

PRIMITIVE_GENERATORS = [
    lambda: random.randint(-(10**6), 10**6),
    lambda: random.randint(-(2**63), 2**63 - 1),
    lambda: random.choice([0, 1, -1, 2**31, -(2**31)]),
    lambda: random.choice([0.0, -0.0, float("inf"), float("-inf"), float("nan")]),
    lambda: random.uniform(-1e300, 1e300),
    lambda: random.choice([True, False]),
    lambda: "".join(random.choices("abc\t\n\r\x00", k=random.randint(0, 10))),
    lambda: bytes(random.randint(0, 50)),
    lambda: None,
]

def generate_random_object(current_depth: int = 0) -> Any:
    """递归生成随机的 Python 对象"""
    if current_depth >= MAX_DEPTH or random.random() < 0.7:
        return random.choice(PRIMITIVE_GENERATORS)()

    container_type = random.choice(["list", "dict", "set", "tuple"])
    size = random.randint(0, MAX_CONTAINER_SIZE)
    items = []

    if container_type == "list":
        for _ in range(size):
            items.append(generate_random_object(current_depth + 1))
        return items

    elif container_type == "tuple":
        for _ in range(size):
            items.append(generate_random_object(current_depth + 1))
        return tuple(items)

    elif container_type == "set":
        for _ in range(size):
            elem = generate_random_object(current_depth + 1)
            while not isinstance(elem, (int, float, bool, str, bytes, tuple, type(None))):
                elem = generate_random_object(current_depth + 1)
            items.append(elem)
        return set(items)

    else:  # dict
        for _ in range(size):
            key = generate_random_object(current_depth + 1)
            while not isinstance(key, (int, float, bool, str, bytes, tuple, type(None))):
                key = generate_random_object(current_depth + 1)
            value = generate_random_object(current_depth + 1)
            items.append((key, value))
        return dict(items)

def safe_repr(obj: Any, max_len: int = 200) -> str:
    try:
        s = repr(obj)
        if len(s) > max_len:
            return s[:max_len] + "... (truncated)"
        return s
    except Exception:
        return f"<unprintable object of type {type(obj).__name__}>"

# ---------- 核心测试用例 (Pytest 自动发现) ----------

def circular_reference_cases() -> List[Tuple[Any, str]]:
    """返回预定义的循环引用对象列表"""
    cases = []
    
    lst = []
    lst.append(lst)
    cases.append((lst, "list_self_reference"))

    d = {}
    d["self"] = d
    cases.append((d, "dict_self_reference"))

    a = []
    b = [a]
    a.append(b)
    cases.append((a, "mutual_reference_list"))

    return cases

# 极其优雅的 Pytest 参数化写法，把 3 个用例拆分成独立的测试项
@pytest.mark.parametrize("obj, desc", circular_reference_cases())
def test_circular_refs(obj, desc):
    """验证 marshal.dumps 对循环引用是否稳定抛出异常"""
    # 预期底层必须防守住，抛出 ValueError 或 RecursionError
    with pytest.raises((ValueError, RecursionError)):
        marshal.dumps(obj)

def test_fuzzer_smoke():
    """
    CI 流水线执行的 Fuzzing 轰炸测试 (1000次)。
    如果抛出了不可预知的底层崩溃异常，将直接打红流水线！
    """
    random.seed(RANDOM_SEED)
    for _ in range(1000):
        obj = generate_random_object()
        try:
            marshal.dumps(obj)
        except (ValueError, RecursionError):
            # 允许的值错误（比如生成的浮点数不被底层支持）或递归错误，放行
            pass
        # 注意：这里不再有 except Exception: pass
        # 如果爆出其他奇葩 Bug，测试直接 Failed，这就成了你们期末报告的素材！

# ---------- 供本地压测的命令行入口 ----------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="marshal 模糊测试引擎")
    parser.add_argument("-n", "--iterations", type=int, default=10000, help="测试次数")
    args = parser.parse_args()

    print(f"Starting Fuzzing for {args.iterations} iterations...")
    random.seed(RANDOM_SEED)
    crash_count = 0
    for i in range(args.iterations):
        obj = generate_random_object()
        try:
            marshal.dumps(obj)
        except Exception:
            crash_count += 1
    print(f"Fuzzing finished. Crashes caught: {crash_count}")