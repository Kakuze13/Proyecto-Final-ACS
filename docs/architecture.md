# Arquitectura de ChatRoom

## Alcance aprobado

Proyecto Final 2, Opción A: chat de consola sobre TCP concurrente, con
servidor `asyncio`, protocolo JSON delimitado por LF, salas, usuarios,
mensajes, notificaciones, persistencia SQLite y pruebas de concurrencia.
Quedan fuera del MVP las interfaces web/gráficas, archivos, multimedia,
autenticación externa y despliegue en la nube.

## Casos de uso

1. Conectar e identificarse con un nombre único.
2. Consultar usuarios y salas, crear y eliminar salas, y entrar/salir de ellas.
3. Enviar mensajes a una sala y consultar su historial.
4. Recibir eventos de conexión, salas, membresía y mensajes.
5. Desconectarse voluntariamente o recuperarse de una desconexión/error.
6. Mantener el servicio disponible ante clientes lentos y durante un cierre limpio.

## Componentes y límites

| Componente | Responsabilidad | No debe |
|---|---|---|
| `server.socket_server` | Configurar y aceptar TCP; crear/cerrar sesiones | Aplicar reglas de salas o SQL |
| `server.client_session` | Leer solicitudes, verificar estado de sesión y escribir su cola | Administrar el estado global |
| `server.connection_manager` | Registrar usuarios/sesiones y retirar conexiones | Persistir mensajes |
| `infrastructure.protocol` | Codificar y validar tramas JSON-LF | Cambiar estado del chat |
| `services.room_service` | Crear/listar/eliminar salas y cambiar membresía | Escribir bytes al socket o ejecutar SQL |
| `services.chat_service` | Validar/envíar mensajes y coordinar historial | Abrir conexiones |
| `services.event_manager` | Encolar eventos para los destinatarios | Aplicar reglas de negocio |
| `repositories` | Leer/escribir SQLite | Decidir permisos o reglas del chat |
| `client` | Presentar comandos y usar el protocolo TCP | Acceder a estructuras del servidor |

El servidor es dueño del estado autoritativo. El nombre del remitente se obtiene
de la sesión autenticada, nunca de un campo enviado con `SEND_MESSAGE`.

## Flujo de conexión

1. El cliente abre un stream TCP a `127.0.0.1:8765`.
2. `asyncio.start_server` acepta la conexión y crea `ClientSession`.
3. La primera solicitud debe ser `CONNECT`; el gestor valida y reserva el nombre.
4. El bucle de sesión lee tramas, valida el protocolo y delega en servicios.
5. Los servicios consultan/repositorios y publican eventos a colas por sesión.
6. Una tarea escritora independiente consume cada cola y escribe al stream.
7. Al cerrar, la sesión se elimina de conexiones y salas, se cancelan tareas y se
   liberan streams; los demás clientes permanecen atendidos.

## Concurrencia y estado compartido

Se usa un único Event Loop `asyncio`, adecuado para conexiones TCP con I/O
predominante. Cada sesión tiene una tarea lectora y una escritora; ninguna
escritura de red se ejecuta dentro de una sección crítica. Las mutaciones
compuestas de conexiones/salas se serializan con `asyncio.Lock`; el bloqueo
abarca solo cambios en memoria y nunca esperas de red o disco. SQL se delega a
hilos de trabajo mediante `asyncio.to_thread`.

Cada cola de salida está limitada a 100 eventos. El encolado espera como máximo
100 ms; si vence, se registra la saturación y se cierra esa sesión, sin bloquear
la distribución a los demás. El límite inicial es 100 conexiones simultáneas.
Cada solicitud incompleta tiene 300 s de timeout. Los límites se centralizan en
la configuración del servidor.

## Persistencia y errores

SQLite conserva salas y mensajes tras reinicios. Repositorios separan SQL de
servicios y ejecutan el acceso bloqueante fuera del Event Loop. Los errores
esperables de entrada producen `ERROR`; un frame inválido o excesivo cierra esa
conexión. Los errores internos se registran en servidor, no se filtran al
cliente, y la sesión afectada se cierra de forma controlada.

Eliminar una sala requiere que el nombre de usuario de la sesión coincida con
`created_by`. La sala y su historial se borran en una transacción SQLite; el
servicio retira el estado y membresías de memoria y publica `ROOM_DELETED` a
todos los usuarios conectados. El MVP no implementa autenticación de cuentas,
por lo que este permiso no verifica una identidad fuera de la sesión actual.

## Patrones y auditoría

`EventManager` aplica Observer/publicación-suscripción: los servicios publican
eventos y el gestor resuelve destinatarios y entrega, sin incorporar envío de
bytes en las reglas de sala o mensajería. `ChatService` coordina validación,
repositorio y eventos de chat, pero no se presenta como un patrón GoF. No se
añaden Factory Method, Builder ni abstracciones intercambiables porque el MVP no
necesita variantes de construcción o algoritmos.

Auditoría de implementación: los locks solo protegen cambios breves de estado;
SQL usa parámetros y se ejecuta en `asyncio.to_thread`; cada conexión SQLite se
cierra; cada cliente tiene lector/escritor y cola acotada; errores de protocolo
son distinguibles de errores de operación; el remitente se obtiene de la
sesión. Las pruebas incluyen clientes concurrentes, cliente lento, desconexión,
reinicio y límite de tamaño de respuestas de historial.

## Decisiones iniciales

- Transporte de demostración: TCP real con `asyncio.start_server` y streams;
  no se implementa un segundo servidor ni se sustituye por HTTP/WebSocket.
- Bind local predeterminado: `127.0.0.1:8765`; los equipos externos requieren
  cambio explícito de host y revisión manual del firewall.
- Trama UTF-8: un objeto JSON compacto por línea LF, máximo 65 536 bytes
  incluido el LF.
- Nombres de usuario: 3-20 caracteres ASCII alfanuméricos o `_`, únicos sin
  distinguir mayúsculas; se conserva el texto introducido para mostrarlo.
- Identificador de sala: 1-32 caracteres ASCII minúsculos, dígitos, `_` o `-`.
  Crear sala también une al creador; las salas vacías persisten.
- Mensaje: 1-2 000 caracteres Unicode, remitente y hora UTC asignados por el
  servidor.
- `LIST_USERS` lista a todos los usuarios activos; si se incluye `room`, lista
  miembros de esa sala. Así se cubre la consulta de integrantes sin inventar
  otro tipo de solicitud.
- Eventos globales se envían a usuarios conectados; eventos de sala se limitan
  a los miembros indicados en `protocol.md`.

## Diagramas

- [Componentes](uml/components.puml)
- [Secuencia de conexión](uml/connection_sequence.puml)
