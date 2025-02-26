import subprocess
import os
import platform
from app.config import logger, PDFLATEX_PATHS

# Variable global para almacenar el estado de disponibilidad
pdflatex_available = None

def is_pdflatex_available():
    """
    Verifica si pdflatex está disponible en el sistema,
    buscando en múltiples ubicaciones comunes.
    """
    global pdflatex_available
    
    # Si ya verificamos antes, reutilizar el resultado
    if pdflatex_available is not None:
        return pdflatex_available
    
    try:
        logger.info(f"Buscando pdflatex en {len(PDFLATEX_PATHS)} ubicaciones posibles")
        
        for path in PDFLATEX_PATHS:
            try:
                logger.info(f"Probando pdflatex en: {path}")
                result = subprocess.run([path, "--version"], 
                                      capture_output=True, 
                                      text=True, 
                                      check=False,
                                      timeout=5)  # Timeout para evitar bloqueos
                
                if result.returncode == 0:
                    logger.info(f"✅ pdflatex encontrado en: {path} - Versión: {result.stdout.splitlines()[0] if result.stdout else 'desconocida'}")
                    pdflatex_available = True
                    return True
                else:
                    logger.info(f"❌ pdflatex en {path} devolvió código de error: {result.returncode}")
            except FileNotFoundError:
                logger.info(f"❌ pdflatex no encontrado en: {path}")
                continue
            except subprocess.TimeoutExpired:
                logger.info(f"⏱️ Timeout al ejecutar pdflatex en: {path}")
                continue
            except Exception as e:
                logger.info(f"❌ Error al verificar pdflatex en {path}: {str(e)}")
                continue
                
        logger.warning("⚠️ pdflatex no encontrado en ninguna ubicación común")
        pdflatex_available = False
        return False
    except Exception as e:
        logger.error(f"❌ Error general al verificar pdflatex: {str(e)}")
        pdflatex_available = False
        return False

def get_system_info():
    """Obtiene información del sistema para diagnóstico."""
    info = {
        "os": platform.system(),
        "version": platform.version(),
        "python": platform.python_version(),
        "pdflatex_disponible": is_pdflatex_available()
    }
    
    # Verificar variable PATH
    info["PATH"] = os.environ.get("PATH", "")
    
    # Verificar espacio en disco
    try:
        import shutil
        total, usado, libre = shutil.disk_usage("/")
        info["espacio_disco"] = {
            "total_gb": round(total / (1024**3), 2),
            "usado_gb": round(usado / (1024**3), 2),
            "libre_gb": round(libre / (1024**3), 2)
        }
    except Exception as e:
        info["espacio_disco"] = {"error": str(e)}
    
    return info

def verify_pdflatex_paths():
    """Verifica todas las rutas posibles de pdflatex y devuelve los resultados."""
    resultados = []
    
    for ruta in PDFLATEX_PATHS:
        try:
            proceso = subprocess.run([ruta, "--version"], 
                                  capture_output=True, 
                                  text=True, 
                                  check=False,
                                  timeout=5)
            resultados.append({
                "ruta": ruta,
                "existe": proceso.returncode == 0,
                "mensaje": proceso.stdout.splitlines()[0] if proceso.returncode == 0 else proceso.stderr
            })
        except FileNotFoundError:
            resultados.append({
                "ruta": ruta,
                "existe": False,
                "mensaje": "Archivo no encontrado"
            })
        except subprocess.TimeoutExpired:
            resultados.append({
                "ruta": ruta,
                "existe": False,
                "mensaje": "Timeout al ejecutar"
            })
        except Exception as e:
            resultados.append({
                "ruta": ruta,
                "existe": False,
                "mensaje": str(e)
            })
    
    return resultados 

def diagnosticar_pdflatex():
    """
    Realiza un diagnóstico completo de la configuración de pdflatex en el sistema.
    
    Returns:
        dict: Información detallada sobre la instalación y disponibilidad de pdflatex.
    """
    diagnóstico = {
        "sistema": get_system_info(),
        "pdflatex": {
            "disponible": is_pdflatex_available(),
            "rutas_posibles": PDFLATEX_PATHS,
            "resultados_por_ruta": verify_pdflatex_paths()
        }
    }
    
    # Intentar obtener la versión de pdflatex si está disponible
    if diagnóstico["pdflatex"]["disponible"]:
        try:
            # Intentar ejecutar pdflatex --version para obtener la versión
            for resultado in diagnóstico["pdflatex"]["resultados_por_ruta"]:
                if resultado["existe"]:
                    try:
                        version_check = subprocess.run(
                            [resultado["ruta"], "--version"],
                            capture_output=True,
                            text=True,
                            check=True,
                            timeout=5
                        )
                        primera_linea = version_check.stdout.splitlines()[0]
                        logger.info(f"Versión: {primera_linea}")
                        diagnóstico["pdflatex"]["version"] = primera_linea
                        break
                    except Exception as e:
                        logger.warning(f"Error al obtener versión: {str(e)}")
                        continue
        except Exception as e:
            logger.error(f"Error al verificar versión: {str(e)}")
            diagnóstico["pdflatex"]["error_version"] = str(e)
    
    # Verificar paquetes de LaTeX básicos
    diagnóstico["pdflatex"]["necesita_paquetes"] = [
        "article", "inputenc", "fontenc", "amsmath", "amssymb", "graphicx"
    ]
    
    # Intentar obtener paths relacionados a LaTeX
    diagnóstico["pdflatex"]["env"] = {
        "TEXINPUTS": os.environ.get("TEXINPUTS", "No definido"),
        "TEXMFCNF": os.environ.get("TEXMFCNF", "No definido"),
        "TEXMFHOME": os.environ.get("TEXMFHOME", "No definido")
    }
    
    return diagnóstico 