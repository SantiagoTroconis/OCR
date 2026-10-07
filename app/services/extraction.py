from app.services.image import (
    validar_imagen,
    extraer_metadatos_imagen
    )
from app.services.ocr import extraer_texto_imagen_ocr, extraer_texto_ocr, tesseract_disponible
from app.services.pdf import (
    PdfError,
    PdfIlegibleError,
    extraer_imagenes,
    extraer_metadatos,
    extraer_tablas,
    extraer_texto,
    validar_pdf,
)

# Máximo de páginas a las que se les aplica OCR en una sola petición.
# El OCR es lo más pesado; este tope protege la memoria del plan gratuito.
MAX_PAGINAS_OCR = 10




def _intentar(funcion, contenido: bytes, nombre: str, advertencias: list) -> list:
    """
    Ejecuta una extracción "opcional". Si falla, no rompe la respuesta:
    devuelve una lista vacía y deja una advertencia.
    """
    try:
        return funcion(contenido)
    except Exception as error:
        advertencias.append(f"No se pudieron extraer {nombre} ({type(error).__name__}).")
        return []


def _aplicar_ocr(contenido: bytes, paginas: list[dict], advertencias: list) -> dict:
    """
    Aplica OCR a las páginas sin texto y actualiza la lista `paginas` en el lugar.
    Devuelve un resumen de lo que pasó.
    """
    resumen = {
        "paginas_leidas": [],
        "paginas_omitidas": [],
        "paginas_con_error": [],
    }

    pendientes = [p["pagina"] for p in paginas if p["requiere_ocr"]]
    if not pendientes:
        return resumen

    if not tesseract_disponible():
        advertencias.append("Tesseract no está disponible; no se aplicó OCR.")
        resumen["paginas_omitidas"] = pendientes
        return resumen

    # Solo procesamos hasta el tope; el resto se avisa como omitido.
    a_procesar = pendientes[:MAX_PAGINAS_OCR]
    resumen["paginas_omitidas"] = pendientes[MAX_PAGINAS_OCR:]
    if resumen["paginas_omitidas"]:
        advertencias.append(
            f"Solo se aplicó OCR a las primeras {MAX_PAGINAS_OCR} páginas sin texto."
        )

    resultados = extraer_texto_ocr(contenido, a_procesar)

    for numero, resultado in resultados.items():
        if resultado["error"]:
            resumen["paginas_con_error"].append(numero)
            continue

        resumen["paginas_leidas"].append(numero)
        texto = resultado["texto"]
        if texto:
            pagina = paginas[numero - 1]
            pagina["texto"] = texto
            pagina["caracteres"] = len(texto)
            pagina["requiere_ocr"] = False
            pagina["texto_origen"] = "ocr"

    return resumen


def extraer_todo(contenido: bytes, usar_ocr: bool = True) -> dict:
    """
    Coordina todas las extracciones y devuelve un único resultado.
    Metadatos y texto son obligatorios; tablas, imágenes y OCR son
    "mejor esfuerzo": si fallan, la respuesta sale igual con una advertencia.
    """
    advertencias = []

    # Antes de gastar recursos, comprobamos que el PDF sea procesable.
    validar_pdf(contenido)

    try:
        metadatos = extraer_metadatos(contenido)
        paginas = extraer_texto(contenido)
    except PdfError:
        raise
    except Exception as error:
        raise PdfIlegibleError("No se pudo leer el contenido del PDF.") from error
    
    for pagina in paginas:
        pagina["texto_origen"] = "pdf" if pagina["texto"] else None

    tablas = _intentar(extraer_tablas, contenido, "las tablas", advertencias)
    imagenes = _intentar(extraer_imagenes, contenido, "las imágenes", advertencias)

    ocr = {"solicitado": usar_ocr}
    if usar_ocr:
        ocr.update(_aplicar_ocr(contenido, paginas, advertencias))

    return {
        "metadatos": metadatos,
        "paginas": paginas,
        "tablas": tablas,
        "imagenes": imagenes,
        "ocr": ocr,
        "advertencias": advertencias,
    }




def extraer_texto_imagen(contenido: bytes, usar_ocr: bool = True) -> dict:
    """
    Aplica OCR a una imagen (JPEG o PNG) y devuelve el texto.
    Devuelve None si falla.
    """
    # Validamos que la imagen sea legible antes de intentar extraer texto.
    validar_imagen(contenido)

    advertencias = []
    paginas = {
        "pagina": 1,
        "texto": "",
        "caracteres": 0,
        "requiere_ocr": True,
        "texto_origen": None,
    }
    
    ocr = {
        'solicitado': usar_ocr,
        'paginas_con_error': [],
        'paginas_leidas': []
    }

    metadatos = extraer_metadatos_imagen(contenido)
 

    
    if usar_ocr:
        resultado = extraer_texto_imagen_ocr(contenido)
        
        if resultado['error']:
            ocr['paginas_con_error'].append(1)
            advertencias.append(resultado['error'])

        if resultado['texto']: 
            ocr["paginas_leidas"].append(1)
            paginas["texto"] = resultado['texto']
            paginas["caracteres"] = len(resultado['texto'])
            paginas["requiere_ocr"] = False
            paginas["texto_origen"] = "ocr"
            

    
    return {
        "metadatos": metadatos,
        "paginas": [paginas],
        "tablas": [],
        "imagenes": [],
        "ocr": ocr,
        "advertencias": advertencias,
    }
