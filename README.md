# EV Charging Station Operations Analysis

一个基于 Python、Pandas 和 Matplotlib 的新能源汽车充电站运营分析项目。第一阶段聚焦可复现的数据结构、数据质量检查、业务指标和站点/时间分析，不包含 Web、数据库、机器学习或 Power BI。

## 项目背景与目标

项目实现以下分析链路：

```text
CSV 数据 → 读取 → 清洗与质量报告 → 指标计算 → 站点分析 → 时间分析 → CSV/图表输出
```

主要目标：

- 输出整体订单量、充电量、收入、客单价和平均充电时长。
- 比较站点订单、收入、单桩表现和设备时间利用率。
- 分析小时订单分布、工作日/周末差异和日趋势。
- 显式统计异常记录，不为提高指标而静默删除数据。

## 数据结构

### `data/stations.csv`

包含 `station_id`、`station_name`、`district`、`pile_count`、`fast_pile_count`、`slow_pile_count` 和 `open_date`。

### `data/charging_orders.csv`

包含 `order_id`、`station_id`、`user_id`、`start_time`、`end_time`、`charging_kwh`、`charging_fee`、`service_fee`、`total_amount` 和 `order_status`。

### `data/users.csv`

包含 `user_id`、`register_date` 和 `user_type`。

示例订单刻意包含少量重复、缺失、外键不匹配、异常时间、异常充电量、负金额及未完成状态，用于验证清洗逻辑。

## 数据清洗规则

核心运营指标只使用 `order_status = completed` 且通过关键校验的订单：

1. 重复 `order_id` 只保留首次记录，重复次数写入质量报告。
2. `station_id` 和 `user_id` 必须存在于对应主数据表。
3. 开始与结束时间转换为日期时间；无法解析的值视为缺失。
4. 缺失时间或 `end_time <= start_time` 的订单不进入核心分析。
5. `charging_kwh` 必须大于 0，`total_amount` 必须非负。
6. 逐字段统计缺失值；非关键缺失不会被无理由删除。
7. 取消或待处理订单保留在原始数据中，但不进入核心指标。

全部检查结果写入 `outputs/data_quality_report.csv`。

## 指标定义

整体指标包括：`total_orders`、`total_charging_kwh`、`total_revenue`、`avg_order_value` 和 `avg_charging_duration_hours`。

站点指标包括：订单量、充电量、收入、客单价、平均充电时长，以及：

- `orders_per_pile` = 站点订单数 ÷ 充电桩数量 ÷ 数据覆盖天数。
- `revenue_per_pile` = 站点收入 ÷ 充电桩数量。
- `equipment_utilization_rate` = 站点总实际充电小时 ÷（充电桩数量 × 24 × 数据覆盖天数）。

覆盖天数按每个站点首末有效订单日期计算并包含首尾。设备利用率会检查是否超出 0–1；展示结果限制在该区间，异常数量写入质量报告。

## 运行方式

```bash
python -m pip install -r requirements.txt
python analysis.py
```

输入和输出路径均基于 `analysis.py` 所在目录，可以从其他工作目录启动。

## 输出结果

- `outputs/station_summary.csv`：站点指标和利用率。
- `outputs/hourly_analysis.csv`：0–23 时订单量、充电量和收入。
- `outputs/data_quality_report.csv`：异常和缺失值统计。
- `outputs/charts/station_orders.png`：站点订单图。
- `outputs/charts/station_revenue.png`：站点收入图。
- `outputs/charts/hourly_orders.png`：小时订单分布图。

终端还会显示整体运营概览、站点排名、工作日/周末对比和日趋势。

## 项目结构

```text
ev-data-analysis/
├── data/
│   ├── stations.csv
│   ├── charging_orders.csv
│   └── users.csv
├── outputs/
│   ├── charts/
│   ├── station_summary.csv
│   ├── hourly_analysis.csv
│   └── data_quality_report.csv
├── screenshots/
├── analysis.py
├── requirements.txt
└── README.md
```
