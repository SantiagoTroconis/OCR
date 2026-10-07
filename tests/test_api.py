"""Pruebas del endpoint POST /extraer (la API completa)."""

CLAVE = "clave-de-prueba"  


def _enviar(cliente, contenido, nombre="a.pdf", tipo="application/pdf", **kwargs):
    """Atajo para subir un archivo a /extraer."""
    return cliente.post("/extraer", files={"file": (nombre, contenido, tipo)}, **kwargs)


def test_extraer_ok(cliente, pdf_texto):
    r = _enviar(cliente, pdf_texto)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["archivo"] == "a.pdf"
    assert cuerpo["metadatos"]["paginas"] == 1
    assert cuerpo["paginas"][0]["texto"] == "Hola mundo"


def test_extraer_sin_ocr(cliente, pdf_mixto):
    r = cliente.post(
        "/extraer?ocr=false", files={"file": ("a.pdf", pdf_mixto, "application/pdf")}
    )
    assert r.status_code == 200
    assert r.json()["ocr"] == {"solicitado": False}


def test_inicio_responde(cliente):
    assert cliente.get("/").status_code == 200


# ---------- Validaciones del archivo ----------


def test_archivo_que_no_es_pdf(cliente):
    r = _enviar(cliente, b"hola", nombre="a.txt", tipo="text/plain")
    assert r.status_code == 400


def test_pdf_vacio(cliente):
    assert _enviar(cliente, b"").status_code == 400


def test_pdf_falso_sin_firma(cliente):
    assert _enviar(cliente, b"esto no es un pdf").status_code == 400


def test_pdf_demasiado_grande(cliente, pdf_texto, monkeypatch):
    # Bajamos el límite a 100 bytes solo en esta prueba.
    monkeypatch.setattr("app.routes.extraction.TAMANO_MAXIMO_BYTES", 100)
    assert _enviar(cliente, pdf_texto).status_code == 413


# ---------- PDFs que no se pueden procesar ----------


def test_pdf_corrupto(cliente):
    r = _enviar(cliente, b"%PDF-basura")
    assert r.status_code == 422
    assert "dañado" in r.json()["detail"]


def test_pdf_con_contrasena(cliente, pdf_cifrado):
    r = _enviar(cliente, pdf_cifrado)
    assert r.status_code == 422
    assert "contraseña" in r.json()["detail"]


def test_pdf_con_demasiadas_paginas(cliente, pdf_mixto, monkeypatch):
    monkeypatch.setattr("app.services.pdf.MAX_PAGINAS", 2)
    r = _enviar(cliente, pdf_mixto)
    assert r.status_code == 413
    assert "máximo" in r.json()["detail"]


# ---------- API key ----------


# (El cliente "cliente" ya envía la clave correcta; "cliente_sin_clave" no.)


def test_sin_enviar_clave(cliente_sin_clave, pdf_texto):
    assert _enviar(cliente_sin_clave, pdf_texto).status_code == 401


def test_clave_incorrecta(cliente_sin_clave, pdf_texto):
    r = _enviar(cliente_sin_clave, pdf_texto, headers={"X-API-Key": "otra"})
    assert r.status_code == 401


def test_clave_correcta(cliente_sin_clave, pdf_texto):
    r = _enviar(cliente_sin_clave, pdf_texto, headers={"X-API-Key": CLAVE})
    assert r.status_code == 200


def test_inicio_no_pide_clave(cliente_sin_clave):
    assert cliente_sin_clave.get("/").status_code == 200
