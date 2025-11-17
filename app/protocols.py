from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .config import configure_logging

logger = configure_logging()


class AgentRole(str, Enum):
    """
    Roles de los agentes definidos en el escenario.

    Estos roles sirven para documentar y también para enrutar mensajes
    entre componentes.
    """

    PLANNER = "planner"
    EXECUTOR = "executor"
    NOTIFIER = "notifier"
    UI = "ui"
    KNOWLEDGE_BASE = "knowledge_base"
    MONITOR = "monitor"


class ProtocolName(str, Enum):
    """
    Conjunto de protocolos utilizados en el proyecto.

    A2A:
        Agent-to-Agent. Capa básica de transporte entre agentes.
    AG_UI:
        Agent-to-User Interface. Comunicación entre la interfaz de usuario
        y el resto de los agentes.
    ACP:
        Agent Communication Protocol. Define el tipo de acto comunicativo
        (request, inform, propose, agree, refuse, etc.).
    MCP:
        Message Content Protocol. Estandariza la forma de los contenidos
        del mensaje (campos y semántica).
    """

    A2A = "A2A"
    AG_UI = "AG-UI"
    ACP = "ACP"
    MCP = "MCP"


class Performative(str, Enum):
    """
    Actos comunicativos básicos que usaremos siguiendo la idea de FIPA ACL.

    REQUEST:
        Un agente solicita que otro realice una acción.
    INFORM:
        Un agente comunica información que considera verdadera.
    PROPOSE:
        Propuesta de plan, horario o recurso.
    AGREE:
        Aceptación de una propuesta o petición.
    REFUSE:
        Rechazo de una propuesta o petición.
    QUERY:
        Consulta de información a otro agente.
    FAILURE:
        Comunicación de fallo al intentar ejecutar una acción.
    """

    REQUEST = "REQUEST"
    INFORM = "INFORM"
    PROPOSE = "PROPOSE"
    AGREE = "AGREE"
    REFUSE = "REFUSE"
    QUERY = "QUERY"
    FAILURE = "FAILURE"


class MessageEnvelope(BaseModel):
    """
    Sobre estándar para todos los mensajes del sistema.

    Un mensaje puede estar asociado a varios protocolos simultáneamente.
    Por ejemplo:
        - A2A + ACP + MCP para comunicación entre Planificador y Ejecutor.
        - AG-UI + MCP para comunicación entre la interfaz y el Planificador.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Identificador único del mensaje.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Marca de tiempo de creación del mensaje en UTC.",
    )

    # Protocolos implicados en este mensaje (uno o varios).
    protocols: list[ProtocolName] = Field(
        default_factory=list,
        description="Protocolos que aplican para este mensaje.",
    )

    # Acto comunicativo (solo uno por mensaje).
    performative: Performative = Field(
        ..., description="Tipo de acto comunicativo según ACP."
    )

    sender: AgentRole = Field(
        ..., description="Rol del agente que envía el mensaje."
    )
    receiver: AgentRole = Field(
        ..., description="Rol del agente que recibe el mensaje."
    )

    # Contenido semántico normalizado (MCP).
    content: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Contenido del mensaje. La estructura concreta se define según MCP "
            "para cada tipo de mensaje."
        ),
    )

    # Campo opcional para metadatos adicionales (por ejemplo, trazas, ids externos).
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos auxiliares no esenciales para la semántica del mensaje.",
    )


def build_message(
    *,
    performative: Performative,
    sender: AgentRole,
    receiver: AgentRole,
    content: Optional[Dict[str, Any]] = None,
    protocols: Optional[list[ProtocolName]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> MessageEnvelope:
    """
    Crea un mensaje estándar y registra en logs la operación.

    Esta función centraliza la creación de mensajes para mantener
    una traza clara de las comunicaciones entre agentes.

    Parameters
    ----------
    performative:
        Tipo de acto comunicativo según ACP.
    sender:
        Rol del agente emisor.
    receiver:
        Rol del agente receptor.
    content:
        Contenido semántico del mensaje (MCP).
    protocols:
        Lista de protocolos implicados. Si es None, se utilizará
        A2A por defecto.
    metadata:
        Metadatos opcionales.

    Returns
    -------
    MessageEnvelope
        Mensaje construido listo para ser procesado por los agentes.
    """
    if protocols is None:
        protocols = [ProtocolName.A2A]

    envelope = MessageEnvelope(
        performative=performative,
        sender=sender,
        receiver=receiver,
        content=content or {},
        protocols=protocols,
        metadata=metadata or {},
    )

    logger.info(
        "Mensaje creado: id=%s, performative=%s, sender=%s, receiver=%s, protocols=%s",
        envelope.id,
        envelope.performative.value,
        envelope.sender.value,
        envelope.receiver.value,
        [p.value for p in envelope.protocols],
    )
    logger.debug("Contenido del mensaje %s: %s", envelope.id, envelope.content)
    return envelope
