import pymysql
import os

db_url = os.getenv(
    'DATABASE_URL', 'mysql+pymysql://root:root@127.0.0.1:3306/')
# Connect to the MySQL server (without specifying a database)
try:
    connection = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='root'
    )
    with connection.cursor() as cursor:
        cursor.execute("CREATE DATABASE IF NOT EXISTS med_app;")
    connection.commit()
    print("Database 'med_app' checked/created successfully.")
except Exception as e:
    print("Error creating database:", e)
finally:
    if 'connection' in locals() and connection.open:
        connection.close()
