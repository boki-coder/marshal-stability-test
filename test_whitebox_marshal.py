"""
White-box tests for CPython marshal.c core branches.

Each test maps to a specific path in w_object / w_complex_object / w_ref.
Coverage target: Python/marshal.c (write path).
"""

import hashlib
import marshal
import sys

import pytest

from utils import get_marshal_hash

FLAG_REF = 0x80

# Mirrors Python/marshal.c platform-specific limits.
if sys.platform == "win32":
    MAX_MARSHAL_STACK_DEPTH = 1000
else:
    MAX_MARSHAL_STACK_DEPTH = 2000


def dumps_version(obj, version=4):
    return marshal.dumps(obj, version)


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def get_type_code(data):
    """Strip FLAG_REF bit to obtain the marshal TYPE_* code."""
    return data[0] & ~FLAG_REF


def assert_stable_hash(obj, repeats=10, version=4):
    """Same input must produce identical SHA256 across repeated dumps."""
    baseline = sha256_hex(dumps_version(obj, version))
    for _ in range(repeats - 1):
        assert sha256_hex(dumps_version(obj, version)) == baseline


def build_nested_list(depth):
    """Build nested list structure used by CPython's own marshal tests."""
    head = last = []
    for _ in range(depth):
        last.append([0])
        last = last[-1]
    return head


class TestWObjectSingletons:
    """w_object: NULL / None / True / False fast paths."""

    def test_wb01_none_singleton_type_code(self):
        # Branch: w_object -> v == Py_None -> TYPE_NONE ('N')
        data = dumps_version(None)
        assert get_type_code(data) == ord("N")
        assert get_marshal_hash(None) == sha256_hex(data)

    def test_wb02_bool_singleton_type_codes(self):
        # Branch: w_object -> Py_False / Py_True
        false_data = dumps_version(False)
        true_data = dumps_version(True)
        assert get_type_code(false_data) == ord("F")
        assert get_type_code(true_data) == ord("T")
        assert_stable_hash(False)
        assert_stable_hash(True)


class TestPyLongBranches:
    """w_complex_object -> PyLong_CheckExact: TYPE_INT vs TYPE_LONG."""

    def test_wb03_zero_uses_type_int(self):
        # Branch: PyLong_AsLongAndOverflow no overflow -> TYPE_INT ('i')
        data = dumps_version(0)
        assert get_type_code(data) == ord("i")
        assert_stable_hash(0)

    def test_wb04_small_int_boundary(self):
        # Branch: 32-bit signed fast path
        value = 2**31 - 1
        data = dumps_version(value)
        assert get_type_code(data) == ord("i")
        assert_stable_hash(value)

    def test_wb05_large_int_uses_type_long(self):
        # Branch: overflow -> w_PyLong -> TYPE_LONG ('l')
        value = 2**31
        data = dumps_version(value)
        assert get_type_code(data) == ord("l")
        assert_stable_hash(value)

    def test_wb06_huge_int_marshal_roundtrip(self):
        # Branch: w_PyLong multi-digit encoding
        value = 10**100
        data = dumps_version(value)
        assert get_type_code(data) == ord("l")
        assert marshal.loads(data) == value
        assert_stable_hash(value)


class TestFloatBranches:
    """w_complex_object -> PyFloat: w_float_bin (v>1) vs w_float_str (v<=1)."""

    def test_wb07_float_binary_stability(self):
        # Branch: version > 1 -> TYPE_BINARY_FLOAT ('g') + w_float_bin
        data = dumps_version(1.5)
        assert get_type_code(data) == ord("g")
        assert_stable_hash(1.5)

    def test_wb08_float_version_one_string_encoding(self):
        # Branch: version <= 1 -> TYPE_FLOAT ('f') + w_float_str
        v1 = dumps_version(1.5, version=1)
        v4 = dumps_version(1.5, version=4)
        assert get_type_code(v1) == ord("f")
        assert get_type_code(v4) == ord("g")
        assert v1 != v4

    def test_wb09_positive_zero_vs_negative_zero(self):
        # Branch: w_float_bin IEEE754 sign bit difference
        pos_hash = sha256_hex(dumps_version(0.0))
        neg_hash = sha256_hex(dumps_version(-0.0))
        assert pos_hash != neg_hash

    def test_wb10_infinity_values_stable(self):
        # Branch: w_float_bin for +/- inf
        for value in (float("inf"), float("-inf")):
            assert_stable_hash(value)

    def test_wb11_nan_single_representation_stability(self):
        # Branch: w_float_bin for NaN; documents per-process stability
        nan = float("nan")
        assert_stable_hash(nan)


class TestUnicodeBranches:
    """w_complex_object -> PyUnicode: ASCII fast paths vs UTF-8."""

    def test_wb12_empty_str_short_ascii(self):
        # Branch: version>=4, ASCII, len<256 -> SHORT_ASCII family
        # Empty str is interned -> TYPE_SHORT_ASCII_INTERNED ('Z')
        data = dumps_version("")
        assert get_type_code(data) in (ord("z"), ord("Z"))
        assert_stable_hash("")

    def test_wb13_long_ascii_boundary(self):
        # Branch: len<256 -> SHORT_ASCII, len>=256 -> ASCII
        short_text = "S" + "h" * 254
        long_text = "L" + "o" * 255
        short_data = dumps_version(short_text)
        long_data = dumps_version(long_text)
        assert get_type_code(short_data) in (ord("z"), ord("Z"))
        assert get_type_code(long_data) in (ord("a"), ord("A"))

    def test_wb14_non_ascii_uses_type_unicode(self):
        # Branch: non-ASCII -> UTF-8 -> TYPE_UNICODE ('u')
        text = "你好"
        data = dumps_version(text)
        assert get_type_code(data) == ord("u")
        assert marshal.loads(data) == text
        assert_stable_hash(text)


class TestContainerBranches:
    """w_complex_object -> tuple/list/dict/set encoding paths."""

    def test_wb15_small_tuple_vs_regular_tuple(self):
        # Branch: version>=4, n<256 -> TYPE_SMALL_TUPLE (')')
        small = dumps_version(tuple(range(255)))
        large = dumps_version(tuple(range(256)))
        assert get_type_code(small) == ord(")")
        assert get_type_code(large) == ord("(")

    def test_wb16_empty_containers_stable(self):
        for obj in ([], {}, (), set(), frozenset()):
            assert_stable_hash(obj)

    def test_wb17_set_order_deterministic(self):
        # Branch: bpo-37596 sorted-by-marshal.dumps element order
        payload = {1, "z", b"x", 3.14, "a"}
        assert_stable_hash(payload)
        assert_stable_hash(frozenset(payload))


class TestReferenceMechanism:
    """w_ref / TYPE_REF / recursion detection (version >= 3)."""

    def test_wb18_shared_reference_emits_type_ref(self):
        # Branch: w_ref detects duplicate object -> TYPE_REF ('r')
        shared = [1]
        data = dumps_version([shared, shared], version=4)
        assert ord("r") in data
        assert_stable_hash([shared, shared], version=4)

    def test_wb19_circular_list_version_gating(self):
        # Branch: version<3 lacks TYPE_REF; version>=3 encodes cycles
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
    """w_object depth guard: WFERR_NESTEDTOODEEP."""

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
        # Branch: default -> TYPE_UNKNOWN + WFERR_UNMARSHALLABLE
        with pytest.raises(ValueError, match="unmarshallable"):
            dumps_version(lambda x: x)


class TestRoundTripIntegrity:
    """r_object symmetry via loads(dumps(x)) for white-box selections."""

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
