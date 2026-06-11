#!/usr/bin/env python3
# flake8: noqa: C901
# -*- coding: utf-8 -*-

import marshal
import random
import time
from typing import Any, List, Tuple

RANDOM_SEED = 42
MAX_DEPTH = 5  # 最大嵌套深度
MAX_CONTAINER_SIZE = 15

# 可哈希的基本类型池（不含容器）
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


def generate_hashable_object(current_depth: int = 0) -> Any:
    """生成可哈希的对象（用于 dict key 和 set 元素）"""
    if current_depth >= MAX_DEPTH or random.random() < 0.8:
        return random.choice(PRIMITIVE_GENERATORS)()
    # 生成简单元组（内部元素也是可哈希的）
    size = random.randint(0, 5)
    items = [generate_hashable_object(current_depth + 1) for _ in range(size)]
    return tuple(items)


def generate_random_object(current_depth: int = 0) -> Any:
    """生成随机对象（可包含不可哈希容器，用于序列化测试）"""
    if current_depth >= MAX_DEPTH or random.random() < 0.6:
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
        # set 元素必须可哈希
        for _ in range(size):
            elem = generate_hashable_object(current_depth + 1)
            items.append(elem)
        return set(items)

    else:  # dict
        for _ in range(size):
            key = generate_hashable_object(current_depth + 1)
            value = generate_random_object(current_depth + 1)
            items.append((key, value))
        return dict(items)


def circular_reference_cases() -> List[Tuple[Any, str]]:
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


def safe_repr(obj: Any, max_len: int = 200) -> str:
    try:
        s = repr(obj)
        if len(s) > max_len:
            return s[:max_len] + "... (truncated)"
        return s
    except Exception:
        return f"<unprintable object of type {type(obj).__name__}>"


def run_fuzzer(iterations: int = 10000, log_file: str = "fuzzing_crashes.log"):
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


# pytest 测试
import pytest


@pytest.mark.parametrize("obj, desc", circular_reference_cases())
def test_circular_refs(obj, desc):
    dumped_v3 = marshal.dumps(obj)
    assert isinstance(dumped_v3, bytes)
    with pytest.raises(ValueError):
        marshal.dumps(obj, 2)


def test_fuzzer_smoke():
    random.seed(RANDOM_SEED)
    for _ in range(100):
        obj = generate_random_object()
        try:
            marshal.dumps(obj)
        except (ValueError, RecursionError):
            pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--iterations", type=int, default=10000)
    parser.add_argument("-l", "--log", type=str, default="fuzzing_crashes.log")
    args = parser.parse_args()
    run_fuzzer(iterations=args.iterations, log_file=args.log)
