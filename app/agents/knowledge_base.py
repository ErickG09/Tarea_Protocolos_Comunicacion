from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config import configure_logging
from ..models import (
    SurgeryCase,
    SurgeryPriority,
    SurgeryStatus,
    SurgeryTask,
    TaskStatus,
)

logger = configure_logging()


def _now() -> datetime:
    """
    Devuelve la hora actual en horario local del servidor.

    Usamos horario local porque las fechas que vienen desde la UI
    (datetime-local) también son locales.
    """
    return datetime.now()


@dataclass
class ORRoom:
    """
    Representa un quirófano físico en el hospital.
    """

    id: str
    name: str


@dataclass
class Notification:
    """
    Notificación simple generada por el agente Notificador.
    """

    timestamp: datetime
    message: str


class KnowledgeBase:
    """
    Base de conocimiento persistente usando SQLite.

    Mantiene:
        - Casos de cirugía.
        - Tareas asociadas.
        - Quirófanos disponibles (en memoria).
        - Notificaciones.
    """

    def __init__(self, db_path: str = "data/hospital.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(exist_ok=True)

        # check_same_thread=False para uso desde hilos diferentes (FastAPI + agentes)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # Aseguramos soporte de claves foráneas
        self._conn.execute("PRAGMA foreign_keys = ON;")

        self._init_schema()

        # Definimos 5 quirófanos del hospital (en memoria).
        self._or_rooms: Dict[str, ORRoom] = {
            "OR-1": ORRoom(id="OR-1", name="Quirófano 1"),
            "OR-2": ORRoom(id="OR-2", name="Quirófano 2"),
            "OR-3": ORRoom(id="OR-3", name="Quirófano 3"),
            "OR-4": ORRoom(id="OR-4", name="Quirófano 4"),
            "OR-5": ORRoom(id="OR-5", name="Quirófano 5"),
        }

        logger.info(
            "KnowledgeBase SQLite inicializada en %s con %d quirófanos.",
            self._db_path,
            len(self._or_rooms),
        )

    # ------------------------------------------------------------------
    # Inicialización de esquema SQLite
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        cur = self._conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS surgery_cases (
                id TEXT PRIMARY KEY,
                patient_name TEXT NOT NULL,
                procedure_name TEXT NOT NULL,
                priority TEXT NOT NULL,
                requested_datetime TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS surgery_tasks (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                or_room_id TEXT,
                scheduled_start TEXT,
                scheduled_end TEXT,
                FOREIGN KEY(case_id) REFERENCES surgery_cases(id)
                    ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                message TEXT NOT NULL
            );
            """
        )

        self._conn.commit()
        logger.info("Esquema SQLite verificado/creado correctamente.")

    # ------------------------------------------------------------------
    # Utilidades de conversión
    # ------------------------------------------------------------------

    @staticmethod
    def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
        return dt.isoformat() if dt is not None else None

    @staticmethod
    def _str_to_dt(value: Optional[str]) -> Optional[datetime]:
        if value is None:
            return None
        return datetime.fromisoformat(value)

    # ------------------------------------------------------------------
    # Gestión de quirófanos
    # ------------------------------------------------------------------

    def list_or_rooms(self) -> List[ORRoom]:
        return list(self._or_rooms.values())

    def get_or_room(self, or_id: str) -> Optional[ORRoom]:
        return self._or_rooms.get(or_id)

    def find_available_or(self, start: datetime, end: datetime) -> Optional[ORRoom]:
        """
        Busca un quirófano donde el intervalo [start, end] no choque
        con ninguna tarea ya programada en ese quirófano.

        Criterio de choque:
            task.start < end AND task.end > start
        """
        cur = self._conn.cursor()

        for or_room in self._or_rooms.values():
            cur.execute(
                """
                SELECT 1
                FROM surgery_tasks
                WHERE or_room_id = ?
                  AND scheduled_start IS NOT NULL
                  AND scheduled_end   IS NOT NULL
                  AND scheduled_start < ?
                  AND scheduled_end   > ?
                LIMIT 1;
                """,
                (
                    or_room.id,
                    self._dt_to_str(end),
                    self._dt_to_str(start),
                ),
            )
            row = cur.fetchone()
            if row is None:
                logger.info(
                    "Quirófano disponible encontrado: %s (%s) para intervalo %s - %s",
                    or_room.id,
                    or_room.name,
                    start,
                    end,
                )
                return or_room

        logger.warning(
            "No se encontró quirófano disponible para intervalo %s - %s.",
            start,
            end,
        )
        return None

    # ------------------------------------------------------------------
    # Gestión de casos (persistencia)
    # ------------------------------------------------------------------

    def add_case(self, case: SurgeryCase) -> None:
        """
        Inserta o reemplaza un caso y sus tareas en la base de datos.
        """
        cur = self._conn.cursor()

        cur.execute(
            """
            INSERT OR REPLACE INTO surgery_cases (
                id, patient_name, procedure_name, priority,
                requested_datetime, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                case.id,
                case.patient_name,
                case.procedure_name,
                case.priority.value,
                self._dt_to_str(case.requested_datetime),
                case.status.value,
                self._dt_to_str(case.created_at),
                self._dt_to_str(case.updated_at),
            ),
        )

        # Eliminamos tareas anteriores del caso y reinsertamos.
        cur.execute("DELETE FROM surgery_tasks WHERE case_id = ?;", (case.id,))

        for task in case.tasks:
            cur.execute(
                """
                INSERT INTO surgery_tasks (
                    id, case_id, name, status, or_room_id,
                    scheduled_start, scheduled_end
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    task.id,
                    task.case_id,
                    task.name,
                    task.status.value,
                    task.or_room_id,
                    self._dt_to_str(task.scheduled_start),
                    self._dt_to_str(task.scheduled_end),
                ),
            )

        self._conn.commit()
        logger.info(
            "Caso de cirugía %s guardado en SQLite con %d tareas.",
            case.id,
            len(case.tasks),
        )

    def delete_case(self, case_id: str) -> None:
        """
        Elimina un caso y sus tareas asociadas de la base de datos.
        Útil para pruebas desde la UI.
        """
        cur = self._conn.cursor()
        # Borramos tareas explícitamente por si el PRAGMA no estuviera activo.
        cur.execute("DELETE FROM surgery_tasks WHERE case_id = ?;", (case_id,))
        cur.execute("DELETE FROM surgery_cases WHERE id = ?;", (case_id,))
        self._conn.commit()
        logger.info("Caso de cirugía %s eliminado de SQLite.", case_id)

    def _row_to_case(self, row: sqlite3.Row) -> SurgeryCase:
        """
        Convierte una fila de surgery_cases + sus tareas asociadas a un SurgeryCase.
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM surgery_tasks
            WHERE case_id = ?
            ORDER BY scheduled_start ASC, id ASC;
            """,
            (row["id"],),
        )
        task_rows = cur.fetchall()

        tasks: List[SurgeryTask] = []
        for t in task_rows:
            tasks.append(
                SurgeryTask(
                    id=t["id"],
                    case_id=t["case_id"],
                    name=t["name"],
                    status=TaskStatus(t["status"]),
                    or_room_id=t["or_room_id"],
                    scheduled_start=self._str_to_dt(t["scheduled_start"]),
                    scheduled_end=self._str_to_dt(t["scheduled_end"]),
                )
            )

        case = SurgeryCase(
            id=row["id"],
            patient_name=row["patient_name"],
            procedure_name=row["procedure_name"],
            priority=SurgeryPriority(row["priority"]),
            requested_datetime=self._str_to_dt(row["requested_datetime"]),
            status=SurgeryStatus(row["status"]),
            created_at=self._str_to_dt(row["created_at"]),
            updated_at=self._str_to_dt(row["updated_at"]),
            tasks=tasks,
        )
        return case

    def get_case(self, case_id: str) -> Optional[SurgeryCase]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM surgery_cases WHERE id = ?;", (case_id,))
        row = cur.fetchone()
        if row is None:
            return None

        case = self._row_to_case(row)
        self._refresh_case_status(case)
        # Persistimos los cambios de estado
        self.add_case(case)
        return case

    def list_cases(self) -> List[SurgeryCase]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM surgery_cases ORDER BY created_at DESC;")
        rows = cur.fetchall()

        cases: List[SurgeryCase] = []
        for row in rows:
            case = self._row_to_case(row)
            self._refresh_case_status(case)
            self.add_case(case)
            cases.append(case)
        return cases

    def _refresh_case_status(self, case: SurgeryCase) -> None:
        """
        Actualiza los estados de las tareas y del caso según la hora actual local.

        Regla simple:
            - Si ahora >= fin_programado -> DONE
            - Si inicio <= ahora < fin -> IN_PROGRESS
            - Si ahora < inicio -> SCHEDULED

        Estado global:
            - Alguna IN_PROGRESS      -> IN_PROGRESS
            - Todas DONE              -> COMPLETED
            - En otro caso            -> PLANNED
        """
        now = _now()
        any_in_progress = False
        all_completed = True

        for task in case.tasks:
            if task.scheduled_start is None or task.scheduled_end is None:
                continue

            if now >= task.scheduled_end:
                task.status = TaskStatus.DONE
            elif task.scheduled_start <= now < task.scheduled_end:
                task.status = TaskStatus.IN_PROGRESS
                any_in_progress = True
                all_completed = False
            else:
                task.status = TaskStatus.SCHEDULED
                all_completed = False

        if any_in_progress:
            case.status = SurgeryStatus.IN_PROGRESS
        elif all_completed and case.tasks:
            case.status = SurgeryStatus.COMPLETED
        else:
            case.status = SurgeryStatus.PLANNED

        case.updated_at = now

    # ------------------------------------------------------------------
    # Notificaciones
    # ------------------------------------------------------------------

    def add_notification(self, message: str) -> None:
        cur = self._conn.cursor()
        ts = self._dt_to_str(_now())
        cur.execute(
            "INSERT INTO notifications (timestamp, message) VALUES (?, ?);",
            (ts, message),
        )
        self._conn.commit()
        logger.info("Notificación registrada en SQLite: %s", message)

    def list_notifications(self) -> List[Notification]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT timestamp, message FROM notifications ORDER BY id DESC LIMIT 50;"
        )
        rows = cur.fetchall()

        notifications: List[Notification] = []
        for row in rows:
            notifications.append(
                Notification(
                    timestamp=self._str_to_dt(row["timestamp"]) or _now(),
                    message=row["message"],
                )
            )
        return notifications
