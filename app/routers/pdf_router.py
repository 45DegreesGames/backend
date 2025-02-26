import re
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.models.schemas import LatexRequest, PdfResponse, PdfLatexStatusResponse, PdfLatexTestResponse, FileInfoResponse
from app.services.pdf_service import generar_pdf_desde_latex, obtener_archivo, run_test_pdflatex, get_file_info
from app.utils.pdflatex import is_pdflatex_available, diagnosticar_pdflatex
from app.config import FORCE_LATEX_ONLY_MODE, logger

# Patrón UUID para validación
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

# Crear el router
router = APIRouter(
    prefix="/pdf",
    tags=["PDF"],
    responses={404: {"description": "No encontrado"}},
)

@router.post("/generar", response_model=PdfResponse, summary="Genera un PDF desde código LaTeX")
async def generar_pdf(request: LatexRequest, background_tasks: BackgroundTasks):
    """
    Genera un PDF a partir de código LaTeX proporcionado.
    
    - **latex**: Código LaTeX para convertir a PDF
    
    Retorna un ID único que puede usarse para descargar el PDF generado.
    """
    try:
        logger.info("Recibida solicitud para generar PDF")
        resultado = await generar_pdf_desde_latex(request.latex, background_tasks)
        logger.info(f"PDF generado con éxito, ID: {resultado['id']}")
        return resultado
    except Exception as e:
        logger.error(f"Error al generar PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {str(e)}")

@router.get("/descargar/{file_id}", summary="Descarga un archivo PDF o LaTeX")
async def descargar_pdf(file_id: str, background_tasks: BackgroundTasks):
    """
    Descarga un archivo PDF previamente generado.
    
    - **file_id**: ID del archivo a descargar
    
    Si pdflatex no está disponible, retorna el código LaTeX como archivo .tex.
    """
    # Validar el ID con expresión regular
    if not UUID_PATTERN.match(file_id):
        logger.warning(f"ID de archivo inválido: {file_id}")
        raise HTTPException(status_code=400, detail="ID de archivo inválido, debe ser un UUID")
    
    try:
        logger.info(f"Solicitud de descarga para archivo {file_id}")
        return await obtener_archivo(file_id, background_tasks)
    except HTTPException:
        # Re-lanzar excepciones HTTP para mantener el código de estado
        raise
    except Exception as e:
        logger.error(f"Error al descargar archivo {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al descargar archivo: {str(e)}")

@router.get("/pdflatex-status", response_model=PdfLatexStatusResponse, summary="Verifica el estado de pdflatex")
async def pdflatex_status():
    """
    Verifica si pdflatex está disponible en el sistema y retorna el modo de operación.
    
    Retorna:
    - **pdflatex_available**: Si pdflatex está disponible
    - **mode**: Modo actual (PDF o LaTeX only)
    """
    pdflatex_disponible = is_pdflatex_available()
    
    if FORCE_LATEX_ONLY_MODE:
        modo = "latex_only (forced)"
    else:
        modo = "pdf_generation" if pdflatex_disponible else "latex_only"
    
    logger.info(f"Consulta de estado de pdflatex: disponible={pdflatex_disponible}, modo={modo}")
    
    return {
        "pdflatex_available": pdflatex_disponible,
        "mode": modo
    }

@router.get("/test-pdflatex", response_model=PdfLatexTestResponse, summary="Prueba la generación de PDF")
async def test_pdflatex():
    """
    Realiza una prueba de generación de PDF para verificar que pdflatex está configurado correctamente.
    
    Crea un documento LaTeX mínimo y intenta generar un PDF, retornando los resultados detallados de la prueba.
    """
    logger.info("Iniciando prueba de pdflatex")
    resultados = run_test_pdflatex()
    logger.info(f"Prueba completada: {resultados.get('conclusión', 'sin conclusión')}")
    return resultados

@router.get("/diagnostico-pdflatex", summary="Proporciona diagnóstico detallado de pdflatex")
async def diagnostico_pdflatex():
    """
    Realiza un diagnóstico completo de la configuración de pdflatex en el sistema.
    
    Retorna información detallada sobre la instalación, versión y disponibilidad de pdflatex.
    """
    logger.info("Iniciando diagnóstico de pdflatex")
    resultados = diagnosticar_pdflatex()
    logger.info("Diagnóstico completado")
    return JSONResponse(content=resultados)

@router.get("/info/{file_id}", response_model=FileInfoResponse, summary="Obtiene información sobre un archivo")
async def obtener_info_archivo(file_id: str):
    """
    Obtiene información detallada sobre un archivo PDF o LaTeX generado.
    
    - **file_id**: ID del archivo
    
    Retorna detalles como tipo de archivo, ruta, tamaño y estado de compilación.
    """
    # Validar el ID con expresión regular
    if not UUID_PATTERN.match(file_id):
        logger.warning(f"ID de archivo inválido: {file_id}")
        raise HTTPException(status_code=400, detail="ID de archivo inválido, debe ser un UUID")
    
    try:
        logger.info(f"Solicitud de información para archivo {file_id}")
        info = get_file_info(file_id)
        return info
    except HTTPException:
        # Re-lanzar excepciones HTTP para mantener el código de estado
        raise
    except Exception as e:
        logger.error(f"Error al obtener información del archivo {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener información: {str(e)}") 