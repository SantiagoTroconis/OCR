

import io
from PIL import Image
from app.services.pdf import PdfError


class ImageIlegibleError(PdfError):
    """La imagen está dañada o no se puede leer."""

class ImageTooBigError(ImageIlegibleError):
    """La imagen es demasiado grande para ser procesada."""
    codigo_http = 413


def extraer_metadatos_imagen(contenido: bytes) -> dict:

    with Image.open(io.BytesIO(contenido)) as img:
        metadatos = {
            "ancho": img.width,
            "alto": img.height,
            "formato": img.format,
            "modo": img.mode
        }

    return metadatos



def validar_imagen(contenido: bytes) -> None:
    """
    Comprueba que la imagen se pueda abrir y procesar. Si no, lanza un ImageIlegibleError
    con un mensaje claro. Si todo está bien, no hace nada.
    """

    try:
        with Image.open(io.BytesIO(contenido)) as img:
            img.verify()  # Verifica que la imagen no esté dañada

            w, h = img.size
            if h * w > 25000000:
                raise ImageTooBigError(
                    f"La imagen es demasiado grande ({w}x{h} píxeles). "
                )
    except ImageTooBigError:
        raise
    except Exception as error:
        raise ImageIlegibleError("No se pudo leer la imagen: está dañada o es inválida.") from error
