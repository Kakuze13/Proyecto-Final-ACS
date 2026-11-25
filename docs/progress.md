# Avance del plan

| Fase | Estado | Evidencia / criterio |
|---|---|---|
| 0 - Preparación | Completa | Python y pytest en `.venv`, VS Code/extensiones, `.gitignore`, `requirements.txt`, prueba mínima y Git local verificados. |
| 1 - Análisis y diseño | Completa | Alcance PF2/Opción A confirmado; arquitectura, flujo, contratos, errores, límites, backpressure, dos diagramas y decisiones registrados. |
| 2 - Servidor TCP mínimo | Completa | Prueba de integración con dos clientes TCP simultáneos; ambos intercambian datos y uno se desconecta sin afectar al otro. |
| 3 - Protocolo | Completa | Encoder/decoder JSON-LF, reconstrucción de fragmentos, mensajes agrupados y validación de errores; suite actual pasa. |
| 4 - Usuarios y sesiones | Completa | Registro único sin distinción de mayúsculas, consulta, desconexión voluntaria e inesperada; pruebas de integración. |
| 5 - Salas | Completa | Crear/listar/unirse/salir, consulta de miembros, aislamiento y limpieza al desconectar; pruebas de integración. |
| 6 - Mensajería | Completa | Validación de sala/pertenencia/contenido; remitente desde sesión; prueba de aislamiento y marca de tiempo. |
| 7 - Notificaciones y eventos | Completa | EventManager separa publicación de reglas; comprobados destinatarios globales y de sala. |
| 8 - Colas y backpressure | Completa | Cola por sesión acotada; timeout de encolado cierra al lento; integración demuestra que otro miembro recibe los mensajes. |
| 9 - Persistencia SQLite | Completa | Salas e historial se restauran tras reinicio; repositorios usan consultas parametrizadas y `asyncio.to_thread`. |
| 10 - Cliente de consola | Completa | Cliente TCP demultiplexa eventos/respuestas; CLI ofrece salas, usuarios, mensajes, historial y salida. |
| 11 - Resiliencia y cierre | Completa | Timeouts, frames inválidos/grandes, límite de conexiones y cierre/reinicio comprobados. |
| 12 - Integración y carga | Completa | Suite completa aprobada; escenarios con 5, 10, 20 y 50 clientes, mensajería simultánea, slow consumer y reinicio. |
| 13 - Auditoría de IA y arquitectura | Completa | Revisadas responsabilidades, dependencias, locks, I/O, framing, colas, tareas, sockets y diagramas; hallazgos corregidos y probados. |
| 14 - Entrega | Completa | Código, README, documentación, pruebas y diagramas publicados en `Kakuze13/Proyecto-Final-ACS`, rama `main`. |

Firewall y pruebas entre equipos quedan pendientes de acciones externas; no
son necesarios para ejecutar el proyecto en loopback.
