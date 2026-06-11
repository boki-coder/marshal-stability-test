#!/usr/bin/env python3
# flake8: noqa: C901
# -*- coding: utf-8 -*-

import marshal
import random
import pytest
from typing import Any, List, Tuple

RANDOM_SEED = 42
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
            while (
                True
            ):  # 修复Bug：使用真实的 hash() 判断，解决元组嵌套集合导致崩溃的问题
                elem = generate_random_object(current_depth + 1)
                try:
                    hash(elem)
                    items.append(elem)
                    break
                except TypeError:
                    pass
        return set(items)

    else:  # dict
        for _ in range(size):
            while True:  # 修复Bug：使用真实的 hash() 判断
                key = generate_random_object(current_depth + 1)
                try:
                    hash(key)
                    break
                except TypeError:
                    pass
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


@pytest.mark.parametrize("obj, desc", circular_reference_cases())
def test_circular_refs(obj, desc):
    """
    重大发现 (Findings) 验证：
    Python 现代版本的 marshal 默认能处理循环引用，但老版本格式 (version 2) 会抛出 ValueError。
    """
    # 1. 测试现代协议 (默认, Version 3/4)：应该成功，不会死循环！
    dumped_v3 = marshal.dumps(obj)
    assert isinstance(dumped_v3, bytes)

    # 2. 测试降级协议 (Version 2)：由于没有 TYPE_REF 机制，必定无法处理循环引用而崩溃！
    with pytest.raises(ValueError):
        # ⚠️ 修复 Bug：去掉了 'version='，直接传数字 2
        marshal.dumps(obj, 2)


def test_fuzzer_smoke():
    random.seed(RANDOM_SEED)
    for _ in range(1000):
        obj = generate_random_object()
        try:
            marshal.dumps(obj)
        except (ValueError, RecursionError):
            pass


if __name__ == "__main__":
    pass
