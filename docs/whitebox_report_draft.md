# 白盒测试策略与覆盖率分析（报告草稿 · 约 1.5 页）

## 1. 测试对象与策略

白盒测试对象为 CPython `Python/marshal.c` 中的序列化核心函数 `w_object`、`w_complex_object` 与 `w_ref`。策略组合为：

- **语句/分支覆盖**：为每个 `TYPE_*` 分发路径设计输入
- **判定表**：对整数溢出、浮点编码版本、引用机制建立条件组合表
- **MC/DC**：确保 `version>1`、`overflow`、`depth>MAX` 等条件独立影响判定
- **稳定性校验**：统一使用 `hashlib.sha256(marshal.dumps(obj))` 验证同输入同输出

## 2. 用例设计摘要

共设计 24 个白盒用例（WB-01~WB-24），覆盖：

- 单例 fast path（None/True/False）
- `TYPE_INT` 与 `TYPE_LONG` 分界（`2**31-1` vs `2**31`）
- `w_float_bin` 与 `w_float_str` 的版本分叉
- ASCII 短/长字符串编码
- small tuple 边界（255 vs 256）
- set 排序确定性（bpo-37596）
- `TYPE_REF` 共享引用与循环引用拒绝
- 平台相关深度阈值（Windows 1000 / 其他 2000）

## 3. 主要发现

| 现象 | 技术归因 | 严重性 |
|------|----------|--------|
| `+0.0` 与 `-0.0` 哈希不同 | `w_float_bin` 保留 IEEE754 符号位 | 预期行为 |
| version=1 与 version=4 浮点字节流不同 | `w_float_str` vs `w_float_bin` | 预期行为 |
| 循环 list/dict 抛 ValueError | `w_ref` 检测递归 | 正确防护 |
| 同平台 NaN 多次 dumps 哈希一致 | `w_float_bin` 固定 bit pattern | 单平台稳定 |

## 4. 覆盖率与局限

- **已覆盖**：Python 层 pytest 可触达的全部主要写路径
- **未覆盖**：`TYPE_CODE`、`TYPE_SLICE`、`TYPE_FROZENDICT` 需要 version>=5/6 或 code 对象
- **C 层 gcov**：需在 Linux 自行编译带 `--coverage` 的 CPython；本仓库先以 Python 层分支断言（type code）间接验证
- **跨版本**：marshal 格式不保证跨大版本稳定，本套件默认 `version=4`

## 5. 局限性

1. 白盒用例通过 Python API 间接验证 C 分支，未直接插桩 `marshal.c`
2. `get_marshal_hash()` 未暴露 `version` 参数，版本相关测试使用 `marshal.dumps` 直调
3. Windows 与 Linux 深度阈值不同，WB-22 仅在对应平台触发
