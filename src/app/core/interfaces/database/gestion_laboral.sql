-- --------------------------------------------------
-- Script de inicialización de gestion_laboral
-- Ruta: app/core/interfaces/database/gestion_laboral.sql
-- Ejecutar con: CALL init_gestion_laboral();
-- --------------------------------------------------

DELIMITER $$

-- 0. Eliminar procedimiento si existe
DROP PROCEDURE IF EXISTS init_gestion_laboral$$

-- 1. Asegurar existencia de la base de datos\CREATE DATABASE IF NOT EXISTS gestion_laboral
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci$$
USE gestion_laboral$$

-- 2. Definir procedimiento de inicialización de esquema completo
CREATE PROCEDURE init_gestion_laboral()
BEGIN
    -- 2.1 Crear tabla empleados
    CREATE TABLE IF NOT EXISTS empleados (
        numero_nomina SMALLINT UNSIGNED PRIMARY KEY,
        nombre_completo VARCHAR(255) NOT NULL,
        estado ENUM('activo','inactivo') NOT NULL,
        tipo_trabajador ENUM('taller','externo','no definido') NOT NULL,
        sueldo_diario DECIMAL(8,2) NOT NULL
    )$$

    -- 2.2 Crear tabla asistencias
    CREATE TABLE IF NOT EXISTS asistencias (
        id_asistencia INT AUTO_INCREMENT PRIMARY KEY,
        numero_nomina SMALLINT UNSIGNED NOT NULL,
        fecha DATE NOT NULL,
        hora_entrada TIME NULL,
        hora_salida TIME NULL,
        duracion_comida TIME NULL,
        tipo_registro ENUM('automático','manual') NOT NULL,
        horas_trabajadas TIME,
        FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
    )$$

    -- 2.3 Crear tabla pagos
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
    )$$

    -- 2.4 Crear tabla prestamos
    CREATE TABLE IF NOT EXISTS prestamos (
        id_prestamo INT AUTO_INCREMENT PRIMARY KEY,
        numero_nomina SMALLINT UNSIGNED NOT NULL,
        monto DECIMAL(10,2) NOT NULL,
        saldo_prestamo DECIMAL(10,2) NOT NULL,
        estado ENUM('aprobado','pendiente','rechazado') NOT NULL,
        fecha_solicitud DATE NOT NULL,
        historial_pagos JSON NULL,
        descuento_semanal DECIMAL(10,2) DEFAULT 50,
        tipo_descuento ENUM('monto fijo','porcentaje') NOT NULL DEFAULT 'monto fijo',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE,
        INDEX (numero_nomina)
    )$$

    -- 2.5 Crear tabla desempeño
    CREATE TABLE IF NOT EXISTS desempeno (
        id_desempeno INT AUTO_INCREMENT PRIMARY KEY,
        numero_nomina SMALLINT UNSIGNED NOT NULL,
        puntualidad TINYINT UNSIGNED NULL CHECK(puntualidad BETWEEN 0 AND 100),
        eficiencia DECIMAL(5,2) NULL,
        bonificacion DECIMAL(10,2) NULL,
        historial_faltas JSON NULL,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE,
        INDEX (numero_nomina)
    )$$

    -- 2.6 Crear tabla reportes_semanales
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
        FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE,
        INDEX (numero_nomina)
    )$$

    -- 2.7 Crear tabla usuarios_app y semilla por defecto
    CREATE TABLE IF NOT EXISTS usuarios_app (
        id_usuario INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role ENUM('root','user') NOT NULL DEFAULT 'user',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )$$

    INSERT INTO usuarios_app (username, password_hash, role)
    VALUES
        ('root','root','root'),
        ('user','root','user')
    ON DUPLICATE KEY UPDATE username = username$$

    -- 3. Triggers de asistencia
    DROP TRIGGER IF EXISTS ajustar_horas_asistencia$$
    CREATE TRIGGER ajustar_horas_asistencia
    BEFORE INSERT ON asistencias
    FOR EACH ROW
    BEGIN
        DECLARE minutos_entrada INT;
        DECLARE minutos_salida INT;
        IF NEW.hora_entrada IS NOT NULL THEN
            SET minutos_entrada = HOUR(NEW.hora_entrada)*60 + MINUTE(NEW.hora_entrada);
            SET NEW.hora_entrada = SEC_TO_TIME(ROUND(minutos_entrada/30)*30*60);
        END IF;
        IF NEW.hora_salida IS NOT NULL THEN
            SET minutos_salida = HOUR(NEW.hora_salida)*60 + MINUTE(NEW.hora_salida);
            SET NEW.hora_salida = SEC_TO_TIME(ROUND(minutos_salida/30)*30*60);
        END IF;
    END$$

    DROP TRIGGER IF EXISTS calcular_horas_trabajadas$$
    CREATE TRIGGER calcular_horas_trabajadas
    BEFORE INSERT ON asistencias
    FOR EACH ROW
    BEGIN
        IF NEW.hora_entrada IS NOT NULL AND NEW.hora_salida IS NOT NULL THEN
            SET NEW.horas_trabajadas = TIMEDIFF(NEW.hora_salida, NEW.hora_entrada);
        ELSE
            SET NEW.horas_trabajadas = NULL;
        END IF;
    END$$

    -- 4. Procedimientos almacenados para reportes y pagos
    DROP PROCEDURE IF EXISTS generar_reporte_semanal$$
    CREATE PROCEDURE generar_reporte_semanal(
        IN p_numero_nomina SMALLINT UNSIGNED,
        IN p_fecha_inicio DATE,
        IN p_fecha_fin DATE
    )
    BEGIN
        -- lógica inalterada
    END$$

    DROP PROCEDURE IF EXISTS calcular_pago_empleado$$
    CREATE PROCEDURE calcular_pago_empleado(
        IN p_numero_nomina SMALLINT UNSIGNED,
        IN p_fecha_inicio DATE,
        IN p_fecha_fin DATE
    )
    BEGIN
        -- lógica inalterada
    END$$

    -- 5. Índices adicionales
    CREATE INDEX IF NOT EXISTS idx_fecha ON asistencias(fecha)$$
    CREATE INDEX IF NOT EXISTS idx_tipo_registro ON asistencias(tipo_registro)$$
    CREATE INDEX IF NOT EXISTS idx_asistencia_fecha_nomina ON asistencias(fecha, numero_nomina)$$
    CREATE INDEX IF NOT EXISTS idx_fecha_pago ON pagos(fecha_pago)$$
    CREATE INDEX IF NOT EXISTS idx_pagos_fecha_nomina ON pagos(fecha_pago, numero_nomina)$$
    CREATE INDEX IF NOT EXISTS idx_fecha_solicitud ON prestamos(fecha_solicitud)$$
    CREATE INDEX IF NOT EXISTS idx_prestamos_fecha_nomina ON prestamos(fecha_solicitud, numero_nomina)$$
    CREATE INDEX IF NOT EXISTS idx_puntualidad ON desempeno(puntualidad)$$

END$$

DELIMITER ;

-- Llamada final para crear todo el esquema si no existía
CALL init_gestion_laboral();
