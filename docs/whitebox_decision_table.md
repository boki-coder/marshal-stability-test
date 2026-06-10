# 白盒判定表与 MC/DC 映射

## 浮点编码判定表（w_complex_object → PyFloat）

| 规则 | version>1 | 输入值 | 编码函数 | 预期 TYPE | 用例 |
|------|-----------|--------|----------|-----------|------|
| R1 | T | 1.5 | w_float_bin | g | WB-07 |
| R2 | F | 1.5 | w_float_str | f | WB-08 |
| R3 | T | +0.0 | w_float_bin | g | WB-09 |
| R4 | T | -0.0 | w_float_bin | g (不同 payload) | WB-09 |
| R5 | T | NaN | w_float_bin | g | WB-11 |
| R6 | T | ±Inf | w_float_bin | g | WB-10 |

MC/DC：`version>1` 单独决定走 `w_float_bin` 还是 `w_float_str`（WB-07 vs WB-08）。

## 整数编码判定表（PyLong_CheckExact）

| 规则 | overflow | 值范围 | 输出 | 用例 |
|------|----------|--------|------|------|
| R1 | 0 | 32-bit 内 | TYPE_INT | WB-03, WB-04 |
| R2 | 1 | 超出 long | TYPE_LONG | WB-05, WB-06 |

MC/DC：`overflow` 单独决定 `TYPE_INT` vs `TYPE_LONG`。

## 引用机制判定表（w_ref, version>=3）

| 规则 | 已登记 | 唯一引用 | 对象类型 | 行为 | 用例 |
|------|--------|----------|----------|------|------|
| R1 | T | - | 任意 | TYPE_REF | WB-18 |
| R2 | F | F | list 自引用 | ValueError | WB-19 |
| R3 | F | F | dict 自引用 | ValueError | WB-20 |

## 深度保护判定表（w_object）

| 规则 | depth > MAX | 行为 | 用例 |
|------|-------------|------|------|
| R1 | F | 正常序列化 | WB-21 |
| R2 | T | ValueError | WB-22 |

## 可追溯矩阵（角色 3 部分）

| 需求 ID | 题目要求 | 用例 ID | 源码位置 | 测试文件 |
|---------|----------|---------|----------|----------|
| REQ-01 | 基础类型稳定性 | WB-01~06 | w_object, w_PyLong | test_whitebox_marshal.py |
| REQ-02 | 浮点极端值 | WB-07~11 | w_float_bin/str | test_whitebox_marshal.py |
| REQ-03 | 字符串编码分支 | WB-12~14 | PyUnicode 分支 | test_whitebox_marshal.py |
| REQ-04 | 容器与 set 确定性 | WB-15~17 | tuple/set 分支 | test_whitebox_marshal.py |
| REQ-05 | 循环/共享引用 | WB-18~20 | w_ref | test_whitebox_marshal.py |
| REQ-06 | 递归深度限制 | WB-21~22 | MAX_MARSHAL_STACK_DEPTH | test_whitebox_marshal.py |
| REQ-07 | 反序列化正确性 | WB-24 | r_object | test_whitebox_marshal.py |
