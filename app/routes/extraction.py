from fastapi import APIRouter, HTTPException, UploadFile

router = APIRouter()

# Tamaño máximo permitido para el PDF subido (20 MB).
TAMANO_MAXIMO_MB = 20
TAMANO_MAXIMO_BYTES = TAMANO_MAXIMO_MB * 1024 * 1024

# Todo archivo PDF real empieza con estos bytes ("firma" del formato).
FIRMA_PDF = b"%PDF-"





@router.post("/extraer")
async def extraer_pdf(file: UploadFile):
    """
    Endpoint para recibir un archivo PDF y extraer información de él.
    """

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF.")

    # Leer contenido sin bloquear
    contenido = await file.read()

    if len(contenido) == 0:
        raise HTTPException(status_code=400, detail="El archivo PDF está vacío.")
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo PDF excede el tamaño máximo permitido de {TAMANO_MAXIMO_MB} MB.",
        )
    if not contenido.startswith(FIRMA_PDF):
        raise HTTPException(status_code=400, detail="El archivo no es un PDF válido.")

    return {"mensaje": "Archivo PDF recibido correctamente. Procesando extracción..."}





