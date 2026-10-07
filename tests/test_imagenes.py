"""Pruebas del soporte de imágenes (JPEG y PNG) en POST /extraer."""

import io

import pytest
from PIL import Image

from app.routes.extraction import _tipo_de_archivo
from app.services.ocr import extraer_texto_imagen_ocr, tesseract_disponible

requiere_tesseract = pytest.mark.skipif(
    not tesseract_disponible(), reason="Tesseract no está instalado"
)


def _enviar(cliente, contenido, nombre="foto.png", query=""):
    """Atajo para subir un archivo a /extraer (el tipo MIME no importa: se detecta por firma)."""
    return cliente.post(
        "/extraer" + query,
        files={"file": (nombre, contenido, "application/octet-stream")},
    )


def _ocr_falso(texto=None, error=None):
    """
    "OCR de mentira" para probar nuestra lógica sin Tesseract.
    Devuelve una función con la misma forma que extraer_texto_imagen_ocr.
    """

    def ocr(contenido):
        return {"texto": texto, "error": error}

    return ocr


def _usar_ocr_falso(monkeypatch, **kwargs):
    monkeypatch.setattr(
        "app.services.extraction.extraer_texto_imagen_ocr", _ocr_falso(**kwargs)
    )


# ---------- Detección del tipo de archivo por firma ----------


@pytest.mark.parametrize(
    "cabecera",
    [
        bytes.fromhex("ffd8ffe0"),  # JPEG tipo JFIF
        bytes.fromhex("ffd8ffe1"),  # JPEG con datos EXIF (fotos de celular)
        bytes.fromhex("ffd8ffdb"),
        bytes.fromhex("ffd8ffee"),  # JPEG tipo Adobe
        b"\x89PNG\r\n\x1a\n",  # PNG
    ],
)
def test_firmas_de_imagen_se_detectan(cabecera):
    assert _tipo_de_archivo(cabecera + b"\x00" * 20) == "imagen"


def test_firma_de_pdf_sigue_detectandose():
    assert _tipo_de_archivo(b"%PDF-1.7 ...") == "pdf"


@pytest.mark.parametrize("contenido", [b"", b"hola", b"\xff\xd8"])
def test_firmas_desconocidas_o_incompletas(contenido):
    assert _tipo_de_archivo(contenido) is None


# ---------- Endpoint: imágenes que se procesan bien ----------


def test_png_ok_con_estructura_igual_a_la_de_pdf(cliente, png_texto, monkeypatch):
    _usar_ocr_falso(monkeypatch, texto="Factura numero 12345")

    r = _enviar(cliente, png_texto)

    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {
        "archivo", "metadatos", "paginas", "tablas", "imagenes", "ocr", "advertencias",
    }
    assert cuerpo["archivo"] == "foto.png"
    # Una imagen es "un PDF de una sola página": paginas es una LISTA con un elemento.
    assert isinstance(cuerpo["paginas"], list) and len(cuerpo["paginas"]) == 1
    assert cuerpo["tablas"] == []
    assert cuerpo["imagenes"] == []
    assert isinstance(cuerpo["advertencias"], list)


def test_metadatos_de_la_imagen(cliente, png_texto, monkeypatch):
    _usar_ocr_falso(monkeypatch, texto="x")
    metadatos = _enviar(cliente, png_texto).json()["metadatos"]
    assert metadatos["ancho"] == 1200
    assert metadatos["formato"] == "PNG"


def test_jpeg_ok(cliente, jpeg_texto, monkeypatch):
    _usar_ocr_falso(monkeypatch, texto="Factura numero 12345")
    r = _enviar(cliente, jpeg_texto, nombre="foto.jpg")
    assert r.status_code == 200
    assert r.json()["metadatos"]["formato"] == "JPEG"


def test_la_imagen_se_detecta_por_firma_y_no_por_nombre(cliente, png_texto, monkeypatch):
    _usar_ocr_falso(monkeypatch, texto="hola")
    assert _enviar(cliente, png_texto, nombre="archivo_sin_extension").status_code == 200
    assert _enviar(cliente, png_texto, nombre="datos.bin").status_code == 200


def test_el_texto_del_ocr_llega_a_la_pagina(cliente, png_texto, monkeypatch):
    _usar_ocr_falso(monkeypatch, texto="Factura numero 12345")

    cuerpo = _enviar(cliente, png_texto).json()
    pagina = cuerpo["paginas"][0]

    assert pagina["pagina"] == 1
    assert pagina["texto"] == "Factura numero 12345"
    assert pagina["caracteres"] == len("Factura numero 12345")
    assert pagina["texto_origen"] == "ocr"
    assert pagina["requiere_ocr"] is False
    assert cuerpo["ocr"]["solicitado"] is True
    assert cuerpo["ocr"]["paginas_leidas"] == [1]
    assert cuerpo["ocr"]["paginas_con_error"] == []
    assert cuerpo["advertencias"] == []


def test_ocr_false_no_ejecuta_ocr(cliente, png_texto, monkeypatch):
    def no_debe_llamarse(contenido):
        raise AssertionError("No debería ejecutarse OCR con ocr=false")

    monkeypatch.setattr(
        "app.services.extraction.extraer_texto_imagen_ocr", no_debe_llamarse
    )

    r = _enviar(cliente, png_texto, query="?ocr=false")

    assert r.status_code == 200
    cuerpo = r.json()
    pagina = cuerpo["paginas"][0]
    assert pagina["texto"] == ""
    assert pagina["requiere_ocr"] is True
    assert pagina["texto_origen"] is None
    assert cuerpo["ocr"]["solicitado"] is False
    assert cuerpo["advertencias"] == []


def test_imagen_sin_texto_queda_pendiente_sin_errores(cliente, png_en_blanco, monkeypatch):
    _usar_ocr_falso(monkeypatch, texto="")

    cuerpo = _enviar(cliente, png_en_blanco).json()

    assert cuerpo["paginas"][0]["texto"] == ""
    assert cuerpo["paginas"][0]["requiere_ocr"] is True
    assert cuerpo["ocr"]["paginas_con_error"] == []
    assert cuerpo["advertencias"] == []


# ---------- Endpoint: el OCR falla, pero la API responde ----------


def test_si_el_ocr_falla_la_api_responde_200_con_advertencia(cliente, png_texto, monkeypatch):
    _usar_ocr_falso(monkeypatch, error="No se pudo procesar la imagen con OCR.")

    r = _enviar(cliente, png_texto)

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["ocr"]["paginas_con_error"] == [1]
    assert cuerpo["advertencias"] == ["No se pudo procesar la imagen con OCR."]
    assert cuerpo["paginas"][0]["requiere_ocr"] is True
    # Los metadatos se entregan igual, aunque el OCR haya fallado.
    assert cuerpo["metadatos"]["ancho"] == 1200


def test_si_tesseract_lanza_una_excepcion_real_la_api_no_se_cae(cliente, png_texto, monkeypatch):
    """Aquí NO usamos el OCR falso: falla de verdad pytesseract dentro de ocr.py."""

    def tesseract_roto(*args, **kwargs):
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr("app.services.ocr.pytesseract.image_to_string", tesseract_roto)

    r = _enviar(cliente, png_texto)

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["ocr"]["paginas_con_error"] == [1]
    assert cuerpo["advertencias"]


# ---------- Endpoint: imágenes inválidas ----------


def test_imagen_corrupta(cliente):
    r = _enviar(cliente, b"\x89PNG\r\n\x1a\n" + b"esto no es una imagen")
    assert r.status_code == 422
    assert "dañada" in r.json()["detail"]


def test_jpeg_corrupto(cliente):
    r = _enviar(cliente, bytes.fromhex("ffd8ffe1") + b"\x00" * 50, nombre="foto.jpg")
    assert r.status_code == 422


def test_imagen_demasiado_grande(cliente):
    # Modo "1" (1 bit por píxel) y un solo color: pesa muy poco en memoria y en disco,
    # pero declara más píxeles (5001 x 5001 = 25 010 001) que el límite de 25 000 000.
    imagen = Image.new("1", (5001, 5001))
    buffer = io.BytesIO()
    imagen.save(buffer, "PNG")

    r = _enviar(cliente, buffer.getvalue())

    assert r.status_code == 413
    assert "demasiado grande" in r.json()["detail"]


def test_archivo_vacio_sigue_dando_400(cliente):
    r = _enviar(cliente, b"")
    assert r.status_code == 400
    assert "vacío" in r.json()["detail"]


def test_la_clave_tambien_protege_las_imagenes(cliente_sin_clave, png_texto):
    assert _enviar(cliente_sin_clave, png_texto).status_code == 401


# ---------- extraer_texto_imagen_ocr (preparación de la imagen) ----------


def _capturar_imagen_enviada_a_tesseract(monkeypatch):
    """Reemplaza a Tesseract por un espía que guarda la imagen que recibe."""
    recibido = {}

    def espia(imagen, **kwargs):
        recibido["imagen"] = imagen
        return "  texto leído \n\x0c"

    monkeypatch.setattr("app.services.ocr.pytesseract.image_to_string", espia)
    return recibido


def test_ocr_de_imagen_limpia_el_texto(png_texto, monkeypatch):
    _capturar_imagen_enviada_a_tesseract(monkeypatch)
    assert extraer_texto_imagen_ocr(png_texto) == {"texto": "texto leído", "error": None}


def test_ocr_de_imagen_convierte_a_gris_y_limita_el_tamano(monkeypatch):
    recibido = _capturar_imagen_enviada_a_tesseract(monkeypatch)
    grande = Image.new("RGB", (6000, 3000), "white")
    buffer = io.BytesIO()
    grande.save(buffer, "PNG")

    extraer_texto_imagen_ocr(buffer.getvalue())

    assert recibido["imagen"].mode == "L"
    assert max(recibido["imagen"].size) <= 3000


def test_ocr_de_imagen_corrige_la_orientacion_exif(monkeypatch):
    """Las fotos de celular guardan los píxeles de lado y un aviso EXIF para girarlas."""
    recibido = _capturar_imagen_enviada_a_tesseract(monkeypatch)
    de_lado = Image.new("RGB", (300, 1200), "white")  # guardada vertical
    exif = Image.Exif()
    exif[274] = 6  # "gira 90° para verla bien"
    buffer = io.BytesIO()
    de_lado.save(buffer, "JPEG", exif=exif)

    extraer_texto_imagen_ocr(buffer.getvalue())

    assert recibido["imagen"].size == (1200, 300)  # ya horizontal


def test_ocr_de_imagen_devuelve_error_si_tesseract_falla(png_texto, monkeypatch):
    def roto(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.ocr.pytesseract.image_to_string", roto)

    resultado = extraer_texto_imagen_ocr(png_texto)

    assert resultado["texto"] is None
    assert resultado["error"]


# ---------- Con Tesseract de verdad (se salta si no está instalado) ----------


@requiere_tesseract
def test_ocr_real_png(cliente, png_texto):
    pagina = _enviar(cliente, png_texto).json()["paginas"][0]
    assert "Factura" in pagina["texto"]
    assert "12345" in pagina["texto"]
    assert pagina["texto_origen"] == "ocr"


@requiere_tesseract
def test_ocr_real_jpeg(cliente, jpeg_texto):
    pagina = _enviar(cliente, jpeg_texto, nombre="foto.jpg").json()["paginas"][0]
    assert "12345" in pagina["texto"]
