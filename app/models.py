from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from .config import configure_logging

logger = configure_logging()


class SurgeryPriority(str, Enum):
    """
    Prioridad clínica del caso de cirugía.
    """

    EMERGENCY = "emergency"
    URGENT = "urgent"
    ELECTIVE = "elective"


class SurgeryStatus(str, Enum):
    """
    Estado general del caso de cirugía.
    """

    NEW = "new"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """
    Estado de una subtarea dentro del plan quirúrgico.
    """

    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ORRoom(BaseModel):
    """
    Representa un quirófano disponible en el hospital.
    """

    id: str = Field(..., description="Identificador interno de la sala.")
    name: str = Field(..., description="Nombre descriptivo de la sala.")
    capacity: int = Field(
        1,
        ge=1,
        description="Capacidad nominal de la sala (por ejemplo, número de mesas).",
    )
    is_available: bool = Field(
        True,
        description="Indica si la sala está disponible para ser reservada.",
    )


class SurgeryTask(BaseModel):
    """
    Subtarea asociada a un caso de cirugía.

    Ejemplos de tareas:
        - Preoperatorio
        - Cirugía principal
        - Postoperatorio
    """

    id: str = Field(..., description="Identificador único de la subtarea.")
    case_id: str = Field(..., description="Identificador del caso al que pertenece.")
    name: str = Field(..., description="Nombre o descripción breve de la tarea.")
    status: TaskStatus = Field(
        TaskStatus.PENDING, description="Estado actual de la subtarea."
    )

    or_room_id: Optional[str] = Field(
        None,
        description="Identificador de la sala asignada, en caso de aplicar.",
    )
    scheduled_start: Optional[datetime] = Field(
        None, description="Fecha y hora de inicio planificada."
    )
    scheduled_end: Optional[datetime] = Field(
        None, description="Fecha y hora de término planificada."
    )


class SurgeryCase(BaseModel):
    """
    Caso de cirugía registrado en el sistema.

    Este modelo representa la entidad principal que el usuario crea desde
    la interfaz. El Planificador descompondrá este caso en subtareas y el
    Ejecutor se encargará de programarlas en quirófanos disponibles.
    """

    id: str = Field(..., description="Identificador único del caso de cirugía.")
    patient_name: str = Field(..., description="Nombre del paciente.")
    procedure_name: str = Field(..., description="Nombre del procedimiento.")
    priority: SurgeryPriority = Field(
        SurgeryPriority.ELECTIVE,
        description="Prioridad clínica de la cirugía.",
    )
    requested_datetime: datetime = Field(
        ...,
        description="Fecha y hora objetivo solicitada para la cirugía.",
    )

    status: SurgeryStatus = Field(
        SurgeryStatus.NEW,
        description="Estado actual del caso.",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Fecha y hora de creación del caso (UTC).",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Fecha y hora de última actualización del caso (UTC).",
    )

    tasks: List[SurgeryTask] = Field(
        default_factory=list,
        description="Subtareas asociadas a este caso.",
    )


# ======================================================================
# Modelos de entrada/salida para la API (lo que vendrá desde la UI).
# Estas clases representan el contenido MCP de mensajes típicos.
# ======================================================================


class NewCaseInput(BaseModel):
    """
    Datos mínimos que el usuario proporciona para registrar un nuevo caso.

    Este modelo se utilizará tanto en la API HTTP como en los mensajes MCP
    del tipo NEW_CASE.
    """

    patient_name: str = Field(..., example="Juan Pérez")
    procedure_name: str = Field(..., example="Colecistectomía laparoscópica")
    priority: SurgeryPriority = Field(
        SurgeryPriority.ELECTIVE, example=SurgeryPriority.ELECTIVE
    )
    requested_datetime: datetime = Field(
        ...,
        example="2025-11-15T09:00:00Z",
        description="Fecha y hora solicitada (en formato ISO 8601).",
    )


class NewCaseCreated(BaseModel):
    """
    Respuesta cuando el sistema ha creado un nuevo caso.

    Este modelo puede formar parte del contenido MCP en un mensaje INFORM
    enviado desde el Planificador a la UI o a la Base de Conocimiento.
    """

    case: SurgeryCase = Field(..., description="Caso de cirugía creado.")


class SimpleMessage(BaseModel):
    """
    Modelo genérico para respuestas sencillas de la API.

    Útil para endpoints de prueba y para mensajes de estado.
    """

    message: str
