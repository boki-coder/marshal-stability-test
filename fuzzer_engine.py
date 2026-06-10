#!/usr/bin/env python3
# flake8: noqa: C901
# -*- coding: utf-8 -*-

"""
fuzzer_engine.py
角色2: 复杂结构与模糊测试（黑盒）

功能：
1. 生成随机深度嵌套的 Python 对象（list/dict/set/tuple + 基本类型）
2. 对 marshal.dumps 进行模糊测试（默认 10000 次），记录所有异常
3. 提供自引用/循环引用的专用测试用例（至少 3 组）
4. 提供 pytest 可识别的轻量级测试（用于 CI 快速验证）

作者：角色2
"""

import marshal
import random
import time
from typing import Any, List, Tuple

# ---------- 随机对象生成器配置 ----------
RANDOM_SEED = 42  # 固定种子，确保可复现
MAX_DEPTH = 6  # 最大嵌套深度
MAX_CONTAINER_SIZE = 20  # 单个容器最大元素数量（避免生成过大的对象）

# 基本类型池（包含极端浮点数）
PRIMITIVE_GENERATORS = [
    lambda: random.randint(-(10**6), 10**6),  # 普通整数
    lambda: random.randint(-(2**63), 2**63 - 1),  # 64位边界整数
    lambda: random.choice([0, 1, -1, 2**31, -(2**31)]),  # 特殊整数值
    lambda: random.choice([0.0, -0.0, float("inf"), float("-inf"), float("nan")]),
    lambda: random.uniform(-1e300, 1e300),  # 一般浮点数
    lambda: random.choice([True, False]),
    lambda: "".join(
        random.choices("abc\t\n\r\x00", k=random.randint(0, 10))
    ),  # 含控制字符
    lambda: bytes(random.randint(0, 50)),  # 随机字节串
    lambda: None,
]


def generate_random_object(current_depth: int = 0) -> Any:
    """
    递归生成随机的 Python 对象，支持 list / dict / set / tuple 任意嵌套。
    深度越深，生成容器的概率越低。
    """
    # 达到最大深度或随机选择基本类型（概率 70%）
    if current_depth >= MAX_DEPTH or random.random() < 0.7:
        return random.choice(PRIMITIVE_GENERATORS)()

    # 容器类型
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
        # set 要求元素可哈希，限制为不可变类型
        for _ in range(size):
            elem = generate_random_object(current_depth + 1)
            while not isinstance(
                elem, (int, float, bool, str, bytes, tuple, type(None))
            ):
                elem = generate_random_object(current_depth + 1)
            items.append(elem)
        return set(items)

    else:  # dict
        for _ in range(size):
            # key 必须可哈希
            key = generate_random_object(current_depth + 1)
            while not isinstance(
                key, (int, float, bool, str, bytes, tuple, type(None))
            ):
                key = generate_random_object(current_depth + 1)
            value = generate_random_object(current_depth + 1)
            items.append((key, value))
        return dict(items)


def safe_repr(obj: Any, max_len: int = 200) -> str:
    """安全地将对象转为字符串，避免打印巨型结构导致日志过大"""
    try:
        s = repr(obj)
        if len(s) > max_len:
            return s[:max_len] + "... (truncated)"
        return s
    except Exception:
        return f"<unprintable object of type {type(obj).__name__}>"


# ---------- 模糊测试主引擎 ----------
def run_fuzzer(iterations: int = 10000, log_file: str = "fuzzing_crashes.log"):
    """
    执行模糊测试：生成随机对象，调用 marshal.dumps，记录所有异常。

    Args:
        iterations: 测试次数
        log_file:   异常日志文件路径
    """
    random.seed(RANDOM_SEED)
    crash_count = 0
    success_count = 0

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"Fuzzing started at {time.ctime()}\n")
        f.write(f"Random seed = {RANDOM_SEED}\n")
        f.write("=" * 80 + "\n")

        for i in range(iterations):
            obj = generate_random_object()
            try:
                marshal.dumps(obj)
                success_count += 1
            except Exception as e:
                crash_count += 1
                crash_info = (
                    f"\n[Crash #{crash_count}] iteration {i}\n"
                    f"Exception: {type(e).__name__}: {str(e)}\n"
                    f"Object repr: {safe_repr(obj)}\n"
                    f"{'-' * 80}\n"
                )
                f.write(crash_info)
                f.flush()

            if (i + 1) % 1000 == 0:
                print(f"Progress: {i+1}/{iterations}, crashes so far: {crash_count}")

    print(
        f"\nFuzzing finished. Total: {iterations}, Success: {success_count}, Crashes: {crash_count}"
    )
    print(f"Crash log saved to {log_file}")


# ---------- 自引用/循环引用用例（至少3组）----------
def circular_reference_cases() -> List[Tuple[Any, str]]:
    """
    返回预定义的循环引用对象列表，每个元素为 (obj, description)
    这些对象在 marshal.dumps 中预期抛出 ValueError 或 RecursionError。
    """
    cases = []

    # 用例1：列表自引用
    lst = []
    lst.append(lst)
    cases.append((lst, "list self-reference: a = []; a.append(a)"))

    # 用例2：字典自引用
    d = {}
    d["self"] = d
    cases.append((d, "dict self-reference: d = {}; d['self'] = d"))

    # 用例3：两个对象互相引用（列表内嵌列表）
    a = []
    b = [a]
    a.append(b)
    cases.append((a, "mutual reference: a = []; b = [a]; a.append(b)"))

    # 用例4（额外）：元组间接自引用（元组包含列表，列表再引用元组？实际元组不可变，但可以构造含循环引用的元组需要借助列表）
    # 这里不再增加，3个足够
    return cases


def test_circular_refs():
    """
    pytest 专用测试：验证 marshal.dumps 对循环引用是否稳定抛出异常。
    预期所有自引用对象均触发 ValueError 或 RecursionError。
    """
    for obj, desc in circular_reference_cases():
        try:
            marshal.dumps(obj)
            # 如果没有抛异常，测试失败
            raise AssertionError(
                f"Expected exception for {desc}, but marshal.dumps succeeded"
            )
        except (ValueError, RecursionError) as e:
            # 预期异常，测试通过
            print(f"✅ {desc} -> correctly raised {type(e).__name__}: {e}")
        except Exception as e:
            # 其他异常也算失败（但通常不会发生）
            raise AssertionError(
                f"Unexpected exception {type(e).__name__} for {desc}: {e}"
            )


def test_fuzzer_smoke():
    """
    pytest 轻量级冒烟测试：只生成少量随机对象，确保引擎不崩溃。
    此函数会由 CI 流水线执行（快速验证）。
    """
    random.seed(RANDOM_SEED)
    for _ in range(100):
        obj = generate_random_object()
        try:
            marshal.dumps(obj)
        except Exception:
            # 允许任何异常，只要不导致进程崩溃即可
            pass


# ---------- 命令行入口 ----------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="marshal 模糊测试引擎")
    parser.add_argument("-n", "--iterations", type=int, default=10000, help="测试次数")
    parser.add_argument(
        "-l", "--log", type=str, default="fuzzing_crashes.log", help="日志文件路径"
    )
    args = parser.parse_args()

    run_fuzzer(iterations=args.iterations, log_file=args.log)

    # 顺便运行循环引用测试（非 pytest 模式下直接执行）
    print("\n--- Testing circular references ---")
    test_circular_refs()
