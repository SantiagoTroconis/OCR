from fastapi import FastAPI

from app.routes.extraction import router as extraction_router

app = FastAPI(
    title="API de extracción de PDFs",
    description="Recibe un documento PDF y extrae toda la información posible: "
    "metadatos, texto, tablas, imágenes y texto escaneado (OCR).",
    version="0.1.0",
)

app.include_router(extraction_router, tags=["Extracción"])


@app.get("/")
def inicio():
    return {"mensaje": "La API está funcionando. Visita /docs para ver la documentación."}
