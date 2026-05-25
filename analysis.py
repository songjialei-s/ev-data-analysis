import pandas as pd
import matplotlib.pyplot as plt

# 新能源汽车充电数据
data = {
    "city":["Beijing","Shanghai","Shenzhen","Guangzhou","Hangzhou"],
    "charging_count":[3200,2800,2500,2100,1800],
    "avg_power_kw":[60,55,58,52,50],
    "daily_orders":[1200,980,860,720,650]
}

# 创建DataFrame
df=pd.DataFrame(data)

print("Basic Data:")
print(df)

print("\nStatistics:")
print(df.describe())

# 利用率分析
df["utilization_rate"]=(
        df["daily_orders"]/
        df["charging_count"]
)

print("\nData with Utilization Rate:")
print(df)

# 排序分析
top_city=df.sort_values(
    by="utilization_rate",
    ascending=False
)

print("\nTop Utilization Ranking:")
print(
    top_city[
        ["city","utilization_rate"]
    ]
)

# 图表
plt.figure(figsize=(8,5))

plt.bar(
    df["city"],
    df["charging_count"]
)

plt.title(
    "EV Charging Distribution"
)

plt.xlabel("City")
plt.ylabel("Charging Count")

plt.savefig(
    "charging_distribution.png"
)

plt.show()