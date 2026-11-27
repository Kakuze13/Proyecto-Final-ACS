# Registro de decisiones de arquitectura

## ADR-001: modalidad y alcance

- Estado: aceptado por el usuario.
- Decisión: Proyecto Final 2, Opción A; ChatRoom es un servidor TCP concurrente.
- Motivo: confirmado antes de iniciar el desarrollo; coincide con el contexto 01.
- Consecuencia: primero se demuestra TCP y concurrencia; GUI, web y extras se posponen.

## ADR-002: modelo de concurrencia

- Estado: propuesto para el MVP.
- Decisión: `asyncio` con Event Loop, streams y tareas por sesión.
- Motivo: múltiples conexiones de I/O con menos coste que un hilo por cliente.
- Consecuencia: no se permite I/O bloqueante en el Event Loop; el estado compuesto
  usa locks breves y el disco se delega con `asyncio.to_thread`.

## ADR-003: transporte y socket

- Estado: propuesto para el MVP.
- Decisión: `asyncio.start_server`; TCP local `127.0.0.1:8765` por defecto.
- Motivo: demuestra TCP real y deja ciclo de vida de sockets a una API estándar.
- Consecuencia: no se crea un segundo listener. `asyncio.start_server` recibe
  `reuse_address=True` para solicitar `SO_REUSEADDR`; no se usa `SO_REUSEPORT`,
  que no es necesario para este único listener.

## ADR-004: framing JSON

- Estado: propuesto para el MVP.
- Decisión: objeto JSON UTF-8 por línea LF; límite de frame de 65 536 bytes.
- Motivo: TCP no mantiene límites de mensajes; LF permite tratar fragmentación y
  agrupación en el stream.
- Consecuencia: cliente y servidor comparten el encoder/decoder y rechazan
  frames inválidos o excesivos.

## ADR-005: límites y backpressure

- Estado: propuesto para el MVP.
- Decisión: máximo 100 conexiones y 100 eventos por cola; espera de encolado de
  100 ms; cerrar la sesión lenta cuando se supere.
- Motivo: límites verificables de recursos y aislamiento entre destinatarios.
- Consecuencia: registrar saturaciones y probar con un consumidor detenido.

## ADR-006: nombres y salas

- Estado: propuesto para el MVP.
- Decisión: usuarios ASCII de 3-20 caracteres, únicos sin distinguir mayúsculas;
  salas slug ASCII de 1-32 caracteres. Crear sala une al creador y sala vacía
  permanece.
- Motivo: validación sencilla y reglas deterministas para el cliente de consola.
- Consecuencia: validaciones centrales en servidor y repositorio de salas.

## ADR-007: consulta de miembros

- Estado: propuesto para el MVP.
- Decisión: `LIST_USERS` acepta el campo opcional `room` para listar miembros.
- Motivo: satisface la consulta global y de integrantes sin agregar un tipo de
  solicitud distinto a los tipos iniciales del contexto.
- Consecuencia: el campo y su validación se documentan en `protocol.md`.

## ADR-008: persistencia

- Estado: propuesto para el MVP.
- Decisión: SQLite local para salas e historial; repositorios separados.
- Motivo: persistencia requerida sin servicio de base de datos externo.
- Consecuencia: llamadas SQLite síncronas se ejecutan fuera del Event Loop.

## ADR-009: historial y límite de frame

- Estado: implementado.
- Decisión: `HISTORY_RESULT` descarta los mensajes más antiguos hasta caber en
  65 536 bytes y devuelve `truncated: true` si fue necesario.
- Motivo: preservar el framing TCP JSON-LF sin ampliar el límite global.
- Consecuencia: el cliente puede mostrar el subconjunto más reciente y avisar
  que el resultado fue truncado.

## ADR-010: eliminación de salas

- Estado: implementado.
- Decisión: solo el creador puede eliminar una sala; se borran sus mensajes y
  se retira a todos sus integrantes.
- Motivo: mantener la propiedad explícita y evitar registros huérfanos en SQLite.
- Consecuencia: la eliminación es transaccional, se anuncia globalmente y la
  GUI actualiza su lista y estado de membresía. La autorización se basa en el
  nombre de usuario de sesión; no sustituye autenticación de cuentas.
