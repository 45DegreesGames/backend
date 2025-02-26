from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional

from app.models.schemas import TextToLatexRequest, TextToLatexResponse
from app.services.ai_service import convert_text_to_latex, stream_latex_conversion
from app.config import logger, AI_PROVIDER

# Crear el router
router = APIRouter(
    prefix="/conversion",
    tags=["Conversión"],
    responses={404: {"description": "No encontrado"}},
)

@router.post("/texto-a-latex", response_model=TextToLatexResponse, summary="Convierte texto a código LaTeX")
async def texto_a_latex(request: TextToLatexRequest):
    """
    Convierte texto plano o con notación matemática a código LaTeX utilizando IA.
    
    - **text**: Texto a convertir
    - **math_mode**: Si contiene fórmulas matemáticas
    
    Retorna el código LaTeX generado.
    """
    try:
        logger.info(f"Solicitando conversión de texto a LaTeX (math_mode={request.math_mode})")
        latex_code = await convert_text_to_latex(request.text, request.math_mode)
        
        if latex_code is None:
            raise HTTPException(status_code=500, detail="No se pudo generar el código LaTeX")
        
        logger.info("Conversión de texto a LaTeX completada con éxito")
        return {"latex": latex_code}
    except Exception as e:
        error_msg = f"Error al convertir texto a LaTeX: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/texto-a-latex/stream", summary="Convierte texto a LaTeX en modo streaming")
async def texto_a_latex_stream(request: TextToLatexRequest):
    """
    Convierte texto a código LaTeX en modo streaming, devolviendo resultados incrementales.
    
    - **text**: Texto a convertir
    - **math_mode**: Si contiene fórmulas matemáticas
    
    Retorna un stream de eventos con el código LaTeX generado incrementalmente.
    """
    try:
        logger.info(f"Solicitando conversión streaming de texto a LaTeX (math_mode={request.math_mode})")
        
        return StreamingResponse(
            stream_latex_conversion(request.text, request.math_mode),
            media_type="application/json"
        )
    except Exception as e:
        error_msg = f"Error al iniciar conversión streaming: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/ai-status", summary="Verifica el estado del proveedor de IA")
async def ai_status():
    """
    Retorna información sobre el proveedor de IA configurado y su estado.
    """
    from app.services.ai_service import initialize_ai_model, ai_model
    
    # Intentar inicializar el modelo si no está inicializado
    if ai_model is None:
        initialization_successful = await initialize_ai_model()
    else:
        initialization_successful = True
    
    return {
        "ai_provider": AI_PROVIDER,
        "status": "available" if initialization_successful else "unavailable",
        "model_initialized": ai_model is not None
    } 