from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

import google.generativeai as genai

from .config import get_settings, configure_logging
from .models import NewCaseInput

logger = configure_logging()


@dataclass
class PlannedTaskDefinition:
    """
    Representa una tarea propuesta por Gemini para un plan quirúrgico.

    offset_start_minutes:
        Minutos de desplazamiento respecto a la hora solicitada de la cirugía.
        Puede ser negativo (por ejemplo, preoperatorio antes de la hora).
    duration_minutes:
        Duración estimada de la tarea en minutos.
    """

    name: str
    offset_start_minutes: int
    duration_minutes: int


class GeminiNotAvailable(Exception):
    """
    Se lanza cuando Gemini no está configurado o no puede utilizarse.
    """


_configured = False
_model_name: str | None = None


def _configure_gemini() -> None:
    """
    Configura el cliente de Gemini si hay API key.

    Si no hay API key, lanza GeminiNotAvailable.
    """
    global _configured, _model_name
    if _configured:
        return

    settings = get_settings()
    if not settings.gemini_api_key:
        logger.warning(
            "Se intentó usar Gemini pero no hay GEMINI_API_KEY configurada."
        )
        raise GeminiNotAvailable("GEMINI_API_KEY no configurada.")

    genai.configure(api_key=settings.gemini_api_key)
    _configured = True
    _model_name = settings.gemini_model
    logger.info(
        "Cliente de Gemini configurado correctamente para el Planificador. "
        "Modelo configurado: %s",
        _model_name,
    )


def _extract_json_block(raw_text: str) -> str:
    """
    Intenta extraer un bloque JSON válido desde el texto devuelto por Gemini.

    - Elimina fences de código tipo ```json ... ```
    - Si hay texto alrededor, toma desde la primera '{' hasta la última '}'.
    """
    text = raw_text.strip()

    # Caso 1: viene como bloque de código ```json ... ``` o ``` ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            inner = "\n".join(lines[1:-1]).strip()
        else:
            inner = text
        text = inner

    # Caso 2: hay texto antes o después del JSON
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return text[start : end + 1]

    return text


def suggest_tasks_for_surgery(data: NewCaseInput) -> List[PlannedTaskDefinition]:
    """
    Utiliza Gemini para proponer un conjunto de subtareas para una cirugía.

    Si hay cualquier problema (no hay API key, error de red, respuesta inválida),
    se lanza GeminiNotAvailable y el llamador deberá usar un plan determinista.
    """
    _configure_gemini()
    settings = get_settings()

    model = genai.GenerativeModel(settings.gemini_model)

    prompt = f"""
Eres un planificador experto de cirugías en un hospital universitario.

Se te proporciona la siguiente información de una cirugía:

- Nombre del paciente: {data.patient_name}
- Procedimiento quirúrgico: {data.procedure_name}
- Prioridad (emergency/urgent/elective): {data.priority.value}
- Fecha/hora solicitada (referencia): {data.requested_datetime.isoformat()}

Objetivo:
Generar un plan detallado de flujo perioperatorio COMPLETO, adaptado específicamente
al tipo de cirugía indicado en "Procedimiento quirúrgico". Este plan se usará para
que un sistema multiagente (Planificador/Ejecutor/Monitor) gestione quirófanos.

Debes devolver EXACTAMENTE un JSON válido con la siguiente estructura:

{{
  "tasks": [
    {{
      "name": "Nombre claro y clínico de la tarea",
      "offset_start_minutes": -120,
      "duration_minutes": 45
    }}
  ]
}}

Reglas obligatorias:
- Devuelve EXACTAMENTE 10 tareas en el arreglo "tasks".
- Las tareas deben cubrir todo el flujo:
  evaluación preoperatoria, preparación de paciente, traslado,
  anestesia, procedimiento principal, cierre, traslado a recuperación,
  vigilancia inicial, etc.
- "offset_start_minutes" es el desplazamiento respecto a la hora solicitada:
  - valores negativos: tareas antes de la hora (preoperatorio).
  - valores positivos: tareas después de la hora (recuperación).
- "duration_minutes" debe ser un entero positivo coherente con la tarea.
- Los nombres de las tareas deben hacer referencia al tipo de cirugía
  específico (por ejemplo, si es un reemplazo de rodilla, que lo mencione).
- No agregues explicaciones fuera del JSON. Si necesitas contexto adicional,
  inclúyelo en el "name" de la tarea.
    """.strip()

    try:
        logger.info(
            "Solicitando a Gemini (modelo=%s) un plan de 10 tareas para el procedimiento '%s'.",
            settings.gemini_model,
            data.procedure_name,
        )
        response = model.generate_content(prompt)

        raw_text = getattr(response, "text", None) or str(response)
        logger.debug("Respuesta cruda de Gemini: %s", raw_text)

        cleaned = _extract_json_block(raw_text)
        logger.debug("Texto limpiado para parsear JSON: %s", cleaned)

        try:
            parsed = json.loads(cleaned)
        except Exception as exc:
            logger.error(
                "No se pudo parsear JSON desde Gemini. Error: %s. Texto limpiado: %s",
                exc,
                cleaned,
            )
            raise GeminiNotAvailable(
                "Respuesta de Gemini no contenía JSON válido."
            ) from exc

        tasks_data = parsed.get("tasks")
        if not isinstance(tasks_data, list) or not tasks_data:
            logger.error(
                "Respuesta de Gemini sin lista 'tasks' válida. Objeto parseado: %s",
                parsed,
            )
            raise GeminiNotAvailable(
                "Respuesta de Gemini no contenía una lista 'tasks' válida."
            )

        result: List[PlannedTaskDefinition] = []
        for t in tasks_data:
            name = str(t.get("name", "")).strip()
            if not name:
                continue
            offset = int(t.get("offset_start_minutes", 0))
            duration = int(t.get("duration_minutes", 60))
            result.append(
                PlannedTaskDefinition(
                    name=name,
                    offset_start_minutes=offset,
                    duration_minutes=duration,
                )
            )

        if not result:
            logger.error(
                "Tras el filtrado, la respuesta de Gemini no tiene tareas utilizables. Datos: %s",
                tasks_data,
            )
            raise GeminiNotAvailable(
                "Gemini devolvió tareas vacías tras el filtrado."
            )

        logger.info(
            "Gemini propuso %d tareas para el procedimiento '%s'.",
            len(result),
            data.procedure_name,
        )
        return result

    except GeminiNotAvailable:
        raise
    except Exception as exc:
        logger.error("Error al utilizar Gemini para planificar: %s", exc)
        raise GeminiNotAvailable("Fallo al obtener plan desde Gemini.") from exc
