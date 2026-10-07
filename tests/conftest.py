"""
Fixtures compartidas por todas las pruebas.
Una "fixture" es una función que prepara datos; la prueba la pide poniendo
su nombre como parámetro. Aquí fabricamos PDFs en memoria con PyMuPDF.
"""

import os

import pymupdf
import pytest
from fastapi.testclient import TestClient

CLAVE_API = "clave-de-prueba"

# La API se niega a arrancar si no existe API_KEY, y eso se comprueba al importar
# app.main. Por eso la definimos ANTES de importarla (solo vive en este proceso
# de pruebas; no toca tu .env ni tu configuración real).
os.environ["API_KEY"] = CLAVE_API

from app.main import app  # noqa: E402

TEXTO_ESCANEADO = "Factura numero 12345\nTotal a pagar: 350 pesos"


@pytest.fixture(autouse=True)
def api_key_de_prueba(monkeypatch):
    """Garantiza que cada prueba use la clave de prueba, pase lo que pase."""
    monkeypatch.setenv("API_KEY", CLAVE_API)


@pytest.fixture
def cliente():
    """Cliente que simula peticiones HTTP, ya con la clave correcta incluida."""
    return TestClient(app, headers={"X-API-Key": CLAVE_API})


@pytest.fixture
def cliente_sin_clave():
    """Cliente que NO envía clave. Sirve para probar el rechazo (401)."""
    return TestClient(app)


def _png_con_texto(texto: str) -> bytes:
    """Dibuja un texto en una página y la devuelve como imagen PNG."""
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), texto, fontsize=18)
    return doc[0].get_pixmap(dpi=150).tobytes("png")


def _agregar_pagina_escaneada(doc, texto: str) -> None:
    """Agrega una página que es solo una imagen (sin texto seleccionable)."""
    pagina = doc.new_page()
    pagina.insert_image(pagina.rect, stream=_png_con_texto(texto))


@pytest.fixture
def pdf_texto() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Hola mundo")
    doc.set_metadata({"title": "Prueba", "author": "Yo"})
    return doc.tobytes()


@pytest.fixture
def pdf_tabla() -> bytes:
    filas = [
        ["Producto", "Cantidad", "Precio"],
        ["Lapiz", "10", ""],
        ["Cuaderno", "5", "$30"],
    ]
    doc = pymupdf.open()
    pagina = doc.new_page()
    for i, fila in enumerate(filas):
        for j, texto in enumerate(fila):
            celda = pymupdf.Rect(
                72 + j * 120, 100 + i * 25, 72 + (j + 1) * 120, 100 + (i + 1) * 25
            )
            pagina.draw_rect(celda)
            pagina.insert_text((celda.x0 + 5, celda.y1 - 8), texto)
    return doc.tobytes()


@pytest.fixture
def pdf_imagen() -> bytes:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 80, 40), False)
    pixmap.set_rect(pixmap.irect, (200, 30, 30))
    doc = pymupdf.open()
    doc.new_page().insert_image(pymupdf.Rect(50, 50, 250, 150), pixmap=pixmap)
    return doc.tobytes()


@pytest.fixture
def pdf_escaneado() -> bytes:
    """Una sola página que es una imagen: no tiene texto seleccionable."""
    doc = pymupdf.open()
    _agregar_pagina_escaneada(doc, TEXTO_ESCANEADO)
    return doc.tobytes()


@pytest.fixture
def pdf_mixto() -> bytes:
    """3 páginas: 1 escaneada, 2 con texto normal, 3 escaneada."""
    doc = pymupdf.open()
    _agregar_pagina_escaneada(doc, TEXTO_ESCANEADO)
    doc.new_page().insert_text((72, 72), "Pagina con texto normal")
    _agregar_pagina_escaneada(doc, TEXTO_ESCANEADO)
    return doc.tobytes()


@pytest.fixture
def pdf_cifrado() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "secreto")
    return doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="123", owner_pw="456"
    )
