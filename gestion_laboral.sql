CREATE DATABASE IF NOT EXISTS gestion_laboral;
USE gestion_laboral;

/*
    CREACION DE LAS TABLAS 
*/

-- Tabla de empleados
CREATE TABLE IF NOT EXISTS empleados (
    numero_nomina SMALLINT UNSIGNED PRIMARY KEY,  -- número de empleado
    nombre_completo VARCHAR(255) NOT NULL,
    estado ENUM('activo', 'inactivo') NOT NULL,
    tipo_trabajador ENUM('taller', 'externo', 'no definido') NOT NULL,
    sueldo_diario DECIMAL(8, 2) NOT NULL  -- sueldo diario base
);

-- Tabla de asistencias
CREATE TABLE IF NOT EXISTS asistencias (
    id_asistencia INT AUTO_INCREMENT PRIMARY KEY,
    numero_nomina SMALLINT UNSIGNED NOT NULL,
    fecha DATE NOT NULL,
    hora_entrada TIME NULL,
    hora_salida TIME NULL,
    duracion_comida TIME NULL,  -- duración de la comida
    tipo_registro ENUM('automático', 'manual') NOT NULL,
    horas_trabajadas TIME,
    FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
);

-- Tabla de pagos (nómina)
CREATE TABLE IF NOT EXISTS pagos (
    id_pago INT AUTO_INCREMENT PRIMARY KEY,
    numero_nomina SMALLINT UNSIGNED NOT NULL,
    fecha_pago DATE NOT NULL, -- cambio a date
    monto_total DECIMAL(10, 2) NOT NULL,
    saldo DECIMAL(10, 2) DEFAULT 0,
    pago_deposito DECIMAL(10, 2) NOT NULL,
    pago_efectivo DECIMAL(10, 2) NOT NULL,
    retenciones_imss DECIMAL(10, 2) DEFAULT 50 NOT NULL,
    FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prestamos (
    id_prestamo INT AUTO_INCREMENT PRIMARY KEY,
    numero_nomina SMALLINT UNSIGNED NOT NULL,
    monto DECIMAL(10, 2) NOT NULL,
    saldo_prestamo DECIMAL(10, 2) NOT NULL,
    estado ENUM('aprobado', 'pendiente', 'rechazado') NOT NULL,
    fecha_solicitud DATE NOT NULL, -- mantiene date
    historial_pagos JSON NULL,
    descuento_semanal DECIMAL(10, 2) DEFAULT 50,
    tipo_descuento ENUM('monto fijo', 'porcentaje') NOT NULL DEFAULT 'monto fijo',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- mantiene timestamp
    FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE,
    INDEX (numero_nomina)
);

-- Tabla de desempeño
CREATE TABLE IF NOT EXISTS desempeno (
    id_desempeno INT AUTO_INCREMENT PRIMARY KEY,
    numero_nomina SMALLINT UNSIGNED NOT NULL,
    puntualidad TINYINT UNSIGNED NULL CHECK(puntualidad BETWEEN 0 AND 100),
    eficiencia DECIMAL(5, 2) NULL,
    bonificacion DECIMAL(10, 2) NULL,
    historial_faltas JSON NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- mantiene timestamp
    FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE,
    INDEX (numero_nomina)
);

-- Tabla de reportes semanales
CREATE TABLE IF NOT EXISTS reportes_semanales (
    id_reporte INT AUTO_INCREMENT PRIMARY KEY,
    numero_nomina SMALLINT UNSIGNED NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    total_horas_trabajadas DECIMAL(10, 2) NOT NULL,
    total_deudas DECIMAL(10, 2) NOT NULL,
    total_abonado DECIMAL(10, 2) NOT NULL,
    saldo_final DECIMAL(10, 2) NOT NULL,
    total_efectivo DECIMAL(10, 2) NOT NULL,
    total_tarjeta DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE,
    INDEX (numero_nomina)
);



/*
TRIGGERS
*/

DELIMITER //

CREATE TRIGGER ajustar_horas_asistencia
BEFORE INSERT ON asistencias
FOR EACH ROW
BEGIN
    DECLARE minutos_entrada INT;
    DECLARE minutos_salida INT;

    -- Verificar si hora_entrada no es NULL antes de ajustar
    IF NEW.hora_entrada IS NOT NULL THEN
        SET minutos_entrada = HOUR(NEW.hora_entrada) * 60 + MINUTE(NEW.hora_entrada);
        SET NEW.hora_entrada = SEC_TO_TIME(ROUND(minutos_entrada / 30) * 30 * 60);
    END IF;

    -- Verificar si hora_salida no es NULL antes de ajustar
    IF NEW.hora_salida IS NOT NULL THEN
        SET minutos_salida = HOUR(NEW.hora_salida) * 60 + MINUTE(NEW.hora_salida);
        SET NEW.hora_salida = SEC_TO_TIME(ROUND(minutos_salida / 30) * 30 * 60);
    END IF;
END;
//

DELIMITER ;

-- Crear el trigger para calcular la duración de horas trabajadas
DELIMITER //

CREATE TRIGGER calcular_horas_trabajadas
BEFORE INSERT ON asistencias
FOR EACH ROW
BEGIN
    IF NEW.hora_entrada IS NOT NULL AND NEW.hora_salida IS NOT NULL THEN
        SET NEW.horas_trabajadas = TIMEDIFF(NEW.hora_salida, NEW.hora_entrada);
    ELSE
        SET NEW.horas_trabajadas = NULL;
    END IF;
END //

DELIMITER ;



/*
PROCEDIMIENTOS ALMACENADOS
*/
DELIMITER //

CREATE PROCEDURE generar_reporte_semanal(
    IN p_numero_nomina SMALLINT UNSIGNED,
    IN p_fecha_inicio DATE,
    IN p_fecha_fin DATE
)
BEGIN
    DECLARE total_horas DECIMAL(10, 2);
    DECLARE total_deudas DECIMAL(10, 2);
    DECLARE total_abonado DECIMAL(10, 2);
    DECLARE saldo_final DECIMAL(10, 2);
    DECLARE total_efectivo DECIMAL(10, 2);
    DECLARE total_tarjeta DECIMAL(10, 2);

    -- Calcular el total de horas trabajadas
    SELECT COALESCE(SUM(TIME_TO_SEC(horas_trabajadas)) / 3600, 0) INTO total_horas
    FROM asistencias
    WHERE numero_nomina = p_numero_nomina
      AND fecha BETWEEN p_fecha_inicio AND p_fecha_fin;

    -- Calcular el total de deudas (préstamos)
    SELECT COALESCE(SUM(monto), 0) INTO total_deudas
    FROM prestamos
    WHERE numero_nomina = p_numero_nomina
      AND fecha_solicitud BETWEEN p_fecha_inicio AND p_fecha_fin;

    -- Calcular el total abonado (pagos)
    SELECT COALESCE(SUM(monto), 0) INTO total_abonado
    FROM pagos
    WHERE numero_nomina = p_numero_nomina
      AND fecha_pago BETWEEN p_fecha_inicio AND p_fecha_fin;

    -- Calcular el saldo remanente
    SET saldo_final = total_deudas - total_abonado;

    -- Calcular el total en efectivo
    SELECT COALESCE(SUM(monto), 0) INTO total_efectivo
    FROM pagos
    WHERE numero_nomina = p_numero_nomina
      AND metodo_pago = 'Efectivo'
      AND fecha_pago BETWEEN p_fecha_inicio AND p_fecha_fin;

    -- Calcular el total en tarjeta
    SELECT COALESCE(SUM(monto), 0) INTO total_tarjeta
    FROM pagos
    WHERE numero_nomina = p_numero_nomina
      AND metodo_pago = 'Tarjeta'
      AND fecha_pago BETWEEN p_fecha_inicio AND p_fecha_fin;

    -- Insertar el reporte en la tabla reportes_semanales
    INSERT INTO reportes_semanales (
        numero_nomina,
        fecha_inicio,
        fecha_fin,
        total_horas_trabajadas,
        total_deudas,
        total_abonado,
        saldo_final,
        total_efectivo,
        total_tarjeta
    ) VALUES (
        p_numero_nomina,
        p_fecha_inicio,
        p_fecha_fin,
        total_horas,
        total_deudas,
        total_abonado,
        saldo_final,
        total_efectivo,
        total_tarjeta
    );
END //


CREATE PROCEDURE calcular_pago_empleado(
    IN p_numero_nomina SMALLINT UNSIGNED,
    IN p_fecha_inicio DATE,
    IN p_fecha_fin DATE
)
BEGIN
    DECLARE total_horas DECIMAL(10, 2);
    DECLARE sueldo_diario DECIMAL(8, 2);
    DECLARE monto_a_pagar DECIMAL(10, 2);
    DECLARE pago_deposito DECIMAL(10, 2);
    DECLARE pago_efectivo DECIMAL(10, 2);
    DECLARE retencion_imss DECIMAL(10, 2) DEFAULT 50;
    DECLARE saldo_actual DECIMAL(10, 2) DEFAULT 0;

    -- Obtener el sueldo diario del empleado
    SELECT sueldo_diario INTO sueldo_diario
    FROM empleados
    WHERE numero_nomina = p_numero_nomina;

    -- Calcular el total de horas trabajadas
    SELECT COALESCE(SUM(TIME_TO_SEC(horas_trabajadas)) / 3600, 0) INTO total_horas
    FROM asistencias
    WHERE numero_nomina = p_numero_nomina
      AND fecha BETWEEN p_fecha_inicio AND p_fecha_fin;

    -- Calcular el monto a pagar
    SET monto_a_pagar = total_horas * sueldo_diario;

    -- Restar la retención de IMSS
    SET monto_a_pagar = monto_a_pagar - retencion_imss;

    -- Obtener el saldo actual del empleado
    SELECT saldo INTO saldo_actual
    FROM pagos
    WHERE numero_nomina = p_numero_nomina
    ORDER BY fecha_pago DESC
    LIMIT 1;

    -- Ajustar el monto a pagar con el saldo actual
    SET monto_a_pagar = monto_a_pagar + COALESCE(saldo_actual, 0);

    -- Calcular el pago en efectivo y depósito
    SET pago_deposito = FLOOR(monto_a_pagar / 50) * 50;
    SET pago_efectivo = monto_a_pagar - pago_deposito;

    -- Insertar el registro de pago
    INSERT INTO pagos (
        numero_nomina,
        fecha_pago,
        monto,
        pago_deposito,
        pago_efectivo,
        area,
        retenciones_imss
    ) VALUES (
        p_numero_nomina,
        CURDATE(),
        monto_a_pagar,
        pago_deposito,
        pago_efectivo,
        'Nómina',
        retencion_imss
    );

    -- Actualizar el saldo del empleado
    UPDATE pagos
    SET saldo = monto_a_pagar - (pago_deposito + pago_efectivo)
    WHERE numero_nomina = p_numero_nomina
    ORDER BY fecha_pago DESC
    LIMIT 1;

END //

DELIMITER ;



/*
INDICES
*/
USE gestion_laboral;

-- Índices para la tabla asistencias
CREATE INDEX idx_fecha ON asistencias(fecha);
CREATE INDEX idx_tipo_registro ON asistencias(tipo_registro);
CREATE INDEX idx_asistencia_fecha_nomina ON asistencias(fecha, numero_nomina);

-- Índices para la tabla pagos
CREATE INDEX idx_fecha_pago ON pagos(fecha_pago);
CREATE INDEX idx_area ON pagos(area);
CREATE INDEX idx_pagos_fecha_nomina ON pagos(fecha_pago, numero_nomina);

-- Índices para la tabla prestamos
CREATE INDEX idx_fecha_solicitud ON prestamos(fecha_solicitud);
CREATE INDEX idx_estado_prestamo ON prestamos(estado);
CREATE INDEX idx_prestamos_fecha_nomina ON prestamos(fecha_solicitud, numero_nomina);

-- Índices para la tabla desempeno
CREATE INDEX idx_puntualidad ON desempeno(puntualidad);

 
/*
CONSULTAS
*/
-- CONSULTAS GENERALES
-- Consultas generales para la tabla empleados
SELECT * FROM empleados;

-- Consultas generales para la tabla asistencias
SELECT * FROM asistencias;

-- Consultas generales para la tabla pagos
SELECT * FROM pagos;

-- Consultas generales para la tabla prestamos
SELECT * FROM prestamos;

-- Consultas generales para la tabla desempeno
SELECT * FROM desempeno;

-- Consultas generales para la tabla reportes_semanales
SELECT * FROM reportes_semanales;


-- Consultas especficas 
-- Total de horas trabajadas por empleado en un rango de fechas
SELECT numero_nomina, SUM(TIME_TO_SEC(horas_trabajadas)) / 3600 AS total_horas
FROM asistencias
WHERE fecha BETWEEN '2025-02-01' AND '2025-02-28'
GROUP BY numero_nomina;

-- Total de pagos realizados por empleado en un rango de fechas
SELECT numero_nomina, SUM(monto) AS total_pagado
FROM pagos
WHERE fecha_pago BETWEEN '2025-02-01' AND '2025-02-28'
GROUP BY numero_nomina;

-- Préstamos pendientes por empleado
SELECT numero_nomina, SUM(saldo_prestamo) AS total_pendiente
FROM prestamos
WHERE estado = 'Pendiente'
GROUP BY numero_nomina;

-- Desempeño promedio de puntualidad por empleado
SELECT numero_nomina, AVG(puntualidad) AS puntualidad_promedio
FROM desempeno
GROUP BY numero_nomina;

-- Reporte semanal de un empleado específico
SELECT *
FROM reportes_semanales
WHERE numero_nomina = 1 AND fecha_inicio = '2025-02-04' AND fecha_fin = '2025-03-04';

-- Empleados con bonificaciones en el último mes
SELECT e.nombre_completo, d.bonificacion
FROM empleados e
JOIN desempeno d ON e.numero_nomina = d.numero_nomina
WHERE d.bonificacion IS NOT NULL AND d.fecha_creacion >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH);

-- Total de retenciones de IMSS por área en un rango de fechas
SELECT area, SUM(retenciones_imss) AS total_retenciones
FROM pagos
WHERE fecha_pago BETWEEN '2025-02-01' AND '2025-02-28'
GROUP BY area;
