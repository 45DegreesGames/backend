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
        # Usar GenerativeModel directamente (versión 0.4.0)
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")
        
        # Preparar la solicitud con las instrucciones del sistema
        prompt = f"{SYSTEM_INSTRUCTION}\n\n{request.texto}"
        
        # Generar el contenido
        response = model.generate_content(prompt)
        
        # Extraer el código LaTeX generado
        latex_code = response.text
        
        return {"latex": latex_code}
    except Exception as e:
        logger.error(f"Error al convertir texto: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en la conversión: {str(e)}")

# Verificar disponibilidad de pdflatex al inicio - versión mejorada
def is_pdflatex_available():
    try:
        # Intentar encontrar pdflatex en diferentes ubicaciones comunes
        possible_paths = [
            "pdflatex",  # En PATH
            "/usr/bin/pdflatex",
            "/usr/local/bin/pdflatex",
            "/usr/texbin/pdflatex"
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, "--version"], 
                                      capture_output=True, 
                                      text=True, 
                                      check=False)
                if result.returncode == 0:
                    logger.info(f"pdflatex encontrado en: {path}")
                    return True
            except FileNotFoundError:
                continue
                
        logger.warning("pdflatex no encontrado en ninguna ubicación común")
        return False
    except Exception as e:
        logger.error(f"Error al verificar pdflatex: {str(e)}")
        return False

# Verificar al inicio de la aplicación
PDFLATEX_AVAILABLE = is_pdflatex_available()
logger.info(f"pdflatex disponible: {PDFLATEX_AVAILABLE}")

# Para forzar la generación de PDF independientemente de la detección
FORCE_PDF_GENERATION = True  # Cambiar a False si quieres que dependa de la detección automática

# Configuración para usar un modo simplificado de pdflatex (menos requisitos pero menos funcionalidades)
USE_SIMPLE_PDFLATEX = True

# Función para normalizar el código LaTeX
def normalizar_latex(codigo_latex):
    """
    Asegura que el código LaTeX tenga la estructura mínima necesaria.
    Si el código no tiene los elementos básicos, los añade.
    Esto ayuda a garantizar que el documento se compile correctamente.
    """
    codigo_trim = codigo_latex.strip()
    
    # Verificar si ya tiene la estructura básica de documento
    tiene_documentclass = "\\documentclass" in codigo_trim
    tiene_begin_document = "\\begin{document}" in codigo_trim
    tiene_end_document = "\\end{document}" in codigo_trim
    
    if tiene_documentclass and tiene_begin_document and tiene_end_document:
        # El documento ya parece tener la estructura básica
        return codigo_trim
    
    # Si falta la estructura básica, creamos un documento mínimo
    if not tiene_documentclass:
        # Extraer lo que parece ser el contenido principal
        if tiene_begin_document and tiene_end_document:
            # Extraer el contenido entre \begin{document} y \end{document}
            inicio = codigo_trim.find("\\begin{document}")
            fin = codigo_trim.find("\\end{document}")
            if inicio != -1 and fin != -1:
                contenido = codigo_trim[inicio + len("\\begin{document}"):fin].strip()
            else:
                contenido = codigo_trim
        
        # Crear un documento mínimo básico
        documento_minimo = """\\documentclass[12pt]{article}
\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage{amsmath}
\\usepackage{amssymb}
\\usepackage{graphicx}

\\begin{document}

%s

\\end{document}
""" % contenido
        
        return documento_minimo
    
    # Si tiene \documentclass pero faltan begin/end document
    elif tiene_documentclass and not (tiene_begin_document and tiene_end_document):
        # Buscar dónde insertar \begin{document}
        lineas = codigo_trim.split('\n')
        preambulo = []
        contenido = []
        
        en_preambulo = True
        for linea in lineas:
            if en_preambulo and linea.strip().startswith('\\documentclass'):
                preambulo.append(linea)
                en_preambulo = True
            elif en_preambulo and (linea.strip().startswith('%') or linea.strip().startswith('\\use') or linea.strip() == ''):
                preambulo.append(linea)
            else:
                en_preambulo = False
                contenido.append(linea)
        
        # Construir el documento nuevo
        documento_nuevo = '\n'.join(preambulo)
        documento_nuevo += '\n\\begin{document}\n\n'
        documento_nuevo += '\n'.join(contenido)
        
        if not tiene_end_document:
            documento_nuevo += '\n\\end{document}\n'
        
        return documento_nuevo
    
    # En cualquier otro caso, devolver el original
    return codigo_trim

@app.post("/generar-pdf", response_model=PDFResponse)
async def generar_pdf(request: LatexRequest, background_tasks: BackgroundTasks):
    try:
        # Normalizar el código LaTeX para asegurar la estructura correcta
        latex_normalizado = normalizar_latex(request.latex)
        
        # Verificar si pdflatex está disponible o si forzamos la generación
        if not (PDFLATEX_AVAILABLE or FORCE_PDF_GENERATION):
            # Solo en caso de que realmente no queramos generar PDFs
            file_id = str(uuid.uuid4())
            pdf_files[file_id] = {
                "latex": latex_normalizado,
                "is_latex_only": True
            }
            background_tasks.add_task(eliminar_archivo_temporal, file_id, 600)
            return {"id": file_id}
        
        # Intentar generar el PDF en todos los casos
        file_id = str(uuid.uuid4())
        
        # Crear un directorio temporal para la compilación
        compile_dir = temp_dir / file_id
        compile_dir.mkdir(exist_ok=True)
        
        # Guardar el código LaTeX en un archivo .tex
        tex_file_path = compile_dir / "documento.tex"
        with open(tex_file_path, "w", encoding="utf-8") as f:
            f.write(latex_normalizado)
        
        logger.info(f"Archivo LaTeX guardado en: {tex_file_path}")
        
        # Determinar el comando de pdflatex a utilizar
        if USE_SIMPLE_PDFLATEX:
            # Modo simplificado - una sola pasada, menos opciones
            pdflatex_cmd = [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory", str(compile_dir),
                "-no-shell-escape",  # Más seguro
                str(tex_file_path)
            ]
        else:
            # Modo normal
            pdflatex_cmd = [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory", str(compile_dir),
                str(tex_file_path)
            ]
            
        logger.info(f"Ejecutando: {' '.join(pdflatex_cmd)}")
        
        try:
            # Primera pasada de pdflatex
            process = subprocess.run(
                pdflatex_cmd,
                check=True,
                capture_output=True
            )
            
            # Registrar stdout y stderr para diagnóstico
            logger.info(f"pdflatex stdout: {process.stdout.decode('utf-8', errors='replace')[:500]}...")
            if process.stderr:
                logger.warning(f"pdflatex stderr: {process.stderr.decode('utf-8', errors='replace')}")
            
            # Si no usamos el modo simple, ejecutamos una segunda pasada para referencias
            if not USE_SIMPLE_PDFLATEX:
                logger.info("Ejecutando segunda pasada de pdflatex")
                subprocess.run(
                    pdflatex_cmd,
                    check=True,
                    capture_output=True
                )
            
            # Verificar si se generó el PDF
            pdf_path = compile_dir / "documento.pdf"
            logger.info(f"Buscando PDF en: {pdf_path}")
            
            if pdf_path.exists():
                logger.info(f"PDF generado correctamente: {pdf_path}")
                pdf_files[file_id] = {
                    "path": str(pdf_path),
                    "compile_dir": str(compile_dir),
                    "is_latex_only": False
                }
            else:
                logger.warning(f"PDF no encontrado en la ruta esperada: {pdf_path}")
                # Buscar si hay algún PDF en el directorio
                pdf_files_in_dir = list(compile_dir.glob("*.pdf"))
                if pdf_files_in_dir:
                    pdf_path = pdf_files_in_dir[0]
                    logger.info(f"Se encontró un PDF alternativo: {pdf_path}")
                    pdf_files[file_id] = {
                        "path": str(pdf_path),
                        "compile_dir": str(compile_dir),
                        "is_latex_only": False
                    }
                else:
                    # Si no hay PDF, caer en modo LaTeX
                    logger.warning("No se pudo generar el PDF, devolviendo modo LaTeX")
                    pdf_files[file_id] = {
                        "latex": latex_normalizado,
                        "is_latex_only": True
                    }
            
            # Programar la eliminación del archivo después de 10 minutos
            background_tasks.add_task(eliminar_archivo_temporal, file_id, 600)
            
            return {"id": file_id}
        except subprocess.CalledProcessError as e:
            logger.error(f"Error al compilar LaTeX: {e.stderr.decode('utf-8', errors='replace')}")
            # En caso de error, también devolvemos el código LaTeX
            pdf_files[file_id] = {
                "latex": latex_normalizado,
                "is_latex_only": True
            }
            background_tasks.add_task(eliminar_archivo_temporal, file_id, 600)
            return {"id": file_id}
    except Exception as e:
        logger.error(f"Error al generar PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {str(e)}")

@app.get("/descargar/{file_id}")
async def descargar_pdf(file_id: str = FastAPIPath(..., regex=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')):
    """
    Permite descargar un archivo PDF generado previamente.
    Si pdflatex no está disponible, devuelve el código LaTeX como archivo .tex.
    El parámetro file_id debe ser un UUID válido en formato 8-4-4-4-12.
    """
    # Verificar si el archivo existe
    if file_id not in pdf_files:
        logger.warning(f"Archivo con ID {file_id} no encontrado")
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    info = pdf_files[file_id]
    logger.info(f"Información del archivo {file_id}: {info}")
    
    # Verificar si hay un PDF disponible
    if not info.get("is_latex_only", False) and "path" in info:
        pdf_path = info["path"]
        logger.info(f"Intentando devolver PDF: {pdf_path}")
        
        # Verificar si el archivo existe en el sistema de archivos
        if os.path.isfile(pdf_path):
            logger.info(f"Devolviendo PDF: {pdf_path}")
            return FileResponse(
                path=pdf_path, 
                filename="documento.pdf", 
                media_type="application/pdf"
            )
        else:
            logger.warning(f"El archivo PDF no existe en el sistema: {pdf_path}")
    
    # Si llegamos aquí, no hay PDF o no se encontró el archivo
    # Manejar el caso de solo código LaTeX o fallback a LaTeX
    if "latex" in info:
        logger.info(f"Devolviendo archivo LaTeX para {file_id}")
        latex_content = info["latex"]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tex", mode="w", encoding="utf-8") as f:
            f.write(latex_content)
            temp_file_path = f.name
        
        # Devolver el archivo .tex
        return FileResponse(
            path=temp_file_path,
            filename="documento.tex",
            media_type="application/x-tex",
            background=BackgroundTasks().add_task(os.unlink, temp_file_path)  # Eliminar después de enviar
        )
    
    # Si llegamos aquí, hay algún problema con los datos
    logger.error(f"Datos inconsistentes para {file_id}: {info}")
    raise HTTPException(status_code=500, detail="Error interno al procesar el archivo")

# Función para eliminar archivos temporales
async def eliminar_archivo_temporal(file_id: str, delay_seconds: int = 600):
    """Elimina el archivo temporal después de un tiempo específico."""
    import asyncio
    
    await asyncio.sleep(delay_seconds)
    
    if file_id in pdf_files:
        try:
            info = pdf_files[file_id]
            
            # Si es un archivo PDF, eliminar el directorio de compilación
            if not info.get("is_latex_only", False):
                compile_dir = info["compile_dir"]
                if os.path.isdir(compile_dir):
                    shutil.rmtree(compile_dir)
            
            # Eliminar la entrada del diccionario en cualquier caso
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
    # Configurar la API
    genai.configure(api_key=api_key)
    
    # Crear modelo generativo
    model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")
    
    # Preparar el prompt completo
    prompt = f"{SYSTEM_INSTRUCTION}\n\n{request_text}"
    
    # Generar respuesta en streaming
    stream = model.generate_content(prompt, stream=True)
    
    # Devolver chunks de respuesta
    for chunk in stream:
        if hasattr(chunk, 'text'):
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

@app.get("/pdflatex-status")
async def pdflatex_status():
    """Endpoint para verificar si pdflatex está disponible en el sistema"""
    return {
        "pdflatex_available": PDFLATEX_AVAILABLE,
        "mode": "PDF generation" if PDFLATEX_AVAILABLE else "LaTeX only (no PDF)"
    }

# Función para verificar y diagnosticar el entorno de pdflatex
def diagnosticar_pdflatex():
    try:
        logger.info("Iniciando diagnóstico de pdflatex")
        
        # Comprobar variables de entorno
        path_env = os.environ.get("PATH", "")
        logger.info(f"Variable PATH: {path_env}")
        
        # Comprobar si texlive está instalado
        texlive_check = subprocess.run(["which", "texlive"], capture_output=True, text=True, check=False)
        logger.info(f"TexLive instalado: {texlive_check.returncode == 0}")
        if texlive_check.stdout:
            logger.info(f"Ruta de TexLive: {texlive_check.stdout.strip()}")
        
        # Comprobar si pdftex o pdflatex están disponibles
        for cmd in ["pdftex", "pdflatex", "latex"]:
            which_check = subprocess.run(["which", cmd], capture_output=True, text=True, check=False)
            logger.info(f"{cmd} encontrado: {which_check.returncode == 0}")
            if which_check.stdout:
                logger.info(f"Ruta de {cmd}: {which_check.stdout.strip()}")
                # Verificar si es ejecutable
                try:
                    version_check = subprocess.run([which_check.stdout.strip(), "--version"], 
                                                capture_output=True, text=True, check=False)
                    logger.info(f"{cmd} es ejecutable: {version_check.returncode == 0}")
                    if version_check.stdout:
                        logger.info(f"Versión: {version_check.stdout.split('\\n')[0]}")
                except Exception as e:
                    logger.error(f"Error al ejecutar {cmd}: {str(e)}")
        
        # Intentar instalar pdflatex si no está disponible
        if not PDFLATEX_AVAILABLE and FORCE_PDF_GENERATION:
            logger.info("Intentando instalar TexLive (minimal)...")
            try:
                # Esto podría fallar en algunos entornos restringidos como Render
                subprocess.run(["apt-get", "update"], check=False)
                subprocess.run(["apt-get", "install", "-y", "texlive-latex-base"], check=False)
                
                # Verificar de nuevo
                after_install = is_pdflatex_available()
                logger.info(f"pdflatex disponible después de intento de instalación: {after_install}")
            except Exception as e:
                logger.error(f"Error al intentar instalar TexLive: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error durante el diagnóstico de pdflatex: {str(e)}")

# Ejecutar diagnóstico al iniciar
@app.on_event("startup")
async def startup_diagnostics():
    # Ejecutar en segundo plano para no bloquear el inicio
    import threading
    threading.Thread(target=diagnosticar_pdflatex).start()

@app.get("/diagnostico-pdflatex")
async def diagnostico_endpoint():
    """Endpoint para verificar y diagnosticar la instalación de pdflatex"""
    # Diccionario para almacenar resultados
    resultados = {}
    
    # Verificar pdflatex
    resultados["pdflatex_disponible"] = PDFLATEX_AVAILABLE
    resultados["forzar_generacion_pdf"] = FORCE_PDF_GENERATION
    
    # Comprobar rutas comunes
    rutas_comunes = [
        "pdflatex",
        "/usr/bin/pdflatex",
        "/usr/local/bin/pdflatex",
        "/usr/texbin/pdflatex"
    ]
    
    resultados["rutas_verificadas"] = []
    for ruta in rutas_comunes:
        try:
            proceso = subprocess.run([ruta, "--version"], 
                                  capture_output=True, 
                                  text=True, 
                                  check=False)
            resultados["rutas_verificadas"].append({
                "ruta": ruta,
                "existe": proceso.returncode == 0,
                "mensaje": proceso.stdout.split('\n')[0] if proceso.returncode == 0 else proceso.stderr
            })
        except FileNotFoundError:
            resultados["rutas_verificadas"].append({
                "ruta": ruta,
                "existe": False,
                "mensaje": "Archivo no encontrado"
            })
        except Exception as e:
            resultados["rutas_verificadas"].append({
                "ruta": ruta,
                "existe": False,
                "mensaje": str(e)
            })
    
    # Verificar variable PATH
    resultados["PATH"] = os.environ.get("PATH", "")
    
    # Verificar espacio en disco
    try:
        import shutil
        total, usado, libre = shutil.disk_usage("/")
        resultados["espacio_disco"] = {
            "total_gb": round(total / (1024**3), 2),
            "usado_gb": round(usado / (1024**3), 2),
            "libre_gb": round(libre / (1024**3), 2)
        }
    except Exception as e:
        resultados["espacio_disco"] = {"error": str(e)}
    
    return resultados

@app.get("/archivos/{file_id}")
async def ver_archivo_info(file_id: str = FastAPIPath(..., regex=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')):
    """
    Devuelve información sobre un archivo generado.
    Útil para depuración.
    """
    # Verificar si el archivo existe
    if file_id not in pdf_files:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    info = pdf_files[file_id].copy()
    
    # Si hay código LaTeX, mostrar solo los primeros 500 caracteres
    if "latex" in info:
        info["latex"] = info["latex"][:500] + "..." if len(info["latex"]) > 500 else info["latex"]
    
    # Si hay un directorio de compilación, listar su contenido
    if "compile_dir" in info:
        try:
            contenido_dir = []
            compile_dir = Path(info["compile_dir"])
            if compile_dir.exists():
                for item in compile_dir.iterdir():
                    if item.is_file():
                        # Mostrar también el tamaño del archivo
                        contenido_dir.append({
                            "nombre": item.name,
                            "tamaño": item.stat().st_size,
                            "modificado": item.stat().st_mtime
                        })
                info["archivos"] = contenido_dir
                
                # Ver si hay un log de LaTeX
                log_path = compile_dir / "documento.log"
                if log_path.exists():
                    try:
                        # Mostrar las últimas 20 líneas del log
                        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                            lineas = f.readlines()
                            info["log_ultimas_lineas"] = "".join(lineas[-20:])
                    except Exception as e:
                        info["log_error"] = str(e)
        except Exception as e:
            info["error_listar_directorio"] = str(e)
    
    return info

# Iniciar el servidor con Uvicorn si este archivo se ejecuta directamente
if __name__ == "__main__":
    import uvicorn
    # Usar el puerto proporcionado por la plataforma de despliegue o 10000 si es local
    # Render espera 10000 como puerto predeterminado
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Iniciando servidor en el puerto {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port) 