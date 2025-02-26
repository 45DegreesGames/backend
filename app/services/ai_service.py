import os
import json
import aiohttp
import vertexai
from vertexai.generative_models import GenerativeModel
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError

from app.config import logger, API_KEY, SYSTEM_INSTRUCTION, AI_PROVIDER, GEMINI_MODEL, TIMEOUT_SECONDS
from app.services.latex_service import normalizar_latex

# Inicializar el modelo de IA según el proveedor configurado
ai_model = None

async def initialize_ai_model():
    """Inicializa el modelo de IA según el proveedor configurado."""
    global ai_model
    
    if AI_PROVIDER == "gemini":
        try:
            if not API_KEY:
                logger.warning("No se ha configurado API_KEY para Gemini")
                return False
            
            # Inicializar el modelo de Gemini
            if GEMINI_MODEL == "gemini-pro":
                import google.generativeai as genai
                genai.configure(api_key=API_KEY)
                
                generation_config = {
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                }
                
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                ]
                
                ai_model = genai.GenerativeModel(
                    model_name=GEMINI_MODEL,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
                
                logger.info(f"Modelo Gemini {GEMINI_MODEL} inicializado correctamente")
                return True
            
            elif GEMINI_MODEL.startswith("gemini-1.5"):
                # Configurar vertexai para gemini-1.5-*
                vertexai.init(api_key=API_KEY)
                ai_model = GenerativeModel(GEMINI_MODEL)
                logger.info(f"Modelo Vertex AI {GEMINI_MODEL} inicializado correctamente")
                return True
            
            else:
                logger.error(f"Modelo Gemini desconocido: {GEMINI_MODEL}")
                return False
                
        except Exception as e:
            logger.error(f"Error al inicializar el modelo Gemini: {str(e)}")
            return False
    
    elif AI_PROVIDER == "openai":
        # Para futura implementación de OpenAI
        logger.warning("Proveedor OpenAI no implementado todavía")
        return False
    
    else:
        logger.error(f"Proveedor de IA no reconocido: {AI_PROVIDER}")
        return False

async def convert_text_to_latex(text, math_mode=False):
    """
    Convierte texto a código LaTeX utilizando un modelo de IA.
    
    Args:
        text (str): Texto a convertir
        math_mode (bool): Si es True, se asume que el texto contiene fórmulas matemáticas
        
    Returns:
        str: Código LaTeX generado o None si hay un error
    """
    global ai_model
    
    if not ai_model and not await initialize_ai_model():
        logger.error("No se pudo inicializar el modelo de IA")
        return None
    
    try:
        # Construir el prompt según el modo
        if math_mode:
            prompt_instructions = "Convierte el siguiente texto con notación matemática a código LaTeX válido. Genera solo el código LaTeX sin comentarios ni explicaciones adicionales."
        else:
            prompt_instructions = "Convierte el siguiente texto a código LaTeX válido. Genera solo el código LaTeX sin comentarios ni explicaciones adicionales."
        
        prompt = f"{prompt_instructions}\n\nTexto: {text}\n\nCódigo LaTeX:"
        
        if AI_PROVIDER == "gemini":
            if GEMINI_MODEL == "gemini-pro":
                import google.generativeai as genai
                
                # Preparar el chat para incluir el system prompt
                chat = ai_model.start_chat(history=[])
                
                # Configurar system prompt
                if SYSTEM_INSTRUCTION:
                    chat_settings = chat._settings
                    if not hasattr(chat_settings, "system_instruction"):
                        # Para versiones anteriores de la API
                        chat._settings = genai.GenerationConfig(
                            **{**chat_settings._asdict(), "system_instructions": SYSTEM_INSTRUCTION}
                        )
                    else:
                        # Para versiones más recientes
                        chat._settings.system_instruction = SYSTEM_INSTRUCTION
                
                # Generar respuesta
                response = chat.send_message(prompt)
                latex_code = response.text.strip()
            
            elif GEMINI_MODEL.startswith("gemini-1.5"):
                # Usando Vertex AI para gemini-1.5-*
                response = ai_model.generate_content(
                    prompt,
                    system_instruction=SYSTEM_INSTRUCTION if SYSTEM_INSTRUCTION else None
                )
                latex_code = response.text.strip()
            
            else:
                logger.error(f"Modelo Gemini desconocido para conversión: {GEMINI_MODEL}")
                return None
        
        elif AI_PROVIDER == "openai":
            logger.warning("Conversión con OpenAI no implementada todavía")
            return None
        
        else:
            logger.error(f"Proveedor de IA no soportado: {AI_PROVIDER}")
            return None
        
        # Normalizar el código LaTeX si se generó correctamente
        if latex_code:
            return normalizar_latex(latex_code)
        else:
            logger.warning("El modelo de IA generó una respuesta vacía")
            return None
    
    except ResourceExhausted as e:
        logger.error(f"Límite de recursos de IA excedido: {str(e)}")
        return None
    except GoogleAPIError as e:
        logger.error(f"Error de API de Google: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error al convertir texto a LaTeX: {str(e)}")
        return None

async def stream_latex_conversion(text, math_mode=False):
    """
    Convierte texto a código LaTeX en modo streaming.
    
    Args:
        text (str): Texto a convertir
        math_mode (bool): Si es True, se asume que el texto contiene fórmulas matemáticas
    
    Yields:
        str: Fragmentos de código LaTeX generados
    """
    global ai_model
    
    if not ai_model and not await initialize_ai_model():
        logger.error("No se pudo inicializar el modelo de IA para streaming")
        yield json.dumps({"error": "No se pudo inicializar el modelo de IA"})
        return
    
    try:
        # Construir el prompt según el modo
        if math_mode:
            prompt_instructions = "Convierte el siguiente texto con notación matemática a código LaTeX válido. Genera solo el código LaTeX sin comentarios ni explicaciones adicionales."
        else:
            prompt_instructions = "Convierte el siguiente texto a código LaTeX válido. Genera solo el código LaTeX sin comentarios ni explicaciones adicionales."
        
        prompt = f"{prompt_instructions}\n\nTexto: {text}\n\nCódigo LaTeX:"
        
        acumulado = ""
        
        if AI_PROVIDER == "gemini":
            if GEMINI_MODEL == "gemini-pro":
                import google.generativeai as genai
                
                # Configurar chat con system prompt
                chat = ai_model.start_chat(history=[])
                
                # Configurar system prompt si existe
                if SYSTEM_INSTRUCTION:
                    chat_settings = chat._settings
                    if not hasattr(chat_settings, "system_instruction"):
                        chat._settings = genai.GenerationConfig(
                            **{**chat_settings._asdict(), "system_instructions": SYSTEM_INSTRUCTION}
                        )
                    else:
                        chat._settings.system_instruction = SYSTEM_INSTRUCTION
                
                # Generar respuesta en streaming
                response = chat.send_message(prompt, stream=True)
                
                for chunk in response:
                    if chunk.text:
                        acumulado += chunk.text
                        yield json.dumps({"chunk": chunk.text, "acumulado": acumulado})
                
                # Enviar mensaje final con el código normalizado
                latex_normalizado = normalizar_latex(acumulado)
                yield json.dumps({"final": True, "latex_completo": latex_normalizado})
            
            elif GEMINI_MODEL.startswith("gemini-1.5"):
                # Streaming con Vertex AI
                response = ai_model.generate_content(
                    prompt,
                    system_instruction=SYSTEM_INSTRUCTION if SYSTEM_INSTRUCTION else None,
                    stream=True
                )
                
                for chunk in response:
                    if chunk.text:
                        acumulado += chunk.text
                        yield json.dumps({"chunk": chunk.text, "acumulado": acumulado})
                
                # Enviar mensaje final con el código normalizado
                latex_normalizado = normalizar_latex(acumulado)
                yield json.dumps({"final": True, "latex_completo": latex_normalizado})
            
            else:
                logger.error(f"Modelo Gemini desconocido para streaming: {GEMINI_MODEL}")
                yield json.dumps({"error": f"Modelo Gemini desconocido: {GEMINI_MODEL}"})
        
        elif AI_PROVIDER == "openai":
            logger.warning("Streaming con OpenAI no implementado todavía")
            yield json.dumps({"error": "Streaming con OpenAI no implementado"})
        
        else:
            logger.error(f"Proveedor de IA no soportado para streaming: {AI_PROVIDER}")
            yield json.dumps({"error": f"Proveedor de IA no soportado: {AI_PROVIDER}"})
    
    except ResourceExhausted as e:
        logger.error(f"Límite de recursos de IA excedido en streaming: {str(e)}")
        yield json.dumps({"error": "Límite de recursos de IA excedido"})
    except GoogleAPIError as e:
        logger.error(f"Error de API de Google en streaming: {str(e)}")
        yield json.dumps({"error": f"Error de API de Google: {str(e)}"})
    except Exception as e:
        logger.error(f"Error al convertir texto a LaTeX en streaming: {str(e)}")
        yield json.dumps({"error": f"Error en la conversión: {str(e)}"}) 