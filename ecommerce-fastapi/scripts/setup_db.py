"""Create the ecom_fastapi_dev database if it doesn't exist."""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect(
    host="localhost",
    dbname="ecom_prod_catalog",
    user="vikas",
    password="kalika1667",
    port=5432,
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

cur.execute("SELECT 1 FROM pg_database WHERE datname = 'ecom_fastapi_dev'")
if cur.fetchone():
    print("Database ecom_fastapi_dev already exists.")
else:
    cur.execute("CREATE DATABASE ecom_fastapi_dev")
    print("Database ecom_fastapi_dev created.")

cur.close()
conn.close()
