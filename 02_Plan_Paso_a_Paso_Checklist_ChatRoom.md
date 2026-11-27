# 02 --- Plan paso a paso y checklist de desarrollo de ChatRoom

## 1. Propósito y reglas de trabajo

Este documento organiza el desarrollo en fases pequeñas, con
dependencias, criterios de aceptación y checklist. Busca evitar que se
mezclen funcionalidades, que varios módulos implementen la misma
responsabilidad o que se avance sin probar lo anterior.

**Regla principal:** no iniciar una fase hasta que la anterior cumpla su
criterio de salida. Si una fase falla, corregirla antes de agregar
funcionalidades.

Consultar también `01_Contexto_General_Proyecto_ChatRoom.md`.

### Reglas para trabajar con IA

Antes de cada fase, proporcionar a la IA: 1. El documento de contexto.
2. Este plan. 3. La estructura actual del proyecto. 4. Los archivos
relevantes. 5. Los resultados de las pruebas actuales.

Instrucciones permanentes: - No reescribir archivos que no estén
relacionados con la tarea. - No cambiar nombres, contratos ni tipos de
mensajes sin advertirlo. - No crear una segunda implementación de una
funcionalidad existente. - No agregar dependencias sin justificarlo. -
No introducir funcionalidades de fases futuras. - Mostrar los archivos
completos creados o modificados. - Explicar dependencias entre
cambios. - Indicar comandos para ejecutar y probar. - No afirmar que una
prueba pasó si no se ejecutó. - Si un cambio afecta el diseño aprobado,
detenerse y solicitar autorización. - Actualizar documentación y
bitácora cuando corresponda.

### Control de cambios

Antes de modificar una funcionalidad: 1. Identificar el módulo
responsable. 2. Identificar módulos dependientes. 3. Definir contratos
de entrada y salida. 4. Modificar el mínimo número de archivos. 5.
Ejecutar pruebas del módulo. 6. Ejecutar pruebas de integración
afectadas. 7. Actualizar diagramas y documentación si cambió el diseño.

El cliente nunca debe manipular directamente las estructuras internas
del servidor. Toda operación pasa por el protocolo y los servicios.

## 2. Tecnologías y qué configurar fuera de VS Code

  -----------------------------------------------------------------------
  Tecnología              Uso                     Configuración externa
  ----------------------- ----------------------- -----------------------
  Python 3                Lenguaje y ejecución    **Sí:** instalar en el
                                                  sistema operativo.

  VS Code                 Editor                  **Sí:** instalar
                                                  aplicación.

  Extensión Python        Depuración y ejecución  **Sí:** instalar en
                                                  Extensions.

  Pylance                 Análisis y              Instalar en Extensions.
                          autocompletado

  `asyncio`, `socket`,    Concurrencia, red,      No; bibliotecas
  `json`, `sqlite3`       protocolo y base local  estándar de Python.

  `pytest`                Pruebas                 Instalar con pip en el
                                                  entorno virtual.

  Git                     Versionamiento          **Sí:** instalar en el
                                                  sistema operativo.

  GitHub                  Repositorio remoto      **Sí:** cuenta y
                                                  autenticación.

  diagrams.net            Diagramas               Navegador o aplicación.

  PlantUML                Diagramas como código   Puede requerir Java y
                                                  Graphviz localmente.

  Firewall                Acceso al puerto        **Puede requerir
                                                  permiso/configuración
                                                  del sistema
                                                  operativo.**
  -----------------------------------------------------------------------

La IA puede dar instrucciones o generar scripts, pero el usuario debe
instalar software, iniciar sesión, autorizar permisos y modificar
configuraciones de seguridad externas.

### Lista de preparación externa

-   [ ] Instalar Python 3.
-   [ ] Comprobar `python --version` o `py --version`.
-   [ ] Instalar Visual Studio Code.
-   [ ] Instalar extensión Python.
-   [ ] Instalar Pylance.
-   [ ] Instalar Git.
-   [ ] Comprobar `git --version`.
-   [ ] Crear o disponer de cuenta GitHub.
-   [ ] Configurar autenticación de GitHub.
-   [ ] Revisar firewall si se conectarán otros equipos.
-   [ ] Elegir un puerto TCP disponible.

## 3. Estructura de carpetas de referencia

``` text
ChatRoom/
├── server/
│   ├── main.py
│   ├── socket_server.py
│   ├── client_session.py
│   └── connection_manager.py
├── client/
│   ├── main.py
│   ├── tcp_client.py
│   └── command_handler.py
├── domain/
│   ├── user.py
│   ├── room.py
│   ├── message.py
│   └── events.py
├── services/
│   ├── chat_service.py
│   └── room_service.py
├── repositories/
│   ├── message_repository.py
│   └── room_repository.py
├── infrastructure/
│   ├── database.py
│   ├── protocol.py
│   └── configuration.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── concurrency/
├── docs/
│   ├── architecture.md
│   ├── protocol.md
│   ├── ai_log.md
│   ├── test_results.md
│   └── uml/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

La estructura puede ajustarse si existe una razón arquitectónica. No
crear archivos vacíos solo para llenar carpetas.

## 4. Fases de desarrollo

# Fase 0 --- Preparación del entorno

**Objetivo:** instalar y comprobar el entorno antes de programar.

Actividades: 1. Instalar Python, VS Code, extensiones Python/Pylance y
Git. 2. Crear la carpeta del proyecto. 3. Abrirla en VS Code. 4. Crear y
activar entorno virtual. 5. Instalar pytest. 6. Crear `requirements.txt`
y `.gitignore`.

Windows PowerShell:

``` powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install pytest
pip freeze > requirements.txt
```

macOS/Linux:

``` bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pytest
pip freeze > requirements.txt
```

Si PowerShell bloquea la activación, revisar la política del equipo o
utilizar otra terminal. No cambiar políticas de seguridad sin comprender
el efecto.

Checklist: - \[ \] Python instalado y comprobado. - \[ \] VS Code
instalado. - \[ \] Extensión Python instalada. - \[ \] Pylance
instalado. - \[ \] Git instalado y comprobado. - \[ \] Carpeta
`ChatRoom` creada. - \[ \] Entorno virtual creado y activado. - \[ \]
`pytest` instalado. - \[ \] `requirements.txt` creado. - \[ \]
`.gitignore` excluye `.venv/`, `__pycache__/`, `.pyc`, base de datos
local y secretos. - \[ \] Script mínimo Python ejecutado.

**Criterio de salida:** Python funciona desde el entorno virtual y Git
reconoce el proyecto.

# Fase 1 --- Análisis y diseño

**Objetivo:** definir contratos y responsabilidades antes de programar.

Actividades: 1. Confirmar alcance MVP. 2. Definir actores y casos de
uso. 3. Aprobar arquitectura cliente-servidor. 4. Definir módulos y
responsabilidades. 5. Justificar `asyncio`. 6. Definir protocolo JSON
con delimitador `\\n`. 7. Definir tipos de mensajes y campos
obligatorios. 8. Definir límites de tamaño y conexiones. 9. Definir
política de colas y backpressure. 10. Definir reglas de salas y
usuarios. 11. Crear diagramas iniciales. 12. Registrar decisiones
arquitectónicas.

Checklist: - \[ \] Alcance MVP aprobado. - \[ \] Casos de uso
definidos. - \[ \] Arquitectura definida. - \[ \] Responsabilidades
documentadas. - \[ \] Flujo de conexión documentado. - \[ \] Protocolo
documentado. - \[ \] Política de errores definida. - \[ \] Política de
saturación definida. - \[ \] Diagrama de componentes creado. - \[ \]
Diagrama de secuencia creado. - \[ \] Decisiones técnicas registradas.

**Criterio de salida:** está definido qué componente recibe, valida,
procesa, almacena y distribuye cada mensaje.

# Fase 2 --- Servidor TCP mínimo

**Objetivo:** conectar clientes y servidor antes de implementar salas.

Actividades: 1. Configurar host y puerto. 2. Crear servidor TCP. 3.
Configurar `SO_REUSEADDR` cuando corresponda. 4. Implementar aceptación
de conexiones. 5. Crear una sesión por cliente. 6. Implementar lectura y
escritura asíncronas. 7. Implementar cierre de conexión. 8. Registrar
conexiones y desconexiones.

Decisión: si se utiliza `asyncio.start_server`, documentar que la API
administra internamente el socket TCP. No crear dos servidores distintos
para demostrar sockets.

Checklist: - \[ \] Servidor inicia y escucha. - \[ \] Un cliente se
conecta. - \[ \] Dos o más clientes se conectan. - \[ \] Servidor recibe
datos. - \[ \] Servidor responde. - \[ \] Una desconexión no detiene el
servidor. - \[ \] Streams y sockets se cierran correctamente. - \[ \]
Errores de conexión se manejan.

**Criterio de salida:** varias conexiones TCP se mantienen e
intercambian datos.

# Fase 3 --- Protocolo de comunicación

**Objetivo:** establecer un formato único.

Actividades: 1. Crear serialización JSON. 2. Definir delimitador `\\n`.
3. Implementar UTF-8. 4. Acumular bytes hasta el delimitador. 5.
Procesar varios mensajes en un bloque. 6. Procesar mensajes
fragmentados. 7. Validar JSON y campos. 8. Definir tamaño máximo. 9.
Definir respuestas `SUCCESS` y `ERROR`. 10. Documentar tipos de
mensajes.

Checklist: - \[ \] Un mensaje se envía y recibe. - \[ \] Se procesan
mensajes consecutivos. - \[ \] Se reconstruye un mensaje fragmentado. -
\[ \] JSON malformado se rechaza. - \[ \] Campos obligatorios se
validan. - \[ \] Mensajes excesivos se rechazan. - \[ \] Los errores no
derriban todo el servidor. - \[ \] Cliente y servidor comparten el mismo
contrato.

**Criterio de salida:** toda comunicación pasa por el protocolo común.

# Fase 4 --- Usuarios y sesiones

**Objetivo:** administrar identidad básica.

Actividades: 1. Definir `User`. 2. Definir `ClientSession`. 3.
Implementar `CONNECT`. 4. Validar nombres. 5. Rechazar duplicados. 6.
Registrar sesiones activas. 7. Implementar `DISCONNECT`. 8. Retirar
sesiones al desconectarse. 9. Consultar usuarios conectados.

Checklist: - \[ \] Usuario se conecta. - \[ \] Nombre vacío se
rechaza. - \[ \] Nombre duplicado se rechaza. - \[ \] Usuario se asocia
a sesión. - \[ \] Lista de conectados es correcta. - \[ \] Desconexión
voluntaria funciona. - \[ \] Desconexión inesperada funciona. - \[ \] No
quedan sesiones huérfanas. - \[ \] Pruebas de usuarios pasan.

**Criterio de salida:** el servidor administra usuarios activos sin
duplicados ni sesiones huérfanas.

# Fase 5 --- Salas

**Objetivo:** administrar salas independientemente.

Actividades: 1. Definir `Room`. 2. Crear `RoomManager`. 3. Implementar
`CREATE_ROOM`. 4. Implementar `LIST_ROOMS`. 5. Implementar `JOIN_ROOM`.
6. Implementar `LEAVE_ROOM`. 7. Consultar integrantes. 8. Validar salas
inexistentes. 9. Evitar miembros duplicados. 10. Definir política de
salas vacías. 11. Retirar usuario de salas al desconectarse.

Checklist: - \[ \] Crear sala. - \[ \] Rechazar nombre inválido. - \[ \]
Listar salas. - \[ \] Unirse a sala. - \[ \] Rechazar sala
inexistente. - \[ \] Evitar ingreso duplicado. - \[ \] Abandonar sala. -
\[ \] Consultar miembros. - \[ \] Desconexión limpia de miembros. - \[
\] Salas independientes.

**Criterio de salida:** las salas funcionan de forma aislada y
consistente.

# Fase 6 --- Mensajería

**Objetivo:** intercambiar mensajes entre miembros de una sala.

Actividades: 1. Definir `Message`. 2. Implementar `SEND_MESSAGE`. 3.
Validar pertenencia del usuario. 4. Validar contenido. 5. Obtener
remitente desde la sesión. 6. Asignar fecha/hora. 7. Distribuir a
miembros. 8. Aislar mensajes por sala. 9. Confirmar resultado al
remitente.

Checklist: - \[ \] Enviar mensaje. - \[ \] Recibir mensaje. - \[ \]
Identificar remitente. - \[ \] Incluir sala y fecha/hora. - \[ \]
Rechazar mensaje vacío. - \[ \] Rechazar envío de no miembro. - \[ \]
Aislar mensajes. - \[ \] Varios usuarios envían simultáneamente. - \[ \]
Pruebas de mensajería pasan.

**Criterio de salida:** mensajes distribuidos correctamente y salas
aisladas.

# Fase 7 --- Notificaciones y eventos

**Objetivo:** separar los eventos de su distribución.

Actividades: 1. Definir tipos de eventos. 2. Implementar
Observer/publicación-suscripción. 3. Publicar conexión y desconexión. 4.
Publicar sala creada. 5. Publicar ingreso y salida. 6. Publicar
mensajes. 7. Definir destinatarios. 8. Manejar errores de distribución.

Checklist: - \[ \] Notificación de conexión. - \[ \] Notificación de
desconexión. - \[ \] Notificación de sala creada. - \[ \] Notificación
de ingreso. - \[ \] Notificación de salida. - \[ \] Mensajes
distribuidos como eventos. - \[ \] Destinatarios correctos. - \[ \] Un
destinatario defectuoso no detiene a todos. - \[ \] Pruebas de eventos
pasan.

**Criterio de salida:** eventos separados de la lógica que los produce y
distribución correcta.

# Fase 8 --- Colas, concurrencia y backpressure

**Objetivo:** evitar que un cliente lento bloquee a los demás y limitar
memoria.

Actividades: 1. Crear cola de salida por sesión. 2. Crear tarea de envío
por sesión. 3. Establecer capacidad máxima. 4. Definir timeout al
encolar. 5. Definir política de saturación. 6. Registrar colas llenas.
7. Cerrar o limitar clientes que no consumen. 8. Revisar accesos al
estado compartido. 9. Usar `asyncio.Lock` donde sea necesario. 10.
Evitar locks durante escrituras de red. 11. Revisar cancelación y cierre
de tareas.

Checklist: - \[ \] Cada cliente tiene su propia cola. - \[ \] Las colas
tienen límite. - \[ \] Existe política de saturación. - \[ \] No se
espera indefinidamente por cliente lento. - \[ \] Cliente lento no
bloquea a otros. - \[ \] No hay crecimiento ilimitado de memoria. - \[
\] Estado compartido protegido. - \[ \] Locks no se mantienen durante
I/O. - \[ \] Tareas se cancelan y cierran. - \[ \] Prueba de
backpressure aprobada.

**Criterio de salida:** una prueba reproducible demuestra que un cliente
lento no congela a los demás y que las colas respetan límites.

# Fase 9 --- Persistencia SQLite

**Objetivo:** guardar historial sin acoplar SQL a la lógica de negocio.

Actividades: 1. Definir tablas. 2. Inicializar base de datos. 3.
Implementar repositorio de salas. 4. Implementar repositorio de
mensajes. 5. Guardar mensajes aceptados. 6. Consultar historial. 7.
Manejar errores de almacenamiento. 8. Evitar operaciones bloqueantes en
Event Loop.

Checklist: - \[ \] Base de datos se crea automáticamente. - \[ \] Tablas
y claves definidas. - \[ \] Mensajes se guardan. - \[ \] Historial se
consulta por sala. - \[ \] Datos aislados entre salas. - \[ \] Errores
de persistencia se manejan. - \[ \] Repositorios separados de
servicios. - \[ \] Pruebas pasan.

**Criterio de salida:** el historial persiste después de reiniciar el
servidor.

# Fase 10 --- Cliente de consola completo

**Objetivo:** usar todas las funciones desde la terminal.

Actividades: 1. Implementar conexión TCP. 2. Solicitar nombre. 3.
Mostrar menú. 4. Crear y listar salas. 5. Entrar y salir de salas. 6.
Enviar mensajes. 7. Recibir mensajes mientras se escribe. 8. Mostrar
notificaciones y errores. 9. Cerrar sesión. 10. Manejar pérdida de
conexión.

Checklist: - \[ \] Cliente se conecta. - \[ \] Usuario se identifica. -
\[ \] Crear/listar salas. - \[ \] Entrar/salir. - \[ \] Enviar
mensajes. - \[ \] Recibir mensajes sin bloquear entrada. - \[ \] Recibir
notificaciones. - \[ \] Consultar historial. - \[ \] Salir
correctamente. - \[ \] Manejar desconexiones.

**Criterio de salida:** una persona puede usar el chat sin escribir JSON
manualmente.

# Fase 11 --- Resiliencia y cierre limpio

**Objetivo:** controlar fallos y liberar recursos.

Actividades: 1. Configurar timeouts. 2. Manejar desconexiones abruptas.
3. Manejar JSON inválido. 4. Manejar mensajes grandes. 5. Manejar colas
saturadas. 6. Limitar conexiones. 7. Gestionar SIGTERM o mecanismo
equivalente. 8. Dejar de aceptar conexiones durante apagado. 9. Cerrar
tareas, streams y sockets. 10. Verificar recursos abiertos.

Checklist: - \[ \] Timeout funciona. - \[ \] Desconexión abrupta no
derriba servidor. - \[ \] Mensajes inválidos se manejan. - \[ \]
Mensajes excesivos se rechazan. - \[ \] Saturación se controla. - \[ \]
Límite de conexiones se aplica. - \[ \] Apagado se gestiona. - \[ \]
Streams y sockets se cierran. - \[ \] No quedan tareas inesperadas. - \[
\] Reinicio funciona.

**Criterio de salida:** servidor se detiene y reinicia sin dejar
recursos o estado inconsistente.

# Fase 12 --- Pruebas de integración y carga

**Objetivo:** obtener evidencia reproducible.

Escenarios: - 5, 10, 20 y 50 clientes, si los recursos lo permiten. -
Varios usuarios enviando mensajes. - Usuarios en salas diferentes. - Un
cliente que no lee mensajes. - Desconexiones durante el envío. - Cola
llena. - Apagado durante actividad.

Checklist: - \[ \] Pruebas unitarias ejecutadas. - \[ \] Pruebas de
integración ejecutadas. - \[ \] Pruebas concurrentes ejecutadas. - \[ \]
Clientes simultáneos comprobados. - \[ \] Aislamiento entre salas
comprobado. - \[ \] Cliente lento comprobado. - \[ \] Saturación
comprobada. - \[ \] Desconexión comprobada. - \[ \] Apagado limpio
comprobado. - \[ \] Resultados reales guardados en
`docs/test_results.md`. - \[ \] Errores y limitaciones registrados.

**Criterio de salida:** existen evidencias de arquitectura, sockets,
sincronización, resiliencia y concurrencia.

# Fase 13 --- Auditoría de IA y arquitectura

**Objetivo:** verificar que el código sea comprensible y respete el
diseño.

Actividades: - Revisar responsabilidades y dependencias. - Revisar
principios SOLID. - Justificar Observer, Facade y Factory Method si se
incorporaron. - Buscar operaciones bloqueantes. - Revisar condiciones de
carrera. - Revisar cierre de recursos. - Comparar UML con código. -
Completar bitácora.

Checklist: - \[ \] Cada módulo tiene responsabilidad clara. - \[ \] No
hay dependencias circulares innecesarias. - \[ \] No hay duplicación de
lógica. - \[ \] Patrones resuelven problemas reales. - \[ \] Código
sugerido por IA fue revisado. - \[ \] Errores y correcciones
documentados. - \[ \] Correcciones tienen pruebas. - \[ \] Diagramas
coinciden con implementación. - \[ \] El estudiante comprende módulos
principales.

**Criterio de salida:** la arquitectura y sus decisiones se pueden
explicar con ejemplos del código.

# Fase 14 --- Entrega y sustentación

**Objetivo:** preparar repositorio y evidencias.

Entregables: - Código fuente. - `README.md`. - `requirements.txt`. -
Diagramas UML. - Documento de arquitectura. - Documento de protocolo. -
Bitácora de IA. - Resultados de pruebas. - Evidencias de clientes
concurrentes. - Instrucciones de ejecución.

Checklist: - \[ \] Repositorio GitHub actualizado. - \[ \] No se subió
`.venv`. - \[ \] No se subieron secretos. - \[ \] No se subieron
archivos temporales. - \[ \] README permite instalar y ejecutar. - \[ \]
Diagramas actualizados. - \[ \] Bitácora completa. - \[ \] Pruebas
documentadas. - \[ \] Proyecto ejecutable desde entorno limpio. - \[ \]
Se explica ciclo de vida de sockets. - \[ \] Se explica asyncio y Event
Loop. - \[ \] Se explica protocolo TCP. - \[ \] Se explica estado
compartido y backpressure. - \[ \] Se demuestra escenario de cliente
lento. - \[ \] Se justifican decisiones arquitectónicas.

**Criterio de salida:** otra persona puede clonar, instalar, ejecutar
servidor y clientes, repetir pruebas y comprender la arquitectura.

## 5. Mapa de dependencias

``` text
Preparación del entorno
        |
        v
Análisis y diseño
        |
        v
Servidor TCP mínimo
        |
        v
Protocolo JSON
        |
        v
Usuarios y sesiones
        |
        v
Salas
        |
        v
Mensajería
        |
        v
Notificaciones
        |
        v
Colas y backpressure
        |
        v
Persistencia
        |
        v
Cliente de consola completo
        |
        v
Resiliencia y cierre limpio
        |
        v
Pruebas de carga
        |
        v
Auditoría, documentación y sustentación
```

Solo desarrollar tareas en paralelo si sus contratos están definidos y
no modifican simultáneamente el mismo módulo.

## 6. Contratos entre módulos

  -----------------------------------------------------------------------
  Módulo                  Puede hacer             No debe hacer
  ----------------------- ----------------------- -----------------------
  `socket_server`         Aceptar conexiones y    Implementar reglas de
                          crear sesiones          salas o SQL

  `client_session`        Leer, validar y enviar  Administrar todas las
                          mensajes de una sesión  salas por su cuenta

  `protocol`              Codificar, delimitar y  Modificar usuarios o
                          validar mensajes        salas

  `connection_manager`    Registrar y retirar     Guardar mensajes
                          sesiones                históricos

  `room_manager`          Crear salas y           Enviar directamente
                          administrar miembros    bytes al socket

  `chat_service`          Aplicar reglas de       Crear conexiones TCP
                          mensajería y coordinar
                          operaciones

  `event_manager`         Publicar y distribuir   Contener reglas de
                          eventos                 persistencia

  `repositories`          Guardar y consultar     Decidir reglas de
                          datos                   negocio

  `client`                Mostrar opciones y      Acceder a estructuras
                          comunicarse por TCP     internas del servidor
  -----------------------------------------------------------------------

## 7. Pruebas mínimas por fase

  Fase             Prueba mínima
  ---------------- ------------------------------------------------------
  Servidor TCP     Dos clientes conectados al mismo tiempo
  Protocolo        Mensaje fragmentado y varios mensajes en una lectura
  Usuarios         Dos clientes intentan usar el mismo nombre
  Salas            Dos salas no comparten miembros ni mensajes
  Mensajería       Varios miembros reciben el mismo mensaje
  Notificaciones   Solo destinatarios definidos reciben el evento
  Backpressure     Cliente que deja de leer no bloquea a otros
  Persistencia     Reiniciar servidor y consultar historial
  Resiliencia      Desconectar cliente abruptamente
  Carga            Aumentar gradualmente clientes

## 8. Plantilla de registro de fase

``` markdown
## Registro de fase

- Fase:
- Fecha:
- Responsable:
- Archivos creados:
- Archivos modificados:
- Funcionalidades implementadas:
- Pruebas ejecutadas:
- Resultado de las pruebas:
- Errores encontrados:
- Correcciones realizadas:
- Cambios arquitectónicos:
- Documentación actualizada:
- ¿Cumple el criterio de salida?: Sí / No
- Aprobación para avanzar: Sí / No
```

## 9. Plantilla de bitácora de IA

  ------------------------------------------------------------------------------------------
  Fecha      Fase       Prompt/objetivo   Archivos    Problema    Corrección y    Prueba
                                          afectados   detectado   justificación
  ---------- ---------- ----------------- ----------- ----------- --------------- ----------


  ------------------------------------------------------------------------------------------

Registrar prompts y respuestas relevantes. No presentar como corrección
propia un cambio que no se haya revisado y comprendido.

## 10. Checklist general de avance

-   [ ] Fase 0 --- Preparación del entorno.
-   [ ] Fase 1 --- Análisis y diseño.
-   [ ] Fase 2 --- Servidor TCP mínimo.
-   [ ] Fase 3 --- Protocolo de comunicación.
-   [ ] Fase 4 --- Usuarios y sesiones.
-   [ ] Fase 5 --- Salas.
-   [ ] Fase 6 --- Mensajería.
-   [ ] Fase 7 --- Notificaciones.
-   [ ] Fase 8 --- Colas, concurrencia y backpressure.
-   [ ] Fase 9 --- Persistencia.
-   [ ] Fase 10 --- Cliente de consola.
-   [ ] Fase 11 --- Resiliencia y cierre limpio.
-   [ ] Fase 12 --- Pruebas de integración y carga.
-   [ ] Fase 13 --- Auditoría de IA y revisión arquitectónica.
-   [ ] Fase 14 --- Entrega y sustentación.

## 11. Cuándo detener el desarrollo

Corregir antes de continuar si: - El servidor deja de aceptar clientes
después de una desconexión. - Un cliente recibe mensajes de una sala a
la que no pertenece. - El protocolo del cliente y servidor no
coincide. - Se cambia una interfaz sin actualizar dependencias. - Hay
colas sin límite. - Una operación bloqueante congela el Event Loop. - Se
mantienen locks mientras se espera red. - Se dejan sockets o tareas sin
cerrar. - Las pruebas anteriores dejan de pasar. - La documentación
describe algo que el código no implementa.

## 12. Recomendación final

Trabajar con una sola fase activa. Mantener una rama o commit estable
cuando una fase haya sido probada. Antes de integrar cambios, ejecutar
las pruebas de los módulos afectados.

No agregar interfaz gráfica, autenticación avanzada ni funciones
adicionales hasta demostrar TCP, concurrencia, sincronización,
backpressure, resiliencia y pruebas.

**Meta:** entregar un sistema pequeño pero completo, con
responsabilidades claras, concurrencia demostrable, pruebas
reproducibles y documentación suficiente para defender cada decisión
técnica.
