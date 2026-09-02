"""SQLite persistence and SQL-file execution helpers."""

import re
import sqlite3
from pathlib import Path

import pandas as pd


def write_analysis_database(database_path, stations, users, valid_orders):
    """Replace the analytical database with clean master and valid order data."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_orders = valid_orders.copy()
    for column in ("start_time", "end_time", "order_date"):
        database_orders[column] = database_orders[column].dt.strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(database_path) as connection:
        stations.to_sql("stations", connection, if_exists="replace", index=False)
        users.to_sql("users", connection, if_exists="replace", index=False)
        database_orders.to_sql("charging_orders", connection, if_exists="replace", index=False)
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stations_id ON stations(station_id)")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_id ON users(user_id)")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_id ON charging_orders(order_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_station ON charging_orders(station_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON charging_orders(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_start ON charging_orders(start_time)")


def run_sql_file(connection, sql_path):
    """Execute named queries separated by ``-- query: name`` comments."""
    sql_text = sql_path.read_text(encoding="utf-8")
    blocks = re.split(r"^-- query:\s*([\w-]+)\s*$", sql_text, flags=re.MULTILINE)
    if len(blocks) < 3:
        raise ValueError(f"No named SQL query found in {sql_path}")

    results = {}
    for index in range(1, len(blocks), 2):
        name = blocks[index]
        query = blocks[index + 1].strip()
        if query:
            results[name] = pd.read_sql_query(query, connection)
    return results


def run_all_sql(database_path, sql_dir):
    """Run all phase-two SQL files and return their named result sets."""
    results = {}
    with sqlite3.connect(database_path) as connection:
        for sql_path in sorted(Path(sql_dir).glob("*.sql")):
            file_results = run_sql_file(connection, sql_path)
            results[sql_path.name] = file_results
    return results
