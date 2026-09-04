# Power BI Data Model and Report Design

## Scope

第三阶段提供 Power BI 可直接导入的标准化 CSV 数据层、星型模型关系建议、基础 DAX 和三页报表设计。仓库不包含或伪造 `.pbix` 文件。站点分类、设备利用率、单桩订单量等指标直接复用第二阶段 Python/SQL 结果，不在 Power BI 中重新定义。

## Star Schema

推荐模型：

```text
dim_station (1) ──────── (*) fact_charging_orders (*) ──────── (1) dim_user
                                  (*)
                                   │
                                   │
                                  (1)
                               dim_date

station_kpi：站点粒度的第二阶段已计算指标，按 station_id 与 dim_station 关联。
```

关系设置：

| 一端 | 多端 | 基数 | 筛选方向 | 是否活动 |
| --- | --- | --- | --- | --- |
| `dim_station[station_id]` | `fact_charging_orders[station_id]` | 一对多 | 单向 | 是 |
| `dim_user[user_id]` | `fact_charging_orders[user_id]` | 一对多 | 单向 | 是 |
| `dim_date[date]` | `fact_charging_orders[date]` | 一对多 | 单向 | 是 |
| `dim_station[station_id]` | `station_kpi[station_id]` | 一对一 | 单向 | 是 |

事实表 `fact_charging_orders` 记录业务事件，一行代表一笔清洗后的有效完成订单。

- `dim_station` 描述在哪里充电。
- `dim_user` 描述谁在充电，并复用第二阶段用户频次分层。
- `dim_date` 描述订单在哪一天发生，可作为统一日期筛选器。
- `station_kpi` 保存第二阶段已确认的站点粒度派生指标与分类。

建议在 Power BI 中将 `dim_date` 标记为日期表，以 `dim_date[date]` 作为日期列。隐藏事实表中的外键、重复展示字段以及技术列，只让业务用户看到维度属性和度量值。

## Data Files

Power BI 从 `outputs/powerbi/` 导入：

| 文件 | 粒度 | 用途 |
| --- | --- | --- |
| `fact_charging_orders.csv` | 一行一笔有效订单 | 订单、充电量、收入和时长聚合 |
| `dim_station.csv` | 一行一个站点 | 站点名称、区域和设备属性 |
| `dim_user.csv` | 一行一个用户 | 用户类型和频次分层 |
| `dim_date.csv` | 一行一个自然日 | 年月、星期和周末标记 |
| `station_kpi.csv` | 一行一个站点 | 站点效率指标和动态分类 |
| `model_validation.csv` | 一行一个检查 | 导入前完整性验证结果 |

导入后检查数据类型：日期列使用 Date，时间戳使用 Date/Time，`is_weekend` 使用 True/False，订单数和日期序号使用 Whole number，金额、kWh、时长和比率使用 Decimal number。

## Measures

基础 DAX 建议集中放在单独的 Measures 表中：

```DAX
Total Orders =
DISTINCTCOUNT(fact_charging_orders[order_id])
```

```DAX
Total Revenue =
SUM(fact_charging_orders[total_amount])
```

```DAX
Total Charging kWh =
SUM(fact_charging_orders[charging_kwh])
```

```DAX
Charging Fee Revenue =
SUM(fact_charging_orders[charging_fee])
```

```DAX
Service Fee Revenue =
SUM(fact_charging_orders[service_fee])
```

```DAX
Service Fee Share =
DIVIDE([Service Fee Revenue], [Total Revenue])
```

```DAX
Active Users =
DISTINCTCOUNT(fact_charging_orders[user_id])
```

```DAX
Average Order Value =
DIVIDE([Total Revenue], [Total Orders])
```

```DAX
Average Charging Duration =
AVERAGE(fact_charging_orders[charging_duration_hours])
```

```DAX
Revenue per kWh =
DIVIDE([Total Revenue], [Total Charging kWh])
```

```DAX
Weekday Orders =
CALCULATE(
    [Total Orders],
    dim_date[is_weekend] = FALSE()
)
```

```DAX
Weekend Orders =
CALCULATE(
    [Total Orders],
    dim_date[is_weekend] = TRUE()
)
```

复杂站点分类、`equipment_utilization_rate`、`orders_per_pile` 和 `revenue_per_pile` 直接使用 `station_kpi` 中的结果。不要为了展示 DAX 再写一套不同计算逻辑。

## Shared Report Controls

三页统一使用以下筛选器：

- 日期范围：`dim_date[date]`
- 区域：`dim_station[district]`
- 站点：`dim_station[station_name]`
- 用户类型：`dim_user[user_type]`

站点分类筛选器只放在 Page 2，用户分层筛选器只放在 Page 3。颜色建议固定：高效核心站点用绿色、高负载扩容候选用橙色、低利用率待优化用红色、普通稳定站点用蓝灰色。

## Page 1 — Operations Overview

### Goal

快速回答整体业务规模、趋势、需求时段和站点订单分布。

### KPI Cards

- Total Orders
- Total Charging kWh
- Total Revenue
- Active Users
- Average Order Value
- Average Charging Duration

金额保留两位小数，充电量保留一位小数，时长以小时显示两位小数。卡片应响应日期、区域、站点和用户类型筛选器。

### Visuals

| 图表 | 字段设计 | 回答的业务问题 |
| --- | --- | --- |
| 日期订单趋势 | X：`dim_date[date]`；Y：`[Total Orders]` | 订单需求是否随日期上升、下降或波动？ |
| 日期收入趋势 | X：`dim_date[date]`；Y：`[Total Revenue]` | 收入趋势是否与订单趋势一致？ |
| 小时订单分布 | X：`fact_charging_orders[hour]`；Y：`[Total Orders]` | 高峰时段在哪里，何时可能出现容量压力？ |
| 工作日 vs 周末 | X：`dim_date[is_weekend]`；Y：`[Total Orders]` | 周末和工作日需求结构是否不同？ |
| 站点订单排名 | Y：`dim_station[station_name]`；X：`[Total Orders]` | 哪些站点承担最多订单？ |

页面布局建议：顶部一行放六张 KPI 卡；中部并排放日期订单和日期收入趋势；底部放小时分布、工作日/周末以及站点排名。站点排名使用横向条形图并按订单降序。

## Page 2 — Station Operations

### Goal

判断哪些站点高效、哪些存在负载压力、哪些需要优先优化资源利用。

### Visuals

| 图表 | 字段设计 | 回答的业务问题 |
| --- | --- | --- |
| 站点订单量排名 | 站点名称 + `station_kpi[order_count]` | 哪些站点流量最高？ |
| 站点收入排名 | 站点名称 + `station_kpi[revenue]` | 哪些站点创造最多收入？ |
| 单桩订单量 | 站点名称 + `station_kpi[orders_per_pile]` | 哪些站点每台设备承担更多订单？ |
| 单桩收入 | 站点名称 + `station_kpi[revenue_per_pile]` | 哪些站点设备收益效率更高？ |
| 设备利用率 | 站点名称 + `station_kpi[equipment_utilization_rate]` | 哪些站点设备使用时间更充分？ |
| 站点分类 | `station_kpi[station_classification]` + 站点数 | 四类站点的数量结构如何？ |
| 站点效率交叉分析 | 散点图，见下方 | 哪些站点同时具有效率、收益或扩容信号？ |

散点图设计：

- X 轴：`station_kpi[equipment_utilization_rate]`
- Y 轴：`station_kpi[revenue_per_pile]`
- 点大小：`station_kpi[order_count]`
- 点标签：`station_kpi[station_name]`
- 图例：`station_kpi[station_classification]`

该图同时观察设备使用程度、单桩收益和订单规模。不要仅凭单一坐标决定扩容；站点类型继续使用 Python 已计算结果。

分类重点：

- `efficient_core_station`：高效核心站点
- `high_load_expansion_candidate`：高负载扩容候选
- `low_utilization_optimization`：低利用率待优化
- `stable_station`：普通稳定站点

## Page 3 — Users and Revenue

### Goal

分析用户价值、收入集中度、收费构成以及站点收益质量。

### Visuals

| 图表 | 字段设计 | 回答的业务问题 |
| --- | --- | --- |
| 用户分层分布 | `dim_user[user_segment]` + 用户数 | 低频、中频和高频用户各有多少？ |
| 高频用户订单贡献 | 高频用户订单 / Total Orders | 订单是否集中在高频用户？ |
| 高频用户收入贡献 | 高频用户收入 / Total Revenue | 收入是否依赖少数高频用户？ |
| 用户消费排名 | `dim_user[user_id]` + `[Total Revenue]` | 哪些用户贡献最多收入？ |
| 收入结构 | `[Charging Fee Revenue]` 与 `[Service Fee Revenue]` | 收入主要来自充电费还是服务费？ |
| 各站点平均订单金额 | 站点名称 + `[Average Order Value]` | 哪些站点客单价更高？ |
| 每 kWh 收入 | 站点名称 + `[Revenue per kWh]` | 不同站点每单位电量收入有何差异？ |

高频用户贡献用于判断订单与收入是否集中在少数用户。收入结构用于判断充电费和服务费的构成，不将总收入与两个组成部分同时堆叠，避免重复表达。

## Confirmed Phase-Two Results

第三阶段展示必须保留以下已验证结果：

- 8 个站点。
- 20 个活跃用户。
- 180 条有效完成订单。
- 总充电量 7,449.0 kWh。
- 总收入 10,893.25。
- 高频用户 5 名。
- 高频用户订单贡献 45.6%。
- 高频用户收入贡献 44.4%。
- 高峰时段为 07:00、08:00、17:00。

站点分类：

- 高负载扩容候选：Central Plaza Station、Lakeside Community Station。
- 高效核心站点：Riverside Station。
- 低利用率待优化：Tech Park Station、South Railway Station、Airport Service Station、East Logistics Station。
- 普通稳定站点：University Town Station。

## Build Checklist

1. 从 `outputs/powerbi/` 导入五张业务表。
2. 设置正确的数据类型。
3. 建立并检查星型模型关系。
4. 将 `dim_date` 标记为日期表。
5. 新建 Measures 表并加入基础 DAX。
6. 使用 `station_kpi` 中的既有复杂指标和分类。
7. 按三页规划建立视觉对象和筛选器。
8. 将 `model_validation.csv` 中所有检查保持为 `PASS` 后再刷新报表。
