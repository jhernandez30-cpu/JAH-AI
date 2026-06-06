from __future__ import annotations

from typing import Any

from services.technical_templates import (
    fallback_programming_answer,
    generate_database_answer,
    generate_learning_path_answer,
    generate_python_crud_answer,
)


def generate_technical_answer(request: str, intent: dict[str, Any]) -> str:
    intent_name = str(intent.get("resolved_intent") or intent.get("intent") or "")

    if intent_name in {"database_design", "sql", "er_model", "sql_generation"}:
        return generate_database_solution(request, intent)
    if intent_name in {"crud_generation"}:
        return generate_python_solution(request, intent)
    if intent_name in {"api_generation", "fastapi_help"}:
        return generate_fastapi_solution(request, intent)
    if intent_name in {"csharp"} or str(intent.get("language")) == "csharp":
        return generate_csharp_solution(request, intent)
    if intent_name in {"code_explanation"}:
        return generate_code_explanation(request, _extract_code(intent))
    if intent_name in {"code_debugging"}:
        return generate_debugging_solution(request, _extract_code(intent))
    if intent_name in {"code_review"}:
        return generate_code_review_solution(request, intent)
    if intent_name in {"cybersecurity_defensive", "cybersecurity_analysis"}:
        return generate_cybersecurity_defensive_answer(request, intent)
    if intent_name in {"logical_structure", "algorithm_design"}:
        return generate_logical_structure(request, intent)
    if intent_name in {"project_structure", "backend_architecture", "frontend_development", "streamlit_help", "flask_help"}:
        return generate_project_structure(request, intent)
    if intent_name in {"python", "code_generation"}:
        return generate_python_solution(request, intent)

    return fallback_programming_answer(request, intent)


def should_use_technical_generator(intent: dict[str, Any] | None) -> bool:
    intent_name = str((intent or {}).get("resolved_intent") or (intent or {}).get("intent") or "")
    return intent_name in {
        "database_design",
        "sql",
        "sql_generation",
        "er_model",
        "crud_generation",
        "api_generation",
        "fastapi_help",
        "python",
        "csharp",
        "code_generation",
        "code_explanation",
        "code_debugging",
        "code_review",
        "cybersecurity_defensive",
        "cybersecurity_analysis",
        "logical_structure",
        "algorithm_design",
        "project_structure",
        "backend_architecture",
        "frontend_development",
        "streamlit_help",
        "flask_help",
    }


def generate_database_solution(request: str, intent: dict[str, Any]) -> str:
    domain = str(intent.get("domain") or "general")
    if domain == "panaderia":
        domain = "bakery"
    elif domain in {"ventas_inventario", "productos"}:
        domain = "products_sales_inventory"
    return generate_database_answer(
        request,
        dialect=str(intent.get("dialect") or "mysql"),
        domain=domain,
    )


def generate_python_solution(request: str, intent: dict[str, Any]) -> str:
    if "crud" in str(intent.get("intent")) or "crud" in request.lower():
        return generate_python_crud_answer(request)
    return """Aqui tienes una base clara para una solucion en Python.

Estructura:

```text
proyecto_python/
  main.py
  requirements.txt
  README.md
```

main.py:

```python
def procesar_datos(datos):
    if not datos:
        return []
    return [dato for dato in datos if dato is not None]


def main():
    datos = ["producto", None, "venta", "inventario"]
    resultado = procesar_datos(datos)
    print(resultado)


if __name__ == "__main__":
    main()
```

Cómo ejecutarlo:

```bash
python main.py
```

Recomendaciones:
- Separa la logica en funciones pequeñas.
- Valida entradas antes de procesar datos.
- Agrega pruebas unitarias cuando la logica crezca.
"""


def generate_csharp_solution(request: str, intent: dict[str, Any]) -> str:
    domain = str(intent.get("domain") or "clientes")
    class_name = "Cliente" if domain in {"clientes", "general"} else domain[:1].upper() + domain[1:]
    return f"""Aqui tienes una clase C# lista para usar.

```csharp
using System;

public class {class_name}
{{
    public int Id {{ get; set; }}
    public string Nombre {{ get; set; }}
    public string Telefono {{ get; set; }}
    public string Email {{ get; set; }}
    public bool Activo {{ get; set; }}
    public DateTime FechaRegistro {{ get; set; }}

    public {class_name}()
    {{
        Nombre = string.Empty;
        Telefono = string.Empty;
        Email = string.Empty;
        Activo = true;
        FechaRegistro = DateTime.Now;
    }}

    public {class_name}(int id, string nombre, string telefono, string email)
    {{
        Id = id;
        Nombre = nombre;
        Telefono = telefono;
        Email = email;
        Activo = true;
        FechaRegistro = DateTime.Now;
    }}

    public bool EsValido()
    {{
        return !string.IsNullOrWhiteSpace(Nombre)
            && !string.IsNullOrWhiteSpace(Email)
            && Email.Contains("@");
    }}

    public override string ToString()
    {{
        return $"{class_name}: {{Nombre}} - {{Email}}";
    }}
}}
```

Ejemplo de uso:

```csharp
var cliente = new {class_name}(1, "Maria Perez", "5555-1234", "maria@example.com");

if (cliente.EsValido())
{{
    Console.WriteLine(cliente);
}}
```

Mejoras posibles:
- Agregar DataAnnotations si se usara con ASP.NET Core.
- Separar DTOs si la clase se expone por una API.
- Validar email con reglas mas estrictas en la capa de servicio.
"""


def generate_fastapi_solution(request: str, intent: dict[str, Any]) -> str:
    if "login" in request.lower() or "autenticacion" in request.lower() or "autenticación" in request.lower():
        return generate_fastapi_login_solution(request, intent)
    return """Aqui tienes una API base en FastAPI para productos.

Estructura:

```text
api_productos/
  main.py
  requirements.txt
```

requirements.txt:

```txt
fastapi
uvicorn
pydantic
```

main.py:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="API de productos")


class Producto(BaseModel):
    id: int
    nombre: str
    precio: float
    stock: int = 0


productos: dict[int, Producto] = {}


@app.post("/productos", response_model=Producto)
def crear_producto(producto: Producto):
    if producto.id in productos:
        raise HTTPException(status_code=409, detail="El producto ya existe")
    productos[producto.id] = producto
    return producto


@app.get("/productos")
def listar_productos():
    return list(productos.values())


@app.get("/productos/{producto_id}", response_model=Producto)
def obtener_producto(producto_id: int):
    if producto_id not in productos:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return productos[producto_id]


@app.put("/productos/{producto_id}", response_model=Producto)
def actualizar_producto(producto_id: int, producto: Producto):
    if producto_id not in productos:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    productos[producto_id] = producto
    return producto


@app.delete("/productos/{producto_id}")
def eliminar_producto(producto_id: int):
    if producto_id not in productos:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    del productos[producto_id]
    return {"ok": True}
```

Ejecutar:

```bash
uvicorn main:app --reload
```

Siguiente mejora natural: conectar SQLite/MySQL, agregar autenticacion y mover la logica a servicios/repositorios.
"""


def generate_fastapi_login_solution(request: str, intent: dict[str, Any]) -> str:
    return """Aqui tienes una API en FastAPI para productos con login basico y estructura ejecutable.

Estructura:

```text
api_productos_login/
  main.py
  requirements.txt
```

requirements.txt:

```txt
fastapi
uvicorn
passlib[bcrypt]
python-jose[cryptography]
```

main.py:

```python
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

SECRET_KEY = "cambia_esta_clave_en_variables_de_entorno"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI(title="API de productos con login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


class Producto(BaseModel):
    id: int
    nombre: str
    precio: float
    stock: int = 0


class Token(BaseModel):
    access_token: str
    token_type: str


usuarios = {
    "admin": {
        "username": "admin",
        "password_hash": pwd_context.hash("admin123"),
        "activo": True,
    }
}
productos: dict[int, Producto] = {}


def verificar_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def autenticar_usuario(username: str, password: str):
    usuario = usuarios.get(username)
    if not usuario or not usuario["activo"]:
        return None
    if not verificar_password(password, usuario["password_hash"]):
        return None
    return usuario


def crear_token(data: dict, expires_delta: timedelta | None = None) -> str:
    payload = data.copy()
    expires = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    payload.update({"exp": expires})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def usuario_actual(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    usuario = usuarios.get(username)
    if not usuario:
        raise credentials_exception
    return usuario


@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    usuario = autenticar_usuario(form_data.username, form_data.password)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario o password incorrectos")
    token = crear_token(
        {"sub": usuario["username"]},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer"}


@app.post("/productos", response_model=Producto)
def crear_producto(producto: Producto, usuario=Depends(usuario_actual)):
    if producto.id in productos:
        raise HTTPException(status_code=409, detail="El producto ya existe")
    productos[producto.id] = producto
    return producto


@app.get("/productos")
def listar_productos(usuario=Depends(usuario_actual)):
    return list(productos.values())


@app.get("/productos/{producto_id}", response_model=Producto)
def obtener_producto(producto_id: int, usuario=Depends(usuario_actual)):
    if producto_id not in productos:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return productos[producto_id]


@app.put("/productos/{producto_id}", response_model=Producto)
def actualizar_producto(producto_id: int, producto: Producto, usuario=Depends(usuario_actual)):
    if producto_id not in productos:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    productos[producto_id] = producto
    return producto


@app.delete("/productos/{producto_id}")
def eliminar_producto(producto_id: int, usuario=Depends(usuario_actual)):
    if producto_id not in productos:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    del productos[producto_id]
    return {"ok": True}
```

Ejecutar:

```bash
uvicorn main:app --reload
```

Probar login:

```bash
curl -X POST http://127.0.0.1:8000/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin&password=admin123"
```

Recomendaciones de seguridad:
- Mueve `SECRET_KEY` a una variable de entorno.
- Cambia el usuario demo por una tabla real de usuarios.
- Guarda solo hashes de contrasenas, nunca texto plano.
- Agrega rate limiting y bloqueo temporal por intentos fallidos.
"""


def generate_code_explanation(request: str, code: str | None = None) -> str:
    code_note = "No veo un bloque de codigo completo en el mensaje." if not code else "Analisis del bloque compartido:"
    return f"""{code_note}

1. Que hace
- Identifica entradas, procesa datos y produce una salida segun la logica implementada.

2. Explicacion por partes
- Variables: guardan estado temporal.
- Funciones/metodos: agrupan logica reutilizable.
- Condicionales: deciden que rama ejecutar.
- Bucles: repiten operaciones sobre colecciones.

3. Posibles problemas
- Validar datos nulos o vacios.
- Manejar excepciones esperadas.
- Separar responsabilidades si el bloque mezcla entrada, logica y salida.

4. Mejora recomendada
- Comparte el codigo entre triple backticks para darte una explicacion linea por linea y una version mejorada.
"""


def generate_debugging_solution(request: str, code: str | None = None) -> str:
    return """Diagnostico tecnico:

1. Posibles causas
- Variable no inicializada o con tipo inesperado.
- Error de sintaxis o indentacion.
- Dependencia no instalada.
- Entrada con formato distinto al esperado.

2. Como corregirlo
- Lee el traceback desde la ultima linea hacia arriba.
- Ubica archivo, linea y tipo de excepcion.
- Valida entradas antes de procesarlas.
- Aisla la funcion que falla y prueba con un caso minimo.

3. Plantilla de correccion en Python

```python
def procesar(valor):
    if valor is None:
        raise ValueError("valor no puede ser None")
    return str(valor).strip()


try:
    resultado = procesar(" ejemplo ")
    print(resultado)
except ValueError as error:
    print(f"Entrada invalida: {error}")
except Exception as error:
    print(f"Error inesperado: {error}")
```

Para darte el arreglo exacto, pega el traceback completo y el fragmento de codigo donde ocurre el error.
"""


def generate_code_review_solution(request: str, intent: dict[str, Any]) -> str:
    return """Revision tecnica recomendada:

Hallazgos a revisar:
- Validacion de entradas antes de guardar o consultar datos.
- Manejo de errores sin exponer detalles internos.
- Separacion entre capa de UI, servicios y datos.
- Uso de consultas parametrizadas si hay SQL.
- Pruebas para flujos principales y casos borde.

Version de checklist:
- Correctitud: la logica cubre entradas validas e invalidas.
- Seguridad: no hay secretos hardcodeados ni SQL concatenado.
- Mantenibilidad: funciones pequenas y nombres claros.
- Rendimiento: evitar consultas repetidas y ciclos innecesarios.

Pega el codigo y te devuelvo hallazgos concretos con lineas, impacto y correccion.
"""


def generate_cybersecurity_defensive_answer(request: str, intent: dict[str, Any]) -> str:
    return """Analisis defensivo permitido.

Checklist para login seguro:

1. Contraseñas
- Guardar hashes, nunca texto plano.
- Usar bcrypt, Argon2 o PBKDF2 con salt.
- Aplicar politica de longitud minima y bloqueo temporal por intentos fallidos.

2. SQL Injection
- Usar consultas parametrizadas u ORM.
- Nunca concatenar usuario/contraseña en SQL.

3. Sesiones y tokens
- Cookies HttpOnly, Secure y SameSite.
- JWT con expiracion corta, firma fuerte y rotacion si aplica.

4. Validacion
- Validar email, longitud y formato.
- Mensajes de error genericos: no revelar si existe el usuario.

5. Protecciones web
- CSRF si hay sesiones con cookies.
- Rate limiting en login.
- Logs de intentos fallidos sin guardar contraseñas.

Ejemplo de hash con bcrypt en Python:

```python
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
```

Esto es defensivo y profesional: ayuda a proteger sistemas propios o autorizados.
"""


def generate_logical_structure(request: str, intent: dict[str, Any]) -> str:
    return generate_learning_path_answer(request)


def generate_project_structure(request: str, intent: dict[str, Any]) -> str:
    return """Estructura de proyecto recomendada:

```text
app/
  main.py
  config.py
  models/
    __init__.py
    product.py
  schemas/
    __init__.py
    product_schema.py
  services/
    __init__.py
    product_service.py
  repositories/
    __init__.py
    product_repository.py
  api/
    __init__.py
    product_routes.py
tests/
  test_products.py
requirements.txt
README.md
```

Responsabilidades:
- api: recibe peticiones y devuelve respuestas.
- schemas: valida datos de entrada/salida.
- services: contiene reglas de negocio.
- repositories: accede a base de datos.
- models: define entidades o tablas.
- tests: valida comportamientos importantes.

Regla practica: cada capa debe saber solo lo necesario de la capa siguiente.
"""


def _extract_code(intent: dict[str, Any]) -> str:
    code_info = intent.get("code") if isinstance(intent, dict) else {}
    if not isinstance(code_info, dict):
        return ""
    return str(code_info.get("code") or "")
