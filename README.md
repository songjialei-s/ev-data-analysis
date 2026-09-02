# EV Charging Station Operations Analysis

一个使用 Python、Pandas、SQLite、SQL 和 Matplotlib 构建的新能源汽车充电站运营分析项目。项目从原始 CSV 出发，完成数据质量检查、有效订单筛选、多维运营分析、站点动态分类，并自动生成可追溯的业务结论。

当前为第二阶段版本，重点是 **SQL + 用户分析 + 收益分析 + 异常站点识别**。暂不包含 Power BI、Web、机器学习或预测模型。

## Analysis Workflow

```text
Raw CSV data
    ↓
Data validation and valid-order filtering
    ↓
Pandas operating metrics
    ↓
Clean data written to SQLite
    ↓
Five business-oriented SQL analyses
    ↓
User, revenue and station cross-analysis
    ↓
Dynamic station classification
    ↓
CSV reports, charts and business_insights.md
```

## Business Questions

项目主要回答：

- 哪些站点订单、收入、充电量和单桩效率最高？
- 哪些站点设备较多但需求和利用率偏低？
- 哪些站点负载和单桩需求较高，可能需要评估扩容？
- 高订单站点是否也具有较高收入效率？
- 用户订单和收入主要由哪些用户贡献？
- 高频用户对订单和收入的贡献比例是多少？
- 充电需求集中在哪些小时？工作日和周末有何差异？
- 收入主要来自充电费还是服务费？
- 应对不同类型站点采取扩容、运营优化还是稳定观察？

## Dataset

仓库包含合成示例数据，用于演示完整分析方法，不代表真实企业经营数据：

- `data/stations.csv`：8 个站点，包含区域、总桩数、快慢充桩数和开站日期。
- `data/users.csv`：20 个用户，包含注册日期和用户类型。
- `data/charging_orders.csv`：190 条原始订单，其中 180 条为有效完成订单。

有效订单覆盖 30 天、多个站点和用户，并保留合理的用户频次、站点需求及早晚高峰差异。额外异常记录用于测试重复订单、主数据不匹配、时间错误、金额错误、费用不一致、缺失值和未完成状态。

## Data Quality Rules

核心分析只使用 `order_status = completed` 且通过关键检查的订单：

1. 重复 `order_id` 仅保留首次记录。
2. `station_id` 与 `user_id` 必须存在于对应主数据表。
3. `start_time`、`end_time` 必须可解析，且结束时间晚于开始时间。
4. `charging_kwh` 必须大于 0，`total_amount` 必须非负。
5. `charging_fee + service_fee` 与 `total_amount` 的差异不得超过 0.01。
6. 取消或待处理订单不进入核心运营指标。
7. 所有异常先统计到 `outputs/data_quality_report.csv`，不静默删除。

SQLite 的 `charging_orders` 表只保存清洗后的有效订单，原始 CSV 始终保留。

## Metrics

### Overall and User Metrics

- 总订单量、总充电量、总收入、平均客单价和平均充电时长。
- 注册用户、活跃用户、活跃用户平均订单数和平均消费金额。
- 用户订单、收入、充电量和客单价排名。

用户充电频次分层根据当前 180 条有效订单设置：

- `low_frequency`：1–5 单。
- `medium_frequency`：6–11 单。
- `high_frequency`：12 单及以上。

该阈值适用于当前演示样本；替换真实数据后应按业务周期和订单分布重新评估。

### Station Metrics

- `orders_per_pile` = 站点订单数 ÷ 充电桩数量 ÷ 数据覆盖天数。
- `revenue_per_pile` = 站点收入 ÷ 充电桩数量。
- `revenue_per_kwh` = 站点收入 ÷ 总充电量。
- `equipment_utilization_rate` = 实际充电小时 ÷（充电桩数量 × 24 × 覆盖天数）。

利用率会检查是否超出 0–1，展示值限制在合理区间，并将异常数量写入质量报告。

## SQL Analysis

程序将清洗后的数据写入 `ev_charging.db`，建立 `stations`、`users` 和 `charging_orders` 三张表。SQL 不是展示性代码，每个文件都对应业务问题：

| SQL | 业务用途 |
| --- | --- |
| `sql/01_station_analysis.sql` | 站点订单、收入、充电量与单桩效率 |
| `sql/02_time_analysis.sql` | 小时订单分布与工作日/周末差异 |
| `sql/03_user_analysis.sql` | 用户消费排名与频次分层 |
| `sql/04_revenue_analysis.sql` | 收入构成、站点收益效率和收益模式 |
| `sql/05_anomaly_analysis.sql` | 动态识别资源闲置、扩容机会和收益效率问题 |

`analysis.py` 每次运行都会执行并验证全部命名 SQL 查询。

## Station Classification

站点分类由中位数和上四分位数动态计算，不使用站点名称或手工标签：

- `efficient_core_station`：单桩需求、单桩收入和总收入均达到同业中位数。
- `high_load_expansion_candidate`：设备利用率位于高位且单桩需求不低于中位数。
- `low_utilization_optimization`：单桩需求和设备利用率均低于中位数。
- `stable_station`：暂未出现明显高负载或低利用特征。

## Business Insights

当前合成样本的自动分析结论包括：

- 180 条有效订单，20 名活跃用户，总充电量 7,449.0 kWh，总收入 10,893.25。
- Lakeside Community Station 的订单、收入、设备利用率和单桩收入均最高。
- 5 名高频用户贡献 45.6% 的订单和 44.4% 的收入。
- 高需求开始时段为 07:00、08:00 和 17:00。
- 周末日均 8 单，工作日日均 5 单。
- Central Plaza Station 和 Lakeside Community Station 被识别为高负载扩容评估对象。
- Tech Park、South Railway、Airport Service 和 East Logistics 被识别为低利用率优化对象。

完整、每次运行自动更新的结论见 `outputs/business_insights.md`。由于使用合成数据，建议仅演示分析框架；真实投资决策仍需结合排队、设备可用率和周边客流数据验证。

## Run

```bash
python -m pip install -r requirements.txt
python analysis.py
```

所有路径均基于 `analysis.py` 所在目录，因此可以从其他工作目录启动。

## Outputs

第一阶段输出继续保留，并新增第二阶段结果：

- `outputs/station_summary.csv`
- `outputs/hourly_analysis.csv`
- `outputs/data_quality_report.csv`
- `outputs/user_summary.csv`
- `outputs/revenue_analysis.csv`
- `outputs/station_classification.csv`
- `outputs/business_insights.md`
- `outputs/charts/user_order_distribution.png`
- `outputs/charts/station_efficiency.png`
- `outputs/charts/revenue_comparison.png`

## Project Structure

```text
ev-data-analysis/
├── data/
│   ├── stations.csv
│   ├── charging_orders.csv
│   └── users.csv
├── sql/
│   ├── 01_station_analysis.sql
│   ├── 02_time_analysis.sql
│   ├── 03_user_analysis.sql
│   ├── 04_revenue_analysis.sql
│   └── 05_anomaly_analysis.sql
├── outputs/
│   ├── charts/
│   ├── station_summary.csv
│   ├── hourly_analysis.csv
│   ├── data_quality_report.csv
│   ├── user_summary.csv
│   ├── revenue_analysis.csv
│   ├── station_classification.csv
│   └── business_insights.md
├── analysis.py
├── db.py
├── ev_charging.db
├── requirements.txt
└── README.md
```
