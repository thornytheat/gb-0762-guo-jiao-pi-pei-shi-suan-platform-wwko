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
| M8 烘干炉可领台账 | 在烘暂扣、复称先配、分账对账、并发防超领 | `/kiln`、`/api/kiln/*` | `app/modules/kiln/service.py` `app/modules/kiln/reconcile.py` `app/modules/kiln/store.py` | `tests/test_kiln.py` |

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
| TRAP-20 | 交班抢开秤，下一炉未出炉 | 把预计出炉量计入可领 | 在烘炉次按投炉量暂扣，预计量永不入账；只有复称验方相符才增加可领 | `app/modules/kiln/service.py` | `tests/test_kiln.py::test_drying_expected_output_is_never_booked` |
| TRAP-21 | 两张领料单同时提交 | 读-改-写竞争，领超同一炉 | SQLite `BEGIN IMMEDIATE` 串行写事务，余量判定后再带 `weighed_g-drawn_g>=?` 条件更新 | `app/modules/kiln/store.py` | `tests/test_kiln.py::test_two_simultaneous_orders_cannot_overdraw_one_furnace` |
| TRAP-22 | 出炉登记成功后已被领用，客户端超时重试 | 复称量二次计入可领 | 非 DRYING 炉次的同参登记原样回放：`created=false`、本次增量 `released_g=0`，不动 `drawn_g` | `app/modules/kiln/service.py` | `tests/test_kiln.py::test_register_retry_after_issue_does_not_double_count` |
| TRAP-23 | 水分蒸发与干物损耗混算、用小数对账 | 浮点误差且无法定位不符账别 | 沿用万分克整数，水账/干物账分列；损耗上限用叉乘判定，不符炉次 HOLD 并 `PAUSED` | `app/modules/kiln/reconcile.py` | `tests/test_kiln.py::test_water_and_dry_ledgers_flag_different_failures` |

## 对账规则

- 脏样本 16 条正文 = 7 采信 + 7 隔离 + 1 重复表头 + 1 空行。
- PJ-01 和 PJ-02 各取 5000 g。干物 4000+5000=9000 g，凝胶度 (4000×120+5000×180)/9000=153.333 SAG。
- 计划 10000 g = 领用 10000 g + 缺口 0 g。采信库存 27000 g = 领用 10000 g + 期末 17000 g。

试算库存源于输入快照。实际出库和电子签章由生产系统处理。本项目使用输入日期裁决有效期。

## 烘干炉台账规则（M8）

同批果胶可分多炉烘干。台账持久化在归档目录的 `kiln.sqlite3`（标准库 SQLite），与内容寻址的试算 JSON 互不影响。

- 可领口径：`可领 = 未送烘余料 + Σ 已复称且对账相符炉次的(实重−已领)`。在烘炉次按投炉量暂扣（`IN_DRYER`），预计出炉量不计入；对账不符炉次整炉暂扣（`RECONCILE_FAILED` / `issuance=PAUSED`），指定该炉开单返回 `KILN_LOAD_NOT_ISSUABLE`。
- 开秤顺序：不指定炉次时，已复称炉次按炉序先配，不足再用未送烘余料。整单不足返回 `KILN_SHORTAGE` 并带 `available_g/short_g`，事务回滚、绝不部分扣减。
- 并发：领料、送烘、登记均在 `BEGIN IMMEDIATE` 事务内完成“读余量→判定→条件扣减”，配合 `busy_timeout`；同一炉被两张单同时开秤也不会领超。领料单号 `req` 作幂等键，并发同号只创建一单。
- 出炉验方：以投炉湿重和来料水分为期初，复称实重与实测水分为期末，按万分克整数分两账：
  - 水账：`水分蒸发 = 投炉水 − 出炉水`，为负判 `WATER_GAIN`；
  - 干物账：`干物损耗 = 入炉干物 − 出炉干物`，为负判 `DRY_GAIN`，损耗率超过 `tolerance_bp`（默认 50‱，即 0.5%）判 `DRY_LOSS_OVER_TOLERANCE`。
  - 任一账不平即 `HOLD`、暂停签发；两账结果与原因码随炉次保存。
- 幂等：开批（同参）、带号送烘、出炉登记、带号领料重试均回放首次结果（HTTP 200，`created=false`），不重复改动余量；同号异参返回 409。
- 演示情景：`POST /api/kiln/demo` 或 `/kiln` 页「载入题面情景」建 `PJ-KILN-DEMO`：30000 g @20% 分两炉各 10000 g，F1 出 8030 g @0.50%（蒸发 1959.8500 g、干损 10.1500 g ≈13‱，相符），F2 在烘，余料 10000 g；可领 18030 g、暂扣 10000 g。
