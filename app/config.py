import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración general
VERSION = "1.0.0"
START_TIME = time.time()

# Configuración de logging
def configure_logging():
    """Configura el sistema de logging."""
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Instancia de logger principal
logger = logging.getLogger("pitorro")
logger.setLevel(logging.INFO)

# Clave API de Gemini desde variable de entorno
API_KEY = os.getenv("API_KEY", "AIzaSyD_W7_6maqHj09Y82ShmiEozomV-EAE1FA")  # Valor por defecto como fallback

# Configuración de IA
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")  # gemini, openai, etc.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")  # gemini-pro, gemini-1.5-pro, etc.
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "30"))

# Directorio para almacenar archivos temporales
def initialize_temp_directory():
    """Inicializa el directorio temporal."""
    global TEMP_DIR
    TEMP_DIR = Path("./temp")
    TEMP_DIR.mkdir(exist_ok=True)
    logger.info(f"Directorio temporal inicializado en {TEMP_DIR}")

TEMP_DIR = Path("./temp")

# Configuración CORS 
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://graditox.netlify.app").split(",")
if "*" in ALLOWED_ORIGINS:
    logger.warning("CORS configurado para permitir cualquier origen (*)")

# Instrucción del sistema para Gemini
SYSTEM_INSTRUCTION = """
Eres un conversor avanzado de texto a LaTeX.
Tu única función es transformar cualquier texto que se te proporcione en un documento LaTeX perfectamente estructurado. Debes asegurarte de que el resultado:
- SIEMPRE sea código LaTeX puro, sin explicaciones, sin texto adicional, sin markdown ni comentarios fuera del código.
- Organice el contenido en secciones, subsecciones y párrafos según corresponda.
- Mantenga el formato correcto para listas, ecuaciones, tablas y cualquier otro elemento presente en el texto de entrada.
- La estructura del documento LaTeX tiene que ser organizada y estética.
"""

# Configuración de PDFLatex 
PDFLATEX_PATHS = [
    "pdflatex",  # En PATH
    "/usr/bin/pdflatex",
    "/usr/local/bin/pdflatex",
    "/usr/texbin/pdflatex",
    "/bin/pdflatex",
    "/opt/homebrew/bin/pdflatex",  # Para macOS con Homebrew
    "C:\\texlive\\2023\\bin\\win32\\pdflatex.exe",  # Windows con TexLive
    "C:\\Program Files\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe"  # Windows con MikTeX
]

# Ajustes para la generación de PDF
FORCE_LATEX_ONLY_MODE = os.getenv("FORCE_LATEX_ONLY_MODE", "True").lower() in ("true", "1", "yes")
FORCE_PDF_GENERATION = os.getenv("FORCE_PDF_GENERATION", "False").lower() in ("true", "1", "yes")
USE_SIMPLE_PDFLATEX = os.getenv("USE_SIMPLE_PDFLATEX", "True").lower() in ("true", "1", "yes")

# Diccionario global para almacenar los PDF generados
PDF_FILES = {}

# Tiempo de vida de los archivos temporales (en segundos)
TEMP_FILE_TTL = int(os.getenv("TEMP_FILE_TTL", "600"))  # 10 minutos por defecto 