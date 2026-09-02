from datetime import datetime, timezone

import requests

from api_config import LIVE_TENNIS_API_KEY


BASE_URL = "https://api.livetennisapi.com/api/public/v1"


def _headers():
    return {
        "X-API-Key": LIVE_TENNIS_API_KEY,
        "Authorization": (
            f"Bearer {LIVE_TENNIS_API_KEY}"
        ),
        "Accept": "application/json",
    }


def _extract_match(payload):
    if not isinstance(
        payload,
        dict
    ):
        return None

    data = payload.get(
        "data"
    )

    if isinstance(
        data,
        dict
    ):
        return data

    if (
        isinstance(
            data,
            list
        )
        and data
        and isinstance(
            data[0],
            dict
        )
    ):
        return data[0]

    return payload


def _player_name(
    match,
    side
):
    players = match.get(
        "players"
    )

    if not isinstance(
        players,
        dict
    ):
        return ""

    player = players.get(
        side
    )

    if isinstance(
        player,
        dict
    ):
        return str(
            player.get(
                "name",
                ""
            )
            or ""
        ).strip()

    return ""


def _sets_won(score):
    """
    Intenta leer el marcador de sets de forma conservadora.

    Formatos soportados:
    - {"sets": [3, 1]}
    - {"sets": {"p1": 3, "p2": 1}}
    - {"sets": {"player1": 3, "player2": 1}}

    Si el formato no es inequívoco devuelve (None, None).
    """
    if not isinstance(score, dict):
        return (None, None)

    sets = score.get("sets")

    if (
        isinstance(sets, (list, tuple))
        and len(sets) == 2
        and all(
            isinstance(value, (int, float))
            for value in sets
        )
    ):
        try:
            return (int(sets[0]), int(sets[1]))
        except Exception:
            return (None, None)

    if isinstance(sets, dict):
        pairs = [
            ("p1", "p2"),
            ("player1", "player2"),
            ("home", "away"),
        ]

        for left, right in pairs:
            if left in sets and right in sets:
                try:
                    return (
                        int(sets[left]),
                        int(sets[right]),
                    )
                except Exception:
                    return (None, None)

    return (None, None)


def _score_text(score):
    if not isinstance(
        score,
        dict
    ):
        return ""

    sets = score.get(
        "sets"
    )

    if (
        isinstance(
            sets,
            (list, tuple)
        )
        and len(sets) >= 2
    ):
        try:
            return (
                f"{int(sets[0])}"
                f"-{int(sets[1])}"
            )
        except Exception:
            pass

    games = score.get(
        "games"
    )

    if games:
        return str(
            games
        )

    return ""


def get_live_match_result(
    fixture_id
):
    """
    Lee UN partido por su id y devuelve también:
    - id real respondido por la API
    - nombres p1/p2
    - scheduled_time
    - status / winner

    Esos campos se usan después para impedir que un ID
    equivocado liquide otro partido.
    """
    if fixture_id in (
        None,
        ""
    ):
        return {
            "ok": False,
            "message": (
                "Fixture sin ID."
            ),
        }

    try:
        response = requests.get(
            (
                f"{BASE_URL}/matches/"
                f"{fixture_id}"
            ),
            headers=_headers(),
            timeout=20
        )

        if response.status_code == 429:
            return {
                "ok": False,
                "rate_limited": True,
                "message": (
                    "Live Tennis API ha alcanzado "
                    "el límite temporal."
                ),
                "retry_after": (
                    response.headers.get(
                        "Retry-After"
                    )
                ),
            }

        if response.status_code == 404:
            return {
                "ok": False,
                "not_found": True,
                "message": (
                    "Partido no encontrado o "
                    "todavía sin detalle."
                ),
            }

        response.raise_for_status()

        match = _extract_match(
            response.json()
        )

        if not match:
            return {
                "ok": False,
                "message": (
                    "Respuesta de partido vacía."
                ),
            }

        api_match_id = match.get(
            "id"
        )

        status = str(
            match.get(
                "status",
                ""
            )
            or ""
        ).strip().lower()

        winner = match.get(
            "winner"
        )

        try:
            winner = (
                int(winner)
                if winner is not None
                else None
            )
        except Exception:
            winner = None

        return {
            "ok": True,
            "requested_id": str(
                fixture_id
            ),
            "match_id": (
                str(api_match_id)
                if api_match_id is not None
                else ""
            ),
            "player1_name": _player_name(
                match,
                "p1"
            ),
            "player2_name": _player_name(
                match,
                "p2"
            ),
            "status": status,
            "winner": winner,
            "event_status": (
                match.get(
                    "event_status"
                )
            ),
            "score": (
                match.get(
                    "score"
                )
            ),
            "score_text": _score_text(
                match.get(
                    "score"
                )
            ),
            "sets_won": _sets_won(
                match.get(
                    "score"
                )
            ),
            "scheduled_time": (
                match.get(
                    "scheduled_time"
                )
            ),
            "checked_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        }

    except Exception as exc:
        return {
            "ok": False,
            "message": str(exc),
        }
