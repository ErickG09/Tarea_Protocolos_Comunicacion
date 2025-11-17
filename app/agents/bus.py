from __future__ import annotations

from typing import Any, Dict

from ..config import configure_logging
from ..protocols import AgentRole, MessageEnvelope
from .base import BaseAgent

logger = configure_logging()


class MessageBus:
    """
    Bus de mensajes sencillo en memoria.

    Se encarga de:
        - Registrar agentes por rol.
        - Entregar mensajes al agente receptor correspondiente.
    """

    def __init__(self) -> None:
        self._agents: Dict[AgentRole, BaseAgent] = {}
        logger.info("MessageBus inicializado.")

    def register_agent(self, agent: BaseAgent) -> None:
        """
        Registra un agente en el bus y le asigna este bus.

        Si ya existe un agente para ese rol, será sobrescrito.
        """
        self._agents[agent.role] = agent
        agent.attach_bus(self)
        logger.info("Agente registrado en el bus: %s", agent.role.value)

    def send(self, message: MessageEnvelope) -> Any:
        """
        Entrega un mensaje al agente receptor y devuelve su respuesta.

        Si no existe un agente para el rol indicado, se registra un error.
        """
        receiver_role = message.receiver
        agent = self._agents.get(receiver_role)

        if agent is None:
            logger.error(
                "No se encontró un agente registrado para el rol %s. "
                "Mensaje %s no entregado.",
                receiver_role.value,
                message.id,
            )
            return None

        logger.info(
            "Bus entregando mensaje %s a agente %s.",
            message.id,
            receiver_role.value,
        )
        return agent.handle_message(message)
