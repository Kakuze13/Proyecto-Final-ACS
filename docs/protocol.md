# Protocolo ChatRoom v1

## Transporte y framing

TCP es un flujo de bytes; cada trama es un objeto JSON UTF-8 seguido de LF
(`0x0A`). El frame completo, incluido LF, no supera 65 536 bytes. Se permiten
varios frames consecutivos y el receptor debe reconstruir los fragmentados.
CRLF no forma parte del contrato. Objetos JSON, no arrays ni valores escalares.
Campos no reconocidos se rechazan para evitar interpretaciones distintas.

Todas las solicitudes requieren `type` y `request_id`. `request_id` es texto
de 1-64 caracteres; se devuelve en `SUCCESS` o `ERROR`. No se acepta
`username` en solicitudes de mensajería: la identidad viene de la sesión.

## Identidad y validaciones comunes

- `CONNECT` debe ser la primera solicitud y solo puede efectuarse una vez.
- Usuario: `[A-Za-z0-9_]{3,20}`; unicidad sin distinguir mayúsculas.
- Sala: `[a-z0-9_-]{1,32}`.
- Contenido de mensaje: 1-2 000 caracteres Unicode válidos, sin NUL ni
  sustitutos Unicode aislados.
- `HISTORY.limit`: entero entre 1 y 100; predeterminado 50.
- Cada solicitud tiene que llegar completa dentro del timeout configurado.
- JSON válido con campos/tipo de solicitud no admitidos responde `ERROR`
  (con `request_id` cuando se puede leer) y mantiene la sesión. JSON malformado,
  frame grande o UTF-8 inválido genera un error de protocolo cuando sea posible
  y cierra la conexión.

## Solicitudes

| Tipo | Campos además de `type`, `request_id` | Condición |
|---|---|---|
| `CONNECT` | `username` | Primera solicitud |
| `DISCONNECT` | ninguno | Sesión identificada |
| `CREATE_ROOM` | `room` | Identificada; el nombre no existe |
| `LIST_ROOMS` | ninguno | Identificada |
| `JOIN_ROOM` | `room` | Sala existente; no miembro todavía |
| `LEAVE_ROOM` | `room` | Miembro de la sala |
| `LIST_USERS` | `room` opcional | Sin `room`: usuarios activos; con `room`: miembros |
| `SEND_MESSAGE` | `room`, `content` | Miembro de la sala |
| `HISTORY` | `room`, `limit` opcional | Miembro de la sala |

`CREATE_ROOM` crea una sala persistente y une a su creador. No se eliminan salas
vacías. La lista de salas incluye identificador y número actual de miembros.
`HISTORY` devuelve los últimos N mensajes de una sala, en orden cronológico.
Si el frame resultante excede el límite de protocolo, el servidor omite los
mensajes más antiguos hasta que la respuesta quepa e indica `"truncated": true`
en `HISTORY_RESULT`.

## Respuestas

Éxito:

```json
{"type":"SUCCESS","request_id":"r1","operation":"JOIN_ROOM","data":{"room":"general"}}
```

Error:

```json
{"type":"ERROR","request_id":"r1","code":"ROOM_NOT_FOUND","message":"La sala no existe"}
```

El servidor genera `request_id: null` si no puede recuperar un id de una trama
malformada. Errores internos no incluyen trazas ni datos privados.

## Eventos del servidor

| Tipo | Campos del evento | Destinatarios |
|---|---|---|
| `USER_CONNECTED` | `username` | Todos los usuarios identificados |
| `USER_DISCONNECTED` | `username` | Todos los demás usuarios identificados |
| `ROOM_CREATED` | `room`, `created_by` | Todos los usuarios identificados |
| `USER_JOINED` | `room`, `username` | Miembros de la sala después del ingreso, incluido el usuario |
| `USER_LEFT` | `room`, `username` | Miembros restantes de la sala; el usuario recibe `SUCCESS` |
| `CHAT_MESSAGE` | `room`, `username`, `content`, `timestamp` | Miembros actuales, incluido el remitente |
| `HISTORY_RESULT` | `room`, `messages`, `truncated` | Solicitante, como respuesta con `request_id` |

`timestamp` es fecha/hora UTC ISO-8601 con sufijo `Z`, generada por el servidor.
Los eventos no asociados a solicitud omiten `request_id`.

## Códigos de error

`INVALID_REQUEST`, `INVALID_USERNAME`, `USERNAME_TAKEN`, `NOT_CONNECTED`,
`ALREADY_CONNECTED`, `INVALID_ROOM`, `ROOM_EXISTS`, `ROOM_NOT_FOUND`,
`ALREADY_IN_ROOM`, `NOT_IN_ROOM`, `INVALID_CONTENT`, `MESSAGE_TOO_LARGE`,
`UNSUPPORTED_TYPE`, `INTERNAL_ERROR`, `SERVER_BUSY`.

Una conexión saturada o con timeout se cierra; no se espera indefinidamente por
ningún destinatario. Cada respuesta/evento pasa por el encoder común.
