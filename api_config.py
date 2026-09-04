"""
Configuración segura para Tennis Edge Pro.

- Streamlit Cloud: lee las claves desde st.secrets.
- Local: admite variables de entorno.
- No contiene claves privadas.
"""

import os

try:
    import streamlit as st
except Exception:
    st = None


def _get_secret(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return str(value).strip()

    if st is not None:
        try:
            value = st.secrets.get(name, default)
            if value:
                return str(value).strip()
        except Exception:
            pass

    return default


THE_ODDS_API_KEY = _get_secret("THE_ODDS_API_KEY")
LIVE_TENNIS_API_KEY = _get_secret("LIVE_TENNIS_API_KEY")

# OddsPapi (proveedor secundario de cobertura)
ODDSPAPI_API_KEY = _get_secret("ODDSPAPI_API_KEY")

# Opcional: slugs separados por comas.
# Si se deja vacío, OddsPapi devuelve las casas disponibles en tu plan.
ODDSPAPI_BOOKMAKERS = _get_secret("ODDSPAPI_BOOKMAKERS")
