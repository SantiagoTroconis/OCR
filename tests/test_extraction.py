"""Pruebas de app/services/extraction.py (el coordinador con OCR de mejor esfuerzo)."""

import pytest

from app.services.extraction import extraer_todo
from app.services.ocr import tesseract_disponible

requiere_tesseract = pytest.mark.skipif(
    not tesseract_disponible(), reason="Tesseract no está instalado"
)


def _ocr_falso(texto_por_pagina: dict):
    """
    Crea un "OCR de mentira" para probar nuestra lógica sin Tesseract.
    Recibe {pagina: texto} y devuelve una función con la misma forma que
    extraer_texto_ocr.
    """

    def ocr(contenido, paginas):
        return {n: {"texto": texto_por_pagina[n], "error": None} for n in paginas}

    return ocr


def test_sin_ocr_las_escaneadas_siguen_pendientes(pdf_mixto):
    resultado = extraer_todo(pdf_mixto, usar_ocr=False)
    assert resultado["ocr"] == {"solicitado": False}
    assert [p["requiere_ocr"] for p in resultado["paginas"]] == [True, False, True]


def test_estructura_del_resultado(pdf_texto):
    resultado = extraer_todo(pdf_texto)
    assert set(resultado) == {
        "metadatos",
        "paginas",
        "tablas",
        "imagenes",
        "ocr",
        "advertencias",
    }
    assert resultado["paginas"][0]["texto_origen"] == "pdf"


def test_sin_tesseract_no_se_cae(pdf_mixto, monkeypatch):
    monkeypatch.setattr("app.services.extraction.tesseract_disponible", lambda: False)

    resultado = extraer_todo(pdf_mixto)

    assert resultado["ocr"]["paginas_omitidas"] == [1, 3]
    assert resultado["ocr"]["paginas_leidas"] == []
    assert any("Tesseract" in a for a in resultado["advertencias"])
    # El resto de la extracción sigue funcionando.
    assert resultado["paginas"][1]["texto"] == "Pagina con texto normal"


def test_ocr_escribe_en_la_pagina_correcta(pdf_mixto, monkeypatch):
    """Protege contra el desfase paginas[numero - 1]: cada texto va a su página."""
    monkeypatch.setattr("app.services.extraction.tesseract_disponible", lambda: True)
    monkeypatch.setattr(
        "app.services.extraction.extraer_texto_ocr",
        _ocr_falso({1: "texto OCR uno", 3: "texto OCR tres"}),
    )

    paginas = extraer_todo(pdf_mixto)["paginas"]

    assert paginas[0]["texto"] == "texto OCR uno"
    assert paginas[0]["texto_origen"] == "ocr"
    assert paginas[0]["requiere_ocr"] is False
    # La página 2 ya tenía texto y no se toca.
    assert paginas[1]["texto"] == "Pagina con texto normal"
    assert paginas[1]["texto_origen"] == "pdf"
    assert paginas[2]["texto"] == "texto OCR tres"
    assert paginas[2]["texto_origen"] == "ocr"


def test_tope_de_paginas_con_ocr(pdf_mixto, monkeypatch):
    monkeypatch.setattr("app.services.extraction.MAX_PAGINAS_OCR", 1)
    monkeypatch.setattr("app.services.extraction.tesseract_disponible", lambda: True)
    monkeypatch.setattr(
        "app.services.extraction.extraer_texto_ocr", _ocr_falso({1: "uno"})
    )

    resultado = extraer_todo(pdf_mixto)

    assert resultado["ocr"]["paginas_leidas"] == [1]
    assert resultado["ocr"]["paginas_omitidas"] == [3]
    assert resultado["paginas"][2]["requiere_ocr"] is True
    assert resultado["advertencias"]


def test_error_de_ocr_en_una_pagina_no_afecta_a_las_demas(pdf_mixto, monkeypatch):
    def ocr(contenido, paginas):
        return {
            1: {"texto": None, "error": "RuntimeError"},
            3: {"texto": "texto OCR tres", "error": None},
        }

    monkeypatch.setattr("app.services.extraction.tesseract_disponible", lambda: True)
    monkeypatch.setattr("app.services.extraction.extraer_texto_ocr", ocr)

    resultado = extraer_todo(pdf_mixto)

    assert resultado["ocr"]["paginas_con_error"] == [1]
    assert resultado["ocr"]["paginas_leidas"] == [3]
    assert resultado["paginas"][0]["requiere_ocr"] is True
    assert resultado["paginas"][0]["texto_origen"] is None
    assert resultado["paginas"][2]["texto"] == "texto OCR tres"


def test_si_fallan_las_tablas_la_respuesta_sale_igual(pdf_texto, monkeypatch):
    def falla(contenido):
        raise ValueError("boom")

    monkeypatch.setattr("app.services.extraction.extraer_tablas", falla)

    resultado = extraer_todo(pdf_texto)

    assert resultado["tablas"] == []
    assert any("tablas" in a for a in resultado["advertencias"])
    assert resultado["paginas"][0]["texto"] == "Hola mundo"


@requiere_tesseract
def test_ocr_real(pdf_mixto):
    """Usa Tesseract de verdad. Se salta si no está instalado (p. ej. en Windows)."""
    paginas = extraer_todo(pdf_mixto)["paginas"]

    assert "Factura" in paginas[0]["texto"]
    assert paginas[0]["texto_origen"] == "ocr"
    assert paginas[1]["texto_origen"] == "pdf"
    assert "12345" in paginas[2]["texto"]
