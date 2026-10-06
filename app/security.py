import logging
import os
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger("uvicorn.error")

# El cliente debe enviar su clave en este encabezado: X-API-Key: <clave>
encabezado_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)

if not os.environ.get("API_KEY"):
    #raise HTTPException(status_code=500, detail="Api key no está definida.")
    logger.log(logging.WARNING, "Api key no está definida.")


def verificar_api_key(clave: str | None = Security(encabezado_api_key)) -> None:
    """
    Dependencia de FastAPI: se ejecuta antes del endpoint y lo bloquea (401)
    si la clave enviada no coincide con la variable de entorno API_KEY.
    Si API_KEY no está definida, no se exige clave (útil solo en desarrollo).
    """

    esperada = os.environ.get("API_KEY")
    if not esperada:
        return

    # compare_digest compara sin revelar, por el tiempo que tarda, cuántos
    # caracteres acertó el atacante.
    if not clave or not secrets.compare_digest(clave, esperada):
        raise HTTPException(status_code=401, detail="API key inválida o ausente.")

    return
