from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import configure_logging
from ..protocols import AgentRole, MessageEnvelope, Performative
from .base import BaseAgent
from .knowledge_base import KnowledgeBase

logger = configure_logging()


class Notifier(BaseAgent):
    """
    Agente Notificador.

    Simula el envío de notificaciones cuando cambia el estado de un caso
    o de una tarea. En lugar de enviar correos, almacena una lista de
    notificaciones en memoria para que puedan ser consultadas desde la UI.
    """

    def __init__(self, kb: KnowledgeBase) -> None:
        super().__init__(AgentRole.NOTIFIER)
        self.kb = kb
        self._notifications: List[Dict[str, Any]] = []

    def add_notification(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "data": data or {},
        }
        self._notifications.append(entry)
        logger.info("Notificador registró notificación: %s", message)

    def list_notifications(self) -> List[Dict[str, Any]]:
        return list(self._notifications)

    def handle_message(self, message: MessageEnvelope) -> Optional[Dict[str, Any]]:
        """
        Maneja mensajes entrantes para el Notificador.

        Para simplificar, tratamos cualquier mensaje INFORM como un evento
        que puede generar una notificación.
        """
        logger.info(
            "Notificador recibió mensaje %s con performative %s.",
            message.id,
            message.performative.value,
        )

        if message.performative == Performative.INFORM:
            event_type = message.content.get("type", "UNSPECIFIED_EVENT")
            self.add_notification(
                f"Evento recibido: {event_type}",
                {"content": message.content},
            )
            return {"status": "notification_recorded", "event_type": event_type}

        logger.warning(
            "Notificador no tiene lógica para el mensaje %s. performative=%s, content=%s",
            message.id,
            message.performative.value,
            message.content,
        )
        return None
