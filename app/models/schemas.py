from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union

# Modelos para PDF
class LatexRequest(BaseModel):
    """Modelo para solicitar la generación de un PDF a partir de código LaTeX."""
    latex: str = Field(..., description="Código LaTeX para convertir a PDF")

class PdfResponse(BaseModel):
    """Modelo para la respuesta de la generación de PDF."""
    id: str = Field(..., description="ID único del archivo generado")

class PdfLatexStatusResponse(BaseModel):
    """Modelo para la respuesta del estado de pdflatex."""
    pdflatex_available: bool = Field(..., description="Indica si pdflatex está disponible")
    mode: str = Field(..., description="Modo de operación (pdf_generation o latex_only)")

class PdfLatexTestStep(BaseModel):
    """Modelo para un paso en la prueba de pdflatex."""
    paso: int = Field(..., description="Número del paso")
    descripción: str = Field(..., description="Descripción del paso")
    estado: str = Field(..., description="Estado del paso (iniciando, completado, error, timeout)")

class PdfLatexTestResponse(BaseModel):
    """Modelo para la respuesta de la prueba de pdflatex."""
    pdflatex_disponible: bool = Field(..., description="Indica si pdflatex está disponible")
    forzar_modo_latex: bool = Field(..., description="Indica si se está forzando el modo solo LaTeX")
    forzar_generacion_pdf: bool = Field(..., description="Indica si se está forzando la generación de PDF")
    modo_simple: bool = Field(..., description="Indica si se está usando el modo simple de pdflatex")
    modo_actual: str = Field(..., description="Modo actual de operación")
    pasos: List[PdfLatexTestStep] = Field(default_factory=list, description="Pasos realizados durante la prueba")
    conclusión: Optional[str] = Field(None, description="Conclusión de la prueba")
    error_general: Optional[str] = Field(None, description="Error general si ocurrió")
    
    # Campos opcionales que pueden estar presentes según el resultado
    test_dir: Optional[str] = Field(None, description="Directorio de prueba")
    archivo_tex: Optional[str] = Field(None, description="Ruta al archivo .tex generado")
    comando: Optional[str] = Field(None, description="Comando ejecutado")
    exit_code: Optional[int] = Field(None, description="Código de salida del comando")
    stdout: Optional[str] = Field(None, description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")
    pdf_existe: Optional[bool] = Field(None, description="Indica si se generó el PDF")
    pdf_path: Optional[str] = Field(None, description="Ruta al PDF generado")
    pdf_size: Optional[int] = Field(None, description="Tamaño del PDF generado")
    error: Optional[str] = Field(None, description="Mensaje de error si falló")
    log_ultimas_lineas: Optional[str] = Field(None, description="Últimas líneas del archivo de log")
    archivos_generados: Optional[List[str]] = Field(None, description="Lista de archivos generados")

class FileItem(BaseModel):
    """Modelo para un archivo en el directorio de compilación."""
    nombre: str = Field(..., description="Nombre del archivo")
    tamaño: int = Field(..., description="Tamaño del archivo en bytes")
    modificado: float = Field(..., description="Timestamp de última modificación")

class FileInfoResponse(BaseModel):
    """Modelo para la información detallada de un archivo."""
    latex: Optional[str] = Field(None, description="Código LaTeX (primeros 500 caracteres)")
    is_latex_only: Optional[bool] = Field(None, description="Indica si es solo LaTeX o PDF")
    path: Optional[str] = Field(None, description="Ruta al archivo PDF si existe")
    compile_dir: Optional[str] = Field(None, description="Directorio de compilación")
    archivos: Optional[List[FileItem]] = Field(None, description="Archivos en el directorio de compilación")
    log_ultimas_lineas: Optional[str] = Field(None, description="Últimas líneas del log de LaTeX")
    log_error: Optional[str] = Field(None, description="Error al leer el log")
    error_listar_directorio: Optional[str] = Field(None, description="Error al listar directorio")

# Modelos para conversión
class TextToLatexRequest(BaseModel):
    """Modelo para solicitar la conversión de texto a LaTeX."""
    text: str = Field(..., description="Texto a convertir a LaTeX")
    math_mode: bool = Field(False, description="Indica si el texto contiene fórmulas matemáticas")

class TextToLatexResponse(BaseModel):
    """Modelo para la respuesta de la conversión de texto a LaTeX."""
    latex: str = Field(..., description="Código LaTeX generado") 