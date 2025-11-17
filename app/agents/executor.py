from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, List

from ..config import configure_logging
from ..models import SurgeryCase, TaskStatus
from ..protocols import (
    AgentRole,
    MessageEnvelope,
    Performative,
    ProtocolName,
    build_message,
)
from .base import BaseAgent
from .knowledge_base import KnowledgeBase

logger = configure_logging()


class Executor(BaseAgent):
    """
    Agente Ejecutor.

    Responsabilidades:
        - Recibir solicitudes para programar un caso de cirugía.
        - Seleccionar un quirófano disponible sin solapamiento de agendas.
        - Asignar el quirófano a todas las tareas del caso.
    """

    def __init__(self, kb: KnowledgeBase) -> None:
        super().__init__(AgentRole.EXECUTOR)
        self.kb = kb

    # ------------------------------------------------------------------
    # Lógica de programación
    # ------------------------------------------------------------------

    def _schedule_case(self, case_id: str) -> Optional[SurgeryCase]:
        case = self.kb.get_case(case_id)
        if case is None:
            logger.warning(
                "El Ejecutor recibió solicitud de programación para un caso inexistente: %s",
                case_id,
            )
            return None

        if not case.tasks:
            logger.warning(
                "El Ejecutor recibió un caso sin tareas para programar: %s",
                case_id,
            )
            return case

        # Tomamos solo tareas con horario válido
        tasks_with_time: List = [
            t for t in case.tasks
            if t.scheduled_start is not None and t.scheduled_end is not None
        ]
        if not tasks_with_time:
            logger.warning(
                "El caso %s no tiene tareas con horario programado; "
                "no se puede asignar quirófano.",
                case_id,
            )
            return case

        start = min(t.scheduled_start for t in tasks_with_time)
        end = max(t.scheduled_end for t in tasks_with_time)

        if start is None or end is None:
            logger.warning(
                "El caso %s tiene horarios incompletos; no se puede programar.",
                case_id,
            )
            return case

        or_room = self.kb.find_available_or(start, end)
        if or_room is None:
            logger.warning(
                "No se pudo programar el caso %s: no hay quirófanos disponibles "
                "para el intervalo %s - %s.",
                case_id,
                start,
                end,
            )
            return case

        # Asignamos el quirófano encontrado a todas las tareas del caso
        for task in case.tasks:
            task.or_room_id = or_room.id
            # Al programar, las marcamos como SCHEDULED.
            task.status = TaskStatus.SCHEDULED

        case.updated_at = datetime.now()
        self.kb.add_case(case)

        logger.info(
            "Ejecutor asignó quirófano %s (%s) al caso %s.",
            or_room.id,
            or_room.name,
            case_id,
        )
        return case

    # ------------------------------------------------------------------
    # Manejo de mensajes
    # ------------------------------------------------------------------

    def handle_message(self, message: MessageEnvelope) -> Optional[Dict[str, Any]]:
        logger.info(
            "Ejecutor recibió mensaje %s con performative %s.",
            message.id,
            message.performative.value,
        )

        if message.performative == Performative.REQUEST:
            msg_type = message.content.get("type")
            if msg_type == "SCHEDULE_CASE":
                case_id = message.content.get("case_id")
                if not case_id:
                    logger.warning(
                        "Mensaje SCHEDULE_CASE sin 'case_id' en el contenido."
                    )
                    return None

                case = self._schedule_case(case_id)
                if case is None:
                    return None

                response = build_message(
                    performative=Performative.INFORM,
                    sender=self.role,
                    receiver=message.sender,
                    protocols=[ProtocolName.A2A, ProtocolName.ACP, ProtocolName.MCP],
                    content={
                        "type": "CASE_SCHEDULED",
                        "payload": {"case": case.model_dump()},
                    },
                )
                return response.model_dump()

        logger.warning(
            "Ejecutor no tiene lógica para el mensaje %s. performative=%s, content=%s",
            message.id,
            message.performative.value,
            message.content,
        )
        return None
