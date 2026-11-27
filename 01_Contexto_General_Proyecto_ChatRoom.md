# 01 --- Contexto general del proyecto ChatRoom

## 1. Identificación

  Elemento                  Definición
  ------------------------- ------------------------------------------------
  Proyecto                  ChatRoom
  Asignatura                IS294 -- Arquitectura Cliente Servidor
  Modalidad                 Proyecto Final 2, Opción A
  Objetivo técnico          Servidor TCP concurrente con estado compartido
  Lenguaje                  Python 3
  Concurrencia              `asyncio` (Event Loop y corrutinas)
  Transporte                TCP mediante sockets
  Protocolo de aplicación   JSON delimitado por salto de línea (`\\n`)
  Persistencia              SQLite
  Cliente inicial           Aplicación de consola en Python

Este documento combina los requisitos académicos del PDF de la
asignatura con decisiones de implementación propuestas para organizar el
desarrollo. Los requisitos de la rúbrica se distinguen de las decisiones
tecnológicas sugeridas.

## 2. Resumen del proyecto

ChatRoom será un sistema de mensajería en tiempo real basado en
arquitectura cliente-servidor. Varios usuarios podrán conectarse a un
servidor TCP, identificarse mediante un nombre de usuario, crear salas,
consultar salas existentes, unirse a ellas, enviar mensajes y recibir
notificaciones de los acontecimientos del sistema.

El servidor deberá atender múltiples clientes simultáneamente. Un
usuario lento, desconectado o que no consuma los mensajes recibidos no
debe detener la atención de los demás.

La primera versión utilizará clientes de consola para concentrar el
trabajo en el servidor TCP, el protocolo y la concurrencia. Una interfaz
gráfica o web se considerará una ampliación posterior, no un requisito
para demostrar el núcleo de red.

## 3. Relación con la rúbrica académica

La guía de IS294 describe un servidor concurrente de red que atienda
múltiples clientes en tiempo real sin que solicitudes lentas o
bloqueantes congelen el servicio (*head-of-line blocking*).

La Opción A propone un servidor TCP concurrente con estado compartido.
Los casos de uso sugeridos incluyen juegos multijugador o un chat por
salas/canales. Menciona sockets TCP (`SOCK_STREAM`), un pool de hilos o
un Event Loop con corrutinas (`asyncio`), y sincronización del estado
mediante mecanismos como `Lock`/`RLock` o regiones críticas.

### Criterios de evaluación del Proyecto Final 2

  ------------------------------------------------------------------------
  Criterio                                    Puntos Evidencia esperada
  --------------------- ---------------------------- ---------------------
  Arquitectura y modelo                           30 Modelo concurrente
  de concurrencia                                    justificado; varios
                                                     clientes atendidos
                                                     sin que uno lento
                                                     bloquee a los demás.

  Manejo de sockets y                             20 Ciclo de vida
  protocolo de red                                   correcto de sockets y
                                                     manejo adecuado del
                                                     protocolo y flujo de
                                                     bytes.

  Sincronización,                                 20 Protección de
  control de estado y                                recursos compartidos,
  resiliencia                                        backpressure,
                                                     límites, timeouts y
                                                     cierre estructurado.

  Uso crítico y                                   20 Bitácora de prompts,
  auditoría de IA                                    identificación de
                                                     errores y
                                                     refactorización
                                                     manual.

  Pruebas de carga                                10 Pruebas con múltiples
  simultánea y defensa                               clientes y
  oral                                               explicación del
                                                     funcionamiento
                                                     interno.

  **Total**                                  **100**
  ------------------------------------------------------------------------

### Requisitos expresos de la guía

-   Gestión del ciclo de vida de sockets: `bind`, `listen`, aceptación y
    recepción, según el modelo implementado.
-   Uso apropiado de opciones como `SO_REUSEADDR` o `SO_REUSEPORT`,
    cuando proceda.
-   Selección y justificación del modelo de concurrencia: hilo por
    conexión/ThreadPool, multiproceso o Event Loop con I/O multiplexado
    (`epoll`/`asyncio`).
-   Protección de variables y recursos compartidos mediante cerrojos,
    colas Producer-Consumer o aislamiento de memoria.
-   Manejo de timeouts y excepciones de red.
-   Captura de señales de apagado o mecanismo de `shutdown`.
-   Liberación de sockets para evitar fugas de descriptores y errores
    como `EMFILE`.
-   Pruebas que demuestren atención simultánea y auditoría del código
    sugerido por IA.

## 4. Objetivo general

Diseñar e implementar un chat por salas cuyo servidor TCP gestione
múltiples clientes concurrentes, distribuya mensajes y notificaciones en
tiempo real y mantenga la estabilidad ante clientes lentos,
desconexiones y errores de comunicación.

## 5. Objetivos específicos

1.  Implementar un servidor TCP que acepte múltiples conexiones.
2.  Definir un protocolo estructurado y validable.
3.  Implementar identificación básica de usuarios conectados.
4.  Crear y administrar salas independientes.
5.  Permitir el ingreso y salida de usuarios de las salas.
6.  Distribuir mensajes únicamente a los miembros de la sala
    correspondiente.
7.  Emitir notificaciones de conexión, desconexión y cambios en las
    salas.
8.  Administrar el estado compartido de forma segura.
9.  Aplicar colas de salida acotadas y una política de backpressure.
10. Gestionar timeouts, excepciones, desconexiones y apagado limpio.
11. Persistir mensajes e información básica de salas en SQLite.
12. Demostrar el comportamiento mediante pruebas unitarias, de
    integración y concurrencia.
13. Documentar el uso de IA y las correcciones técnicas realizadas por
    el estudiante.

## 6. Alcance funcional

### 6.1 Incluido en la primera versión

**Usuarios** - Conectarse al servidor. - Identificarse con un nombre de
usuario. - Rechazar nombres vacíos, inválidos o duplicados entre
usuarios conectados. - Consultar usuarios conectados. - Desconectarse
correctamente.

**Salas** - Crear una sala con identificador y nombre. - Consultar salas
disponibles. - Unirse y abandonar una sala. - Consultar integrantes. -
Impedir que un usuario se una dos veces a la misma sala. - Mantener
separados los mensajes de cada sala.

**Mensajes** - Enviar mensajes a una sala. - Identificar remitente, sala
y fecha/hora. - Rechazar contenido vacío o inválido. - Recibir mensajes
en tiempo real. - Consultar el historial.

**Notificaciones** - Usuario conectado o desconectado. - Sala creada. -
Usuario que entra o abandona una sala. - Nuevo mensaje. - Error o
confirmación de operación.

### 6.2 Fuera del alcance inicial

No son necesarias para la primera entrega: - Llamadas de voz o
videollamadas. - Envío de archivos o imágenes. - Cifrado de extremo a
extremo. - Recuperación de contraseñas o autenticación externa. -
Aplicación móvil. - Interfaz web. - Mensajes editables o eliminables. -
Reacciones avanzadas o indicadores complejos de escritura. - Despliegue
en la nube.

Estas funciones solo se considerarán cuando el núcleo requerido esté
terminado y probado.

## 7. Actores y escenarios principales

**Actor principal: usuario conectado.** Puede conectarse, identificarse,
consultar salas, crear una sala, unirse a ella, enviar mensajes, recibir
mensajes y notificaciones, consultar el historial y salir.

Escenarios: 1. **Conexión:** el cliente abre una conexión TCP; el
servidor valida el nombre y registra la sesión. 2. **Creación de sala:**
el servidor valida el nombre, crea la sala y confirma la operación. 3.
**Ingreso:** el servidor agrega al usuario y notifica a los integrantes
correspondientes. 4. **Mensaje:** el servidor valida, registra y
distribuye el mensaje a los miembros conectados de esa sala. 5.
**Cliente lento:** su cola de salida alcanza el límite; se aplica una
política de saturación sin detener a otros clientes. 6. **Desconexión:**
el servidor elimina la sesión, retira al usuario de las salas y libera
recursos. 7. **Apagado:** el servidor deja de aceptar conexiones, cierra
sesiones y libera sockets y tareas.

## 8. Arquitectura propuesta

Se propone una arquitectura cliente-servidor con responsabilidades
separadas. `asyncio` gestionará la concurrencia de entrada/salida.

  -----------------------------------------------------------------------
  Componente                          Responsabilidad
  ----------------------------------- -----------------------------------
  Servidor TCP                        Preparar el socket, aceptar
                                      conexiones y coordinar el ciclo de
                                      vida.

  Sesión de cliente                   Representar una conexión, procesar
                                      entrada y administrar la cola de
                                      salida.

  Protocolo                           Codificar, delimitar, decodificar y
                                      validar mensajes JSON.

  Gestor de conexiones                Registrar y retirar sesiones
                                      activas.

  Gestor de salas                     Crear salas y administrar miembros.

  Servicio de chat                    Coordinar operaciones y reglas de
                                      negocio.

  Gestor de eventos                   Publicar y distribuir
                                      notificaciones.

  Repositorios                        Separar consultas/escrituras SQLite
                                      de la lógica de negocio.

  Cliente de consola                  Enviar comandos y recibir mensajes
                                      sin bloquear la red.
  -----------------------------------------------------------------------

### Flujo general

1.  El cliente abre una conexión TCP.
2.  El servidor acepta la conexión y crea una sesión.
3.  El cliente envía su mensaje de conexión.
4.  El servidor valida y registra al usuario.
5.  El cliente envía operaciones: crear sala, unirse o enviar mensaje.
6.  El servidor valida la operación y llama al servicio correspondiente.
7.  El servicio actualiza el estado y, cuando aplique, persiste
    información.
8.  Los eventos se distribuyen a las sesiones destinatarias mediante sus
    colas.
9.  Una tarea independiente por sesión envía los datos pendientes.
10. Ante desconexión o error, se cierra la sesión y se liberan recursos.

## 9. Modelo de concurrencia

Se propone **`asyncio` con Event Loop y corrutinas** porque el chat
mantiene conexiones abiertas y realiza principalmente operaciones de
entrada/salida. Permite gestionar múltiples conexiones sin crear
obligatoriamente un hilo del sistema operativo por cliente.

Cada sesión tendrá tareas asíncronas para leer/procesar mensajes y
enviar mensajes pendientes. Deben aplicarse estas reglas:

-   No ejecutar operaciones bloqueantes de larga duración dentro del
    Event Loop.
-   Mantener una cola de salida independiente por sesión.
-   Establecer límites de tamaño para colas y mensajes.
-   Usar `asyncio.Lock` cuando una secuencia de operaciones sobre estado
    compartido requiera exclusión mutua.
-   No introducir locks por costumbre: documentar qué protegen y por
    qué.
-   No mantener un lock mientras se espera una operación de red.
-   Evitar tareas huérfanas y asegurar su cancelación y cierre.

### Precisión sobre sockets

La aplicación debe demostrar comunicación TCP real. Se puede utilizar
`asyncio.start_server`, `StreamReader` y `StreamWriter`, que administran
sockets TCP internamente. Si se necesita mostrar configuración explícita
del socket, documentar y configurar el socket con el módulo `socket`
antes de entregarlo al Event Loop.

No sustituir el transporte principal por una implementación
exclusivamente HTTP o WebSocket. El transporte de este proyecto es TCP y
el protocolo de aplicación será JSON propio.

## 10. Protocolo de aplicación

TCP transmite un flujo de bytes y no conserva límites de mensajes. Por
ello, cada mensaje JSON se serializará en una línea terminada en `\\n`.
El receptor acumulará bytes hasta encontrar el delimitador, validará el
tamaño y decodificará el mensaje completo.

Ejemplo de solicitud:

``` json
{
  "type": "SEND_MESSAGE",
  "request_id": "req-001",
  "room": "general",
  "content": "Hola a todos"
}
```

El servidor debe identificar al remitente a partir de la sesión
registrada, no confiar ciegamente en un `username` enviado por el
cliente.

Ejemplo de evento del servidor:

``` json
{
  "type": "CHAT_MESSAGE",
  "room": "general",
  "username": "ana",
  "content": "Hola a todos",
  "timestamp": "2026-11-24T18:00:00Z"
}
```

Tipos iniciales de solicitud: - `CONNECT` - `DISCONNECT` -
`CREATE_ROOM` - `LIST_ROOMS` - `JOIN_ROOM` - `LEAVE_ROOM` -
`LIST_USERS` - `SEND_MESSAGE` - `HISTORY`

Respuestas y eventos: - `SUCCESS` - `ERROR` - `ROOM_CREATED` -
`USER_JOINED` - `USER_LEFT` - `CHAT_MESSAGE` - `USER_CONNECTED` -
`USER_DISCONNECTED` - `HISTORY_RESULT`

Cada tipo debe tener campos obligatorios, validaciones y destinatarios
documentados en `docs/protocol.md`.

## 11. Estado compartido y backpressure

Estado compartido mínimo: - Sesiones activas. - Nombres de usuario
ocupados. - Salas existentes. - Miembros de cada sala. - Colas de salida
por cliente.

Se debe documentar qué componente modifica cada estructura y qué
sincronización necesita.

Cada cliente tendrá una cola de salida acotada y una tarea de envío
independiente. La política de saturación debe: - Establecer capacidad
máxima configurable. - Aplicar un tiempo límite al intentar encolar. -
Registrar el evento de saturación. - Cerrar de forma controlada o
aplicar otra política explícita si el cliente no consume. - Impedir
crecimiento ilimitado de memoria. - Evitar esperar indefinidamente por
un cliente lento durante la distribución.

Usar `asyncio.Queue` por sí solo no demuestra backpressure: deben
existir límites y una política verificable.

## 12. Persistencia

SQLite almacenará: - Salas persistentes. - Mensajes enviados. -
Identificador de sala. - Remitente. - Contenido. - Fecha y hora.

La lógica de negocio no debe ejecutar SQL directamente. Utilizar
repositorios. Las operaciones de disco potencialmente bloqueantes no
deben ejecutarse directamente dentro del Event Loop; se puede utilizar
`asyncio.to_thread` para operaciones síncronas acotadas o una biblioteca
asíncrona si se justifica.

SQLite es una base de datos local: no requiere instalar ni mantener un
servidor de base de datos separado.

## 13. Tecnologías y configuración externa

  -----------------------------------------------------------------------
  Tecnología              Uso                     ¿Requiere configuración
                                                  fuera del código?
  ----------------------- ----------------------- -----------------------
  Python 3                Lenguaje y ejecución    **Sí:** instalar en el
                                                  sistema operativo y
                                                  verificar versión.

  Visual Studio Code      Editor                  **Sí:** instalar
                                                  aplicación.

  Extensión Python        Edición, ejecución y    **Sí:** instalar desde
                          depuración              Extensions.

  Pylance                 Análisis y              Recomendable; instalar
                          autocompletado          desde Extensions.

  `asyncio`               Concurrencia            No; biblioteca
                                                  estándar.

  `socket`                Sockets TCP             No; biblioteca
                                                  estándar.

  `json`                  Serialización           No; biblioteca
                                                  estándar.

  `sqlite3`               Persistencia local      No requiere servidor
                                                  externo; viene con
                                                  Python.

  `pytest`                Pruebas                 Instalar en el entorno
                                                  virtual con `pip`.

  Git                     Control de versiones    **Sí:** instalar en el
                                                  sistema operativo.

  GitHub                  Repositorio remoto      **Sí:** cuenta y
                                                  autenticación desde el
                                                  equipo.

  diagrams.net            Diagramas               Navegador o aplicación
                                                  de escritorio.

  PlantUML                Diagramas como código   Puede requerir Java y
                                                  Graphviz según la
                                                  instalación.

  Firewall                Permitir conexiones TCP **Puede requerir
                                                  configuración
                                                  externa**,
                                                  especialmente entre
                                                  equipos.
  -----------------------------------------------------------------------

### Acciones que la IA no puede completar únicamente modificando código

1.  Instalar Python en Windows/Linux/macOS.
2.  Instalar VS Code y sus extensiones.
3.  Instalar Git y configurar credenciales.
4.  Crear una cuenta de GitHub y autorizar acceso.
5.  Permitir el puerto TCP en el firewall del sistema operativo.
6.  Configurar router, red local o reglas de seguridad si se conectan
    equipos de redes distintas.
7.  Instalar Java/Graphviz si se utiliza PlantUML local que los
    requiera.

La IA puede generar instrucciones o scripts, pero el usuario debe
ejecutarlos y autorizar permisos cuando el sistema lo solicite.

## 14. Pruebas y evidencias

**Pruebas funcionales:** conexiones, nombres duplicados,
creación/listado de salas, ingreso/salida, mensajes, aislamiento entre
salas, notificaciones e historial.

**Pruebas de concurrencia:** 5, 10, 20 y, si el equipo lo permite, 50
clientes. Registrar conexiones exitosas, mensajes, errores, tiempos
observados y comportamiento de colas.

**Pruebas de resiliencia:** desconexión abrupta, JSON malformado,
mensaje excesivo, cliente que deja de leer, cola llena, timeout y
apagado durante actividad.

No inventar métricas ni resultados. Ejecutar las pruebas y conservar
evidencia.

## 15. Uso responsable y auditoría de IA

La IA es asistente de programación. El estudiante debe revisar y
comprender las propuestas.

`docs/ai_log.md` registrará fecha, objetivo del prompt, propuesta,
archivos afectados, riesgo detectado, corrección, justificación y prueba
de verificación.

Auditar especialmente: - Operaciones bloqueantes en el Event Loop. -
Errores de delimitación del flujo TCP. - Colas ilimitadas. - Condiciones
de carrera. - Locks mantenidos durante operaciones de red. - Tareas
asíncronas no canceladas. - Sockets no cerrados. - Manejo incorrecto de
desconexiones.

## 16. Definición de terminado

El núcleo estará terminado cuando: - El servidor TCP acepte múltiples
clientes. - Los usuarios se identifiquen correctamente. - Se creen y
administren salas. - Los mensajes lleguen solo a miembros de la sala. -
Se distribuyan notificaciones. - Exista persistencia del historial. - Se
controle el estado compartido. - Existan colas acotadas y política de
backpressure. - Un cliente lento no bloquee a los demás. - Se gestionen
timeouts, desconexiones y apagado limpio. - Las pruebas de concurrencia
se ejecuten y documenten. - La bitácora de IA esté completa. - Los
diagramas reflejen el código real. - El estudiante pueda explicar y
demostrar las decisiones.

## 17. Riesgos y prevención

  -----------------------------------------------------------------------
  Riesgo                              Prevención
  ----------------------------------- -----------------------------------
  Mezclar funcionalidades             Desarrollar por fases y aprobar
  prematuramente                      cada una.

  Introducir interfaz gráfica         Mantener primero cliente de
  demasiado pronto                    consola.

  Sustituir TCP por WebSocket         Mantener sockets TCP como
                                      transporte principal.

  Acoplar salas, conexiones y         Separar gestores, servicios y
  persistencia                        repositorios.

  Bloquear el Event Loop              Revisar operaciones potencialmente
                                      bloqueantes.

  Colas ilimitadas                    Definir capacidad y política de
                                      saturación.

  Diagramas desactualizados           Actualizarlos ante cambios
                                      arquitectónicos.

  Código IA incomprendido             Explicar, revisar y probar cada
                                      módulo.

  Alcance excesivo                    Posponer extras hasta cumplir la
                                      rúbrica.
  -----------------------------------------------------------------------

## 18. Regla de oro

Construir primero un servidor TCP pequeño, concurrente y verificable.
Después incorporar salas, mensajes, notificaciones y persistencia,
probando cada incremento antes de avanzar. Una aplicación pequeña que
cumple y demuestra la rúbrica es preferible a una grande cuya
arquitectura no pueda explicarse.
