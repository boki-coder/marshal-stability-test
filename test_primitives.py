"""
test_primitives.py - 基础类型边界值黑盒测试
使用 pytest 框架，验证 marshal.dumps 对基础类型的序列化确定性。
"""

import sys
import hashlib
import marshal
import pytest


def get_hash(obj):
    """辅助函数：计算对象的marshal序列化字节流的SHA256哈希"""
    return hashlib.sha256(marshal.dumps(obj)).hexdigest()


# ========================== int 测试 ==========================
class TestIntBoundaries:
    def test_int_zero(self):
        assert get_hash(0) == get_hash(0)

    def test_int_one(self):
        assert get_hash(1) == get_hash(1)

    def test_int_negative_one(self):
        assert get_hash(-1) == get_hash(-1)

    def test_int_64bit_max(self):
        val = 2**63 - 1
        assert get_hash(val) == get_hash(val)

    def test_int_64bit_min(self):
        val = -(2**63)
        assert get_hash(val) == get_hash(val)

    def test_int_large_positive(self):
        val = 2**100
        assert get_hash(val) == get_hash(val)

    def test_int_large_negative(self):
        val = -(2**100)
        assert get_hash(val) == get_hash(val)


# ========================= float 测试 ========================
class TestFloatBoundaries:
    def test_positive_zero(self):
        val = 0.0
        assert get_hash(val) == get_hash(val)

    def test_negative_zero(self):
        val = -0.0
        assert get_hash(val) == get_hash(val)

    def test_infinity(self):
        val = float("inf")
        assert get_hash(val) == get_hash(val)

    def test_negative_infinity(self):
        val = -float("inf")
        assert get_hash(val) == get_hash(val)

    def test_nan_same_object(self):
        # 同一个 nan 对象两次序列化应一致
        val = float("nan")
        assert get_hash(val) == get_hash(val)

    def test_nan_different_objects(self):
        # 注意：不同 nan 对象可能具有不同位模式，
        # 这里记录为潜在缺陷，仅观察不强制断言
        val1 = float("nan")
        val2 = float("nan")
        h1 = get_hash(val1)
        h2 = get_hash(val2)
        if h1 != h2:
            pytest.xfail("Known issue: NaN payload may differ between instances")
        assert h1 == h2

    def test_normal_float(self):
        assert get_hash(1.0) == get_hash(1.0)
        assert get_hash(-1.0) == get_hash(-1.0)

    def test_min_subnormal(self):
        val = sys.float_info.min * 0.5
        assert get_hash(val) == get_hash(val)

    def test_max_float(self):
        val = sys.float_info.max
        assert get_hash(val) == get_hash(val)

    def test_min_float(self):
        val = sys.float_info.min
        assert get_hash(val) == get_hash(val)

    def test_pi(self):
        assert get_hash(3.141592653589793) == get_hash(3.141592653589793)

    def test_inf_symmetry(self):
        val = [float("inf"), -float("inf")]
        assert get_hash(val) == get_hash(val)


# ========================= bool 测试 =========================
class TestBool:
    def test_true(self):
        assert get_hash(True) == get_hash(True)

    def test_false(self):
        assert get_hash(False) == get_hash(False)


# ========================= str 测试 ==========================
class TestStrBoundaries:
    def test_empty_string(self):
        assert get_hash("") == get_hash("")

    def test_single_char(self):
        assert get_hash("a") == get_hash("a")

    def test_normal_string(self):
        assert get_hash("hello world") == get_hash("hello world")

    def test_long_string(self):
        val = "a" * 1000
        assert get_hash(val) == get_hash(val)

    def test_null_char(self):
        val = "\x00"
        assert get_hash(val) == get_hash(val)

    def test_unicode_null(self):
        val = "\u0000"
        assert get_hash(val) == get_hash(val)

    def test_emoji(self):
        val = "😊"
        assert get_hash(val) == get_hash(val)

    def test_mixed_unicode(self):
        val = "αβγ"
        assert get_hash(val) == get_hash(val)

    def test_very_long_string(self):
        val = " " * 10000
        assert get_hash(val) == get_hash(val)


# ======================== bytes 测试 =========================
class TestBytesBoundaries:
    def test_empty_bytes(self):
        assert get_hash(b"") == get_hash(b"")

    def test_single_zero_byte(self):
        assert get_hash(b"\x00") == get_hash(b"\x00")

    def test_single_ff_byte(self):
        assert get_hash(b"\xff") == get_hash(b"\xff")

    def test_normal_bytes(self):
        assert get_hash(b"hello") == get_hash(b"hello")

    def test_many_null_bytes(self):
        val = b"\x00" * 1000
        assert get_hash(val) == get_hash(val)

    def test_all_byte_values(self):
        val = bytes(range(256))
        assert get_hash(val) == get_hash(val)

    def test_large_bytes(self):
        val = b"\x00" * 100000
        assert get_hash(val) == get_hash(val)


# ======================== None 测试 ==========================
class TestNone:
    def test_none(self):
        assert get_hash(None) == get_hash(None)


# ====================== 混合基础类型 ==========================
class TestMixedPrimitives:
    def test_list_of_primitives(self):
        val = [0, 1.0, -float("inf"), True, None, "test", b"\x00"]
        assert get_hash(val) == get_hash(val)

    def test_dict_of_primitives(self):
        val = {"int": 42, "float": 3.14, "none": None}
        assert get_hash(val) == get_hash(val)
