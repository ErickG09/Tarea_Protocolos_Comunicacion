from fastapi import (
    FastAPI,
    Request,
    Form,
    HTTPException,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings, configure_logging
from .agents import get_agent_context
from .models import NewCaseInput
from .protocols import (
    AgentRole,
    Performative,
    ProtocolName,
    build_message,
)

logger = configure_logging()
settings = get_settings()

app = FastAPI(title="Gestor de Cirugías Multitagente")

# Archivos estáticos (CSS, imágenes, etc.)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates Jinja2
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
async def on_startup() -> None:
    """
    Evento de arranque de la aplicación.

    Inicializa configuración, logging y contexto de agentes.
    """
    logger.info("Aplicación FastAPI iniciando")
    logger.info("Entorno de la aplicación: %s", settings.app_env)

    if settings.gemini_api_key:
        logger.info("Gemini configurado correctamente (GEMINI_API_KEY presente).")
    else:
        logger.warning(
            "Gemini no está configurado. "
            "Defina GEMINI_API_KEY en el archivo .env si desea usar IA en el Planificador."
        )

    # Inicializamos el contexto de agentes para que el sistema esté listo
    # desde el arranque.
    context = get_agent_context()
    logger.info(
        "Contexto de agentes listo. Casos actuales: %d, Quirófanos: %d",
        len(context.kb.list_cases()),
        len(context.kb.list_or_rooms()),
    )


@app.get("/health", tags=["infraestructura"])
async def healthcheck() -> dict:
    """
    Endpoint de salud simple para verificar que la aplicación está viva.

    Devuelve información mínima que también puede ser útil para depuración.
    """
    logger.info("Healthcheck solicitado")
    return {
        "status": "ok",
        "gemini_configured": settings.gemini_api_key is not None,
        "environment": settings.app_env,
    }


@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def index(request: Request):
    """
    Vista principal del sistema.

    Muestra:
        - Formulario para registrar un nuevo caso de cirugía.
        - Lista de casos registrados.
        - Resumen del estado global (snapshot del Monitor).
        - Un resumen de las últimas notificaciones.
    """
    context = get_agent_context()

    cases = context.kb.list_cases()
    snapshot = context.monitor.get_snapshot()
    notifications = context.notifier.list_notifications()

    # Mostramos solo las últimas 5 notificaciones para no saturar la página.
    last_notifications = notifications[-5:]

    logger.info(
        "Renderizando página principal con %d casos y %d notificaciones.",
        len(cases),
        len(notifications),
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_env": settings.app_env,
            "gemini_configured": settings.gemini_api_key is not None,
            "cases": cases,
            "snapshot": snapshot,
            "notifications": last_notifications,
        },
    )


@app.get("/cases/{case_id}", response_class=HTMLResponse, tags=["ui"])
async def case_detail(request: Request, case_id: str):
    """
    Vista de detalle de un caso de cirugía.

    Muestra información general del caso y las subtareas generadas
    por el Planificador.
    """
    context = get_agent_context()
    case = context.kb.get_case(case_id)

    if case is None:
        logger.warning("Se solicitó detalle de un caso inexistente: %s", case_id)
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    has_unassigned_tasks = any(task.or_room_id is None for task in case.tasks)

    logger.info("Renderizando detalle para el caso %s.", case_id)

    return templates.TemplateResponse(
        "case_detail.html",
        {
            "request": request,
            "case": case,
            "has_unassigned_tasks": has_unassigned_tasks,
        },
    )


# ============================================================================
# Endpoints UI (HTML) que internamente usan los protocolos y el bus de agentes
# ============================================================================


@app.post("/cases", tags=["ui"])
async def create_case_from_form(
    request: Request,
    patient_name: str = Form(...),
    procedure_name: str = Form(...),
    priority: str = Form(...),
    requested_datetime: str = Form(...),
):
    """
    Crea un nuevo caso de cirugía a partir de un formulario HTML.

    Internamente:
        - Construye un mensaje AG-UI + ACP + MCP desde la "UI" hacia el
          Planificador.
        - El Planificador devuelve un mensaje INFORM con el caso creado.
    """
    context = get_agent_context()

    payload = {
        "patient_name": patient_name,
        "procedure_name": procedure_name,
        "priority": priority,
        "requested_datetime": requested_datetime,
    }

    logger.info(
        "Formulario de nuevo caso recibido: paciente=%s, procedimiento=%s, prioridad=%s, fecha=%s",
        patient_name,
        procedure_name,
        priority,
        requested_datetime,
    )

    message = build_message(
        performative=Performative.REQUEST,
        sender=AgentRole.UI,
        receiver=AgentRole.PLANNER,
        protocols=[
            ProtocolName.AG_UI,
            ProtocolName.ACP,
            ProtocolName.MCP,
            ProtocolName.A2A,
        ],
        content={
            "type": "NEW_CASE",
            "payload": payload,
        },
    )

    response_envelope = context.bus.send(message)
    if response_envelope is None:
        logger.error("No se recibió respuesta al crear caso desde el Planificador.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear el caso de cirugía.",
        )

    content = response_envelope.get("content") or {}
    inner_payload = content.get("payload") or {}
    case_data = inner_payload.get("case")

    if not case_data:
        logger.error(
            "La respuesta del Planificador no contiene datos de caso. content=%s",
            content,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Respuesta inválida del Planificador.",
        )

    case_id = case_data.get("id")
    logger.info("Caso creado correctamente con id=%s. Redirigiendo a detalle.", case_id)

    # Notificación al agente Notificador
    notify_message = build_message(
        performative=Performative.INFORM,
        sender=AgentRole.UI,
        receiver=AgentRole.NOTIFIER,
        protocols=[ProtocolName.A2A, ProtocolName.ACP, ProtocolName.MCP],
        content={
            "type": "NEW_CASE_CREATED",
            "payload": {"case_id": case_id},
        },
    )
    context.bus.send(notify_message)

    return RedirectResponse(
        url=f"/cases/{case_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/cases/{case_id}/schedule", tags=["ui"])
async def schedule_case_from_form(case_id: str):
    """
    Programa un caso de cirugía desde la UI.

    Internamente:
        - Envía un mensaje REQUEST con tipo SCHEDULE_CASE desde la UI al
          Ejecutor.
        - El Ejecutor asigna quirófano y cambia el estado de las tareas.
        - Se genera una notificación para el Notificador.
    """
    context = get_agent_context()

    logger.info("Solicitud de programación de caso recibida para case_id=%s", case_id)

    message = build_message(
        performative=Performative.REQUEST,
        sender=AgentRole.UI,
        receiver=AgentRole.EXECUTOR,
        protocols=[ProtocolName.A2A, ProtocolName.ACP, ProtocolName.MCP],
        content={
            "type": "SCHEDULE_CASE",
            "case_id": case_id,
        },
    )

    result = context.bus.send(message)
    if result is None:
        logger.error(
            "El Ejecutor no devolvió resultado al programar el caso %s.", case_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al programar el caso.",
        )

    logger.info("Caso %s programado correctamente por el Ejecutor.", case_id)

    # Notificación
    notify_message = build_message(
        performative=Performative.INFORM,
        sender=AgentRole.UI,
        receiver=AgentRole.NOTIFIER,
        protocols=[ProtocolName.A2A, ProtocolName.ACP, ProtocolName.MCP],
        content={
            "type": "CASE_SCHEDULED",
            "payload": {"case_id": case_id},
        },
    )
    context.bus.send(notify_message)

    return RedirectResponse(
        url=f"/cases/{case_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/cases/{case_id}/delete", tags=["ui"])
async def delete_case_from_form(case_id: str):
    """
    Elimina un caso de cirugía (y sus tareas asociadas) desde la UI.

    Útil para limpiar datos de prueba. Después de eliminar redirige al dashboard.
    """
    context = get_agent_context()

    logger.info("Solicitud de eliminación de caso recibida para case_id=%s", case_id)

    # Eliminamos el caso directamente desde la Base de Conocimiento (SQLite).
    context.kb.delete_case(case_id)

    # Registramos una notificación sencilla.
    context.kb.add_notification(f"Caso {case_id} eliminado desde la interfaz.")

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ============================================================================
# Endpoints JSON (API) opcionales, útiles para pruebas y documentación
# ============================================================================


@app.post("/api/cases", tags=["api"])
async def api_create_case(input_data: NewCaseInput):
    """
    Crea un caso de cirugía a partir de JSON (API).

    Este endpoint es equivalente al formulario HTML, pero usando JSON.
    """
    context = get_agent_context()

    message = build_message(
        performative=Performative.REQUEST,
        sender=AgentRole.UI,
        receiver=AgentRole.PLANNER,
        protocols=[
            ProtocolName.AG_UI,
            ProtocolName.ACP,
            ProtocolName.MCP,
            ProtocolName.A2A,
        ],
        content={
            "type": "NEW_CASE",
            "payload": input_data.model_dump(),
        },
    )

    response_envelope = context.bus.send(message)
    if response_envelope is None:
        logger.error("No se recibió respuesta al crear caso desde el Planificador (API).")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear el caso de cirugía.",
        )

    return response_envelope


@app.post("/api/cases/{case_id}/schedule", tags=["api"])
async def api_schedule_case(case_id: str):
    """
    Programa un caso desde la API JSON.
    """
    context = get_agent_context()

    message = build_message(
        performative=Performative.REQUEST,
        sender=AgentRole.UI,
        receiver=AgentRole.EXECUTOR,
        protocols=[ProtocolName.A2A, ProtocolName.ACP, ProtocolName.MCP],
        content={
            "type": "SCHEDULE_CASE",
            "case_id": case_id,
        },
    )

    result = context.bus.send(message)
    if result is None:
        logger.error(
            "El Ejecutor no devolvió resultado al programar el caso %s (API).", case_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al programar el caso.",
        )

    return result


@app.get("/api/monitor/snapshot", tags=["api"])
async def api_monitor_snapshot():
    """
    Devuelve el snapshot global del sistema usando el Monitor como agente.
    """
    context = get_agent_context()
    snapshot = context.monitor.get_snapshot()
    return snapshot


@app.get("/api/notifications", tags=["api"])
async def api_notifications():
    """
    Devuelve todas las notificaciones registradas por el Notificador.
    """
    context = get_agent_context()
    return context.notifier.list_notifications()
