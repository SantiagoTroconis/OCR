import io
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, ImageOps

# Idiomas que Tesseract usará para leer: español e inglés.
IDIOMAS = "spa+eng"

# Resolución con la que convertimos la página en imagen. Más alta = más precisión,
# pero más lento y con más memoria. 200 es un buen equilibrio para el plan gratuito.
DPI = 200

# Tiempo máximo (en segundos) que Tesseract puede tardar en UNA página.
TIMEOUT_SEGUNDOS = 30

# En Windows, el instalador de Tesseract lo deja en esta carpeta, pero no siempre
# la agrega al PATH (la lista de lugares donde Windows busca programas). Si el
# archivo existe ahí, le decimos a pytesseract dónde encontrarlo.
RUTA_WINDOWS = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if RUTA_WINDOWS.exists():
    pytesseract.pytesseract.tesseract_cmd = str(RUTA_WINDOWS)


def tesseract_disponible() -> bool:
    """Devuelve True si Tesseract está instalado y Python puede encontrarlo."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except pytesseract.TesseractNotFoundError:
        return False


def extraer_texto_ocr(contenido: bytes, paginas: list[int]) -> dict[int, dict]:
    """
    Aplica OCR a las páginas indicadas (numeradas desde 1).
    Devuelve {numero_de_pagina: {"texto": "...", "error": None}}.
    Si una página falla, su "texto" es None y "error" dice por qué; las demás
    páginas se siguen procesando.
    """

    resultado = {}
    pdf = pymupdf.open(stream=contenido, filetype="pdf")

    with pdf as documento:
        for numero in paginas:
            try:
                # Las páginas de PyMuPDF empiezan en 0, por eso restamos 1.
                pagina = documento[numero - 1]

                # 1) Convertimos la página en una imagen (como una captura de pantalla).
                pixmap = pagina.get_pixmap(dpi=DPI)
                imagen = Image.open(io.BytesIO(pixmap.tobytes("png")))

                # 2) Tesseract "lee" esa imagen y devuelve el texto.
                texto = pytesseract.image_to_string(
                    imagen, lang=IDIOMAS, timeout=TIMEOUT_SEGUNDOS
                )
                resultado[numero] = {"texto": texto.strip(), "error": None}

            except Exception as error:
                # Si algo falla en esta página (tiempo agotado, memoria, etc.),
                # lo anotamos y seguimos con la siguiente.
                resultado[numero] = {"texto": None, "error": type(error).__name__}

    return resultado



def extraer_texto_imagen_ocr(contenido: bytes) -> dict[str, str | None]:
    """
    Aplica OCR a una imagen y devuelve el texto.
    """
    try:
        with Image.open(io.BytesIO(contenido)) as img:
            img = img.convert("L") # Convierte a escala de grises para mejorar OCR
            img.thumbnail((3000, 3000))  # Limita tamaño para no usar demasiada memoria

            img = ImageOps.exif_transpose(img)  
            
        resultados =  {"texto": pytesseract.image_to_string(img, lang=IDIOMAS, timeout=TIMEOUT_SEGUNDOS).strip(), "error": None}

        return resultados
    except Exception:
        resultados = {"texto": None, "error": "No se pudo procesar la imagen con OCR."}
        
        return resultados
    