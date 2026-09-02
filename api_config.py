"""
Configuración segura para Tennis Edge Pro.

- En Streamlit Community Cloud lee las claves desde st.secrets.
- En local también admite variables de entorno.
- Este archivo NO contiene ninguna clave privada y sí puede subirse a GitHub.
"""

import os

try:
    import streamlit as st
except Exception:
    st = None


def _get_secret(name: str, default: str = "") -> str:
    # 1) Variable de entorno
    value = os.getenv(name)
    if value:
        return str(value).strip()

    # 2) Streamlit Secrets
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
