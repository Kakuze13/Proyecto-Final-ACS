# ChatRoom

Chat de consola para IS294, Proyecto Final 2/Opción A. Implementa un servidor
TCP real con `asyncio`, JSON delimitado por LF, salas, mensajería concurrente,
notificaciones, backpressure y persistencia SQLite.

## Requisitos

- Python 3.10 o posterior.
- Windows PowerShell, VS Code y Git son recomendados para el desarrollo.
- pytest está incluido en `requirements.txt`; SQLite y `asyncio` pertenecen a
  la biblioteca estándar de Python.

## Preparar el entorno en Windows

Desde esta carpeta:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
```

Si PowerShell impide activar el entorno, se puede invocar directamente
`.venv\Scripts\python.exe` sin cambiar la política de ejecución del equipo.

## Ejecutar

En una terminal, iniciar el servidor:

```powershell
python -m server.main --host 127.0.0.1 --port 8765 --database chatroom.db
```

En otra terminal, iniciar el cliente:

```powershell
python -m client.main --host 127.0.0.1 --port 8765
```

El servidor crea la base local `chatroom.db`. Usa `Ctrl+C` para detenerlo; se
cierran el listener, las sesiones y sus tareas. `127.0.0.1` solo permite
conexiones desde el mismo equipo. Para una red local se puede usar
`--host 0.0.0.0`, pero el usuario debe revisar firewall y permisos del equipo.

## Comandos del cliente

Después de identificarse:

```text
/rooms
/create general
/users
/say general Hola a todos
/history general 50
/leave general
/quit
```

Las salas creadas se conservan tras reiniciar. El creador entra automáticamente;
las salas vacías permanecen. Otro cliente puede ejecutar `/join general` y
`/users general` para consultar sus integrantes. Solo los miembros pueden
enviar mensajes o consultar el historial. El servidor asigna remitente y hora.

## Transporte, límites y concurrencia

- TCP con streams de `asyncio`; no usa HTTP ni WebSocket.
- Cada frame es un objeto JSON UTF-8 terminado en LF; máximo 65 536 bytes.
- Máximo inicial: 100 conexiones; timeout de lectura inactiva: 300 s.
- Una cola de salida independiente por cliente, capacidad 100 y timeout de
  encolado de 100 ms. Si se satura, se cierra solo ese cliente.
- Mensajes de hasta 2 000 caracteres; `HISTORY_RESULT` puede indicar
  `truncated: true` para respetar el máximo de frame.
- SQLite se accede mediante repositorios y `asyncio.to_thread`; no se ejecuta
  SQL directamente desde los servicios.

Ver [arquitectura](docs/architecture.md), [protocolo](docs/protocol.md),
[decisiones](docs/decisions.md), [diagramas UML](docs/uml/),
[bitácora de IA](docs/ai_log.md) y [resultados de pruebas](docs/test_results.md).

## Pruebas de carga automatizadas

```powershell
python -m pytest -q tests/integration/test_tcp_server.py -k concurrent_clients
```

La prueba parametrizada ejecuta 5, 10, 20 y 50 clientes simultáneos. Comprueba
conexión, ingreso a una sala y recepción de los mensajes enviados en paralelo.
También se prueba un cliente lento y la persistencia tras reiniciar el servidor.
