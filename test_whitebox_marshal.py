# 白盒测试：针对 marshal.c 中 w_object / w_complex_object / w_ref 分支

import hashlib
import marshal
import sys

import pytest

from utils import get_marshal_hash

FLAG_REF = 0x80

# marshal.c 里各平台的递归深度上限
if sys.platform == "win32":
    MAX_MARSHAL_STACK_DEPTH = 1000
else:
    MAX_MARSHAL_STACK_DEPTH = 2000


def dumps_version(obj, version=4):
    return marshal.dumps(obj, version)


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def get_type_code(data):
    # 去掉 FLAG_REF 高位，取真实 type code
    return data[0] & ~FLAG_REF


def assert_stable_hash(obj, repeats=10, version=4):
    # 同一对象多次 dumps，哈希必须相同
    baseline = sha256_hex(dumps_version(obj, version))
    for _ in range(repeats - 1):
        assert sha256_hex(dumps_version(obj, version)) == baseline


def build_nested_list(depth):
    # 构造深层嵌套 list，用于测试递归深度上限
    head = last = []
    for _ in range(depth):
        last.append([0])
        last = last[-1]
    return head


class TestWObjectSingletons:
    # None / True / False 单例路径

    def test_wb01_none_singleton_type_code(self):
        # w_object -> v == Py_None -> TYPE_NONE ('N')
        data = dumps_version(None)
        assert get_type_code(data) == ord("N")
        assert get_marshal_hash(None) == sha256_hex(data)

    def test_wb02_bool_singleton_type_codes(self):
        # w_object -> Py_False / Py_True
        false_data = dumps_version(False)
        true_data = dumps_version(True)
        assert get_type_code(false_data) == ord("F")
        assert get_type_code(true_data) == ord("T")
        assert_stable_hash(False)
        assert_stable_hash(True)


class TestPyLongBranches:
    # 整数 TYPE_INT / TYPE_LONG 分界

    def test_wb03_zero_uses_type_int(self):
        # PyLong_AsLongAndOverflow no overflow -> TYPE_INT ('i')
        data = dumps_version(0)
        assert get_type_code(data) == ord("i")
        assert_stable_hash(0)

    def test_wb04_small_int_boundary(self):
        # 32-bit signed fast path
        value = 2**31 - 1
        data = dumps_version(value)
        assert get_type_code(data) == ord("i")
        assert_stable_hash(value)

    def test_wb05_large_int_uses_type_long(self):
        # overflow -> w_PyLong -> TYPE_LONG ('l')
        value = 2**31
        data = dumps_version(value)
        assert get_type_code(data) == ord("l")
        assert_stable_hash(value)

    def test_wb06_huge_int_marshal_roundtrip(self):
        # w_PyLong multi-digit encoding
        value = 10**100
        data = dumps_version(value)
        assert get_type_code(data) == ord("l")
        assert marshal.loads(data) == value
        assert_stable_hash(value)


class TestFloatBranches:
    # 浮点数二进制/字符串编码

    def test_wb07_float_binary_stability(self):
        # version > 1 -> TYPE_BINARY_FLOAT ('g') + w_float_bin
        data = dumps_version(1.5)
        assert get_type_code(data) == ord("g")
        assert_stable_hash(1.5)

    def test_wb08_float_version_one_string_encoding(self):
        # version <= 1 -> TYPE_FLOAT ('f') + w_float_str
        v1 = dumps_version(1.5, version=1)
        v4 = dumps_version(1.5, version=4)
        assert get_type_code(v1) == ord("f")
        assert get_type_code(v4) == ord("g")
        assert v1 != v4

    def test_wb09_positive_zero_vs_negative_zero(self):
        # w_float_bin IEEE754 sign bit difference
        pos_hash = sha256_hex(dumps_version(0.0))
        neg_hash = sha256_hex(dumps_version(-0.0))
        assert pos_hash != neg_hash

    def test_wb10_infinity_values_stable(self):
        # w_float_bin for +/- inf
        for value in (float("inf"), float("-inf")):
            assert_stable_hash(value)

    def test_wb11_nan_single_representation_stability(self):
        # w_float_bin for NaN; documents per-process stability
        nan = float("nan")
        assert_stable_hash(nan)


class TestUnicodeBranches:
    # 字符串 ASCII / Unicode 编码

    def test_wb12_empty_str_short_ascii(self):
        # version>=4, ASCII, len<256 -> SHORT_ASCII family
        # Empty str is interned -> TYPE_SHORT_ASCII_INTERNED ('Z')
        data = dumps_version("")
        assert get_type_code(data) in (ord("z"), ord("Z"))
        assert_stable_hash("")

    def test_wb13_long_ascii_boundary(self):
        # len<256 -> SHORT_ASCII, len>=256 -> ASCII
        short_text = "S" + "h" * 254
        long_text = "L" + "o" * 255
        short_data = dumps_version(short_text)
        long_data = dumps_version(long_text)
        assert get_type_code(short_data) in (ord("z"), ord("Z"))
        assert get_type_code(long_data) in (ord("a"), ord("A"))

    def test_wb14_non_ascii_uses_type_unicode(self):
        # non-ASCII -> UTF-8 -> TYPE_UNICODE ('u')
        text = "你好"
        data = dumps_version(text)
        assert get_type_code(data) == ord("u")
        assert marshal.loads(data) == text
        assert_stable_hash(text)


class TestContainerBranches:
    # tuple / set 等容器编码

    def test_wb15_small_tuple_vs_regular_tuple(self):
        # version>=4, n<256 -> TYPE_SMALL_TUPLE (')')
        small = dumps_version(tuple(range(255)))
        large = dumps_version(tuple(range(256)))
        assert get_type_code(small) == ord(")")
        assert get_type_code(large) == ord("(")

    def test_wb16_empty_containers_stable(self):
        for obj in ([], {}, (), set(), frozenset()):
            assert_stable_hash(obj)

    def test_wb17_set_order_deterministic(self):
        # bpo-37596 sorted-by-marshal.dumps element order
        payload = {1, "z", b"x", 3.14, "a"}
        assert_stable_hash(payload)
        assert_stable_hash(frozenset(payload))


class TestReferenceMechanism:
    # 共享引用与循环结构

    def test_wb18_shared_reference_emits_type_ref(self):
        # w_ref detects duplicate object -> TYPE_REF ('r')
        shared = [1]
        data = dumps_version([shared, shared], version=4)
        assert ord("r") in data
        assert_stable_hash([shared, shared], version=4)

    def test_wb19_circular_list_version_gating(self):
        # version<3 lacks TYPE_REF; version>=3 encodes cycles
        cyclic = []
        cyclic.append(cyclic)
        with pytest.raises(ValueError):
            dumps_version(cyclic, version=2)
        data = dumps_version(cyclic, version=4)
        assert b"r" in data
        restored = marshal.loads(data)
        assert restored[0] is restored
        assert_stable_hash(cyclic, version=4)

    def test_wb20_circular_dict_version_gating(self):
        cyclic = {}
        cyclic["self"] = cyclic
        with pytest.raises(ValueError):
            dumps_version(cyclic, version=2)
        data = dumps_version(cyclic, version=4)
        restored = marshal.loads(data)
        assert restored["self"] is restored
        assert_stable_hash(cyclic, version=4)


class TestDepthAndErrors:
    # 递归深度上限与不可序列化对象

    def test_wb21_nested_depth_within_limit(self):
        head = build_nested_list(MAX_MARSHAL_STACK_DEPTH - 2)
        data = dumps_version(head)
        restored = marshal.loads(data)
        assert len(restored) == len(head)

    def test_wb22_nested_depth_exceeds_limit(self):
        head = last = []
        for _ in range(MAX_MARSHAL_STACK_DEPTH - 2):
            last.append([0])
            last = last[-1]
        last.append([0])
        with pytest.raises(ValueError, match="too deeply nested"):
            dumps_version(head)

    def test_wb23_unmarshallable_object_rejected(self):
        # default -> TYPE_UNKNOWN + WFERR_UNMARSHALLABLE
        with pytest.raises(ValueError, match="unmarshallable"):
            dumps_version(lambda x: x)


class TestRoundTripIntegrity:
    # loads(dumps(x)) 往返验证

    @pytest.mark.parametrize(
        "obj",
        [
            None,
            True,
            42,
            2**40,
            1.25,
            "ascii",
            "中文",
            b"bytes",
            [1, [2, 3]],
            {"k": "v"},
            (1, 2),
            {1, 2, 3},
        ],
    )
    def test_wb24_roundtrip_equals_original(self, obj):
        data = dumps_version(obj)
        assert marshal.loads(data) == obj
