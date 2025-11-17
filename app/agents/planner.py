from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from typing import Any, Optional, Dict, List

from ..config import configure_logging
from ..models import (
    NewCaseInput,
    SurgeryCase,
    SurgeryPriority,
    SurgeryStatus,
    SurgeryTask,
    TaskStatus,
)
from ..protocols import (
    AgentRole,
    MessageEnvelope,
    Performative,
    ProtocolName,
    build_message,
)
from ..ai_adapter import (
    suggest_tasks_for_surgery,
    GeminiNotAvailable,
    PlannedTaskDefinition,
)
from .base import BaseAgent
from .knowledge_base import KnowledgeBase

logger = configure_logging()


class Planner(BaseAgent):
    """
    Agente Planificador.

    Responsabilidades:
        - Recibir solicitudes de nuevos casos desde la UI (AG-UI + ACP + MCP).
        - Crear un plan quirúrgico a partir de los datos de entrada.
          - Si es posible, utiliza Gemini para proponer tareas.
          - En caso contrario, utiliza un plan determinista por defecto.
        - Guardar el caso en la Base de Conocimiento.
        - Responder a la UI con el caso creado.
    """

    def __init__(self, kb: KnowledgeBase) -> None:
        super().__init__(AgentRole.PLANNER)
        self.kb = kb

    def _generate_case_id(self) -> str:
        return f"CASE-{uuid4().hex[:8].upper()}"

    def _generate_task_id(self, case_id: str, index_or_suffix: str) -> str:
        return f"{case_id}-{index_or_suffix}"

    # ------------------------------------------------------------------
    # LÓGICA DE PLANIFICACIÓN
    # ------------------------------------------------------------------

    def _build_tasks_with_gemini(
        self, case_id: str, data: NewCaseInput
    ) -> List[SurgeryTask]:
        """
        Intenta obtener el plan de tareas desde Gemini.

        Si Gemini no está disponible o falla, se propaga GeminiNotAvailable
        para que el llamador utilice el plan determinista.
        """
        proposed: List[PlannedTaskDefinition] = suggest_tasks_for_surgery(data)

        tasks: List[SurgeryTask] = []
        reference = data.requested_datetime

        for index, t in enumerate(proposed, start=1):
            start = reference + timedelta(minutes=t.offset_start_minutes)
            end = start + timedelta(minutes=t.duration_minutes)

            task = SurgeryTask(
                id=self._generate_task_id(case_id, f"T{index}"),
                case_id=case_id,
                name=t.name,
                status=TaskStatus.SCHEDULED,
                scheduled_start=start,
                scheduled_end=end,
            )
            tasks.append(task)

        logger.info(
            "Planificador construyó %d tareas usando Gemini para el caso %s.",
            len(tasks),
            case_id,
        )
        return tasks

    def _build_tasks_deterministic(
        self, case_id: str, data: NewCaseInput
    ) -> List[SurgeryTask]:
        """
        Planificador determinista de respaldo.

        Divide la cirugía en tres fases fijas:

            - Preoperatorio: 60 minutos antes de la hora solicitada.
            - Cirugía principal: 120 minutos a partir de la hora solicitada.
            - Postoperatorio: 60 minutos después de la cirugía principal.
        """
        pre_start = data.requested_datetime - timedelta(hours=1)
        pre_end = data.requested_datetime
        surg_start = data.requested_datetime
        surg_end = data.requested_datetime + timedelta(hours=2)
        post_start = surg_end
        post_end = surg_end + timedelta(hours=1)

        tasks = [
            SurgeryTask(
                id=self._generate_task_id(case_id, "PRE"),
                case_id=case_id,
                name="Preoperatorio",
                status=TaskStatus.SCHEDULED,
                scheduled_start=pre_start,
                scheduled_end=pre_end,
            ),
            SurgeryTask(
                id=self._generate_task_id(case_id, "SURG"),
                case_id=case_id,
                name="Cirugía principal",
                status=TaskStatus.SCHEDULED,
                scheduled_start=surg_start,
                scheduled_end=surg_end,
            ),
            SurgeryTask(
                id=self._generate_task_id(case_id, "POST"),
                case_id=case_id,
                name="Postoperatorio",
                status=TaskStatus.SCHEDULED,
                scheduled_start=post_start,
                scheduled_end=post_end,
            ),
        ]

        logger.info(
            "Planificador construyó %d tareas usando plan determinista para el caso %s.",
            len(tasks),
            case_id,
        )
        return tasks

    def _build_tasks_for_case(
        self, case_id: str, data: NewCaseInput
    ) -> List[SurgeryTask]:
        """
        Intenta primero utilizar Gemini; si no es posible, usa el plan
        determinista.

        Esta función es el punto central de decisión para el origen del plan.
        """
        try:
            tasks = self._build_tasks_with_gemini(case_id, data)
            logger.info(
                "Se utilizó Gemini para planificar el caso %s (%s).",
                case_id,
                data.procedure_name,
            )
            return tasks
        except GeminiNotAvailable as exc:
            logger.warning(
                "No fue posible usar Gemini para el caso %s (%s). "
                "Se usará el plan determinista. Motivo: %s",
                case_id,
                data.procedure_name,
                exc,
            )
            return self._build_tasks_deterministic(case_id, data)

    def create_case(self, data: NewCaseInput) -> SurgeryCase:
        """
        Crea un caso de cirugía y sus subtareas.

        1. Genera un identificador de caso.
        2. Construye el conjunto de subtareas (usando Gemini o plan determinista).
        3. Guarda el caso en la Base de Conocimiento.
        """
        case_id = self._generate_case_id()
        now = datetime.utcnow()

        # Construimos las tareas primero
        tasks = self._build_tasks_for_case(case_id, data)

        case = SurgeryCase(
            id=case_id,
            patient_name=data.patient_name,
            procedure_name=data.procedure_name,
            priority=data.priority,
            requested_datetime=data.requested_datetime,
            status=SurgeryStatus.PLANNED,
            created_at=now,
            updated_at=now,
            tasks=tasks,
        )

        self.kb.add_case(case)

        logger.info(
            "Planificador creó caso %s para paciente %s con prioridad %s.",
            case.id,
            case.patient_name,
            case.priority.value,
        )
        return case

    # ------------------------------------------------------------------
    # MANEJO DE MENSAJES
    # ------------------------------------------------------------------

    def handle_message(self, message: MessageEnvelope) -> Optional[Dict[str, Any]]:
        """
        Maneja mensajes entrantes para el Planificador.

        Implementa:
            - REQUEST con content.type == 'NEW_CASE'
        """
        logger.info(
            "Planificador recibió mensaje %s con performative %s.",
            message.id,
            message.performative.value,
        )

        if message.performative == Performative.REQUEST:
            msg_type = message.content.get("type")
            if msg_type == "NEW_CASE":
                payload = message.content.get("payload") or {}
                data = NewCaseInput(**payload)
                case = self.create_case(data)

                response = build_message(
                    performative=Performative.INFORM,
                    sender=self.role,
                    receiver=message.sender,
                    protocols=[
                        ProtocolName.A2A,
                        ProtocolName.ACP,
                        ProtocolName.MCP,
                    ],
                    content={
                        "type": "NEW_CASE_CREATED",
                        "payload": {"case": case.model_dump()},
                    },
                )
                # Devolvemos la representación del mensaje de respuesta
                # para que el llamador pueda decidir qué hacer con él.
                return response.model_dump()

        logger.warning(
            "Planificador no tiene lógica para el mensaje %s. "
            "performative=%s, content=%s",
            message.id,
            message.performative.value,
            message.content,
        )
        return None
