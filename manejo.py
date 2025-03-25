import sqlite3
from datetime import datetime
# Conectar a la base de datos (se crea si no existe)
conn = sqlite3.connect('negocio.db')
cursor = conn.cursor()
# Función para agregar un producto
def agregar_producto(nombre, codigo_barras, stock):
    cursor.execute('''
    INSERT INTO productos (nombre, codigo_barras, stock)
    VALUES (?, ?, ?)
    ''', (nombre, codigo_barras, stock))
    conn.commit()
    print(f"Producto '{nombre}' agregado correctamente.")

# Función para registrar una venta
def registrar_venta(producto_id, cantidad):
    # Verificar si hay suficiente stock
    cursor.execute('SELECT stock FROM productos WHERE id = ?', (producto_id,))
    stock_actual = cursor.fetchone()[0]

    if stock_actual >= cantidad:
        # Registrar la venta
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO ventas (producto_id, cantidad, fecha)
        VALUES (?, ?, ?)
        ''', (producto_id, cantidad, fecha_actual))

        # Actualizar el stock
        nuevo_stock = stock_actual - cantidad
        cursor.execute('''
        UPDATE productos SET stock = ? WHERE id = ?
        ''', (nuevo_stock, producto_id))

        conn.commit()
        print(f"Venta registrada correctamente. Stock actualizado: {nuevo_stock}")
    else:
        print("No hay suficiente stock para realizar la venta.")

# Función para ver el stock actual
def ver_stock():
    cursor.execute('SELECT id, nombre, codigo_barras, stock FROM productos')
    productos = cursor.fetchall()
    for producto in productos:
        print(f"ID: {producto[0]}, Nombre: {producto[1]}, Código de barras: {producto[2]}, Stock: {producto[3]}")

# Función para ver el historial de ventas
def ver_ventas():
    cursor.execute('''
    SELECT v.id, p.nombre, v.cantidad, v.fecha
    FROM ventas v
    JOIN productos p ON v.producto_id = p.id
    ''')
    ventas = cursor.fetchall()
    for venta in ventas:
        print(f"Venta ID: {venta[0]}, Producto: {venta[1]}, Cantidad: {venta[2]}, Fecha: {venta[3]}")

# Agregar productos
agregar_producto("Laptop", "123456789012", 10)
agregar_producto("Mouse", "987654321098", 50)

# Registrar ventas
registrar_venta(1, 2)  # Vender 2 laptops
registrar_venta(2, 5)  # Vender 5 mouses

# Ver stock actual
print("\nStock actual:")
ver_stock()

# Ver historial de ventas
print("\nHistorial de ventas:")
ver_ventas()

# Cerrar la conexión a la base de datos
conn.close()        