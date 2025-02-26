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

# Endpoint de compatibilidad con frontend antiguo
@app.post("/convertir")
async def convertir_compat(request: Request):
    """
    Endpoint de compatibilidad con frontend antiguo.
    Redirige las solicitudes a /conversion/texto-a-latex
    """
    from app.models.schemas import TextToLatexRequest
    from app.services.ai_service import convert_text_to_latex
    
    # Obtener datos de la solicitud
    json_data = await request.json()
    text = json_data.get("text", "")
    math_mode = json_data.get("math_mode", False)
    
    logger.info(f"Solicitud de compatibilidad a /convertir, redirigiendo a /conversion/texto-a-latex")
    
    try:
        # Usar el mismo servicio que el endpoint oficial
        latex_code = await convert_text_to_latex(text, math_mode)
        
        if latex_code is None:
            return JSONResponse(
                status_code=500,
                content={"error": "No se pudo generar el código LaTeX"}
            )
        
        # Devolver en el formato que espera el frontend
        return {"latex": latex_code}
    except Exception as e:
        error_msg = f"Error al convertir texto a LaTeX: {str(e)}"
        logger.error(error_msg)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )

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