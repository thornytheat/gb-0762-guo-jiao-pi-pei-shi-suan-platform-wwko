# 化验批、试配约束与库存定义

`assays.csv` 必填 `lot,expires,stock,unit,moisture_pct,gel_sag`，列序可变。批号为原形字符串。有效期记日历日期 `YYYY-MM-DD`，到期日当日仍可用。日粒度按试配记录所在工厂日历解释。`stock` 为 g 或 kg，统一成整克。水分按百分数录入，保留至 0.01%；凝胶度为 SAG，可录至千分之一。UTF-8 允许首行 BOM。数值接受合法千分位及全角数字。空单元格、空值哨兵、JSON null 分别由相应校验识别。

空文件、全空行、仅表头分别有 `EMPTY_FILE`、`BLANK_FILE`、`HEADER_ONLY`。原件行号是记录起始物理行，原值保留。相同批号按归一日期、库存、水分、凝胶度比较，相同保留首个来源，冲突整组隔离。每份 CSV 至多 250,000 字符。

计划 `as_of` 为试配日，`target_g` 和 `step_g` 为正整数。前者必须可被后者整除，且领用步数最多 60。`dry_min_g` 为干物下限，`gel_low_sag` 和 `gel_high_sag` 均含界。可选 `proposal` 是批号到非负整克的映射。公式用万分克整数累计干物，乘毫 SAG 得凝胶矩，精确叉乘验上下限，展示值四舍五入为 3 位小数。

寻优用到期日、批号排序，以最少领用批为首要目标，同批数优先最大化较早批次的用量。超出 14 个可用整步批或 300,000 状态上限时报错。不可行时整单留待处理，库存保持原量。结算库存包含已采信但过期与不足整步的库存，冲突批计入隔离清单。

同份化验文本和同参数计算同一 SHA-256 标识。运行保存源摘要、计划、候选提案、UTC 建立时间、耗时、规则和逐阶段证据。归档经同目录临时文件写入和原子发布，重复提交返回既有快照。证据摘要以排序键、UTF-8 和紧凑 JSON 复算。

## 烘干炉台账实体（`/kiln`，SQLite `kiln.sqlite3`）

- `kiln_batches`：`batch` 批号主键；`stock_g` 整批湿重；`moisture_bp` 来料水分（万分比，20.00%=2000）；`remainder_g` 未送烘余料，送烘时扣减，领料末位扣减。
- `kiln_loads`（炉次）：`load` 炉次号主键（不传则 `<批号>-F<两位炉序>`）；`batch/seq`；`charged_g` 投炉湿重；`moisture_in_bp` 投料时来料水分快照；`status ∈ DRYING|WEIGHED|HOLD`；`weighed_g/moisture_out_bp` 出炉复称实重与实测水分；`drawn_g` 该炉累计已领；`ledger_json` 水账/干物账证据。
- `kiln_requisitions` / `kiln_req_lines`：领料单（`req` 幂等键、`amount_g`、可选 `load_ref`）与分摊行；行 `source` 为炉次号或 `REMAINDER`。
- 试算视图 `GET /api/kiln/batches/<batch>` 与 `/kiln?batch=<batch>`：每炉给 `available_g/withheld_g/availability_code/issuance`。原因码：`WEIGHED`（已复称可领）、`REMAINDER`（未送烘照常可领）、`IN_DRYER`（在烘暂扣，预计出炉量不入账，附 `reason_code=EXPECTED_OUTPUT_NOT_BOOKED`）、`RECONCILE_FAILED`（对账不符，`issuance=PAUSED`，并带 `reconcile_codes`）。
- 接口：`POST /api/kiln/batches` 开批；`POST /api/kiln/loads` 送烘；`POST /api/kiln/loads/<load>/register` 复称验方（可传 `tolerance_bp`）；`POST /api/kiln/requisitions` 领料（可传 `req`、`load`）；`GET /api/kiln/batches` 列表；`POST /api/kiln/demo` 题面情景。写接口新鲜创建返回 201，幂等回放返回 200 且 `created=false`；冲突 409，缺料/状态不允许 422，找不到 404。错误体为 `{"code", ...明细}`，缺料含 `available_g/need_g/short_g`。
