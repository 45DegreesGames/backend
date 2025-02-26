import os
import sys
import platform
import time
import psutil
from fastapi import APIRouter, Depends
from datetime import datetime

from app.config import VERSION, START_TIME, logger, ALLOWED_ORIGINS, FORCE_LATEX_ONLY_MODE
from app.utils.pdflatex import is_pdflatex_available

# Crear el router
router = APIRouter(
    tags=["Salud"],
    responses={404: {"description": "No encontrado"}},
)

@router.get("/", summary="Información básica de la API", include_in_schema=False)
async def root():
    """Punto de entrada principal que muestra información básica de la API."""
    return {
        "name": "API Pitorro",
        "description": "API para convertir texto a LaTeX y PDF",
        "version": VERSION,
        "documentation": "/docs"
    }

@router.get("/health", summary="Verifica el estado de salud de la API")
async def health():
    """
    Verifica el estado de salud de la API y retorna información básica.
    
    Útil para monitoreo y verificación de disponibilidad.
    """
    uptime = time.time() - START_TIME
    uptime_formatted = f"{int(uptime // 86400)}d {int((uptime % 86400) // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s"
    
    # Obtener información del sistema
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    return {
        "status": "ok",
        "version": VERSION,
        "uptime": uptime_formatted,
        "timestamp": datetime.now().isoformat(),
        "system_info": {
            "platform": platform.platform(),
            "python_version": sys.version,
            "process_id": os.getpid(),
            "memory_usage_mb": round(memory_info.rss / (1024 * 1024), 2),
        }
    }

@router.get("/config", summary="Información sobre la configuración actual")
async def get_config():
    """
    Retorna información sobre la configuración actual de la API.
    
    Incluye información como CORS, modo de operación, etc.
    """
    config_info = {
        "version": VERSION,
        "cors": {
            "allowed_origins": ALLOWED_ORIGINS,
        },
        "features": {
            "pdflatex_available": is_pdflatex_available(),
            "force_latex_only": FORCE_LATEX_ONLY_MODE,
        }
    }
    
    return config_info 