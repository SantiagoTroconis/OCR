"""Pruebas de app/services/pdf.py (las funciones de extracción, sin API)."""

import pytest

from app.services.pdf import (
    PdfDemasiadasPaginasError,
    PdfIlegibleError,
    PdfProtegidoError,
    extraer_imagenes,
    extraer_metadatos,
    extraer_tablas,
    extraer_texto,
    validar_pdf,
)


def test_metadatos(pdf_texto):
    datos = extraer_metadatos(pdf_texto)
    assert datos["titulo"] == "Prueba"
    assert datos["autor"] == "Yo"
    assert datos["paginas"] == 1
    assert datos["protegido_con_contrasena"] is False


def test_texto_de_pagina_normal(pdf_texto):
    paginas = extraer_texto(pdf_texto)
    assert len(paginas) == 1
    assert paginas[0]["pagina"] == 1
    assert "Hola mundo" in paginas[0]["texto"]
    assert paginas[0]["requiere_ocr"] is False


def test_pagina_escaneada_requiere_ocr(pdf_escaneado):
    pagina = extraer_texto(pdf_escaneado)[0]
    assert pagina["texto"] == ""
    assert pagina["caracteres"] == 0
    assert pagina["requiere_ocr"] is True


def test_tablas(pdf_tabla):
    tablas = extraer_tablas(pdf_tabla)
    assert len(tablas) == 1
    assert tablas[0]["pagina"] == 1
    # La celda vacía debe ser "" y no None.
    assert tablas[0]["filas"] == [
        ["Producto", "Cantidad", "Precio"],
        ["Lapiz", "10", ""],
        ["Cuaderno", "5", "$30"],
    ]


def test_sin_tablas(pdf_texto):
    assert extraer_tablas(pdf_texto) == []


def test_imagenes(pdf_imagen):
    imagenes = extraer_imagenes(pdf_imagen)
    assert len(imagenes) == 1
    assert imagenes[0]["pagina"] == 1
    assert imagenes[0]["ancho"] == 80
    assert imagenes[0]["alto"] == 40
    assert imagenes[0]["formato"] == "png"
    assert imagenes[0]["tamano_bytes"] > 0


def test_sin_imagenes(pdf_texto):
    assert extraer_imagenes(pdf_texto) == []


def test_validar_pdf_correcto(pdf_texto):
    # Si el PDF es válido no lanza nada (devuelve None).
    assert validar_pdf(pdf_texto) is None


def test_validar_pdf_corrupto():
    with pytest.raises(PdfIlegibleError):
        validar_pdf(b"%PDF-basura")


def test_validar_pdf_con_contrasena(pdf_cifrado):
    with pytest.raises(PdfProtegidoError):
        validar_pdf(pdf_cifrado)


def test_validar_pdf_demasiadas_paginas(pdf_mixto, monkeypatch):
    # pdf_mixto tiene 3 páginas; bajamos el límite a 2 solo durante esta prueba.
    monkeypatch.setattr("app.services.pdf.MAX_PAGINAS", 2)
    with pytest.raises(PdfDemasiadasPaginasError):
        validar_pdf(pdf_mixto)
