from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, validator, Field
from fastapi import Path as FastAPIPath
import google.generativeai as genai
from google.generativeai import types
import subprocess
import os
import uuid
import shutil
from pathlib import Path
import tempfile
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("Iniciando aplicación")

# Clave API de Gemini desde variable de entorno
API_KEY = os.getenv("API_KEY", "AIzaSyD_W7_6maqHj09Y82ShmiEozomV-EAE1FA")  # Valor por defecto como fallback

# Configuración de Google Gemini
genai.configure(api_key=API_KEY)

# Crear directorio para almacenar archivos temporales
temp_dir = Path("./temp")
temp_dir.mkdir(exist_ok=True)

# Definir la aplicación FastAPI
app = FastAPI(title="Conversor de Texto a LaTeX")

# Configurar CORS para permitir peticiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://graditox.netlify.app"],  # Dominio específico del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de datos
class TextoRequest(BaseModel):
    texto: str
    
    @validator('texto')
    def texto_no_vacio(cls, v):
        if not v.strip():
            raise ValueError('El texto no puede estar vacío')
        return v

class LatexRequest(BaseModel):
    latex: str = Field(..., max_length=50000)  # Establecer un límite máximo

class LatexResponse(BaseModel):
    latex: str

class PDFResponse(BaseModel):
    id: str

# Diccionario para almacenar los PDF generados
pdf_files = {}

# Instrucción del sistema para Gemini
SYSTEM_INSTRUCTION = """
Eres un conversor avanzado de texto a LaTeX.
Tu única función es transformar cualquier texto que se te proporcione en un documento LaTeX perfectamente estructurado. Debes asegurarte de que el resultado:
- SIEMPRE sea código LaTeX puro, sin explicaciones, sin texto adicional, sin markdown ni comentarios fuera del código.
- Organice el contenido en secciones, subsecciones y párrafos según corresponda.
- Mantenga el formato correcto para listas, ecuaciones, tablas y cualquier otro elemento presente en el texto de entrada.
- La estructura del documento LaTeX tiene que ser organizada y estética.
"""

# Rutas de la API
@app.get("/")
async def read_root():
    return {"mensaje": "API del Conversor de Texto a LaTeX"}

@app.get("/health")
async def health_check():
    """Endpoint para verificar que el servidor está funcionando correctamente"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "port": os.getenv("PORT", "no definido"),
        "environment": os.getenv("ENVIRONMENT", "desarrollo")
    }

@app.post("/convertir", response_model=LatexResponse)
async def convertir_texto(request: TextoRequest):
    try:
        # Crear un cliente de Gemini
        client = genai.Client(api_key=API_KEY)
        
        # Definir el modelo a utilizar
        model_name = "gemini-2.0-flash-thinking-exp-01-21"
        
        # Preparar el contenido de la solicitud
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=request.texto)
                ]
            )
        ]
        
        # Configurar la generación de contenido
        generate_content_config = types.GenerateContentConfig(
            temperature=0.1,  # Baja temperatura para respuestas más deterministas
            top_p=0.95,
            top_k=64,
            max_output_tokens=65536,
            response_mime_type="text/plain",
            system_instruction=[
                types.Part.from_text(text=SYSTEM_INSTRUCTION)
            ]
        )
        
        # Generar el contenido
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=generate_content_config
        )
        
        # Extraer el código LaTeX generado
        latex_code = response.text
        
        return {"latex": latex_code}
    except Exception as e:
        logger.error(f"Error al convertir texto: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en la conversión: {str(e)}")

@app.post("/generar-pdf", response_model=PDFResponse)
async def generar_pdf(request: LatexRequest, background_tasks: BackgroundTasks):
    try:
        # Generar un ID único para el archivo
        file_id = str(uuid.uuid4())
        
        # Crear un directorio temporal para la compilación
        compile_dir = temp_dir / file_id
        compile_dir.mkdir(exist_ok=True)
        
        # Guardar el código LaTeX en un archivo .tex
        tex_file_path = compile_dir / "documento.tex"
        with open(tex_file_path, "w", encoding="utf-8") as f:
            f.write(request.latex)
        
        # Intentar compilar el archivo LaTeX
        try:
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(compile_dir), str(tex_file_path)],
                check=True,
                capture_output=True
            )
            
            # Verificar si se generó el PDF
            pdf_path = compile_dir / "documento.pdf"
            if not pdf_path.exists():
                raise HTTPException(status_code=500, detail="No se pudo generar el PDF")
                
            # Guardar la ruta del PDF generado
            pdf_files[file_id] = {
                "path": str(pdf_path),
                "compile_dir": str(compile_dir)
            }
            
            # Programar la eliminación del archivo después de 10 minutos
            background_tasks.add_task(eliminar_archivo_temporal, file_id, 600)
            
            return {"id": file_id}
        except subprocess.CalledProcessError as e:
            logger.error(f"Error al compilar LaTeX: {e.stderr.decode('utf-8')}")
            raise HTTPException(status_code=500, detail="Error al compilar el documento LaTeX")
    except Exception as e:
        logger.error(f"Error al generar PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {str(e)}")

@app.get("/descargar/{file_id}")
async def descargar_pdf(file_id: str = FastAPIPath(..., regex=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')):
    """
    Permite descargar un archivo PDF generado previamente.
    El parámetro file_id debe ser un UUID válido en formato 8-4-4-4-12.
    """
    # Verificar si el archivo existe
    if file_id not in pdf_files:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    pdf_path = pdf_files[file_id]["path"]
    
    # Verificar si el archivo existe en el sistema de archivos
    if not os.path.isfile(pdf_path):
        raise HTTPException(status_code=404, detail="El archivo PDF ya no existe")
    
    # Devolver el archivo PDF
    return FileResponse(
        path=pdf_path, 
        filename="documento.pdf", 
        media_type="application/pdf"
    )

# Función para eliminar archivos temporales
async def eliminar_archivo_temporal(file_id: str, delay_seconds: int = 600):
    """Elimina el archivo temporal después de un tiempo específico."""
    import asyncio
    
    await asyncio.sleep(delay_seconds)
    
    if file_id in pdf_files:
        try:
            # Eliminar el directorio de compilación completo
            compile_dir = pdf_files[file_id]["compile_dir"]
            if os.path.isdir(compile_dir):
                shutil.rmtree(compile_dir)
            
            # Eliminar la entrada del diccionario
            del pdf_files[file_id]
            logger.info(f"Archivo temporal {file_id} eliminado correctamente")
        except Exception as e:
            logger.error(f"Error al eliminar archivo temporal {file_id}: {str(e)}")

# Limpieza al iniciar la aplicación
@app.on_event("startup")
async def startup_event():
    logger.info("Limpiando directorio temporal al iniciar...")
    try:
        if temp_dir.exists():
            for item in temp_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        logger.info("Limpieza completada")
    except Exception as e:
        logger.error(f"Error durante la limpieza inicial: {str(e)}")

async def content_generator(request_text, api_key):
    """Generador de contenido para streaming de respuestas."""
    # Crear un cliente de Gemini
    client = genai.Client(api_key=api_key)
    
    # Definir el modelo a utilizar
    model_name = "gemini-2.0-flash-thinking-exp-01-21"
    
    # Preparar el contenido de la solicitud
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=request_text)
            ]
        )
    ]
    
    # Configurar la generación de contenido
    generate_content_config = types.GenerateContentConfig(
        temperature=0.1,
        top_p=0.95,
        top_k=64,
        max_output_tokens=65536,
        response_mime_type="text/plain",
        system_instruction=[
            types.Part.from_text(text=SYSTEM_INSTRUCTION)
        ]
    )
    
    # Generar el contenido en streaming
    stream = client.models.generate_content_stream(
        model=model_name,
        contents=contents,
        config=generate_content_config
    )
    
    # Devolver chunks de respuesta
    for chunk in stream:
        if chunk.text:
            yield chunk.text

@app.post("/convertir-stream")
async def convertir_texto_stream(request: TextoRequest):
    """Endpoint para convertir texto a LaTeX con streaming de respuesta."""
    try:
        return StreamingResponse(
            content_generator(request.texto, API_KEY),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Error al convertir texto (streaming): {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en la conversión: {str(e)}")

# Iniciar el servidor con Uvicorn si este archivo se ejecuta directamente
if __name__ == "__main__":
    import uvicorn
    # Usar el puerto proporcionado por la plataforma de despliegue o 10000 si es local
    # Render espera 10000 como puerto predeterminado
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Iniciando servidor en el puerto {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port) 