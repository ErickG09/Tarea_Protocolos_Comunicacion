from __future__ import annotations

from collections import Counter
from typing import Dict, Any

from ..config import configure_logging
from ..models import SurgeryCase, SurgeryStatus
from ..protocols import AgentRole, MessageEnvelope
from .base import BaseAgent
from .knowledge_base import KnowledgeBase

logger = configure_logging()


class Monitor(BaseAgent):
    """
    Agente Monitor.

    Proporciona una vista agregada del estado del sistema:
        - Número de casos por estado.
        - Número total de casos y quirófanos.
    """

    def __init__(self, kb: KnowledgeBase) -> None:
        super().__init__(AgentRole.MONITOR)
        self.kb = kb

    def get_snapshot(self) -> Dict[str, Any]:
        cases = self.kb.list_cases()
        rooms = self.kb.list_or_rooms()

        status_counter = Counter(case.status.value for case in cases)

        snapshot = {
            "total_cases": len(cases),
            "total_or_rooms": len(rooms),
            "cases_by_status": dict(status_counter),
        }
        logger.info("Monitor generó snapshot del sistema: %s", snapshot)
        return snapshot

    def handle_message(self, message: MessageEnvelope) -> Dict[str, Any]:
        """
        El Monitor, por ahora, ignora el contenido del mensaje y devuelve
        siempre un snapshot del sistema. Esto es suficiente para fines
        de visualización en la UI.
        """
        logger.info(
            "Monitor recibió mensaje %s. Se devolverá snapshot del sistema.",
            message.id,
        )
        return self.get_snapshot()
