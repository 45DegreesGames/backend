import google.generativeai as genai
from app.config import API_KEY, SYSTEM_INSTRUCTION, logger

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
        lineas = codigo_trim.splitlines()
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

def convertir_texto_a_latex(texto):
    """
    Convierte texto plano a código LaTeX utilizando Gemini AI.
    
    Args:
        texto (str): Texto plano para convertir
        
    Returns:
        str: Código LaTeX generado
    
    Raises:
        Exception: Si hay error en la conversión
    """
    try:
        # Configurar la API
        genai.configure(api_key=API_KEY)
        
        # Usar GenerativeModel directamente
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")
        
        # Preparar la solicitud con las instrucciones del sistema
        prompt = f"{SYSTEM_INSTRUCTION}\n\n{texto}"
        
        # Generar el contenido
        response = model.generate_content(prompt)
        
        # Extraer el código LaTeX generado
        return response.text
    except Exception as e:
        logger.error(f"Error al convertir texto: {str(e)}")
        raise

async def generate_content_stream(texto):
    """
    Genera contenido LaTeX en modo streaming.
    
    Args:
        texto (str): Texto plano para convertir
        
    Yields:
        str: Chunks del código LaTeX generado
    """
    # Configurar la API
    genai.configure(api_key=API_KEY)
    
    # Crear modelo generativo
    model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")
    
    # Preparar el prompt completo
    prompt = f"{SYSTEM_INSTRUCTION}\n\n{texto}"
    
    # Generar respuesta en streaming
    stream = model.generate_content(prompt, stream=True)
    
    # Devolver chunks de respuesta
    for chunk in stream:
        if hasattr(chunk, 'text'):
            yield chunk.text 