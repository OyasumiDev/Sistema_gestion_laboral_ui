-- 0. Eliminar procedimiento existente
DROP PROCEDURE IF EXISTS init_gestion_laboral;

-- 1. Creación del procedimiento init_gestion_laboral
DELIMITER //

CREATE PROCEDURE init_gestion_laboral()
BEGIN
    -- 1.1 Crear base de datos y usarla
    CREATE DATABASE IF NOT EXISTS gestion_laboral;
    USE gestion_laboral;

    -- 1.2 Tablas
    CREATE TABLE IF NOT EXISTS empleados (
        numero_nomina SMALLINT UNSIGNED PRIMARY KEY,
        nombre_completo VARCHAR(255) NOT NULL,
        estado ENUM('activo','inactivo') NOT NULL,
        tipo_trabajador ENUM('taller','externo','no definido') NOT NULL,
        sueldo_diario DECIMAL(8,2) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS asistencias (
        id_asistencia INT AUTO_INCREMENT PRIMARY KEY,
        numero_nomina SMALLINT UNSIGNED NOT NULL,
        fecha DATE NOT NULL,
        hora_entrada TIME,
        hora_salida TIME,
        duracion_comida TIME,
        tipo_registro ENUM('automático','manual') NOT NULL,
        horas_trabajadas TIME,
        FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS pagos (
        id_pago INT AUTO_INCREMENT PRIMARY KEY,
        numero_nomina SMALLINT UNSIGNED NOT NULL,
        fecha_pago DATE NOT NULL,
        monto_total DECIMAL(10,2) NOT NULL,
        saldo DECIMAL(10,2) DEFAULT 0,
        pago_deposito DECIMAL(10,2) NOT NULL,
        pago_efectivo DECIMAL(10,2) NOT NULL,
        retenciones_imss DECIMAL(10,2) NOT NULL DEFAULT 50,
        FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS prestamos (
        id_prestamo INT AUTO_INCREMENT PRIMARY KEY,
        numero_nomina SMALLINT UNSIGNED NOT NULL,
        monto DECIMAL(10,2) NOT NULL,
        saldo_prestamo DECIMAL(10,2) NOT NULL,
        estado ENUM('aprobado','pendiente','rechazado') NOT NULL,
        fecha_solicitud DATE NOT NULL,
        historial_pagos JSON,
        descuento_semanal DECIMAL(10,2) DEFAULT 50,
        tipo_descuento ENUM('monto fijo','porcentaje') NOT NULL DEFAULT 'monto fijo',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS performance (
        id_desempeno INT AUTO_INCREMENT PRIMARY KEY,
        numero_nomina SMALLINT UNSIGNED NOT NULL,
        puntualidad TINYINT UNSIGNED CHECK (puntualidad BETWEEN 0 AND 100),
        eficiencia DECIMAL(5,2),
        bonificacion DECIMAL(10,2),
        historial_faltas JSON,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS reportes_semanales (
        id_reporte INT AUTO_INCREMENT PRIMARY KEY,
        numero_nomina SMALLINT UNSIGNED NOT NULL,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        total_horas_trabajadas DECIMAL(10,2) NOT NULL,
        total_deudas DECIMAL(10,2) NOT NULL,
        total_abonado DECIMAL(10,2) NOT NULL,
        saldo_final DECIMAL(10,2) NOT NULL,
        total_efectivo DECIMAL(10,2) NOT NULL,
        total_tarjeta DECIMAL(10,2) NOT NULL,
        FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS usuarios_app (
        id_usuario INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role ENUM('root','user') NOT NULL DEFAULT 'user',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );

    -- 1.3 Insertar datos iniciales de usuarios
    INSERT INTO usuarios_app (username, password_hash, role)
    VALUES
        ('root','root','root'),
        ('user','root','user')
    ON DUPLICATE KEY UPDATE
        password_hash = VALUES(password_hash),
        role = VALUES(role);
END //

DELIMITER ;

-- 2. Ejecutar el procedimiento
CALL init_gestion_laboral();
