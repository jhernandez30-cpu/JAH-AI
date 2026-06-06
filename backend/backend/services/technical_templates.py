from __future__ import annotations

from typing import Any

from services.conversation_resolver import normalize_text
from services.database_generator import generate_database_schema


def generate_database_answer(
    request: str,
    context: str | None = None,
    dialect: str = "mysql",
    domain: str | None = None,
) -> str:
    resolved_domain = domain or _domain_from_request(request)
    schema = generate_database_schema(resolved_domain, dialect=dialect)
    database_name = _database_name(resolved_domain)
    tables = _tables_for_domain(resolved_domain)
    relations = _relations_for_domain(resolved_domain)

    return f"""Aqui tienes la estructura completa lista para usar.

Base de datos: {database_name}
Descripcion: modelo relacional para gestionar categorias, productos, clientes, empleados, proveedores, compras, ventas, inventario y usuarios.

Tablas principales:
{_bullet_list(tables)}

Relaciones:
{_bullet_list(relations)}

Script SQL completo ({dialect}):

```sql
{schema}
```
"""


def fallback_programming_answer(message: str, intent: dict[str, Any] | None = None) -> str:
    intent = intent or {}
    intent_name = str(intent.get("intent") or "general_question")
    domain = str(intent.get("domain") or _domain_from_request(message))
    dialect = str(intent.get("dialect") or "mysql")

    if intent_name in {"database_design", "sql_generation", "er_model"}:
        return generate_database_answer(message, dialect=dialect, domain=domain)

    if intent_name == "learning_path" or domain == "programming_languages":
        return generate_learning_path_answer(message)

    if intent_name == "crud_generation":
        return generate_python_crud_answer(message)

    if intent_name in {"api_development", "web_development", "code_generation", "programming_help"}:
        return generate_general_programming_answer(message, intent)

    return (
        "Puedo ayudarte con esa tarea tecnica. Dame el lenguaje, framework o formato de salida que prefieres "
        "y te entrego una solucion completa con estructura, codigo y pasos de prueba."
    )


def is_direct_technical_template_intent(intent: dict[str, Any] | None) -> bool:
    intent_name = str((intent or {}).get("intent") or "")
    return intent_name in {
        "database_design",
        "sql_generation",
        "er_model",
        "crud_generation",
        "learning_path",
    }


def generate_learning_path_answer(message: str) -> str:
    return """Esta es una estructura logica para aprender lenguajes de programacion desde cero.

Ruta recomendada:

1. Fundamentos universales
- Logica, variables, tipos de datos, condicionales, bucles y funciones.
- Practica: calculadora, conversor de unidades y validador de formularios.

2. Python como primer lenguaje
- Sintaxis, listas, diccionarios, archivos, modulos, excepciones y entornos virtuales.
- Practica: gestor de tareas en consola y lector de archivos CSV.

3. SQL y bases de datos
- Tablas, claves primarias, claves foraneas, SELECT, JOIN, INSERT, UPDATE y DELETE.
- Practica: base de datos de tienda con productos, clientes, ventas e inventario.

4. HTML, CSS y JavaScript
- Estructura web, estilos, DOM, eventos, formularios y consumo de APIs.
- Practica: catalogo de productos con buscador y carrito simple.

5. Backend con Python
- Flask o FastAPI, rutas, controladores, validacion, conexion a base de datos y autenticacion basica.
- Practica: API CRUD de productos conectada a SQLite o MySQL.

6. Git y flujo profesional
- Repositorios, ramas, commits, pull requests, README y pruebas.
- Practica: publicar un proyecto con instrucciones de instalacion.

7. Proyecto integrador
- App completa: frontend + API + base de datos + CRUD + login basico.
- Entregables: diagrama entidad-relacion, script SQL, endpoints, codigo y pruebas manuales.

Orden sugerido: Python -> SQL -> HTML/CSS -> JavaScript -> FastAPI/Flask -> Git -> proyecto final.
"""


def generate_python_crud_answer(message: str) -> str:
    return """Aqui tienes un CRUD base en Python para productos usando FastAPI y SQLite.

Estructura:

```text
crud_productos/
  main.py
  requirements.txt
  productos.db
```

requirements.txt:

```txt
fastapi
uvicorn
```

main.py:

```python
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DB_PATH = "productos.db"
app = FastAPI(title="CRUD de productos")


class ProductoCreate(BaseModel):
    nombre: str
    precio: float
    stock: int = 0
    categoria: Optional[str] = None


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    precio: Optional[float] = None
    stock: Optional[int] = None
    categoria: Optional[str] = None


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS productos (
                id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                precio REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                categoria TEXT,
                estado INTEGER NOT NULL DEFAULT 1
            )
            '''
        )


def row_to_dict(row):
    return dict(row) if row else None


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/productos")
def crear_producto(producto: ProductoCreate):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO productos (nombre, precio, stock, categoria) VALUES (?, ?, ?, ?)",
            (producto.nombre, producto.precio, producto.stock, producto.categoria),
        )
        conn.commit()
        return {"id_producto": cursor.lastrowid, **producto.model_dump()}


@app.get("/productos")
def listar_productos():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM productos WHERE estado = 1 ORDER BY id_producto DESC").fetchall()
        return [row_to_dict(row) for row in rows]


@app.get("/productos/{id_producto}")
def obtener_producto(id_producto: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM productos WHERE id_producto = ? AND estado = 1",
            (id_producto,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return row_to_dict(row)


@app.put("/productos/{id_producto}")
def actualizar_producto(id_producto: int, producto: ProductoUpdate):
    actual = obtener_producto(id_producto)
    data = producto.model_dump(exclude_unset=True)
    if not data:
        return actual

    campos = ", ".join(f"{campo} = ?" for campo in data)
    valores = list(data.values()) + [id_producto]
    with get_connection() as conn:
        conn.execute(f"UPDATE productos SET {campos} WHERE id_producto = ?", valores)
        conn.commit()
    return obtener_producto(id_producto)


@app.delete("/productos/{id_producto}")
def eliminar_producto(id_producto: int):
    obtener_producto(id_producto)
    with get_connection() as conn:
        conn.execute("UPDATE productos SET estado = 0 WHERE id_producto = ?", (id_producto,))
        conn.commit()
    return {"ok": True, "message": "Producto eliminado"}
```

Ejecutar:

```bash
uvicorn main:app --reload
```

Endpoints:
- POST /productos
- GET /productos
- GET /productos/{id_producto}
- PUT /productos/{id_producto}
- DELETE /productos/{id_producto}
"""


def generate_general_programming_answer(message: str, intent: dict[str, Any] | None = None) -> str:
    return f"""Puedo construirlo. Para avanzar con una respuesta ejecutable, usaria esta estructura base:

1. Definir objetivo y entradas.
2. Crear modelo de datos o estructura de carpetas.
3. Implementar la logica principal.
4. Agregar validaciones y manejo de errores.
5. Probar con casos reales.

Solicitud interpretada: {message}

Si quieres codigo directamente, especifica lenguaje o framework; por ejemplo: Python/FastAPI, Flask, Streamlit, HTML/CSS/JS, React o SQL.
"""


def _domain_from_request(request: str) -> str:
    text = normalize_text(request)
    if "panaderia" in text or "bakery" in text:
        return "bakery"
    if any(token in text for token in ["productos", "ventas", "inventario", "stock"]):
        return "products_sales_inventory"
    if "lenguajes de programacion" in text:
        return "programming_languages"
    return "general"


def _database_name(domain: str) -> str:
    if domain == "bakery":
        return "panaderia_db"
    if domain == "products_sales_inventory":
        return "ventas_inventario_db"
    return "negocio_db"


def _tables_for_domain(domain: str) -> list[str]:
    if domain == "bakery":
        return [
            "categorias",
            "productos",
            "clientes",
            "empleados",
            "proveedores",
            "compras",
            "detalle_compras",
            "ventas",
            "detalle_ventas",
            "inventario",
            "usuarios",
        ]
    if domain == "products_sales_inventory":
        return ["categorias", "productos", "clientes", "ventas", "detalle_ventas", "inventario"]
    return ["clientes", "productos", "ventas", "detalle_ventas"]


def _relations_for_domain(domain: str) -> list[str]:
    if domain == "bakery":
        return [
            "productos.id_categoria -> categorias.id_categoria",
            "usuarios.id_empleado -> empleados.id_empleado",
            "compras.id_proveedor -> proveedores.id_proveedor",
            "compras.id_empleado -> empleados.id_empleado",
            "detalle_compras.id_compra -> compras.id_compra",
            "detalle_compras.id_producto -> productos.id_producto",
            "ventas.id_cliente -> clientes.id_cliente",
            "ventas.id_empleado -> empleados.id_empleado",
            "detalle_ventas.id_venta -> ventas.id_venta",
            "detalle_ventas.id_producto -> productos.id_producto",
            "inventario.id_producto -> productos.id_producto",
        ]
    if domain == "products_sales_inventory":
        return [
            "productos.id_categoria -> categorias.id_categoria",
            "ventas.id_cliente -> clientes.id_cliente",
            "detalle_ventas.id_venta -> ventas.id_venta",
            "detalle_ventas.id_producto -> productos.id_producto",
            "inventario.id_producto -> productos.id_producto",
        ]
    return [
        "ventas.id_cliente -> clientes.id_cliente",
        "detalle_ventas.id_venta -> ventas.id_venta",
        "detalle_ventas.id_producto -> productos.id_producto",
    ]


def _bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
