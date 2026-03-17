import sqlite3
import pandas as pd

# conectar base
conn = sqlite3.connect("gestion_comercial.db")

# leer tabla
df = pd.read_sql_query("SELECT * FROM productos", conn)

# exportar a excel
df.to_excel("productos_clf.xlsx", index=False)

conn.close()