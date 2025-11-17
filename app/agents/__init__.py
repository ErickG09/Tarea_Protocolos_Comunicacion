from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import configure_logging
from .bus import MessageBus
from .executor import Executor
from .knowledge_base import KnowledgeBase
from .monitor import Monitor
from .notifier import Notifier
from .planner import Planner

logger = configure_logging()


@dataclass
class AgentContext:
    """
    Contiene todas las instancias compartidas de agentes y la base
    de conocimiento.

    Esta clase será utilizada por los endpoints FastAPI para interactuar
    con el sistema multitagente.
    """

    kb: KnowledgeBase
    bus: MessageBus
    planner: Planner
    executor: Executor
    notifier: Notifier
    monitor: Monitor


_context: Optional[AgentContext] = None


def get_agent_context() -> AgentContext:
    """
    Devuelve un contexto único de agentes.

    Si aún no existe, inicializa la Base de Conocimiento, el bus
    y todos los agentes, registrándolos en el bus.
    """
    global _context
    if _context is not None:
        return _context

    kb = KnowledgeBase()
    bus = MessageBus()

    planner = Planner(kb=kb)
    executor = Executor(kb=kb)
    notifier = Notifier(kb=kb)
    monitor = Monitor(kb=kb)

    for agent in (planner, executor, notifier, monitor):
        bus.register_agent(agent)

    _context = AgentContext(
        kb=kb,
        bus=bus,
        planner=planner,
        executor=executor,
        notifier=notifier,
        monitor=monitor,
    )

    logger.info("Contexto de agentes inicializado correctamente.")
    return _context
