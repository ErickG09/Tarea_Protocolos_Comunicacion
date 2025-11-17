# 1. Datos generales del proyecto

El presente proyecto corresponde al desarrollo de un **Sistema Multiagente para la Gestión de Cirugías en un Hospital**, realizado como parte de la actividad práctica de la materia *Agentes Inteligentes*. El objetivo principal del equipo fue implementar un sistema funcional capaz de coordinar diferentes agentes autónomos mediante protocolos formales de comunicación, integrando además una interfaz web profesional y persistencia real con base de datos.

El sistema permite gestionar el ciclo completo de una cirugía: registro del paciente, generación del plan quirúrgico mediante IA, asignación inteligente de quirófanos, actualización dinámica de estados y monitoreo global del hospital. Todas estas operaciones se realizaron aplicando estrictamente los protocolos exigidos en la actividad (A2A, ACP, AG-UI y MCP), demostrando un entendimiento práctico y completo del paradigma multiagente.

Datos del proyecto:

- Nombre del proyecto: **Sistema Multiagente para Gestión de Cirugías Hospitalarias**
- Nombre del alumno: *Erick Guevara Morales*
- Materia: **Agentes Inteligentes**
---

# 2. Introducción

La coordinación de cirugías dentro de un hospital es un proceso complejo que involucra múltiples roles, recursos limitados y decisiones críticas basadas en tiempo. Para resolver esta problemática, se desarrolló un **sistema multiagente** capaz de modelar, planificar y ejecutar de manera autónoma las tareas relacionadas con la gestión quirúrgica, utilizando protocolos de comunicación formales y agentes especializados.

En este proyecto, el usuario humano interactúa únicamente con la **Interfaz de Usuario (UI)**, la cual envía sus solicitudes a través del protocolo **AG-UI** hacia el resto del sistema. Cada agente interno cumple un rol específico:  
- El **Planificador** genera un plan quirúrgico de 10 subtareas utilizando la inteligencia artificial de **Gemini 2.5**, adaptándose al procedimiento seleccionado.  
- El **Ejecutor** asigna quirófanos disponibles, evita colisiones temporales, actualiza estados dinámicamente y gestiona la logística operativa.  
- La **Base de Conocimiento** almacena toda la información en una base de datos SQLite persistente.  
- El **Notificador** registra eventos importantes del sistema.  
- El **Monitor** compila un snapshot global que refleja el estado del hospital en tiempo real.

El sistema implementa los cuatro protocolos de comunicación requeridos por la actividad: **A2A**, **ACP**, **AG-UI** y **MCP**, garantizando que la interacción entre agentes siga reglas consistentes y formales.

Finalmente, se desarrolló una **interfaz web moderna y profesional** que permite visualizar casos, generar cirugías, programarlas en quirófanos y consultar el estado del sistema, simulando fielmente un entorno hospitalario real. Este proyecto demuestra la aplicabilidad de los sistemas multiagente en escenarios críticos donde la coordinación, la autonomía y la comunicación estructurada son indispensables.


# 3. Arquitectura multiagente y protocolos utilizados

El sistema desarrollado implementa una arquitectura multiagente completa, donde cada agente posee responsabilidades específicas dentro del flujo quirúrgico. La comunicación entre ellos se realiza mediante un **Message Bus interno**, utilizando protocolos formales que estructuran tanto la forma como el contenido de los mensajes.

A continuación se describen los agentes implementados y los protocolos utilizados en el proyecto, siguiendo exactamente las especificaciones de la actividad académica.

---

## 3.1 Agentes implementados

### **1. Interfaz de Usuario (UI)**
Es el único punto de interacción con el usuario humano.  
Desde la UI se crean casos quirúrgicos, se programan cirugías y se visualizan notificaciones y estados del sistema.  
Cada acción enviada por el usuario se transforma en un mensaje utilizando el protocolo **AG-UI**, lo que permite iniciar el flujo multiagente.

---

### **2. Planificador**
Recibe solicitudes para crear nuevos casos quirúrgicos.  
Su función principal es generar un **plan quirúrgico de 10 subtareas**, con tiempos estimados, responsabilidades, descripciones clínicas y orden lógico.

Para esto utiliza:
- **Gemini 2.5 Flash** (IA generativa clínica)  
- Un mecanismo determinista de respaldo si la IA no responde

Una vez generado el plan, lo almacena en la Base de Conocimiento y notifica al sistema mediante un mensaje INFORM.

---

### **3. Ejecutor**
Es el agente encargado de la **lógica operacional**.  
Se encarga de:
- Asignar quirófanos disponibles (OR-1 a OR-5)  
- Evitar colisiones de horarios entre cirugías  
- Actualizar los estados de las subtareas (pending, scheduled, in_progress, done)  
- Ajustar estados en función de la hora actual  
- Notificar eventos importantes (CASE_SCHEDULED)

El Ejecutor opera completamente mediante mensajes internos **A2A**, aplicando ACP y MCP.

---

### **4. Base de Conocimiento (KB)**
Es una capa persistente basada en **SQLite** que almacena:
- Casos quirúrgicos  
- Subtareas generadas  
- Quirófanos y ocupaciones  
- Notificaciones del sistema  

Todos los agentes interactúan con la KB, lo que permite que la información se mantenga entre ejecuciones del servidor.

---

### **5. Notificador**
Registra todos los eventos relevantes del sistema, tales como:
- Creación de casos  
- Programación de cirugías  
- Cambios de estado  

La UI muestra los últimos eventos al usuario como “notificaciones”.

---

### **6. Monitor** *(requerido como componente opcional)*
Consulta la Base de Conocimiento y genera un **snapshot** completo del hospital:
- Cantidad total de casos  
- Casos agrupados por estado  
- Disponibilidad de quirófanos  
- Tiempos actuales de operación  

La UI muestra esta información en el dashboard principal.

---

## 3.2 Protocolos utilizados en el sistema

El proyecto utiliza **cuatro protocolos obligatorios**, todos implementados de manera explícita en el bus de mensajes:

---

### **1. AG-UI (Agent to User Interface)**
Define la comunicación entre el usuario humano y el sistema multiagente.  
Se utiliza únicamente cuando la acción inicia en la interfaz.

Ejemplos:
- Crear un caso quirúrgico  
- Solicitar programación de quirófano  
- Visualizar estados del sistema  

Toda interacción proveniente del usuario se encapsula en un mensaje AG-UI → Planner o AG-UI → Executor.

---

### **2. ACP (Agent Communication Protocol)**
Estructura formal del intercambio entre agentes.  
Define la forma general del mensaje:

- performative (REQUEST, INFORM)  
- sender  
- receiver  
- protocols  
- content.type  
- content.payload  

Este protocolo garantiza diálogos coherentes entre agentes internos.

---

### **3. MCP (Message Content Protocol)**
Estandariza la semántica del contenido en el campo `content`.

Los mensajes MCP del sistema siempre tienen esta forma:

```json
{
  "id": "uuid",
  "performative": "REQUEST | INFORM",
  "sender": "...",
  "receiver": "...",
  "protocols": ["A2A", "ACP", "AG_UI", "MCP"],
  "content": {
    "type": "ACTION_NAME",
    "payload": { }
  }
}
```

Ejemplos reales:

NEW_CASE
SCHEDULE_CASE
CASE_SCHEDULED
NEW_CASE_CREATED
De esta manera, todos los agentes interpretan correctamente el significado del mensaje.


### **4. A2A (Agent to Agent)**
Protocolo para comunicación directa entre agentes internos.
Utilizado constantemente en:

- Planner → KB
- Executor → KB
- Executor → Notifier
- Monitor → KB

Este protocolo habilita la coordinación entre componentes autónomos sin intervención del usuario.


#### **3.3 Estructura estándar del mensaje en el sistema**
Todos los mensajes intercambiados tienen el mismo formato general:
{
  "id": "uuid",
  "performative": "REQUEST | INFORM",
  "sender": "ui | planner | executor | notifier | monitor",
  "receiver": "planner | executor | notifier | monitor | ui",
  "protocols": ["A2A", "ACP", "AG_UI", "MCP"],
  "content": {
    "type": "ACTION_NAME",
    "payload": { }
  }
}

Esta estandarización asegura coherencia, compatibilidad entre agentes y cumplimiento estricto de la actividad académica.

#### **3.4 Resumen de la arquitectura multiagente**

- La UI inicia acciones usando AG-UI.
- El Planificador genera planes quirúrgicos mediante IA.
- El Ejecutor asigna quirófanos y gestiona estados.
- La KB conserva persistencia real.
- El Notificador registra eventos importantes.
- El Monitor supervisa el estado global.
- La comunicación se realiza mediante un bus central utilizando A2A + ACP + MCP.

# 4. Desarrollo de la solución

Este apartado describe detalladamente cómo fue construida la solución final, explicando cada uno de los componentes implementados y cómo se integran en un sistema multiagente funcional orientado a la gestión clínica de cirugías. Toda la descripción corresponde exactamente al proyecto desarrollado, mostrando cómo se resolvió el escenario del hospital utilizando agentes, protocolos de comunicación y persistencia de datos.

---

## 4.1 Interfaz Web (UI)

La Interfaz de Usuario fue implementada utilizando **FastAPI**, **Jinja2** y **CSS personalizado**.  
Su objetivo es permitir que el usuario humano interactúe con el sistema multiagente de manera intuitiva.

Incluye:

- Un **dashboard** principal que muestra:
  - Casos registrados
  - Últimas notificaciones
  - Estado global del hospital (snapshot del Monitor)
  - Disponibilidad de quirófanos

- Un **formulario moderno** para registrar un nuevo caso quirúrgico:
  - Nombre del paciente
  - Procedimiento
  - Prioridad (urgente / electiva)
  - Fecha y hora usando `datetime-local` para un ingreso rápido

- Una **vista detallada del caso**, donde aparecen:
  - Datos del paciente
  - Plan quirúrgico generado (10 subtareas)
  - Estado de cada subtarea
  - Botón para “Programar Quirófano”
  - Botón para “Eliminar Caso” (para pruebas)

El propósito de la UI es **iniciar los mensajes AG-UI** que activan el flujo multiagente.

---

## 4.2 Generación de Plan Quirúrgico Inteligente (Planificador)

El **Planificador** es uno de los agentes principales.  
Su responsabilidad es crear un plan quirúrgico completo, estructurado en **10 subtareas**, a partir de la información ingresada por el usuario.

Para ello utiliza:

- **Gemini 2.5 Flash**, el modelo clínico más actualizado de Google
- Un mecanismo determinista como fallback para asegurar que el sistema nunca falle

El plan generado incluye:

- Descripción clínica de cada subtarea
- Duración estimada en minutos
- Rol responsable (cirujano, anestesiólogo, enfermería, etc.)
- Orden lógico del flujo perioperatorio
- Tiempos ajustados según el procedimiento solicitado

Ejemplo de subtareas generadas:

1. Admisión del paciente  
2. Preparación de sala quirúrgica  
3. Inducción anestésica  
4. Procedimiento principal  
5. Cierre quirúrgico  
6. Recuperación en PACU

Una vez generado el plan, el Planificador lo almacena en la Base de Conocimiento y envía notificaciones internas.

---

## 4.3 Programación Inteligente de Quirófanos (Ejecutor)

El **Ejecutor** es el agente encargado de coordinar la logística realista del hospital.  
Su función es asignar uno de los **5 quirófanos disponibles**:

- OR-1  
- OR-2  
- OR-3  
- OR-4  
- OR-5  

El Ejecutor:

- Evalúa disponibilidad según:
  - Horario del caso
  - Duración de las subtareas
  - Colisiones con otros procedimientos
- Selecciona un quirófano libre automáticamente
- Evita superposiciones de horarios
- Reajusta el estado de las subtareas según la hora actual:
  - pending → scheduled  
  - scheduled → in_progress  
  - in_progress → done  

Si el quirófano está ocupado, busca otro disponible.  
Si todos los quirófanos colisionan, notifica el problema.

Este agente usa exclusivamente protocolos **A2A**, **ACP** y **MCP**.

---

## 4.4 Persistencia en SQLite (Base de Conocimiento)

Toda la información del sistema se almacena en una base de datos **SQLite**, diseñada para servir como la **Base de Conocimiento persistente** del sistema.

Se almacena:

- Casos quirúrgicos
- Subtareas generadas por Gemini
- Quirófanos y su ocupación
- Notificaciones del sistema
- Estado y tiempos de cada tarea

Gracias a SQLite:

- La información **permanece al reiniciar** el servidor.
- El sistema se comporta como un software hospitalario real.
- Los agentes pueden consultar o actualizar datos sin perder coherencia.

---

## 4.5 Sistema de Notificaciones (Notificador)

El **Notificador** registra cada evento importante del sistema.  
Ejemplos:

- NEW_CASE_CREATED  
- CASE_SCHEDULED  
- TASK_STATE_CHANGED  

La UI muestra las cinco notificaciones más recientes.  
Esto simula un registro clínico o un log operativo hospitalario.

---

## 4.6 Monitor del Sistema

El **Monitor** es un agente opcional según la actividad, pero fue completamente implementado.  
Su labor es generar un **snapshot** del estado global del hospital:

Incluye:

- Total de casos creados
- Distribución por estado:
  - planned
  - scheduled
  - in_progress
  - done
- Quirófanos ocupados vs disponibles
- Timestamp actual

Este snapshot se muestra en el dashboard principal de la UI.

---

## 4.7 Comunicación entre agentes mediante Message Bus

Todos los agentes se comunican mediante un **Message Bus interno**, el cual:

- Recibe mensajes estructurados según ACP + MCP
- Determina dinámicamente qué agente debe procesar cada mensaje
- Mantiene trazabilidad mediante logs
- Apoya el cumplimiento del protocolo A2A para agentes internos

La canalización funciona así:

UI → (AG-UI) → Planner → KB → Notifier  
UI → (AG-UI) → Executor → KB → Notifier  
UI → Monitor  
Monitor → KB  
Executor → KB

Esta arquitectura garantiza un comportamiento realmente multiagente.

---

En conjunto, este desarrollo implementa un **sistema completamente funcional**, profesional y alineado al escenario real del hospital, demostrando la aplicación práctica y correcta de los protocolos multiagente.

# 5. Pruebas

Para validar el funcionamiento del sistema multiagente desarrollado, se realizaron diversas pruebas que abarcan todo el flujo quirúrgico: desde la creación de casos, la generación del plan quirúrgico mediante IA, la programación de quirófanos, el manejo de estados y la persistencia de datos. Todas las pruebas se ejecutaron directamente sobre la interfaz web y utilizando la base de datos SQLite integrada.

A continuación se describen detalladamente las pruebas realizadas y los resultados obtenidos.

---

## 5.1 Pruebas de creación de casos quirúrgicos

Se realizaron pruebas creando múltiples casos desde la interfaz, utilizando distintos tipos de procedimientos.  
Ejemplos probados:

- Apendicectomía laparoscópica  
- Colecistectomía laparoscópica  
- Reconstrucción de Ligamento Cruzado Anterior (LCA)  
- Histerectomía laparoscópica  
- Hernioplastía inguinal  
- Artroscopía diagnóstica  

En todos los casos:

- El formulario con `datetime-local` registró correctamente fecha y hora.
- La UI envió el mensaje **AG-UI → Planner** sin errores.
- Se generó un nuevo caso con un ID único.
- El caso apareció inmediatamente en el dashboard y en la vista de detalle.

---

## 5.2 Pruebas del plan quirúrgico generado por Gemini 2.5

Para cada caso creado, el Planificador generó correctamente **10 subtareas clínicas**, cada una con:

- Descripción profesional
- Duración estimada
- Secuencia lógica
- Responsables (cirujano, anestesiólogo, enfermería)
- Tiempos basados en el procedimiento seleccionado

Resultados observados:

- Los planes fueron consistentes entre casos del mismo tipo.
- El contenido clínico fue realista y estructurado.
- No se generaron subtareas incoherentes o vacías.
- El fallback determinista funcionó cuando se simuló la falta de conexión.

---

## 5.3 Pruebas de programación de quirófanos

Se crearon varios casos con **horarios superpuestos** para validar la lógica del Ejecutor.

Resultados:

- El Ejecutor asignó quirófanos disponibles en el orden OR-1 → OR-5.
- Se evitaron colisiones automáticamente.
- Si un quirófano estaba ocupado, se asignó el siguiente libre.
- En escenarios de saturación, el sistema notificó el conflicto.
- El plan completo quedó asociado al quirófano asignado.
- La UI reflejó visualmente el quirófano utilizado en cada caso.

---

## 5.4 Pruebas de actualización automática de estados

El Ejecutor incluye un mecanismo de cronología interna basado en la hora actual.

Casos probados:

- Subtareas que ya deberían haber iniciado.
- Subtareas en progreso.
- Subtareas que ya deberían haber terminado.

Cambios observados:

- pending → scheduled  
- scheduled → in_progress  
- in_progress → done  

Esto permitió simular el avance real del día quirúrgico.

---

## 5.5 Pruebas del sistema de notificaciones

Se verificó que cada evento importante generara una nueva notificación:

- Caso creado
- Caso programado
- Estados actualizados
- Problemas con quirófanos

Resultados:

- Las notificaciones se registraron en SQLite.
- La UI mostró siempre las más recientes.
- No hubo duplicados ni mensajes vacíos.

---

## 5.6 Pruebas del Monitor y snapshot global

El Monitor generó correctamente un snapshot general del hospital, incluyendo:

- Casos totales
- Estados agregados (planned, scheduled, in_progress, done)
- Quirófanos libres y ocupados
- Timestamp actualizado

Validaciones:

- Cada cambio en la KB fue reflejado por el Monitor.
- La UI actualizó el snapshot al entrar al dashboard.

---

## 5.7 Pruebas de persistencia en SQLite

Se realizaron pruebas apagando el servidor y volviéndolo a encender.

Resultados:

- Todos los casos seguían presentes.
- Las subtareas conservaban su orden y estado.
- Los quirófanos retenían ocupaciones asignadas.
- Las notificaciones históricas permanecieron íntegras.

Con esto se validó que la Base de Conocimiento funciona correctamente como capa persistente del sistema.

---

## 5.8 Pruebas del flujo completo del sistema

Se realizó el flujo integral:

1. Crear caso  
2. Generar plan quirúrgico con IA  
3. Programar quirófano  
4. Actualizar estados según hora  
5. Generar notificaciones  
6. Mostrar snapshot global  

El sistema completó el flujo **sin errores**, demostrando:

- Correcto uso de los protocolos AG-UI, A2A, ACP y MCP  
- Colaboración entre agentes  
- Persistencia y trazabilidad  
- Integración exitosa con Gemini 2.5  

---

Las pruebas realizadas confirman que el sistema multiagente es estable, confiable y cumple con todos los requerimientos funcionales establecidos en la actividad.

# 6. Conclusiones

El desarrollo del **Sistema Multiagente para la Gestión de Cirugías en un Hospital** permitió demostrar la aplicación práctica y efectiva de los protocolos de comunicación multiagente dentro de un escenario realista y complejo. La interacción entre agentes autónomos, el uso de una base de conocimiento persistente y la integración con un modelo avanzado de inteligencia artificial evidencian la solidez de la arquitectura implementada.

Entre las conclusiones más importantes se destacan:

- **Cumplimiento total del enfoque multiagente:**  
  El sistema implementa correctamente los agentes requeridos (UI, Planificador, Ejecutor, Base de Conocimiento, Notificador y Monitor), cada uno con roles bien definidos y comportamientos autónomos.

- **Implementación exitosa de los cuatro protocolos formales obligatorios:**  
  AG-UI, A2A, ACP y MCP fueron aplicados estrictamente en todos los mensajes, garantizando un flujo de comunicación claro, estructurado y verificable entre agentes.

- **Generación inteligente de planes quirúrgicos con Gemini 2.5:**  
  La inclusión de inteligencia artificial permitió producir planes quirúrgicos detallados, coherentes y clínicamente realistas, agregando un fuerte componente de valor tecnológico y práctico al sistema.

- **Gestión automática de quirófanos y estados:**  
  El Ejecutor fue capaz de asignar quirófanos, evitar colisiones horarias, ajustar estados según la hora actual y notificar cambios importantes, replicando de forma precisa el comportamiento de un sistema clínico real.

- **Persistencia confiable mediante SQLite:**  
  La Base de Conocimiento almacenó todos los datos de manera estable, permitiendo reiniciar el sistema sin pérdida de información y garantizando continuidad operativa.

- **Interfaz web profesional y funcional:**  
  La UI facilitó la interacción con el sistema multiagente mediante un diseño claro, accesible y orientado a la experiencia del usuario, incorporando formularios modernos, notificaciones y visualización del estado hospitalario.

En conjunto, el proyecto cumple completamente con los requerimientos académicos y demuestra cómo la arquitectura multiagente puede aplicarse eficazmente en entornos hospitalarios para coordinar procesos críticos y sensibles al tiempo.

---


# 7. Archivos fuente

El proyecto está organizado siguiendo una arquitectura clara y modular, lo que facilita su mantenimiento, comprensión y ampliación futura. A continuación se listan los archivos y directorios que conforman la solución:

AGENTESPROTOCOLOPROYECTO/
│
├── app/
│ ├── pycache/ # Caché generado por Python
│ │
│ ├── agents/ # Implementación de los agentes del sistema
│ │ ├── pycache/
│ │ ├── init.py
│ │ ├── base.py # Clase base común para todos los agentes
│ │ ├── bus.py # Message Bus interno: envío/recepción ACP + A2A
│ │ ├── executor.py # Ejecutor: asigna quirófano y actualiza estados
│ │ ├── knowledge_base.py # Base de Conocimiento (SQLite + queries)
│ │ ├── monitor.py # Monitor: genera snapshot global del sistema
│ │ ├── notifier.py # Notificador: registra eventos importantes
│ │ └── planner.py # Planificador: genera subtareas (Gemini 2.5)
│ │
│ ├── static/
│ │ └── main.css # Estilos completos de la interfaz (UI)
│ │
│ ├── templates/ # Vistas HTML renderizadas con Jinja2
│ │ ├── base.html # Layout principal de la aplicación
│ │ ├── case_detail.html # Vista de detalle de cada caso quirúrgico
│ │ └── index.html # Vista principal y dashboard del hospital
│ │
│ ├── init.py
│ ├── ai_adapter.py # Adaptador para modelos Gemini 2.5
│ ├── config.py # Configuraciones globales + logging + .env
│ ├── main.py # Rutas FastAPI + lógica de UI + endpoints API
│ ├── models.py # Entidades, Pydantic y estructuras del dominio
│ └── protocols.py # Implementación AG-UI, A2A, ACP, MCP
│
├── data/
│ └── hospital.db # Base de datos SQLite persistente
│
├── logs/
│ └── app.log # Bitácora del sistema multiagente
│
├── venv/ # Entorno virtual con dependencias
│
├── .env # Variables de entorno (incluye GEMINI_API_KEY)
└── requirements.txt # Lista de dependencias del proyecto


