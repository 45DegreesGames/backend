import os
import shutil
import uuid
import subprocess
import tempfile
import asyncio
from pathlib import Path
from fastapi import HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, PlainTextResponse

from app.config import (
    logger, TEMP_DIR, PDF_FILES, TEMP_FILE_TTL,
    FORCE_LATEX_ONLY_MODE, FORCE_PDF_GENERATION, USE_SIMPLE_PDFLATEX
)
from app.utils.pdflatex import is_pdflatex_available
from app.services.latex_service import normalizar_latex

async def generar_pdf_desde_latex(latex_code, background_tasks: BackgroundTasks):
    """
    Genera un PDF a partir de código LaTeX, o almacena el código
    si la generación de PDF no es posible.
    
    Args:
        latex_code (str): Código LaTeX para convertir a PDF
        background_tasks: Objeto para tareas en segundo plano
    
    Returns:
        dict: Diccionario con el ID del archivo generado
    """
    try:
        # Normalizar el código LaTeX para asegurar la estructura correcta
        latex_normalizado = normalizar_latex(latex_code)
        
        logger.info("Generando PDF con código LaTeX normalizado")
        
        # Generar un ID único siempre
        file_id = str(uuid.uuid4())
        logger.info(f"ID generado: {file_id}")
        
        # SIEMPRE crear la entrada en PDF_FILES primero (antes de intentar cualquier operación)
        PDF_FILES[file_id] = {
            "latex": latex_normalizado,
            "is_latex_only": True  # Por defecto, modo LaTeX-only
        }
        
        # Si estamos en modo forzado de solo LaTeX, devolvemos directamente
        if FORCE_LATEX_ONLY_MODE:
            logger.info("Modo forzado de solo LaTeX activo - devolviendo código LaTeX sin generar PDF")
            background_tasks.add_task(eliminar_archivo_temporal, file_id, TEMP_FILE_TTL)
            return {"id": file_id}
        
        # Verificar si pdflatex está disponible o si forzamos la generación
        try_pdflatex = is_pdflatex_available() or FORCE_PDF_GENERATION
        
        # Si no vamos a intentar usar pdflatex, devolvemos de inmediato solo el código LaTeX
        if not try_pdflatex:
            logger.warning("pdflatex no disponible y no se fuerza generación - devolviendo solo LaTeX")
            background_tasks.add_task(eliminar_archivo_temporal, file_id, TEMP_FILE_TTL)
            return {"id": file_id}
        
        # A partir de aquí intentamos generar el PDF, con manejo seguro de errores
        try:
            # Crear un directorio temporal para la compilación
            compile_dir = TEMP_DIR / file_id
            compile_dir.mkdir(exist_ok=True)
            
            # Guardar el código LaTeX en un archivo .tex
            tex_file_path = compile_dir / "documento.tex"
            with open(tex_file_path, "w", encoding="utf-8") as f:
                f.write(latex_normalizado)
            
            logger.info(f"Archivo LaTeX guardado en: {tex_file_path}")
            
            # Actualizar el registro con la ruta del directorio de compilación
            PDF_FILES[file_id]["compile_dir"] = str(compile_dir)
            
            # Determinar el comando de pdflatex a utilizar
            pdflatex_cmd = ["pdflatex"]
            
            if USE_SIMPLE_PDFLATEX:
                # Modo simplificado - una sola pasada, menos opciones
                pdflatex_cmd.extend([
                    "-interaction=nonstopmode",
                    "-output-directory", str(compile_dir),
                    "-no-shell-escape",  # Más seguro
                    str(tex_file_path)
                ])
            else:
                # Modo normal
                pdflatex_cmd.extend([
                    "-interaction=nonstopmode",
                    "-output-directory", str(compile_dir),
                    str(tex_file_path)
                ])
                
            logger.info(f"Ejecutando: {' '.join(pdflatex_cmd)}")
            
            # Intentar ejecutar pdflatex con manejo de errores
            try:
                # Primera pasada de pdflatex con timeout por seguridad
                process = subprocess.run(
                    pdflatex_cmd,
                    check=True,
                    capture_output=True,
                    timeout=30  # Máximo 30 segundos
                )
                
                # Registrar stdout y stderr para diagnóstico
                stdout_text = process.stdout.decode('utf-8', errors='replace')
                stderr_text = process.stderr.decode('utf-8', errors='replace') if process.stderr else ""
                
                logger.info(f"pdflatex exitoso con código: {process.returncode}")
                logger.info(f"pdflatex stdout: {stdout_text[:300]}...")
                if stderr_text:
                    logger.warning(f"pdflatex stderr: {stderr_text}")
                
                # Si no usamos el modo simple, ejecutamos una segunda pasada para referencias
                if not USE_SIMPLE_PDFLATEX:
                    logger.info("Ejecutando segunda pasada de pdflatex")
                    subprocess.run(
                        pdflatex_cmd,
                        check=True,
                        capture_output=True,
                        timeout=30
                    )
                
                # Verificar si se generó el PDF
                pdf_path = compile_dir / "documento.pdf"
                logger.info(f"Buscando PDF en: {pdf_path}")
                
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    logger.info(f"PDF generado correctamente: {pdf_path} ({pdf_path.stat().st_size} bytes)")
                    # Actualizar la entrada con la información del PDF
                    PDF_FILES[file_id].update({
                        "path": str(pdf_path),
                        "is_latex_only": False
                    })
                else:
                    logger.warning(f"PDF no encontrado en la ruta esperada: {pdf_path}")
                    # Buscar si hay algún PDF en el directorio
                    pdf_files_in_dir = list(compile_dir.glob("*.pdf"))
                    if pdf_files_in_dir:
                        pdf_path = pdf_files_in_dir[0]
                        logger.info(f"Se encontró un PDF alternativo: {pdf_path} ({pdf_path.stat().st_size} bytes)")
                        PDF_FILES[file_id].update({
                            "path": str(pdf_path),
                            "is_latex_only": False
                        })
                    else:
                        # Buscar archivo de log para diagnóstico
                        log_path = compile_dir / "documento.log"
                        if log_path.exists():
                            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                                log_content = f.read()
                                # Mostrar las últimas líneas donde suelen estar los errores
                                log_error = log_content[-500:] if len(log_content) > 500 else log_content
                                logger.error(f"Error en compilación LaTeX (del log): {log_error}")
                        
                        # Si no hay PDF, mantenemos el modo LaTeX que ya está configurado
                        logger.warning("No se pudo generar el PDF, devolviendo modo LaTeX")
            except FileNotFoundError as e:
                # Error específico cuando pdflatex no está instalado
                logger.error(f"pdflatex no encontrado en el sistema: {str(e)}")
                # Actualizar la variable global para evitar futuros intentos
                from app.utils.pdflatex import pdflatex_available
                globals()['pdflatex_available'] = False
            except subprocess.CalledProcessError as e:
                logger.error(f"Error al compilar LaTeX: {e.returncode}")
                logger.error(f"Error stdout: {e.stdout.decode('utf-8', errors='replace')[:300]}...")
                logger.error(f"Error stderr: {e.stderr.decode('utf-8', errors='replace')}")
            except subprocess.TimeoutExpired:
                logger.error("Timeout al ejecutar pdflatex (excedió 30 segundos)")
        except Exception as e:
            # Error al crear archivos o directorios
            logger.error(f"Error en el proceso de generación de PDF: {str(e)}")
        
        # Programar la eliminación del archivo después del tiempo configurado
        background_tasks.add_task(eliminar_archivo_temporal, file_id, TEMP_FILE_TTL)
        
        # Siempre devolver el ID, independientemente de si se generó PDF o no
        return {"id": file_id}
    except Exception as e:
        logger.error(f"Error general en generar-pdf: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en el servidor: {str(e)}")

async def obtener_archivo(file_id: str, background_tasks: BackgroundTasks):
    """
    Obtiene el archivo PDF o LaTeX según el ID proporcionado.
    
    Args:
        file_id (str): ID del archivo a obtener
        background_tasks: Objeto para tareas en segundo plano
    
    Returns:
        FileResponse o PlainTextResponse: Respuesta con el archivo
    
    Raises:
        HTTPException: Si el archivo no existe o hay un error
    """
    # Verificar si el archivo existe
    if file_id not in PDF_FILES:
        logger.warning(f"Archivo con ID {file_id} no encontrado")
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    info = PDF_FILES[file_id]
    logger.info(f"Información del archivo {file_id}: {info}")
    
    # Verificar si hay un PDF disponible
    if not info.get("is_latex_only", False) and "path" in info:
        pdf_path = info["path"]
        logger.info(f"Intentando devolver PDF: {pdf_path}")
        
        # Verificar si el archivo existe en el sistema de archivos y tiene tamaño válido
        if os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 100:  # Al menos 100 bytes
            logger.info(f"Devolviendo PDF: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
            try:
                return FileResponse(
                    path=pdf_path, 
                    filename="documento.pdf", 
                    media_type="application/pdf"
                )
            except Exception as e:
                logger.error(f"Error al devolver PDF: {str(e)}")
                # Continuamos para caer en el fallback de LaTeX
        else:
            logger.warning(f"El archivo PDF no existe o es demasiado pequeño: {pdf_path}")
    
    # Si llegamos aquí, no hay PDF o no se encontró el archivo
    # Manejar el caso de solo código LaTeX o fallback a LaTeX
    if "latex" in info:
        logger.info(f"Devolviendo archivo LaTeX para {file_id}")
        latex_content = info["latex"]
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tex", mode="w", encoding="utf-8") as f:
                f.write(latex_content)
                temp_file_path = f.name
            
            # Devolver el archivo .tex
            temp_bg_tasks = BackgroundTasks()
            temp_bg_tasks.add_task(os.unlink, temp_file_path)  # Eliminar después de enviar
            
            return FileResponse(
                path=temp_file_path,
                filename="documento.tex",
                media_type="application/x-tex",
                background=temp_bg_tasks
            )
        except Exception as e:
            logger.error(f"Error al crear archivo LaTeX temporal: {str(e)}")
            # Como último recurso, devolver el contenido LaTeX directamente
            return PlainTextResponse(
                content=latex_content,
                headers={"Content-Disposition": "attachment; filename=documento.tex"}
            )
    
    # Si llegamos aquí, hay algún problema con los datos
    logger.error(f"Datos inconsistentes para {file_id}: {info}")
    raise HTTPException(status_code=500, detail="Error interno al procesar el archivo")

async def eliminar_archivo_temporal(file_id: str, delay_seconds: int = 600):
    """
    Elimina el archivo temporal después de un tiempo específico.
    
    Args:
        file_id (str): ID del archivo a eliminar
        delay_seconds (int): Tiempo de espera antes de eliminar
    """
    await asyncio.sleep(delay_seconds)
    
    if file_id in PDF_FILES:
        try:
            info = PDF_FILES[file_id]
            
            # Si es un archivo PDF, eliminar el directorio de compilación
            if not info.get("is_latex_only", False) and "compile_dir" in info:
                compile_dir = info["compile_dir"]
                if os.path.isdir(compile_dir):
                    shutil.rmtree(compile_dir)
            
            # Eliminar la entrada del diccionario en cualquier caso
            del PDF_FILES[file_id]
            logger.info(f"Archivo temporal {file_id} eliminado correctamente")
        except Exception as e:
            logger.error(f"Error al eliminar archivo temporal {file_id}: {str(e)}")

def limpiar_archivos_temporales():
    """Limpia todos los archivos temporales al iniciar la aplicación."""
    logger.info("Limpiando directorio temporal al iniciar...")
    try:
        if TEMP_DIR.exists():
            for item in TEMP_DIR.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        logger.info("Limpieza completada")
    except Exception as e:
        logger.error(f"Error durante la limpieza inicial: {str(e)}")

def run_test_pdflatex():
    """
    Realiza una prueba de generación de PDF simple para
    verificar que pdflatex está configurado correctamente.
    
    Returns:
        dict: Resultados de la prueba
    """
    resultados = {
        "pdflatex_disponible": is_pdflatex_available(),
        "forzar_modo_latex": FORCE_LATEX_ONLY_MODE,
        "forzar_generacion_pdf": FORCE_PDF_GENERATION,
        "modo_simple": USE_SIMPLE_PDFLATEX,
        "modo_actual": "LaTeX only (configuración forzada)" if FORCE_LATEX_ONLY_MODE else (
            "PDF generation" if is_pdflatex_available() else "LaTeX only (pdflatex no disponible)"
        ),
        "pasos": []
    }
    
    # Si estamos en modo forzado de solo LaTeX, informar y salir
    if FORCE_LATEX_ONLY_MODE:
        resultados["conclusión"] = "Prueba no realizada porque el sistema está configurado para operar solo en modo LaTeX."
        return resultados
    
    try:
        # Paso 1: Crear un directorio de prueba
        resultados["pasos"].append({"paso": 1, "descripción": "Crear directorio de prueba", "estado": "iniciando"})
        test_dir = TEMP_DIR / "test-pdflatex"
        if test_dir.exists():
            shutil.rmtree(test_dir)
        test_dir.mkdir(exist_ok=True)
        resultados["pasos"][-1]["estado"] = "completado"
        resultados["test_dir"] = str(test_dir)
        
        # Paso 2: Crear un documento LaTeX mínimo
        resultados["pasos"].append({"paso": 2, "descripción": "Crear documento LaTeX mínimo", "estado": "iniciando"})
        minimal_latex = r"""
\documentclass{article}
\begin{document}
Documento de prueba para verificar que pdflatex funciona correctamente.
\end{document}
"""
        tex_file_path = test_dir / "test.tex"
        with open(tex_file_path, "w", encoding="utf-8") as f:
            f.write(minimal_latex)
        resultados["pasos"][-1]["estado"] = "completado"
        resultados["archivo_tex"] = str(tex_file_path)
        
        # Paso 3: Ejecutar pdflatex
        resultados["pasos"].append({"paso": 3, "descripción": "Ejecutar pdflatex", "estado": "iniciando"})
        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-output-directory", str(test_dir),
            "-no-shell-escape",
            str(tex_file_path)
        ]
        resultados["comando"] = " ".join(cmd)
        
        try:
            process = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=30  # Timeout de 30 segundos
            )
            resultados["pasos"][-1]["estado"] = "completado"
            resultados["exit_code"] = process.returncode
            resultados["stdout"] = process.stdout.decode('utf-8', errors='replace')[:300] + "..."  # Primeros 300 caracteres
            if process.stderr:
                resultados["stderr"] = process.stderr.decode('utf-8', errors='replace')
        except FileNotFoundError as e:
            resultados["pasos"][-1]["estado"] = "error"
            resultados["exit_code"] = -1
            resultados["error"] = f"pdflatex no encontrado: {str(e)}"
            resultados["conclusión"] = "pdflatex no está instalado o no está en el PATH"
            return resultados
        except subprocess.CalledProcessError as e:
            resultados["pasos"][-1]["estado"] = "error"
            resultados["exit_code"] = e.returncode
            resultados["stdout"] = e.stdout.decode('utf-8', errors='replace')[:300] + "..."
            resultados["stderr"] = e.stderr.decode('utf-8', errors='replace')
        except subprocess.TimeoutExpired:
            resultados["pasos"][-1]["estado"] = "timeout"
            resultados["error"] = "El comando pdflatex excedió el tiempo de espera (30s)"
        
        # Paso 4: Verificar si se generó el PDF
        resultados["pasos"].append({"paso": 4, "descripción": "Verificar PDF generado", "estado": "iniciando"})
        pdf_path = test_dir / "test.pdf"
        resultados["pdf_existe"] = pdf_path.exists()
        
        if pdf_path.exists():
            resultados["pasos"][-1]["estado"] = "completado"
            resultados["pdf_path"] = str(pdf_path)
            resultados["pdf_size"] = pdf_path.stat().st_size
            resultados["conclusión"] = "PDF generado correctamente"
        else:
            resultados["pasos"][-1]["estado"] = "error"
            resultados["conclusión"] = "No se pudo generar el PDF"
            
            # Comprobar si hay archivos de log
            log_path = test_dir / "test.log"
            if log_path.exists():
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    log_content = f.read()
                    # Mostrar las últimas líneas donde suelen estar los errores
                    resultados["log_ultimas_lineas"] = log_content[-1000:] if len(log_content) > 1000 else log_content
            
            # Listar archivos en el directorio
            resultados["archivos_generados"] = [f.name for f in test_dir.iterdir() if f.is_file()]
            
    except Exception as e:
        resultados["error_general"] = str(e)
        resultados["conclusión"] = "Error durante la prueba de pdflatex"
    
    return resultados

def get_file_info(file_id: str):
    """
    Obtiene información detallada sobre un archivo generado.
    
    Args:
        file_id (str): ID del archivo
        
    Returns:
        dict: Información sobre el archivo
        
    Raises:
        HTTPException: Si el archivo no existe
    """
    # Verificar si el archivo existe
    if file_id not in PDF_FILES:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    info = PDF_FILES[file_id].copy()
    
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