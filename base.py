import sqlite3
from datetime import datetime
import sqlite3


# Conectar a la base de datos
conn = sqlite3.connect('negocio.db')
cursor = conn.cursor()

# Verificar si las columnas ya existen
cursor.execute('PRAGMA table_info(ventas)')
columns = cursor.fetchall()
column_names = [column[1] for column in columns]

if 'tipo_pago' not in column_names:
    cursor.execute('ALTER TABLE ventas ADD COLUMN tipo_pago TEXT')
if 'dni_cliente' not in column_names:
    cursor.execute('ALTER TABLE ventas ADD COLUMN dni_cliente TEXT')

conn.commit()
conn.close()

print("Columnas 'tipo_pago' y 'dni_cliente' agregadas correctamente.")