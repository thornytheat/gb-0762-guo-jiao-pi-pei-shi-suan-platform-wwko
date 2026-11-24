# 果胶批配试算台

原料工程师可检查化验单、核算干物、验现有配方、按离散称量寻优并留档。首页展示配方余量轨。顶部横向工序和左侧导航可直达各环节。来料争议样本包含互相矛盾的化验记录与不可试配的原提案。

`docker compose up --build` 后访问 `http://localhost:18461/`。本地安装 `pip install -r requirements.txt` 后，执行 `python -m flask --app app.main run --port=18461`，使用 `pytest -q` 验收。`PECTIN_ARCHIVE` 是归档目录，Compose 将它保存在命名卷中。

预览和留档 API 接收 `{"sample":"dirty"}`、`{"sample":"clean"}` 或 `{ "assays":"CSV", "plan":{...}, "proposal":{"批号":2500} }`。计划示例见 `sample_data/dirty/trial.json`。从留档页提交，再到试配签发页审读和下载证据。

## 烘干炉可领台账

同批果胶分炉烘干时，不必等整批烘完：**已复称且对账相符的炉次先配，未送烘余料照常可领；在烘炉次按投炉量暂扣，预计出炉量不计入可领库存；对账不符的炉次暂停签发。** 打开 `/kiln`（或试算页导航里的「烘干试算」，首页库存轨下方也有汇总）可看每炉可领/暂扣克数与原因，并直接送烘、做出炉复称验方、开领料单；「载入题面情景」会建好「首炉已复称、次炉在烘、余料可领」的样例。

- 出炉复称按实重与实测水分，用万分克整数分别结**水账**（水分蒸发）和**干物账**（干物损耗，默认容忍 50‱）；任一账不平该炉转 `HOLD` 并暂停签发。
- 领料/登记均为事务操作：两张单同时提交也不会领超同一炉；出炉登记或领料单按原号重试只回放首次结果，不重复计入可领量。
- API：`POST /api/kiln/batches`、`POST /api/kiln/loads`、`POST /api/kiln/loads/<炉号>/register`、`POST /api/kiln/requisitions`、`GET /api/kiln/batches/<批号>`、`POST /api/kiln/demo`。台账存于归档目录的 `kiln.sqlite3`。

- [模块与复算](docs/DEPTH.md)
- [数据定义](docs/DATA-DICTIONARY.md)
