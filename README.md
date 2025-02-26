# API Pitorro

API para convertir texto a LaTeX y generar PDF, con soporte de IA para la conversión de texto a código LaTeX.

## Características

- Conversión de texto a código LaTeX usando IA (Gemini)
- Generación de PDF a partir de código LaTeX
- Modo fallback para entornos sin pdflatex
- API REST con documentación automática
- Funciona en diferentes plataformas (Windows, Linux, macOS)

## Requisitos

- Python 3.8 o superior
- pdflatex (opcional, para generación de PDFs)
- Clave de API de Google Gemini (para la conversión de texto a LaTeX)
- vertexai 1.71.1 y otras dependencias (ver requirements.txt)

## Instalación

1. Clonar el repositorio:

```bash
git clone https://github.com/yourusername/pitorro.git
cd pitorro
```

2. Crear un entorno virtual:

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate  # Windows
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Crear un archivo `.env` en la raíz del proyecto:

```
API_KEY=tu_clave_api_de_gemini
ALLOWED_ORIGINS=https://tudominio.com,http://localhost:3000
FORCE_LATEX_ONLY_MODE=False  # True si no deseas generar PDFs
PORT=8000
```

## Ejecución

Para iniciar el servidor:

```bash
python main.py
```

El servidor se iniciará en `http://localhost:8000` por defecto.

## Uso de la API

### Documentación

La documentación interactiva está disponible en:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Endpoints principales

#### Conversión de texto a LaTeX

```
POST /conversion/texto-a-latex
```

Ejemplo de cuerpo de la solicitud:
```json
{
  "text": "El teorema de Pitágoras establece que a^2 + b^2 = c^2",
  "math_mode": true
}
```

#### Generación de PDF

```
POST /pdf/generar
```

Ejemplo de cuerpo de la solicitud:
```json
{
  "latex": "\\documentclass{article}\\begin{document}Hello World\\end{document}"
}
```

Respuesta:
```json
{
  "id": "1234-5678-90ab-cdef"
}
```

#### Descarga de PDF/LaTeX

```
GET /pdf/descargar/{id}
```

### Verificación del estado de la API

```
GET /health
```

## Configuración

Las siguientes variables de entorno pueden configurarse:

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| API_KEY | Clave API de Gemini | - |
| ALLOWED_ORIGINS | Orígenes permitidos para CORS | - |
| FORCE_LATEX_ONLY_MODE | Si se debe forzar el modo solo LaTeX | False |
| FORCE_PDF_GENERATION | Si se debe forzar la generación de PDF | False |
| USE_SIMPLE_PDFLATEX | Usar modo simple de pdflatex | True |
| TEMP_FILE_TTL | Tiempo de vida para archivos temporales (segundos) | 600 |
| PORT | Puerto para el servidor | 8000 |

## Despliegue en Render

Este servicio está diseñado para desplegarse fácilmente en [Render](https://render.com).

1. Crear un nuevo servicio web
2. Conectar con el repositorio de GitHub
3. Configurar como:
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Agregar las variables de entorno necesarias

## Solución de problemas

### Problemas de dependencias

Si encuentras problemas con las dependencias durante el despliegue:

1. Verifica que las versiones en `requirements.txt` estén disponibles en PyPI
2. Para problemas con vertexai, asegúrate de usar la versión 1.71.1 o posterior
3. Si usas modelos Gemini 1.5, verifica que las importaciones usen `vertexai.generative_models` en lugar de `vertexai.preview.generative_models`

### Errores comunes

- **Error de API_KEY**: Asegúrate de configurar una API_KEY válida para Google Gemini
- **pdflatex no disponible**: La aplicación funcionará en modo solo LaTeX, pero no generará PDFs
- **Problemas de CORS**: Configura correctamente ALLOWED_ORIGINS para tu frontend
- **SyntaxError en f-strings**: Si encuentras un error de sintaxis relacionado con f-strings que contienen caracteres de escape (`\n`, `\t`, etc.), reemplaza `split('\n')` con `splitlines()` o utiliza variables intermedias

## Licencia

[MIT](LICENSE)

## Contribuciones

Las contribuciones son bienvenidas. Por favor, envía un pull request o abre un issue para discutir los cambios propuestos. 