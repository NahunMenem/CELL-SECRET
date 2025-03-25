from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from datetime import datetime, timedelta
import pytz
import os
from flask import send_file
from psycopg2.extras import DictCursor

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Necesario para usar sesiones

# Configuración de la conexión a PostgreSQL
def get_db_connection():
    conn = psycopg2.connect(
        dbname="negocio_54gh",
        user="negocio_54gh_user",
        password="lwclY7Am6oVOImETtdFwjbSRvRFXO6yr",
        host="dpg-cv8a1da3esus73ch8mrg-a.oregon-postgres.render.com",
        port="5432"
    )
    conn.cursor_factory = DictCursor
    return conn

# Crear tabla de usuarios si no existe
def crear_tabla_usuarios():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios_secret (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')
    conn.commit()
    conn.close()

# Llamar a la función para crear la tabla de usuarios al iniciar la aplicación
crear_tabla_usuarios()

# Función para crear la tabla `equipos` si no existe
def crear_tabla_equipos():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipos_secret (
            id SERIAL PRIMARY KEY,
            tipo_reparacion TEXT NOT NULL,
            marca TEXT NOT NULL,
            modelo TEXT NOT NULL,
            tecnico TEXT NOT NULL,
            monto REAL NOT NULL,
            nombre_cliente TEXT NOT NULL,
            telefono TEXT NOT NULL,
            nro_orden TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Llamar a la función para crear la tabla al iniciar la aplicación
crear_tabla_equipos()

# Proteger rutas que requieren autenticación
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Debes iniciar sesión para acceder a esta página.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta principal (redirige al login si no está autenticado)
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('inicio'))  # Redirige a la página principal del sistema
    return redirect(url_for('login'))  # Redirige al login si no está autenticado


# Ruta para el login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('inicio'))  # Redirige a la página principal si ya está autenticado

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usuarios_secret WHERE username = %s', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and user['password'] == password:
            session['username'] = user['username']
            session['role'] = user['role']

            return redirect(url_for('inicio'))  # Redirige a la página principal después del login
        else:
            flash('Usuario o contraseña incorrectos', 'error')

    return render_template('login.html')

# Ruta para la página principal del sistema (después del login)
@app.route('/inicio')
def inicio():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirige al login si no está autenticado
    return render_template('inicio.html')

# Ruta para el logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('login'))

# Ruta para registrar ventas
@app.route('/registrar_venta', methods=['GET', 'POST'])
def registrar_venta():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Inicializar el carrito en la sesión si no existe
    if 'carrito' not in session:
        session['carrito'] = []

    if request.method == 'POST':
        # Buscar producto por código de barras o nombre
        if 'buscar' in request.form:
            busqueda = request.form['busqueda']
            cursor.execute('''
            SELECT id, nombre, codigo_barras, stock, precio FROM productos_secret
            WHERE codigo_barras = %s OR nombre ILIKE %s
        ''', (busqueda, f'%{busqueda}%'))
            productos = cursor.fetchall()
            conn.close()
            return render_template('registrar_venta.html', productos=productos, carrito=session['carrito'])

        # Agregar producto al carrito (venta normal)
        elif 'agregar' in request.form:
            producto_id = request.form['producto_id']
            cantidad = int(request.form['cantidad'])

            # Obtener detalles del producto
            cursor.execute('SELECT id, nombre, precio FROM productos_secret WHERE id = %s', (producto_id,))
            producto = cursor.fetchone()

            if producto:
                if producto['precio'] is not None:
                    # Verificar si hay suficiente stock
                    cursor.execute('SELECT stock FROM productos_secret WHERE id = %s', (producto_id,))
                    stock = cursor.fetchone()['stock']

                    if stock >= cantidad:
                        # Agregar producto al carrito
                        item = {
                            'id': producto['id'],
                            'nombre': producto['nombre'],
                            'precio': producto['precio'],
                            'cantidad': cantidad
                        }
                        session['carrito'].append(item)
                        session.modified = True
            
                    else:
                        flash(f'No hay suficiente stock para "{producto["nombre"]}"', 'error')
                else:
                    flash(f'El producto "{producto["nombre"]}" no tiene un precio definido', 'error')
            else:
                flash('Producto no encontrado', 'error')

        # Agregar venta manual al carrito
        elif 'agregar_manual' in request.form:
            nombre = request.form['nombre_manual']
            precio = float(request.form['precio_manual'])
            cantidad = int(request.form['cantidad_manual'])

            # Agregar venta manual al carrito
            item = {
                'id': None,  # No tiene ID porque no está en el stock
                'nombre': nombre,
                'precio': precio,
                'cantidad': cantidad
            }
            session['carrito'].append(item)
            session.modified = True
            flash(f'Servicio técnico "{nombre}" agregado al carrito', 'success')

        # Registrar la venta (tanto normal como manual)
        elif 'registrar' in request.form:
            if not session['carrito']:
                flash('El carrito está vacío. Agrega productos antes de registrar la venta', 'error')
                return redirect(url_for('registrar_venta'))

            # Obtener el tipo de pago y el DNI del cliente
            tipo_pago = request.form['tipo_pago']
            dni_cliente = request.form['dni_cliente']
            argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
            fecha_actual = datetime.now(argentina_tz).strftime('%Y-%m-%d %H:%M:%S')

            # Registrar cada producto del carrito
            for item in session['carrito']:
                producto_id = item['id']
                nombre = item['nombre']
                precio = item['precio']
                cantidad = item['cantidad']

                if producto_id is not None:
                    # Verificar si hay suficiente stock (solo para productos en stock)
                    cursor.execute('SELECT stock FROM productos_secret WHERE id = %s', (producto_id,))
                    producto = cursor.fetchone()

                    if producto and producto['stock'] >= cantidad:
                        # Registrar la venta en la tabla 'ventas'
                        cursor.execute('''
                            INSERT INTO ventas_secret (producto_id, cantidad, fecha, nombre_manual, precio_manual, tipo_pago, dni_cliente)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ''', (producto_id, cantidad, fecha_actual, None, None, tipo_pago, dni_cliente))

                        # Actualizar el stock
                        cursor.execute('UPDATE productos_secret SET stock = stock - %s WHERE id = %s', (cantidad, producto_id))
                    else:
                        conn.close()
                        flash(f'No hay suficiente stock para el producto: {nombre}', 'error')
                        return redirect(url_for('registrar_venta'))
                else:
                    # Registrar venta manual en la tabla 'reparaciones'
                    cursor.execute('''
                        INSERT INTO reparaciones_secret (nombre_servicio, precio, cantidad, tipo_pago, dni_cliente, fecha)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (nombre, precio, cantidad, tipo_pago, dni_cliente, fecha_actual))

            conn.commit()
            conn.close()
            session.pop('carrito', None)  # Vaciar el carrito después de registrar la venta
            flash('Venta registrada con éxito', 'success')
            return redirect(url_for('registrar_venta'))

        # Vaciar el carrito
        elif 'vaciar' in request.form:
            session.pop('carrito', None)
            flash('Carrito vaciado con éxito', 'success')
            return redirect(url_for('registrar_venta'))

    # Calcular el total del carrito
    total = sum(item['precio'] * item['cantidad'] for item in session['carrito'])

    # Si es GET, mostrar el formulario de búsqueda
    conn.close()
    return render_template('registrar_venta.html', productos=None, carrito=session['carrito'], total=total)

# Ruta para mostrar los productos más vendidos
@app.route('/productos_mas_vendidos')
def productos_mas_vendidos():
    # Conectar a la base de datos
    conn = get_db_connection()
    cursor = conn.cursor()

    # Consulta para obtener los 5 productos más vendidos
    cursor.execute('''
        SELECT nombre, precio, cantidad_vendida 
        FROM productos_secret
        ORDER BY cantidad_vendida DESC 
        LIMIT 5
    ''')
    productos = cursor.fetchall()

    # Calcular el total de ventas
    cursor.execute('SELECT SUM(cantidad_vendida) FROM productos_secret')
    total_ventas = cursor.fetchone()[0]

    # Calcular el porcentaje de ventas para cada producto
    productos_con_porcentaje = []
    for producto in productos:
        nombre, precio, cantidad_vendida = producto
        porcentaje = (cantidad_vendida / total_ventas) * 100 if total_ventas > 0 else 0
        productos_con_porcentaje.append({
            'nombre': nombre,
            'precio': precio,
            'cantidad_vendida': cantidad_vendida,
            'porcentaje': round(porcentaje, 2)  # Redondear a 2 decimales
        })

    # Cerrar la conexión
    conn.close()

    # Renderizar la plantilla HTML con los productos y el total de ventas
    return render_template('productos_mas_vendidos.html', productos=productos_con_porcentaje, total_ventas=total_ventas)

# Ruta para productos por agotarse
@app.route('/productos_por_agotarse')
def productos_por_agotarse():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener productos con stock menor o igual a 2
    cursor.execute('''
    SELECT id, nombre, codigo_barras, stock, precio, precio_costo
    FROM productos_secret
    WHERE stock <= 2
    ORDER BY stock ASC
    ''')
    productos = cursor.fetchall()

    conn.close()
    return render_template('productos_por_agotarse.html', productos=productos)

# Ruta principal para mostrar las ventas y reparaciones
from flask import send_file
from openpyxl import Workbook
from io import BytesIO

@app.route('/ultimas_ventas')
def ultimas_ventas():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener la fecha actual en la zona horaria de Argentina
    argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_actual = datetime.now(argentina_tz).strftime('%Y-%m-%d')

    # Obtener las fechas desde y hasta de los parámetros de la URL
    fecha_desde = request.args.get('fecha_desde', fecha_actual)
    fecha_hasta = request.args.get('fecha_hasta', fecha_actual)
    exportar = request.args.get('exportar', False)

    # Consultar todas las ventas en el rango de fechas con más detalles (incluyendo DNI si existe)
    cursor.execute('''
        SELECT 
            v.id AS venta_id,
            p.nombre AS nombre_producto,
            v.cantidad,
            p.precio AS precio_unitario,
            (v.cantidad * p.precio) AS total,
            v.fecha,
            v.tipo_pago,
            v.dni_cliente
        FROM ventas_secret v
        JOIN productos_secret p ON v.producto_id = p.id
        WHERE DATE(v.fecha) BETWEEN %s AND %s
        ORDER BY v.fecha DESC
    ''', (fecha_desde, fecha_hasta))
    ventas = cursor.fetchall()

    # Si se solicita exportar a Excel
    if exportar:
        # Crear un nuevo libro de Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Ventas"

        # Escribir los encabezados
        headers = [
            "ID Venta", "Producto", "Cantidad", "Precio Unitario", 
            "Total", "Fecha", "Tipo de Pago", "DNI Cliente"
        ]
        ws.append(headers)

        # Escribir los datos
        for venta in ventas:
            ws.append([
                venta['venta_id'],
                venta['nombre_producto'],
                venta['cantidad'],
                venta['precio_unitario'],
                venta['total'],
                venta['fecha'].strftime('%Y-%m-%d %H:%M:%S') if venta['fecha'] else '',
                venta['tipo_pago'],
                venta['dni_cliente'] or ''
            ])

        # Crear un archivo en memoria
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        # Configurar la respuesta para descargar el archivo
        nombre_archivo = f"ventas_{fecha_desde}_a_{fecha_hasta}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    # Resto del código para mostrar en la página web (sin cambios)
    cursor.execute('''
        SELECT 
            id AS reparacion_id,
            nombre_servicio AS nombre_servicio,
            cantidad,
            precio AS precio_unitario,
            (cantidad * precio) AS total,
            fecha,
            tipo_pago
        FROM reparaciones_secret
        WHERE DATE(fecha) BETWEEN %s AND %s
        ORDER BY fecha DESC
    ''', (fecha_desde, fecha_hasta))
    reparaciones = cursor.fetchall()

    # Calcular totales (sin cambios)
    total_ventas_por_pago = {}
    for venta in ventas:
        tipo_pago = venta['tipo_pago']
        total = venta['total']
        if tipo_pago in total_ventas_por_pago:
            total_ventas_por_pago[tipo_pago] += total
        else:
            total_ventas_por_pago[tipo_pago] = total

    total_reparaciones_por_pago = {}
    for reparacion in reparaciones:
        tipo_pago = reparacion['tipo_pago']
        total = reparacion['total']
        if tipo_pago in total_reparaciones_por_pago:
            total_reparaciones_por_pago[tipo_pago] += total
        else:
            total_reparaciones_por_pago[tipo_pago] = total

    conn.close()

    return render_template(
        'ultimas_ventas.html',
        ventas=ventas,
        reparaciones=reparaciones,
        fecha_actual=fecha_actual,
        total_ventas_por_pago=total_ventas_por_pago,
        total_reparaciones_por_pago=total_reparaciones_por_pago,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta
    )

# Ruta para eliminar una venta
@app.route('/anular_venta/<int:venta_id>', methods=['POST'])
def anular_venta(venta_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verificar si la venta existe
        cursor.execute('SELECT * FROM ventas_secret WHERE id = %s', (venta_id,))
        venta = cursor.fetchone()

        if not venta:
            return jsonify({'success': False, 'message': 'Venta no encontrada'}), 404

        # Eliminar la venta
        cursor.execute('DELETE FROM ventas_secret WHERE id = %s', (venta_id,))
        conn.commit()

        return jsonify({'success': True, 'message': 'Venta eliminada correctamente'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

# Ruta para eliminar una reparación
@app.route('/anular_reparacion/<int:reparacion_id>', methods=['POST'])
def anular_reparacion(reparacion_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verificar si la reparación existe
        cursor.execute('SELECT * FROM reparaciones_secret WHERE id = %s', (reparacion_id,))
        reparacion = cursor.fetchone()

        if not reparacion:
            return jsonify({'success': False, 'message': 'Reparación no encontrada'}), 404

        # Eliminar la reparación
        cursor.execute('DELETE FROM reparaciones_secret WHERE id = %s', (reparacion_id,))
        conn.commit()

        return jsonify({'success': True, 'message': 'Reparación eliminada correctamente'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

# Ruta para egresos
@app.route('/egresos', methods=['GET', 'POST'])
def egresos():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Agregar un nuevo egreso
    if request.method == 'POST' and 'agregar' in request.form:
        fecha = request.form['fecha']
        monto = float(request.form['monto'])
        descripcion = request.form['descripcion']
        tipo_pago = request.form['tipo_pago']  # Nuevo campo

        cursor.execute('''
        INSERT INTO egresos_secret (fecha, monto, descripcion, tipo_pago)
        VALUES (%s, %s, %s, %s)
        ''', (fecha, monto, descripcion, tipo_pago))
        conn.commit()
        conn.close()
        return redirect(url_for('egresos'))

    # Eliminar un egreso
    if request.method == 'POST' and 'eliminar' in request.form:
        egreso_id = request.form['egreso_id']
        cursor.execute('DELETE FROM egresos_secret WHERE id = %s', (egreso_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('egresos'))

    # Obtener todos los egresos
    cursor.execute('SELECT id, fecha, monto, descripcion, tipo_pago FROM egresos_secret ORDER BY fecha DESC')
    egresos = cursor.fetchall()
    conn.close()
    return render_template('egresos.html', egresos=egresos)

# Ruta para el dashboard
@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener las fechas seleccionadas o usar la fecha actual por defecto
    fecha_desde = request.args.get('fecha_desde', datetime.now().strftime('%Y-%m-%d'))
    fecha_hasta = request.args.get('fecha_hasta', datetime.now().strftime('%Y-%m-%d'))

    # Calcular el total de ventas de productos en el rango de fechas
    cursor.execute('''
    SELECT SUM(v.cantidad * COALESCE(p.precio, v.precio_manual)) AS total_ventas_productos
    FROM ventas_secret v
    LEFT JOIN productos_secret p ON v.producto_id = p.id
    WHERE DATE(v.fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta))
    total_ventas_productos = cursor.fetchone()['total_ventas_productos'] or 0

    # Calcular el total de ventas de reparaciones en el rango de fechas
    cursor.execute('''
    SELECT SUM(precio) AS total_ventas_reparaciones
    FROM reparaciones_secret
    WHERE DATE(fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta))
    total_ventas_reparaciones = cursor.fetchone()['total_ventas_reparaciones'] or 0

    total_ventas = total_ventas_productos + total_ventas_reparaciones

    # Calcular el total de egresos en el rango de fechas
    cursor.execute('''
    SELECT SUM(monto) AS total_egresos
    FROM egresos_secret
    WHERE DATE(fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta))
    total_egresos = cursor.fetchone()['total_egresos'] or 0

    # Calcular el costo de los productos vendidos en el rango de fechas
    cursor.execute('''
    SELECT SUM(v.cantidad * p.precio_costo) AS total_costo
    FROM ventas_secret v
    JOIN productos_secret p ON v.producto_id = p.id
    WHERE DATE(v.fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta))
    total_costo = cursor.fetchone()['total_costo'] or 0

    # Calcular la ganancia en el rango de fechas
    ganancia = total_ventas - total_egresos - total_costo

    # Obtener la distribución de ventas por tipo (productos vs. reparaciones)
    cursor.execute('''
    SELECT 'Productos_secret' AS tipo, SUM(v.cantidad * COALESCE(p.precio, v.precio_manual)) AS total
    FROM ventas_secret v
    LEFT JOIN productos_secret p ON v.producto_id = p.id
    WHERE DATE(v.fecha) BETWEEN %s AND %s
    UNION ALL
    SELECT 'Reparaciones_secret' AS tipo, SUM(precio) AS total
    FROM reparaciones_secret
    WHERE DATE(fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta, fecha_desde, fecha_hasta))
    distribucion_ventas = cursor.fetchall()

    conn.close()

    return render_template('dashboard.html', 
                          total_ventas=total_ventas, 
                          total_egresos=total_egresos, 
                          total_costo=total_costo, 
                          ganancia=ganancia,
                          total_ventas_productos=total_ventas_productos,  # Asegúrate de pasar este valor
                          total_ventas_reparaciones=total_ventas_reparaciones,  # Asegúrate de pasar este valor
                          distribucion_ventas=distribucion_ventas,
                          fecha_desde=fecha_desde,
                          fecha_hasta=fecha_hasta)

# Ruta para resumen semanal
@app.route('/resumen_semanal')
def resumen_semanal():
    # Obtener la fecha de inicio de la semana (lunes)
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana_str = inicio_semana.strftime('%Y-%m-%d')

    # Conectar a la base de datos
    conn = get_db_connection()
    cursor = conn.cursor()

    # Consultar las ventas de la semana actual
    cursor.execute('''
        SELECT tipo_pago, SUM(total) as total
        FROM ventas_secret
        WHERE fecha >= %s
        GROUP BY tipo_pago
    ''', (inicio_semana_str,))

    resumen = cursor.fetchall()

    # Cerrar la conexión
    conn.close()

    # Renderizar la plantilla con el resumen
    return render_template('resumen_semanal.html', resumen=resumen)

# Ruta para caja
@app.route('/caja')
def caja():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener la fecha actual en la zona horaria de Argentina
    argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
    hoy = datetime.now(argentina_tz).date()

    # Obtener parámetros de la URL (fechas personalizadas)
    fecha_desde = request.args.get('fecha_desde', hoy.strftime('%Y-%m-%d'))  # Por defecto: hoy
    fecha_hasta = request.args.get('fecha_hasta', hoy.strftime('%Y-%m-%d'))  # Por defecto: hoy

    # Consultar todas las ventas del período seleccionado
    cursor.execute('''
        SELECT 
            v.id AS venta_id,
            p.nombre AS nombre_producto,
            v.cantidad,
            p.precio AS precio_unitario,
            (v.cantidad * p.precio) AS total,
            v.fecha,
            v.tipo_pago
        FROM ventas_secret v
        JOIN productos_secret p ON v.producto_id = p.id
        WHERE DATE(v.fecha) BETWEEN %s AND %s
        ORDER BY v.fecha DESC
    ''', (fecha_desde, fecha_hasta))
    ventas = cursor.fetchall()

    # Consultar todas las reparaciones del período seleccionado
    cursor.execute('''
        SELECT 
            id AS reparacion_id,
            nombre_servicio AS nombre_servicio,
            cantidad,
            precio AS precio_unitario,
            (cantidad * precio) AS total,
            fecha,
            tipo_pago
        FROM reparaciones_secret
        WHERE DATE(fecha) BETWEEN %s AND %s
        ORDER BY fecha DESC
    ''', (fecha_desde, fecha_hasta))
    reparaciones = cursor.fetchall()

    # Consultar todos los egresos del período seleccionado
    cursor.execute('''
        SELECT 
            id AS egreso_id,
            descripcion,
            monto,
            tipo_pago,
            fecha
        FROM egresos_secret
        WHERE DATE(fecha) BETWEEN %s AND %s
        ORDER BY fecha DESC
    ''', (fecha_desde, fecha_hasta))
    egresos = cursor.fetchall()

    # Calcular el total por tipo de pago para ventas
    total_ventas_por_pago = {}
    for venta in ventas:
        tipo_pago = venta['tipo_pago']
        total = venta['total']
        if tipo_pago in total_ventas_por_pago:
            total_ventas_por_pago[tipo_pago] += total
        else:
            total_ventas_por_pago[tipo_pago] = total

    # Calcular el total por tipo de pago para reparaciones
    total_reparaciones_por_pago = {}
    for reparacion in reparaciones:
        tipo_pago = reparacion['tipo_pago']
        total = reparacion['total']
        if tipo_pago in total_reparaciones_por_pago:
            total_reparaciones_por_pago[tipo_pago] += total
        else:
            total_reparaciones_por_pago[tipo_pago] = total

    # Calcular el total combinado por tipo de pago (ventas + reparaciones)
    total_combinado_por_pago = {}
    for tipo_pago, total in total_ventas_por_pago.items():
        total_combinado_por_pago[tipo_pago] = total_combinado_por_pago.get(tipo_pago, 0) + total
    for tipo_pago, total in total_reparaciones_por_pago.items():
        total_combinado_por_pago[tipo_pago] = total_combinado_por_pago.get(tipo_pago, 0) + total

    # Calcular el total de egresos por tipo de pago
    total_egresos_por_pago = {}
    for egreso in egresos:
        tipo_pago = egreso['tipo_pago']
        monto = egreso['monto']
        if tipo_pago in total_egresos_por_pago:
            total_egresos_por_pago[tipo_pago] += monto
        else:
            total_egresos_por_pago[tipo_pago] = monto

    # Calcular el neto por tipo de pago (total combinado - egresos correspondientes)
    neto_por_pago = {}
    for tipo_pago, total in total_combinado_por_pago.items():
        # Obtener los egresos para este tipo de pago (si no hay, usar 0)
        egresos_tipo_pago = total_egresos_por_pago.get(tipo_pago, 0)
        # Calcular el neto
        neto_por_pago[tipo_pago] = total - egresos_tipo_pago

    conn.close()

    # Pasar los datos a la plantilla
    return render_template(
        'caja.html',
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        neto_por_pago=neto_por_pago
    )

# Ruta para reparaciones
@app.route('/reparaciones', methods=['GET', 'POST'])
def reparaciones():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Obtener los datos del formulario
        tipo_reparacion = request.form['tipo_reparacion']
        marca = request.form['equipo']
        modelo = request.form['modelo']
        tecnico = request.form['tecnico']
        monto = float(request.form['monto'])
        nombre_cliente = request.form['nombre_cliente']
        telefono = request.form['telefono']
        nro_orden = request.form['nro_orden']
        fecha = datetime.now().strftime('%Y-%m-%d')
        hora = datetime.now().strftime('%H:%M:%S')

        # Insertar los datos en la base de datos
        cursor.execute('''
            INSERT INTO equipos_secret (
                tipo_reparacion, marca, modelo, tecnico, monto, nombre_cliente, telefono, nro_orden, fecha, hora
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (tipo_reparacion, marca, modelo, tecnico, monto, nombre_cliente, telefono, nro_orden, fecha, hora))
        conn.commit()

    # Obtener las fechas de filtro desde la URL
    fecha_desde = request.args.get('fecha_desde', (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
    fecha_hasta = request.args.get('fecha_hasta', datetime.now().strftime('%Y-%m-%d'))

    # Obtener los últimos equipos cargados en el rango de fechas seleccionado
    cursor.execute("SELECT * FROM equipos_secret WHERE fecha >= %s AND fecha <= %s ORDER BY nro_orden DESC", (fecha_desde, fecha_hasta))
    ultimos_equipos = cursor.fetchall()

    # Obtener la cantidad de equipos por técnico en el rango de fechas seleccionado
    cursor.execute('''
        SELECT tecnico, COUNT(*) as cantidad
        FROM equipos_secret
        WHERE fecha >= %s AND fecha <= %s
        GROUP BY tecnico
    ''', (fecha_desde, fecha_hasta))
    datos_tecnicos = cursor.fetchall()

    conn.close()

    # Preparar los datos para la vista
    equipos_por_tecnico = {row['tecnico']: row['cantidad'] for row in datos_tecnicos}

    return render_template(
        'reparaciones.html',
        ultimos_equipos=ultimos_equipos,
        equipos_por_tecnico=equipos_por_tecnico,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta
    )

# Ruta para eliminar reparaciones
@app.route('/eliminar_reparacion/<int:id>', methods=['POST'])
def eliminar_reparacion(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Eliminar el equipo por su ID
    cursor.execute('DELETE FROM equipos_secret WHERE id = %s', (id,))
    conn.commit()
    conn.close()

    # Redirigir a la página de reparaciones después de eliminar
    return redirect(url_for('reparaciones'))

# Ruta para actualizar estado de reparaciones
@app.route('/actualizar_estado', methods=['POST'])
def actualizar_estado():
    data = request.get_json()
    nro_orden = data['nro_orden']
    estado = data['estado']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE equipos_secret
        SET estado = %s
        WHERE nro_orden = %s
    ''', (estado, nro_orden))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

# Ruta para mercadería fallada
@app.route('/mercaderia_fallada', methods=['GET', 'POST'])
def mercaderia_fallada():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Buscar productos
    if request.method == 'POST' and 'buscar' in request.form:
        busqueda = request.form['busqueda']
        cursor.execute('''
        SELECT id, nombre, codigo_barras, stock, precio, precio_costo
        FROM productos_secret
        WHERE nombre LIKE %s OR codigo_barras LIKE %s
        ''', (f'%{busqueda}%', f'%{busqueda}%'))
        productos = cursor.fetchall()
        conn.close()
        return render_template('mercaderia_fallada.html', productos=productos)

    # Registrar mercadería fallada
    if request.method == 'POST' and 'registrar_fallada' in request.form:
        producto_id = request.form['producto_id']
        cantidad = int(request.form['cantidad'])
        descripcion = request.form['descripcion']
        fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Verificar si hay suficiente stock
        cursor.execute('SELECT stock FROM productos_secret WHERE id = %s', (producto_id,))
        producto = cursor.fetchone()

        if producto and producto['stock'] >= cantidad:
            # Registrar en la tabla `mercaderia_fallada`
            cursor.execute('''
            INSERT INTO mercaderia_fallada_secret (producto_id, cantidad, fecha, descripcion)
            VALUES (%s, %s, %s, %s)
            ''', (producto_id, cantidad, fecha, descripcion))

            # Actualizar el stock en la tabla `productos`
            cursor.execute('UPDATE productos_secret SET stock = stock - %s WHERE id = %s', (cantidad, producto_id))
            conn.commit()
            conn.close()
            return redirect(url_for('mercaderia_fallada'))
        else:
            conn.close()
            return f"No hay suficiente stock para el producto seleccionado."

    # Obtener historial de mercadería fallada
    cursor.execute('''
    SELECT mf.id, p.nombre, mf.cantidad, mf.fecha, mf.descripcion
    FROM mercaderia_fallada mf
    JOIN productos_secret p ON mf.producto_id = p.id
    ORDER BY mf.fecha DESC
    ''')
    historial = cursor.fetchall()

    conn.close()
    return render_template('mercaderia_fallada.html', historial=historial)

@app.route('/agregar_stock', methods=['GET', 'POST'])
def agregar_stock():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener el término de búsqueda (si existe)
    busqueda = request.args.get('busqueda', '')

    try:
        # Eliminar un producto
        if request.method == 'POST' and 'eliminar' in request.form:
            producto_id = request.form['producto_id']
            cursor.execute('DELETE FROM productos_secret WHERE id = %s', (producto_id,))
            conn.commit()
            return redirect(url_for('agregar_stock'))

        # Editar un producto
        if request.method == 'POST' and 'editar' in request.form:
            producto_id = request.form['producto_id']
            nombre = request.form['nombre'].upper()  # Convertir a mayúsculas
            codigo_barras = request.form['codigo_barras']
            stock = int(request.form['stock'])
            precio = float(request.form['precio'])
            precio_costo = float(request.form['precio_costo'])

            cursor.execute('''
            UPDATE productos_secret
            SET nombre = %s, codigo_barras = %s, stock = %s, precio = %s, precio_costo = %s
            WHERE id = %s
            ''', (nombre, codigo_barras, stock, precio, precio_costo, producto_id))
            conn.commit()
            return redirect(url_for('agregar_stock'))

        # Agregar stock a un producto existente
        if request.method == 'POST' and 'agregar_stock' in request.form:
            producto_id = request.form['producto_id']
            cantidad = int(request.form['cantidad'])

            cursor.execute('''
            UPDATE productos_secret
            SET stock = stock + %s
            WHERE id = %s
            ''', (cantidad, producto_id))
            conn.commit()
            return redirect(url_for('agregar_stock'))

        # Agregar un nuevo producto
        if request.method == 'POST' and 'agregar' in request.form:
            nombre = request.form['nombre'].upper()  # Convertir a mayúsculas
            codigo_barras = request.form['codigo_barras']
            stock = int(request.form['stock'])
            precio = float(request.form['precio'])
            precio_costo = float(request.form['precio_costo'])

            cursor.execute('''
            INSERT INTO productos_secret (nombre, codigo_barras, stock, precio, precio_costo)
            VALUES (%s, %s, %s, %s, %s)
            ''', (nombre, codigo_barras, stock, precio, precio_costo))
            conn.commit()
            return redirect(url_for('agregar_stock'))

        # Obtener productos filtrados por búsqueda (si existe)
        try:
            if busqueda:
                cursor.execute('''
                SELECT id, nombre, codigo_barras, stock, precio, precio_costo
                FROM productos_secret
                WHERE nombre LIKE %s OR codigo_barras LIKE %s
                ''', (f'%{busqueda}%', f'%{busqueda}%'))
            else:
                # Si no hay búsqueda, obtener todos los productos
                cursor.execute('SELECT id, nombre, codigo_barras, stock, precio, precio_costo FROM productos_secret')

            productos = cursor.fetchall()
        except Exception as e:
            conn.rollback()
            return f"Error: {str(e)}"
        finally:
            conn.close()

        return render_template('agregar_stock.html', productos=productos, busqueda=busqueda)

    except Exception as e:
        conn.rollback()
        return f"Error: {str(e)}"
    finally:
        conn.close()

    return render_template('agregar_stock.html', productos=productos, busqueda=busqueda)

if __name__ == '__main__':
    app.run(debug=True)
