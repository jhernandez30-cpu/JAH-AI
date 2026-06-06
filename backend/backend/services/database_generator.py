from __future__ import annotations

from services.conversation_resolver import normalize_text


def generate_database_schema(domain: str, dialect: str = "mysql") -> str:
    """
    Genera estructura SQL completa para el dominio solicitado.
    """
    normalized_domain = normalize_text(domain)
    if "bakery" in normalized_domain or "panaderia" in normalized_domain:
        return generate_bakery_database_schema(dialect=dialect)
    if any(token in normalized_domain for token in ["product", "producto", "venta", "inventario", "sales", "inventory"]):
        return generate_products_sales_inventory_schema(dialect=dialect)
    return generate_generic_business_database_schema(dialect=dialect)


def generate_bakery_database_schema(dialect: str = "mysql") -> str:
    """
    Genera base de datos completa de panaderia.
    """
    dialect = _normalize_dialect(dialect)
    if dialect == "postgresql":
        return _postgres_from_mysql(_BAKERY_MYSQL)
    if dialect == "sqlite":
        return _sqlite_from_mysql(_BAKERY_MYSQL)
    return _BAKERY_MYSQL.strip()


def generate_products_sales_inventory_schema(dialect: str = "mysql") -> str:
    dialect = _normalize_dialect(dialect)
    if dialect == "postgresql":
        return _postgres_from_mysql(_PRODUCTS_SALES_MYSQL)
    if dialect == "sqlite":
        return _sqlite_from_mysql(_PRODUCTS_SALES_MYSQL)
    return _PRODUCTS_SALES_MYSQL.strip()


def generate_generic_business_database_schema(dialect: str = "mysql") -> str:
    dialect = _normalize_dialect(dialect)
    if dialect == "postgresql":
        return _postgres_from_mysql(_GENERIC_BUSINESS_MYSQL)
    if dialect == "sqlite":
        return _sqlite_from_mysql(_GENERIC_BUSINESS_MYSQL)
    return _GENERIC_BUSINESS_MYSQL.strip()


def _normalize_dialect(dialect: str) -> str:
    text = normalize_text(dialect)
    if text in {"postgres", "postgresql"}:
        return "postgresql"
    if text == "sqlite":
        return "sqlite"
    return "mysql"


def _postgres_from_mysql(sql: str) -> str:
    converted = sql
    converted = converted.replace("CREATE DATABASE IF NOT EXISTS panaderia_db;\nUSE panaderia_db;\n\n", "")
    converted = converted.replace("CREATE DATABASE IF NOT EXISTS negocio_db;\nUSE negocio_db;\n\n", "")
    converted = converted.replace("CREATE DATABASE IF NOT EXISTS ventas_inventario_db;\nUSE ventas_inventario_db;\n\n", "")
    converted = converted.replace(" INT AUTO_INCREMENT PRIMARY KEY", " SERIAL PRIMARY KEY")
    converted = converted.replace(" TINYINT DEFAULT 1", " SMALLINT DEFAULT 1")
    converted = converted.replace("ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;", "")
    converted = converted.replace("DATETIME", "TIMESTAMP")
    return converted.strip()


def _sqlite_from_mysql(sql: str) -> str:
    converted = sql
    converted = converted.replace("CREATE DATABASE IF NOT EXISTS panaderia_db;\nUSE panaderia_db;\n\n", "PRAGMA foreign_keys = ON;\n\n")
    converted = converted.replace("CREATE DATABASE IF NOT EXISTS negocio_db;\nUSE negocio_db;\n\n", "PRAGMA foreign_keys = ON;\n\n")
    converted = converted.replace("CREATE DATABASE IF NOT EXISTS ventas_inventario_db;\nUSE ventas_inventario_db;\n\n", "PRAGMA foreign_keys = ON;\n\n")
    converted = converted.replace(" INT AUTO_INCREMENT PRIMARY KEY", " INTEGER PRIMARY KEY AUTOINCREMENT")
    converted = converted.replace(" TINYINT DEFAULT 1", " INTEGER DEFAULT 1")
    converted = converted.replace("ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;", "")
    converted = converted.replace("DATETIME", "TEXT")
    converted = converted.replace("DATE", "TEXT")
    return converted.strip()


_BAKERY_MYSQL = """
CREATE DATABASE IF NOT EXISTS panaderia_db;
USE panaderia_db;

CREATE TABLE categorias (
    id_categoria INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    estado TINYINT DEFAULT 1,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE productos (
    id_producto INT AUTO_INCREMENT PRIMARY KEY,
    id_categoria INT NOT NULL,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    unidad_medida VARCHAR(30) NOT NULL DEFAULT 'unidad',
    precio_venta DECIMAL(10,2) NOT NULL,
    costo_estandar DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    stock_minimo DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    estado TINYINT DEFAULT 1,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_productos_categorias
        FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE clientes (
    id_cliente INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    telefono VARCHAR(30),
    email VARCHAR(120),
    direccion VARCHAR(255),
    estado TINYINT DEFAULT 1,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE empleados (
    id_empleado INT AUTO_INCREMENT PRIMARY KEY,
    nombres VARCHAR(120) NOT NULL,
    apellidos VARCHAR(120) NOT NULL,
    cargo VARCHAR(80) NOT NULL,
    telefono VARCHAR(30),
    email VARCHAR(120),
    fecha_contratacion DATE,
    salario DECIMAL(10,2) DEFAULT 0.00,
    estado TINYINT DEFAULT 1,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE proveedores (
    id_proveedor INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    contacto VARCHAR(120),
    telefono VARCHAR(30),
    email VARCHAR(120),
    direccion VARCHAR(255),
    estado TINYINT DEFAULT 1,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE usuarios (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    id_empleado INT NOT NULL,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(40) NOT NULL DEFAULT 'vendedor',
    estado TINYINT DEFAULT 1,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_usuarios_empleados
        FOREIGN KEY (id_empleado) REFERENCES empleados(id_empleado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE compras (
    id_compra INT AUTO_INCREMENT PRIMARY KEY,
    id_proveedor INT NOT NULL,
    id_empleado INT NOT NULL,
    fecha_compra DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    numero_factura VARCHAR(80),
    subtotal DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    impuesto DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    total DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    estado VARCHAR(30) NOT NULL DEFAULT 'registrada',
    CONSTRAINT fk_compras_proveedores
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor),
    CONSTRAINT fk_compras_empleados
        FOREIGN KEY (id_empleado) REFERENCES empleados(id_empleado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE detalle_compras (
    id_detalle_compra INT AUTO_INCREMENT PRIMARY KEY,
    id_compra INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad DECIMAL(10,2) NOT NULL,
    costo_unitario DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_detalle_compras_compras
        FOREIGN KEY (id_compra) REFERENCES compras(id_compra),
    CONSTRAINT fk_detalle_compras_productos
        FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ventas (
    id_venta INT AUTO_INCREMENT PRIMARY KEY,
    id_cliente INT,
    id_empleado INT NOT NULL,
    fecha_venta DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    numero_comprobante VARCHAR(80) NOT NULL UNIQUE,
    metodo_pago VARCHAR(40) NOT NULL DEFAULT 'efectivo',
    subtotal DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    impuesto DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    descuento DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    total DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    estado VARCHAR(30) NOT NULL DEFAULT 'pagada',
    CONSTRAINT fk_ventas_clientes
        FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
    CONSTRAINT fk_ventas_empleados
        FOREIGN KEY (id_empleado) REFERENCES empleados(id_empleado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE detalle_ventas (
    id_detalle_venta INT AUTO_INCREMENT PRIMARY KEY,
    id_venta INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad DECIMAL(10,2) NOT NULL,
    precio_unitario DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_detalle_ventas_ventas
        FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
    CONSTRAINT fk_detalle_ventas_productos
        FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE inventario (
    id_inventario INT AUTO_INCREMENT PRIMARY KEY,
    id_producto INT NOT NULL UNIQUE,
    stock_actual DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    ultimo_movimiento DATETIME DEFAULT CURRENT_TIMESTAMP,
    ubicacion VARCHAR(100) DEFAULT 'mostrador',
    CONSTRAINT fk_inventario_productos
        FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO categorias (nombre, descripcion) VALUES
('Panes', 'Panes dulces y salados'),
('Pasteles', 'Pasteles y reposteria'),
('Bebidas', 'Bebidas calientes y frias');

INSERT INTO empleados (nombres, apellidos, cargo, telefono, email) VALUES
('Ana', 'Lopez', 'Cajera', '5555-1001', 'ana@panaderia.local'),
('Carlos', 'Mendez', 'Panadero', '5555-1002', 'carlos@panaderia.local');

INSERT INTO productos (id_categoria, codigo, nombre, unidad_medida, precio_venta, costo_estandar, stock_minimo) VALUES
(1, 'PAN-001', 'Pan frances', 'unidad', 0.25, 0.10, 50),
(1, 'PAN-002', 'Pan integral', 'unidad', 0.35, 0.14, 40),
(2, 'PAS-001', 'Pastel de chocolate', 'unidad', 12.00, 6.50, 2);

INSERT INTO clientes (nombre, telefono, email) VALUES
('Cliente general', NULL, NULL),
('Maria Perez', '5555-2001', 'maria@example.com');

INSERT INTO proveedores (nombre, contacto, telefono, email) VALUES
('Harinas del Norte', 'Roberto Ruiz', '5555-3001', 'ventas@harinas.local');

INSERT INTO usuarios (id_empleado, username, password_hash, rol) VALUES
(1, 'ana.caja', 'hash_seguro_aqui', 'cajero');

INSERT INTO inventario (id_producto, stock_actual, ubicacion) VALUES
(1, 120, 'mostrador'),
(2, 80, 'mostrador'),
(3, 5, 'vitrina');

-- Consulta 1: productos con su categoria y stock actual.
SELECT
    p.codigo,
    p.nombre,
    c.nombre AS categoria,
    p.precio_venta,
    i.stock_actual
FROM productos p
JOIN categorias c ON c.id_categoria = p.id_categoria
LEFT JOIN inventario i ON i.id_producto = p.id_producto
WHERE p.estado = 1;

-- Consulta 2: ventas por dia.
SELECT
    DATE(fecha_venta) AS dia,
    COUNT(*) AS cantidad_ventas,
    SUM(total) AS total_vendido
FROM ventas
GROUP BY DATE(fecha_venta)
ORDER BY dia DESC;

-- Consulta 3: productos bajo stock minimo.
SELECT
    p.codigo,
    p.nombre,
    i.stock_actual,
    p.stock_minimo
FROM productos p
JOIN inventario i ON i.id_producto = p.id_producto
WHERE i.stock_actual <= p.stock_minimo;
"""


_PRODUCTS_SALES_MYSQL = """
CREATE DATABASE IF NOT EXISTS ventas_inventario_db;
USE ventas_inventario_db;

CREATE TABLE categorias (
    id_categoria INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    estado TINYINT DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE productos (
    id_producto INT AUTO_INCREMENT PRIMARY KEY,
    id_categoria INT NOT NULL,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    stock_minimo DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    estado TINYINT DEFAULT 1,
    CONSTRAINT fk_productos_categorias
        FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE clientes (
    id_cliente INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    telefono VARCHAR(30),
    email VARCHAR(120)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ventas (
    id_venta INT AUTO_INCREMENT PRIMARY KEY,
    id_cliente INT,
    fecha_venta DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subtotal DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    impuesto DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    total DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    estado VARCHAR(30) NOT NULL DEFAULT 'pagada',
    CONSTRAINT fk_ventas_clientes
        FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE detalle_ventas (
    id_detalle_venta INT AUTO_INCREMENT PRIMARY KEY,
    id_venta INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad DECIMAL(10,2) NOT NULL,
    precio_unitario DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_detalle_ventas_ventas
        FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
    CONSTRAINT fk_detalle_ventas_productos
        FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE inventario (
    id_inventario INT AUTO_INCREMENT PRIMARY KEY,
    id_producto INT NOT NULL UNIQUE,
    stock_actual DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    ultimo_movimiento DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inventario_productos
        FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


_GENERIC_BUSINESS_MYSQL = """
CREATE DATABASE IF NOT EXISTS negocio_db;
USE negocio_db;

CREATE TABLE clientes (
    id_cliente INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    telefono VARCHAR(30),
    email VARCHAR(120),
    estado TINYINT DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE productos (
    id_producto INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    estado TINYINT DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ventas (
    id_venta INT AUTO_INCREMENT PRIMARY KEY,
    id_cliente INT,
    fecha_venta DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    CONSTRAINT fk_ventas_clientes
        FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE detalle_ventas (
    id_detalle_venta INT AUTO_INCREMENT PRIMARY KEY,
    id_venta INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad DECIMAL(10,2) NOT NULL,
    precio_unitario DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_detalle_ventas_ventas
        FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
    CONSTRAINT fk_detalle_ventas_productos
        FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
