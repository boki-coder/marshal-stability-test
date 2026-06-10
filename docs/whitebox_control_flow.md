# marshal.c 白盒控制流说明

## 序列化入口

```
marshal.dumps(obj, version)
  -> _PyMarshal_WriteObjectToString()
       -> w_init_refs()          [version >= 3 时创建 hashtable]
       -> w_object(obj, &wf)
       -> w_clear_refs()
```

## w_object 控制流

1. `p->error != WFERR_OK` → 直接返回
2. `depth++`
3. `depth > MAX_MARSHAL_STACK_DEPTH` → `WFERR_NESTEDTOODEEP`
4. 单例对象：`NULL` / `None` / `True` / `False` / `StopIteration` / `Ellipsis`
5. 其他对象：`w_ref()` 检查引用
   - 已存在 → 写 `TYPE_REF` + index，结束
   - 首次出现 → `w_complex_object()`
6. `depth--`

## w_complex_object 类型分发

| 条件 | 函数/输出 | 测试用例 |
|------|-----------|----------|
| `PyLong` 不溢出 | `TYPE_INT` | WB-03, WB-04 |
| `PyLong` 溢出 | `TYPE_LONG` / `w_PyLong` | WB-05, WB-06 |
| `PyFloat`, version>1 | `TYPE_BINARY_FLOAT` / `w_float_bin` | WB-07~11 |
| `PyFloat`, version<=1 | `TYPE_FLOAT` / `w_float_str` | WB-08 |
| ASCII str, len<256 | `TYPE_SHORT_ASCII` | WB-12, WB-13 |
| ASCII str, len>=256 | `TYPE_ASCII` | WB-13 |
| 非 ASCII str | `TYPE_UNICODE` (UTF-8) | WB-14 |
| tuple, n<256 | `TYPE_SMALL_TUPLE` | WB-15 |
| tuple, n>=256 | `TYPE_TUPLE` | WB-15 |
| set/frozenset | 按 `marshal.dumps(elem)` 排序 | WB-17 |
| 循环引用 | `w_ref` 报错 | WB-19, WB-20 |
| 深度超限 | `WFERR_NESTEDTOODEEP` | WB-21, WB-22 |
| 不支持类型 | `TYPE_UNKNOWN` | WB-23 |

## 平台相关常量

- Windows: `MAX_MARSHAL_STACK_DEPTH = 1000`
- Linux/macOS: `MAX_MARSHAL_STACK_DEPTH = 2000`
