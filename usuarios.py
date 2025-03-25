
import sqlite3
def get_db_connection():
    conn = sqlite3.connect('negocio.db')
    conn.row_factory = sqlite3.Row
    return conn
def agregar_usuario_ejemplo():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO usuarios (username, password, role)
        VALUES (?, ?, ?)
    ''', ('nahun', 'Rocko345', 'admin'))
    cursor.execute('''
        INSERT INTO usuarios (username, password, role)
        VALUES (?, ?, ?)
    ''', ('eze', 'ona777', 'user'))
    conn.commit()
    conn.close()

# Llamar a la función para agregar usuarios de ejemplo (solo una vez)
agregar_usuario_ejemplo()