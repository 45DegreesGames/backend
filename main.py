import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.config import (
    ALLOWED_ORIGINS, VERSION, logger, TEMP_DIR, 
    configure_logging, initialize_temp_directory
)
from app.services.pdf_service import limpiar_archivos_temporales
from app.routers import health_router, pdf_router, conversion_router
from app.utils.pdflatex import is_pdflatex_available

# Configurar logging y directorio temporal
configure_logging()
initialize_temp_directory()

# Crear la aplicación FastAPI
app = FastAPI(
    title="API Pitorro",
    description="API para convertir texto a LaTeX y generar PDF",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manejador global de errores
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no manejado: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno del servidor: {str(exc)}"}
    )

# Incluir routers
app.include_router(health_router.router)
app.include_router(pdf_router.router)
app.include_router(conversion_router.router)

# Eventos de inicio y cierre
@app.on_event("startup")
async def startup_event():
    """Ejecuta tareas al iniciar la aplicación."""
    logger.info(f"Iniciando API Pitorro v{VERSION}")
    
    # Comprobar disponibilidad de pdflatex
    if is_pdflatex_available():
        logger.info("pdflatex está disponible en el sistema")
    else:
        logger.warning("pdflatex NO está disponible - operando en modo solo LaTeX")
    
    # Limpiar archivos temporales de ejecuciones anteriores
    limpiar_archivos_temporales()
    
    # Inicializar modelo de IA
    from app.services.ai_service import initialize_ai_model
    if await initialize_ai_model():
        logger.info("Modelo de IA inicializado correctamente")
    else:
        logger.warning("No se pudo inicializar el modelo de IA - la funcionalidad de conversión podría no estar disponible")
    
    logger.info("API lista para recibir solicitudes")

@app.on_event("shutdown")
async def shutdown_event():
    """Ejecuta tareas al cerrar la aplicación."""
    logger.info("Cerrando API y limpiando recursos")
    
    # Limpiar archivos temporales al cerrar
    try:
        limpiar_archivos_temporales()
    except Exception as e:
        logger.error(f"Error al limpiar archivos temporales: {str(e)}")

if __name__ == "__main__":
    import os
    # Obtener puerto del entorno o usar 8000 por defecto
    port = int(os.environ.get("PORT", 8000))
    
    # Iniciar el servidor con uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Deshabilitar en producción
        workers=1,
    ) 