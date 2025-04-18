import pandas as pd
from tkinter import Tk, messagebox
from tkinter.filedialog import askopenfilename
import mysql.connector
from mysql.connector import Error

def load_excel_file():
    """Muestra una ventana emergente para seleccionar un archivo Excel y lo carga como DataFrame."""
    root = Tk()
    root.withdraw()  # Oculta la ventana principal
    root.attributes('-topmost', True)  # Mantiene la ventana en primer plano

    file_name = askopenfilename(
        title="Seleccione un archivo Excel",
        filetypes=[("Excel files", "*.xlsx;*.xls;*.xlsb")]
    )

    root.destroy()  # Cierra la ventana después de seleccionar el archivo

    if not file_name:
        print("No se seleccionó ningún archivo.")
        return None

    motores = ["openpyxl", "xlrd", "pyxlsb"]  # Motores a probar
    for motor in motores:
        try:
            df = pd.read_excel(file_name, engine=motor, header=0)
            print(f"Archivo '{file_name}' cargado correctamente con el motor '{motor}'.")
            return df
        except Exception as e:
            print(f"Intento fallido con '{motor}': {e}")

    print("Error: No se pudo cargar el archivo con ningún motor disponible.")
    return None

def procesar_empleados(df):
    """Procesa el DataFrame para extraer la información de los empleados."""
    if df is None:
        print("Error: No se pudo cargar el archivo.")
        return None

    # Eliminar la primera fila (encabezados) si es necesario
    df = df.iloc[1:].reset_index(drop=True)

    # Asignar nombres a las columnas manualmente
    column_names = ['No', 'NSS', 'Nombre(s)', 'Apellido Paterno', 'Apellido Materno',
                    'CURP', 'SD 2024', 'SDI 2024', 'SD 2025', 'SDI 2025', 'Puesto', 'RFC', 'Estado']
    datos = df.copy()  # Copiar para evitar advertencias de modificación
    datos.columns = column_names  # Asignar nombres de columnas manualmente

    # Convertir 'No' a tipo entero
    datos['No'] = pd.to_numeric(datos['No'], errors='coerce').fillna(0).astype(int)

    # Limpiar espacios adicionales en la columna 'Estado' y asegurarse de que los valores sean 'Activo' o 'Inactivo'
    datos['Estado'] = datos['Estado'].str.strip().replace({'Activo ': 'Activo', 'Inactivo ': 'Inactivo'})

    # Seleccionar las columnas de interés
    datos['nombre_completo'] = datos['Nombre(s)'] + ' ' + datos['Apellido Paterno'] + ' ' + datos['Apellido Materno']
    datos_empleados = datos[['No', 'nombre_completo', 'Estado', 'SD 2024']].copy()
    datos_empleados.columns = ['numero_nomina', 'nombre_completo', 'estado', 'sueldo_diario']

    # Asignar sueldo diario: 0 si está inactivo, SD 2024 si está activo
    datos_empleados['sueldo_diario'] = datos_empleados.apply(
        lambda row: 0 if row['estado'] == 'Inactivo' else row['sueldo_diario'],
        axis=1
    )

    # Agregar columna tipo_trabajador
    datos_empleados['tipo_trabajador'] = 'no definido'

    return datos_empleados

def generar_sql_insercion(datos_empleados):
    """Genera las instrucciones SQL para insertar los datos en la base de datos."""
    insert_statements = []

    for _, row in datos_empleados.iterrows():
        numero_nomina = row['numero_nomina']
        nombre_completo = row['nombre_completo']
        estado = row['estado']
        tipo_trabajador = row['tipo_trabajador']
        sueldo_diario = row['sueldo_diario']

        # Crear la instrucción INSERT
        insert_statement = (
            f"INSERT INTO empleados (numero_nomina, nombre_completo, estado, tipo_trabajador, sueldo_diario) "
            f"VALUES ({numero_nomina}, '{nombre_completo}', '{estado}', '{tipo_trabajador}', {sueldo_diario});"
        )
        insert_statements.append(insert_statement)

    return "\n".join(insert_statements)

def conectar_bd():
    """Intenta conectar a la base de datos y verifica la conexión."""
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="GalejRumber0064",
            database="gestion_laboral",
            port=3306  # Cambia este puerto si tu MySQL usa otro
        )
        if conexion.is_connected():
            print("Conexión exitosa a la base de datos.")
            cursor = conexion.cursor()
            cursor.execute("SELECT DATABASE();")  # Verifica la base de datos activa
            db_name = cursor.fetchone()
            print(f"Base de datos activa: {db_name[0]}")
            cursor.close()
            return conexion
    except Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def subir_datos_a_bd(sql_script):
    """Sube los datos a la base de datos ejecutando el script SQL."""
    conexion = conectar_bd()
    if conexion is None:
        return

    try:
        cursor = conexion.cursor()
        for statement in sql_script.split(';')[:-1]:  # Ejecutar cada sentencia individualmente
            cursor.execute(statement)
        conexion.commit()
        print("Datos insertados correctamente en la base de datos.")
    except Error as e:
        print(f"Error al insertar datos: {e}")
    finally:
        cursor.close()
        conexion.close()

def main():
    df = load_excel_file()
    datos_empleados = procesar_empleados(df)

    if datos_empleados is not None:
        sql_script = generar_sql_insercion(datos_empleados)
        print("Script SQL generado:")
        print(sql_script)

        # Preguntar al usuario si desea subir los datos a la base de datos
        respuesta = messagebox.askyesno("Confirmación", "¿Desea subir los datos a la base de datos?")
        if respuesta:
            subir_datos_a_bd(sql_script)

if __name__ == "__main__":
    main()