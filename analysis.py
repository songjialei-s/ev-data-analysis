import pandas as pd

data = {
    "city":["Beijing","Shanghai","Shenzhen"],
    "charging_count":[3200,2800,2500]
}

df = pd.DataFrame(data)

print(df)
print(df.describe())