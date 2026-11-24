# 深度登记 果胶批配试算台

- 规模：中型
- 核心规则：离散称量同时验湿重、干重与凝胶区间，先最少批再裁决到期先后。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 批次化验采信 | 扫描原件与冲突 | POST /api/assay | `app/modules/assay/service.py` | `tests/test_assay.py` |
| M2 干物折算 | 检查过期与干物库存 | POST /api/dry | `app/modules/dry/service.py` | `tests/test_dry.py` |
| M3 目标区间验方 | 输入提案并查约束 | POST /api/formula | `app/modules/formula/service.py` | `tests/test_formula.py` `tests/test_plan_contract.py` |
| M4 整数配料寻优 | 按称量刻度求组合 | POST /api/blend | `app/modules/blend/search.py` | `tests/test_blend.py` `tests/test_solver_oracle.py` |
| M5 领用与余量核算 | 核对库存、领用和缺口 | POST /api/stock | `app/modules/stock/balance.py` | `tests/test_stock.py` |
| M6 批次留档复跑 | 留档并验证重复提交 | POST /api/batches | `app/modules/batches/storage.py` | `tests/test_batches.py` |
| M7 试配证据签发 | 复核试配状态并下载 | GET /api/certificate/<id> | `app/modules/certificate/service.py` | `tests/test_certificate.py` |

## 陷阱登记

| TRAP | 原件现象 | 朴素错误 | 处理 | 位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-02 | 化验首列有 BOM | 批号列未识别 | 移除首 BOM | `app/modules/assay/reader.py` | `tests/test_assay.py::test_bom_and_split_header` |
| TRAP-04 | 化验接表 | 表头进清单 | 统计分段 | `app/modules/assay/reader.py` | `tests/test_assay.py::test_bom_and_split_header` |
| TRAP-05 | PJ-10 附多列 | 误读化验结果 | 逐行隔离 | `app/modules/assay/reader.py` | `tests/test_assay.py::test_extra_column_keeps_line` |
| TRAP-06 | PJ-01 全角千分位 | 原料重量读错 | NFKC 与格式校验 | `app/modules/assay/units.py` | `tests/test_assay.py::test_fullwidth_thousands_and_decimal_contract` |
| TRAP-07 | 哨兵和空格 | 当成零水分 | 稳定原因区分 | `app/reasons.py` | `tests/test_assay.py::test_blank_and_sentinel_are_distinct` |
| TRAP-10 | 按干物计算小数 | 浮点或提前取整 | 万分克整数累计 | `app/modules/dry/weights.py` | `tests/test_dry.py::test_mass_exact_with_fractional_moisture` |
| TRAP-14 | PJ-06 双化验冲突 | 后写覆盖 | 两个原件行均隔离 | `app/modules/assay/service.py` | `tests/test_assay.py::test_contradictory_assays_disable_both` |
| TRAP-15 | PJ-02 克和千克混写 | 重复入库 | 规范成克后判同批 | `app/modules/assay/units.py` | `tests/test_assay.py::test_kg_is_normalized_before_duplicate_detection` |
| TRAP-19 | PJ-02 与 PJ-04 均可配 | 随记录顺序 | 先批数再到期，再按批号 | `app/modules/blend/search.py` | `tests/test_blend.py::test_conflicting_valid_choices_resolve_by_expiry` |

## 对账规则

- 脏样本 16 条正文 = 7 采信 + 7 隔离 + 1 重复表头 + 1 空行。
- PJ-01 和 PJ-02 各取 5000 g。干物 4000+5000=9000 g，凝胶度 (4000×120+5000×180)/9000=153.333 SAG。
- 计划 10000 g = 领用 10000 g + 缺口 0 g。采信库存 27000 g = 领用 10000 g + 期末 17000 g。

试算库存源于输入快照。实际出库和电子签章由生产系统处理。本项目使用输入日期裁决有效期。
