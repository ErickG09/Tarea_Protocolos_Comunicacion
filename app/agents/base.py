from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

from ..config import configure_logging
from ..protocols import AgentRole, MessageEnvelope

# Import solo para type checking, evita dependencias cíclicas
if TYPE_CHECKING:
    from .bus import MessageBus

logger = configure_logging()


class BaseAgent(ABC):
    """
    Clase base para todos los agentes del sistema.

    Proporciona:
        - Rol del agente.
        - Acceso al logger.
        - Referencia opcional al bus de mensajes.
    """

    def __init__(self, role: AgentRole) -> None:
        self.role = role
        self.logger = logger
        self._bus: Optional["MessageBus"] = None

    def attach_bus(self, bus: "MessageBus") -> None:
        """
        Asigna el bus de mensajes al agente.

        Este método es llamado automáticamente por el MessageBus cuando
        se registra el agente.
        """
        self._bus = bus
        self.logger.info(
            "Agente %s asociado al bus de mensajes.", self.role.value
        )

    @property
    def bus(self) -> "MessageBus":
        """
        Devuelve el bus de mensajes asociado.

        Lanza un error si el bus aún no ha sido asignado, para evitar
        errores silenciosos.
        """
        if self._bus is None:
            raise RuntimeError(
                f"El agente {self.role.value} no tiene un bus de mensajes asociado."
            )
        return self._bus

    @abstractmethod
    def handle_message(self, message: MessageEnvelope):
        """
        Procesa un mensaje recibido.

        Cada agente implementará la lógica específica según su rol.
        """
        raise NotImplementedError
