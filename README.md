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

También se puede usar la interfaz gráfica de escritorio:

```powershell
python -m client.gui --host 127.0.0.1 --port 8765
```

La interfaz permite crear salas, unirse, consultar integrantes e intercambiar
mensajes en tiempo real. Los controles se pueden recorrer con `Tab` y las
salas con las flechas del teclado. En el chat, `Ctrl+Enter` envía el mensaje,
`Ctrl+L` enfoca el cuadro de escritura y `Ctrl+R` actualiza las salas. Los
botones `A−` y `A+` ajustan el tamaño del texto. Los nombres de sala se
normalizan a minúsculas y admiten letras, números, `_` y `-`.

El servidor crea la base local `chatroom.db`. Usa `Ctrl+C` para detenerlo; se
cierran el listener, las sesiones y sus tareas. `127.0.0.1` solo permite
conexiones desde el mismo equipo. Para una red local se puede usar
`--host 0.0.0.0`, pero el usuario debe revisar firewall y permisos del equipo.

## Comandos del cliente

Después de identificarse:

```text
/rooms
/create general
/delete general
/users
/say general Hola a todos
/history general 50
/leave general
/quit
```

Las salas creadas se conservan tras reiniciar. El creador entra automáticamente;
las salas vacías permanecen hasta que su creador las elimina con `/delete`.
Eliminar una sala borra también su historial y retira a todos sus integrantes;
la GUI pide confirmación y solo habilita la acción para el creador. El permiso
se basa en el nombre de usuario de la sesión, ya que el MVP no implementa
autenticación de cuentas. Otro cliente puede ejecutar `/join general` y
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

## Demostración visible en la interfaz gráfica

Para reproducir la saturación de forma determinista, detén el servidor normal
con `Ctrl+C` y reinícialo con estos límites de demostración:

```powershell
python -m server.main --host 127.0.0.1 --port 8765 --database chatroom.db --queue-size 1 --enqueue-timeout 0.01 --socket-send-buffer 1024
```

Luego abre la GUI, inicia sesión y crea o únete a `demo_concurrencia`. Desde
una tercera terminal, en esta carpeta, ejecuta:

```powershell
python -m client.demo_concurrency --room demo_concurrencia
```

Pulsa Enter cuando la GUI esté dentro de la sala. El generador conecta un
emisor, un cliente saludable y un cliente lento que no consume mensajes; envía
200 mensajes de 2 000 caracteres y comprueba que el saludable los recibe todos
y que el lento se desconecta por backpressure. Los mensajes con la marca
`DEMO-...` aparecerán en la sala de la GUI. Los límites reducidos son solo para
esta demostración; sin ellos se aplican los valores normales. La prueba
automatizada equivalente, con servidor aislado, está en
`tests/integration/test_tcp_server.py`.
