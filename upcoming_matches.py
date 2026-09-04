"""
Tennis Edge Pro · upcoming_matches.py
Versión estable compatible con Live Tennis API (2026-09).

IMPORTANTE:
- /fixtures devuelve player1_name / player2_name EN PLANO.
- La app espera una LISTA de diccionarios con player1 / player2.
- Una sola llamada trae fixtures y filtramos ATP + Challenger localmente.
"""

import requests

from api_config import LIVE_TENNIS_API_KEY


BASE_URL = "https://api.livetennisapi.com/api/public/v1"


def _headers():
    """
    Live Tennis API acepta ambos esquemas.
    Enviamos los dos para máxima compatibilidad.
    """
    return {
        "Authorization": f"Bearer {LIVE_TENNIS_API_KEY}",
        "X-API-Key": LIVE_TENNIS_API_KEY,
        "Accept": "application/json",
    }


def _is_atp_or_challenger(fixture):
    """
    El campo 'tour' puede ser granular (p.ej. challenger_men).
    Si viene vacío, usamos el nombre del torneo como fallback.
    """
    tour = str(
        fixture.get("tour", "")
        or ""
    ).strip().lower()

    tournament = str(
        fixture.get("tournament", "")
        or ""
    ).strip().lower()

    if (
        "challenger" in tour
        or tour == "atp"
        or tour.startswith("atp_")
    ):
        return True

    if (
        "challenger" in tournament
        or tournament.startswith("atp ")
        or tournament.startswith("atp-")
    ):
        return True

    return False


def get_upcoming_matches(tour=None, limit=200):
    """
    Devuelve LISTA de dicts compatible con app.py:

    id, match_id, event_date, start_time,
    player1, player2, player1_id, player2_id,
    tournament, surface, round, tour, status

    Si 'tour' se especifica y es atp/challenger, se envía a la API.
    Si no, hacemos una sola llamada y filtramos ATP + Challenger localmente.
    """
    if not LIVE_TENNIS_API_KEY:
        print(
            "Error Live Tennis API: LIVE_TENNIS_API_KEY no configurada."
        )
        return []

    try:
        limit = int(limit)
    except Exception:
        limit = 200

    limit = max(
        1,
        min(
            limit,
            200
        )
    )

    params = {
        "limit": limit,
        "offset": 0,
        # La app sólo trabaja con partidos individuales.
        "draw": "singles",
    }

    requested_tour = str(
        tour
        or ""
    ).strip().lower()

    # Sólo enviamos vocabulario que el endpoint acepta.
    if requested_tour in {
        "atp",
        "challenger",
    }:
        params["tour"] = requested_tour

    try:
        response = requests.get(
            f"{BASE_URL}/fixtures",
            headers=_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            body = str(
                response.text
                or ""
            ).strip()

            if len(body) > 800:
                body = body[:800] + "..."

            retry_after = response.headers.get(
                "Retry-After"
            )

            print(
                "Error Live Tennis API /fixtures: "
                f"HTTP {response.status_code}"
                + (
                    f" · Retry-After={retry_after}"
                    if retry_after
                    else ""
                )
                + (
                    f" · {body}"
                    if body
                    else ""
                )
            )

            return []

        payload = response.json()

    except requests.exceptions.RequestException as exc:
        print(
            f"Error conectando con Live Tennis API: {exc}"
        )
        return []

    except ValueError:
        print(
            "Error Live Tennis API: /fixtures no devolvió JSON válido."
        )
        return []

    matches = (
        payload.get("data", [])
        if isinstance(payload, dict)
        else []
    )

    if not isinstance(matches, list):
        print(
            "Error Live Tennis API: formato inesperado en /fixtures."
        )
        return []

    rows = []

    for match in matches:
        if not isinstance(match, dict):
            continue

        # Si no se pidió un tour concreto, dejamos sólo ATP + Challenger.
        if not requested_tour and not _is_atp_or_challenger(match):
            continue

        # ESQUEMA REAL DE /fixtures:
        # player1_name / player2_name son campos planos.
        player1 = str(
            match.get("player1_name", "")
            or ""
        ).strip()

        player2 = str(
            match.get("player2_name", "")
            or ""
        ).strip()

        # Sin los dos nombres el modelo no puede resolver el partido.
        if not player1 or not player2:
            continue

        fixture_id = match.get("id")

        event_date = (
            match.get("event_date")
            or ""
        )

        start_time = (
            match.get("start_time")
            or ""
        )

        rows.append(
            {
                "id": fixture_id,
                # Conservamos ambos nombres porque el lock pre-match
                # y el tracker ya contemplan los dos campos.
                "match_id": fixture_id,

                "event_date": event_date,
                "start_time": start_time,

                "player1": player1,
                "player2": player2,

                "player1_id": match.get(
                    "player1_id"
                ),
                "player2_id": match.get(
                    "player2_id"
                ),

                "tournament": (
                    match.get("tournament")
                    or ""
                ),
                "surface": (
                    match.get("surface")
                    or ""
                ),
                "round": (
                    match.get("round")
                    or match.get("round_code")
                    or ""
                ),
                "round_code": (
                    match.get("round_code")
                    or ""
                ),
                "tour": (
                    match.get("tour")
                    or ""
                ),
                "status": (
                    match.get("status")
                    or "upcoming"
                ),
            }
        )

    # Orden determinista: fecha + hora + torneo.
    rows.sort(
        key=lambda item: (
            str(
                item.get(
                    "event_date",
                    ""
                )
            ),
            str(
                item.get(
                    "start_time",
                    ""
                )
            ),
            str(
                item.get(
                    "tournament",
                    ""
                )
            ),
            str(
                item.get(
                    "player1",
                    ""
                )
            ),
        )
    )

    print(
        "Live Tennis API /fixtures OK: "
        f"{len(matches)} recibidos · "
        f"{len(rows)} ATP/Challenger singles válidos."
    )

    return rows


if __name__ == "__main__":
    upcoming = get_upcoming_matches()

    print(
        f"Próximos ATP/Challenger: {len(upcoming)}"
    )

    for item in upcoming[:20]:
        print(
            f"{item.get('event_date')} "
            f"{item.get('start_time')} · "
            f"{item.get('tournament')} · "
            f"{item.get('player1')} vs "
            f"{item.get('player2')}"
        )
