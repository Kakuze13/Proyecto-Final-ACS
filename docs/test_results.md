# Resultados de pruebas y verificaciones

## Fase 0 - Preparación del entorno (2026-11-24)

- Python: `3.13.7`, disponible mediante `py` y `python`.
- Git: `2.53.0.windows.2`.
- VS Code: `1.147.0`; extensiones Python `2026.10.0` y Pylance `2026.4.1`.
- Entorno local `.venv`: pytest `8.4.2` instalado desde `requirements.txt`.
- Verificación ejecutada: importar `pytest`, imprimir versiones y ejecutar el script mínimo.
- Resultado: correcto.
- Git: repositorio local inicializado en `ChatRoom/`; no se configuró remoto ni credenciales.

No se ejecutaron pruebas funcionales antes de iniciar la Fase 2.

## Fase 2 - Servidor TCP mínimo (2026-11-24)

- Prueba: `python -m pytest -q tests\integration\test_tcp_server.py`.
- Resultado: 2 pruebas parametrizadas aprobadas.
- Evidencia: dos clientes permanecen conectados, intercambian bytes y la
  desconexión de uno no interrumpe al otro.

## Fase 3 - Protocolo (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 10 pruebas aprobadas.
- Evidencia: JSON-LF, entradas fragmentadas y agrupadas, JSON inválido,
  estructura de solicitud y límite de tamaño.

## Fase 4 - Usuarios y sesiones (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 9 pruebas aprobadas.
- Evidencia: identidades únicas sin distinción de mayúsculas, nombres
  inválidos/duplicados, listado y desconexión voluntaria e inesperada.

## Fase 5 - Salas (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 10 pruebas aprobadas.
- Evidencia: creación, ingreso, duplicados, consulta de miembros y retiro
  automático del usuario desconectado.

## Fase 6 - Mensajería (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 11 pruebas aprobadas.
- Evidencia: mensajes enviados solo por miembros, rechazo de contenido vacío
  y campo de identidad falsificado, distribución a miembros, aislamiento de
  salas y remitente asignado por la sesión.

## Fase 7 - Notificaciones y eventos (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 12 pruebas aprobadas.
- Evidencia: `USER_CONNECTED`, `USER_DISCONNECTED`, `ROOM_CREATED`,
  `USER_JOINED`, `USER_LEFT` y `CHAT_MESSAGE`, con destinatarios verificados.

## Fase 8 - Colas y backpressure (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 13 pruebas aprobadas.
- Evidencia: cola acotada y timeout de 10 ms en la prueba; un cliente TCP real
  que deja de leer se desconecta y el miembro activo recibe los 100 mensajes.
  En producción se usa capacidad 100 y timeout 100 ms.

## Fase 9 - Persistencia SQLite (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 14 pruebas aprobadas.
- Evidencia: sala e historial consultables después de cerrar y reiniciar el
  servidor; se comprueba orden y remitente del registro persistido.

## Fase 10 - Cliente de consola (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 15 pruebas aprobadas.
- Evidencia: componente TCP cliente enruta una respuesta por `request_id` y
  entrega por separado eventos asíncronos; interfaz CLI implementa los comandos
  del protocolo y recibe mientras espera entrada.

## Fase 11 - Resiliencia y cierre limpio (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 17 pruebas aprobadas.
- Evidencia: JSON inválido y frame excesivo reciben error/cierre; timeout idle,
  límite de conexiones, desconexión y cierre/reinicio de servidor verificados.

## Fase 12 - Integración y carga (2026-11-24)

- Prueba: `python -m pytest -q`.
- Resultado: 22 pruebas aprobadas.
- Carga ejecutada: 5, 10, 20 y 50 clientes simultáneos; cada cliente se
  identifica, entra a una sala y envía un mensaje concurrentemente.
- Resultado observable: cada participante recibió los mensajes de todos los
  usuarios; no se registran métricas de latencia, ya que el test no las mide.
- También se verificaron cliente lento, aislamiento, frames inválidos y
  persistencia/reinicio. Evidencia automatizada en `tests/integration/`.

## Fases 13-14 - Auditoría y verificación final (2026-11-24)

- Suite final: `python -m pytest -q` — 27 pruebas aprobadas.
- Sintaxis: `python -m compileall -q client domain infrastructure repositories server services tests` — correcto.
- Inicio/documentación CLI: `python -m server.main --help` y
  `python -m client.main --help` — ambos comandos disponibles.
- Auditoría: framing y tamaño máximo, límites de solicitudes, operaciones SQLite,
  destinatarios, cierre de tareas/streams y backpressure revisados.
- Repositorio remoto: `https://github.com/Kakuze13/Proyecto-Final-ACS`, rama
  `main`; commit inicial `9cdb5453558bd9ecb3852c742341db16febad2f2` verificado.
- Firewall y pruebas entre equipos requieren configuración externa y siguen
  pendientes; no son necesarios para loopback.

## Demostración visible de concurrencia (2026-11-26)

- Servidor de demostración: cola de salida de 1 evento, timeout de 10 ms y
  `SO_SNDBUF` de 1 024 bytes para hacer reproducible la saturación.
- `client.demo_concurrency` envía mensajes etiquetados a una sala existente,
  comprueba que un cliente saludable recibe todos y espera el cierre del cliente
  lento. La GUI, unida a la misma sala, muestra los mensajes en tiempo real.
- Prueba automatizada: `test_concurrency_demo_verifies_slow_client_isolation`;
  la suite completa pasó con 28 pruebas.

## Eliminación de salas (2026-11-26)

- `DELETE_ROOM` permite borrar solo al creador; una transacción elimina la sala
  y todos sus mensajes, retira las membresías y publica `ROOM_DELETED`.
- La GUI confirma la acción, la limita al creador y actualiza salas e historial;
  la consola ofrece `/delete <sala>`.
- Pruebas: usuario no creador rechazado, notificación a los integrantes,
  eliminación del historial y comando de consola.
- Suite completa: `python -m pytest -q` — 31 pruebas aprobadas.
