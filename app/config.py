from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional, List, Dict

from pydantic_settings import BaseSettings, SettingsConfigDict
import re

class Settings(BaseSettings):
    """
    Configuración global de la aplicación.

    Se cargan variables desde el entorno y desde el archivo .env.
    """
    app_env: str = "development"

    # Clave para Gemini (obligatoria si se quiere usar IA)
    gemini_api_key: Optional[str] = None

    # Nombre del modelo de Gemini a utilizar.
    # Por defecto uso un modelo moderno; si tú ya usas "gemini-2.5-flash"
    # simplemente declara en tu .env:
    #   GEMINI_MODEL="gemini-2.5-flash"
    gemini_model: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


_settings: Optional[Settings] = None
_logger: Optional[logging.Logger] = None


def get_settings() -> Settings:
    """
    Devuelve una única instancia de Settings (patrón singleton sencillo).
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def configure_logging() -> logging.Logger:
    """
    Configura el sistema de logging de la aplicación.

    - Registra en consola (stdout).
    - Registra en un archivo rotativo en logs/app.log.
    """
    global _logger
    if _logger is not None:
        return _logger

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("hospital_multiagent")
    logger.setLevel(logging.INFO)

    # Evitamos añadir handlers duplicados si se llama más de una vez.
    if not logger.handlers:
        log_file = log_dir / "app.log"

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,   # ~1 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    _logger = logger
    return logger

def get_log_file_path() -> Path:
    """
    Devuelve la ruta al archivo principal de logs (logs/app.log).
    """
    log_dir = Path("logs")
    return log_dir / "app.log"


def read_log_entries(limit: int = 500) -> List[Dict[str, str]]:
    """
    Lee el archivo de logs y devuelve una lista de entradas parseadas.

    Cada entrada tiene:
        - timestamp: str
        - level: str
        - message: str
    """
    log_file = get_log_file_path()
    entries: List[Dict[str, str]] = []

    if not log_file.exists():
        return entries

    # Leemos sólo las últimas `limit` líneas para no saturar la UI
    with log_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()[-limit:]

    pattern = re.compile(
        r"\[(?P<timestamp>[^\]]+)\]\s+\[(?P<level>[^\]]+)\]\s+(?P<logger>[^-]+)-\s+(?P<message>.*)"
    )

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = pattern.match(line)
        if not match:
            # Si no coincide el formato por alguna razón, mostramos la línea cruda.
            entries.append(
                {
                    "timestamp": "",
                    "level": "INFO",
                    "message": line,
                }
            )
            continue

        entries.append(
            {
                "timestamp": match.group("timestamp"),
                "level": match.group("level"),
                "message": match.group("message"),
            }
        )

    return entries
