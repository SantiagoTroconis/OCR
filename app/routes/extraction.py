from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.security import verificar_api_key
from app.services.extraction import extraer_texto_imagen, extraer_todo
from app.services.pdf import PdfError

# dependencies=[...] hace que TODOS los endpoints de este router exijan la API key.
router = APIRouter(dependencies=[Depends(verificar_api_key)])

# Tamaño máximo permitido para el PDF subido (20 MB).
TAMANO_MAXIMO_MB = 20
TAMANO_MAXIMO_BYTES = TAMANO_MAXIMO_MB * 1024 * 1024

# Todo archivo PDF real empieza con estos bytes ("firma" del formato).
FIRMA_PDF = b"%PDF-"

# Todo JPEG empieza con estos 3 bytes. El 4.º byte cambia según el programa que lo
# creó (JFIF, EXIF, Adobe...), por eso no lo comparamos.
FIRMA_JPEG = b"\xff\xd8\xff"
FIRMA_PNG = b"\x89PNG\r\n\x1a\n"

# startswith acepta una tupla: devuelve True si el contenido empieza con cualquiera.
FIRMAS_IMAGEN = (FIRMA_JPEG, FIRMA_PNG)


def _tipo_de_archivo(contenido: bytes) -> str | None:
    """
    Devuelve "pdf", "imagen" o None según el contenido del archivo.
    """
    if contenido.startswith(FIRMA_PDF):
        return "pdf"
    if contenido.startswith(FIRMAS_IMAGEN):
        return "imagen"
    return None


@router.post("/extraer")
async def extraer_pdf(file: UploadFile, ocr: bool = True):
    """
    Endpoint para recibir un archivo PDF y extraer información de él.
    - **ocr**: si es `true` (por defecto), las páginas sin texto se leen con OCR
      (con límite de páginas). Con `false` se omite el OCR.
    """


    if not file.filename:
        raise HTTPException(status_code=400, detail="No se subió ningún archivo.")

   
    # Leemos como máximo 1 byte más que el límite: así sabemos si se pasó sin
    # cargar en memoria un archivo gigante completo.
    contenido = await file.read(TAMANO_MAXIMO_BYTES + 1)
    if len(contenido) == 0:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    
    
    
    tipo = _tipo_de_archivo(contenido)

    if tipo is None:
            raise HTTPException(
                status_code=400,
                detail="El archivo no es un PDF ni una imagen (JPEG o PNG).",
            )
        

    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo excede el tamaño máximo permitido de {TAMANO_MAXIMO_MB} MB.",
        )
    
    # La extracción es trabajo pesado (usa CPU). run_in_threadpool la ejecuta en
    # un hilo aparte para que la API siga atendiendo otras peticiones mientras tanto.
    try:
        if tipo == "pdf":
            resultado = await run_in_threadpool(extraer_todo, contenido, ocr)
        elif tipo == "imagen":
            resultado = await run_in_threadpool(extraer_texto_imagen, contenido, ocr)
    except PdfError as error:
        # Errores esperados (PDF dañado, con contraseña, muy largo): respuesta clara.
        raise HTTPException(status_code=error.codigo_http, detail=str(error))

    return {"archivo": file.filename, **resultado}

