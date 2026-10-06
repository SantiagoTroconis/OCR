import io

import pdfplumber
import pymupdf

# Máximo de páginas que aceptamos por PDF. Protege la memoria del plan gratuito.
MAX_PAGINAS = 100


class PdfError(Exception):
    """Error base: el PDF no se puede procesar. Lleva el código HTTP a responder."""

    codigo_http = 422


class PdfIlegibleError(PdfError):
    """El PDF está dañado o no se puede leer."""


class PdfProtegidoError(PdfError):
    """El PDF necesita contraseña para abrirse."""


class PdfDemasiadasPaginasError(PdfError):
    """El PDF tiene más páginas de las permitidas."""

    codigo_http = 413


def validar_pdf(contenido: bytes) -> None:
    """
    Comprueba que el PDF se pueda abrir y procesar. Si no, lanza un PdfError
    con un mensaje claro. Si todo está bien, no hace nada.
    """

    try:
        with pymupdf.open(stream=contenido, filetype="pdf") as documento:
            if documento.needs_pass:
                raise PdfProtegidoError(
                    "El PDF está protegido con contraseña. Quita la protección y vuelve a enviarlo."
                )
            if documento.page_count == 0:
                raise PdfIlegibleError("El PDF no contiene páginas.")
            if documento.page_count > MAX_PAGINAS:
                raise PdfDemasiadasPaginasError(
                    f"El PDF tiene {documento.page_count} páginas y el máximo permitido "
                    f"es {MAX_PAGINAS}. Divídelo en partes más pequeñas."
                )
    except PdfError:
        raise
    except Exception as error:
        raise PdfIlegibleError("No se pudo leer el PDF: está dañado o es inválido.") from error


def extraer_metadatos(contenido: bytes) -> dict:
    """
    Recibe el PDF como bytes y devuelve sus metadatos
    (título, autor, fechas, número de páginas, etc.).
    """

    # Abrimos el PDF directamente desde la memoria (sin guardarlo en disco).
    pdf = pymupdf.open(stream=contenido, filetype="pdf")

    # "with" cierra el documento automáticamente cuando terminamos.
    with pdf as documento:
        datos = documento.metadata
        return {
            "paginas": documento.page_count,
            "titulo": datos.get("title") or None,
            "autor": datos.get("author") or None,
            "asunto": datos.get("subject") or None,
            "palabras_clave": datos.get("keywords") or None,
            "programa_creador": datos.get("creator") or None,
            "programa_pdf": datos.get("producer") or None,
            "fecha_creacion": datos.get("creationDate") or None,
            "fecha_modificacion": datos.get("modDate") or None,
            "version_formato": datos.get("format") or None,
            "protegido_con_contrasena": bool(documento.needs_pass),
            "cifrado": documento.is_encrypted,
        }


def extraer_texto(contenido: bytes) -> list[dict]:
    """
    Recibe el PDF como bytes y devuelve el texto de cada página.
    Cada elemento de la lista es una página: {"pagina": 1, "texto": "...", ...}
    """

    paginas = []
    pdf = pymupdf.open(stream=contenido, filetype="pdf")

    with pdf as documento:
        for numero, pagina in enumerate(documento, start=1):
            texto = pagina.get_text().strip()

            paginas.append(
                {
                    "pagina": numero,
                    "texto": texto,
                    "caracteres": len(texto),
                    "requiere_ocr": len(texto) == 0,
                }
            )

    return paginas


def extraer_tablas(contenido: bytes) -> list[dict]:
    """
    Recibe el PDF como bytes y devuelve todas las tablas que encuentre.
    Cada tabla es: {"pagina": 1, "indice": 1, "filas": [["a", "b"], ["c", "d"]]}
    """

    tablas = []
    # pdfplumber no lee bytes directamente, sino "archivos". io.BytesIO convierte
    # nuestros bytes en un archivo falso que vive en la memoria.
    pdf = pdfplumber.open(io.BytesIO(contenido))

    with pdf as documento:
        for numero, pagina in enumerate(documento.pages, start=1):
            # extract_tables() devuelve una lista de tablas; cada tabla es una
            # lista de filas; cada fila es una lista de celdas.
            for indice, tabla in enumerate(pagina.extract_tables(), start=1):
                # Las celdas vacías llegan como None; las cambiamos por "".
                filas = [[celda or "" for celda in fila] for fila in tabla]
                tablas.append({"pagina": numero, "indice": indice, "filas": filas})

            # pdfplumber guarda en memoria lo que lee de cada página. Lo liberamos
            # al terminar la página para no acumular memoria en PDFs largos.
            pagina.flush_cache()

    return tablas


def extraer_imagenes(contenido: bytes) -> list[dict]:
    """
    Recibe el PDF como bytes y devuelve los datos de cada imagen incrustada
    (página, tamaño, formato, peso). No devuelve la imagen en sí.
    """

    imagenes = []
    pdf = pymupdf.open(stream=contenido, filetype="pdf")

    with pdf as documento:
        for numero, pagina in enumerate(documento, start=1):
            # get_images() lista las imágenes de la página. De cada una nos
            # interesa el primer dato, "xref": el número de identificación
            # interno de esa imagen dentro del PDF.
            for indice, imagen in enumerate(pagina.get_images(full=True), start=1):
                xref = imagen[0]
                datos = documento.extract_image(xref)

                # Algunas imágenes no se pueden extraer; las saltamos.
                if not datos:
                    continue

                imagenes.append(
                    {
                        "pagina": numero,
                        "indice": indice,
                        "ancho": datos["width"],
                        "alto": datos["height"],
                        "formato": datos["ext"],
                        "tamano_bytes": len(datos["image"]),
                    }
                )

    return imagenes
