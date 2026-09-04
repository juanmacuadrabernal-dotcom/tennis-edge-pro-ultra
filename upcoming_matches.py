"""
Tennis Edge Pro · upcoming_matches.py
FIX V3 — compatible con Live Tennis API OpenAPI 1.3.1

Motivo del fix:
- /fixtures SOLO acepta: tour, limit, offset.
- La versión anterior enviaba draw=singles -> parámetro no soportado.
- Consultamos ATP y Challenger por separado usando el filtro oficial.
"""

import requests

from api_config import LIVE_TENNIS_API_KEY


BASE_URL = "https://api.livetennisapi.com/api/public/v1"


def _headers():
    return {
        "Authorization": f"Bearer {LIVE_TENNIS_API_KEY}",
        "X-API-Key": LIVE_TENNIS_API_KEY,
        "Accept": "application/json",
    }


def _fetch_fixture_page(tour, limit=200, offset=0):
    """
    /fixtures acepta oficialmente:
    - tour
    - limit
    - offset
    """
    params = {
        "tour": tour,
        "limit": limit,
        "offset": offset,
    }

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

        if len(body) > 1000:
            body = body[:1000] + "..."

        retry_after = response.headers.get(
            "Retry-After"
        )

        print(
            "Error Live Tennis API /fixtures "
            f"(tour={tour}): HTTP {response.status_code}"
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

        return [], {
            "has_more": False,
            "total": None,
        }

    try:
        payload = response.json()
    except ValueError:
        print(
            "Error Live Tennis API /fixtures "
            f"(tour={tour}): JSON inválido."
        )
        return [], {
            "has_more": False,
            "total": None,
        }

    if not isinstance(payload, dict):
        print(
            "Error Live Tennis API /fixtures "
            f"(tour={tour}): formato inesperado."
        )
        return [], {
            "has_more": False,
            "total": None,
        }

    data = payload.get(
        "data",
        []
    )

    meta = payload.get(
        "meta",
        {}
    )

    if not isinstance(data, list):
        data = []

    if not isinstance(meta, dict):
        meta = {}

    return data, meta


def _normalize_fixture(match):
    if not isinstance(match, dict):
        return None

    player1 = str(
        match.get("player1_name", "")
        or ""
    ).strip()

    player2 = str(
        match.get("player2_name", "")
        or ""
    ).strip()

    # Según OpenAPI los nombres están siempre presentes,
    # pero somos conservadores si llega una fila dañada.
    if not player1 or not player2:
        return None

    fixture_id = match.get(
        "id"
    )

    return {
        "id": fixture_id,
        "match_id": fixture_id,

        "event_date": (
            match.get("event_date")
            or ""
        ),
        "start_time": (
            match.get("start_time")
            or ""
        ),

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


def get_upcoming_matches(tour=None, limit=200):
    """
    Devuelve LISTA de diccionarios compatible con app.py.

    Sin tour:
      - 1 llamada ATP
      - 1 llamada Challenger

    Con tour:
      - sólo consulta ese tour si es válido.
    """
    if not LIVE_TENNIS_API_KEY:
        print(
            "Error Live Tennis API: "
            "LIVE_TENNIS_API_KEY no configurada."
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

    requested = str(
        tour
        or ""
    ).strip().lower()

    if requested:
        if requested not in {
            "atp",
            "challenger",
        }:
            print(
                "Live Tennis API: tour no soportado "
                f"por Tennis Edge Pro: {requested}"
            )
            return []

        tours = [
            requested
        ]
    else:
        tours = [
            "atp",
            "challenger",
        ]

    merged = {}

    for current_tour in tours:
        try:
            rows, meta = _fetch_fixture_page(
                current_tour,
                limit=limit,
                offset=0,
            )
        except requests.exceptions.RequestException as exc:
            print(
                "Error conectando con Live Tennis API "
                f"(tour={current_tour}): {exc}"
            )
            continue

        print(
            "Live Tennis API /fixtures OK "
            f"(tour={current_tour}): "
            f"{len(rows)} recibidos"
            + (
                f" · total={meta.get('total')}"
                if meta.get("total") is not None
                else ""
            )
            + (
                " · has_more=True"
                if meta.get("has_more")
                else ""
            )
        )

        for raw in rows:
            item = _normalize_fixture(
                raw
            )

            if item is None:
                continue

            fixture_id = item.get(
                "id"
            )

            # ID es estable según OpenAPI.
            if fixture_id is not None:
                key = (
                    "id",
                    str(fixture_id)
                )
            else:
                key = (
                    "fallback",
                    str(item.get("event_date", "")),
                    str(item.get("start_time", "")),
                    item["player1"].lower(),
                    item["player2"].lower(),
                )

            merged[key] = item

    result = list(
        merged.values()
    )

    result.sort(
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
        "Tennis Edge Pro próximos partidos: "
        f"{len(result)} ATP + Challenger."
    )

    return result


if __name__ == "__main__":
    upcoming = get_upcoming_matches()

    print(
        f"Próximos ATP/Challenger: {len(upcoming)}"
    )

    for item in upcoming[:30]:
        print(
            f"{item.get('event_date')} "
            f"{item.get('start_time')} · "
            f"{item.get('tour')} · "
            f"{item.get('tournament')} · "
            f"{item.get('player1')} vs "
            f"{item.get('player2')}"
        )
