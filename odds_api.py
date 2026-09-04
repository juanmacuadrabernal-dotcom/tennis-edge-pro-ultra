"""
Tennis Edge Pro · Odds Engine V4 Multi-Provider

Proveedor principal:
- The Odds API

Proveedor secundario opcional:
- OddsPapi v4

Interfaz compatible con la app actual:
- get_tennis_odds()
- construir_indice_cuotas()
- buscar_mejores_cuotas()

OddsPapi:
- sportId 12 = Tennis
- market 121 = Match Winner
- outcome 121 = participant 1
- outcome 122 = participant 2
"""

import statistics
from datetime import datetime, timedelta, timezone

import requests

from api_config import (
    THE_ODDS_API_KEY,
    ODDSPAPI_API_KEY,
    ODDSPAPI_BOOKMAKERS,
)
from player_resolver import normalizar_nombre


PRIMARY_BASE_URL = "https://api.the-odds-api.com/v4"
ODDSPAPI_BASE_URL = "https://api.oddspapi.io/v4"

TENNIS_SPORT_ID = 12
TENNIS_WINNER_MARKET_ID = "121"
TENNIS_P1_OUTCOME_ID = "121"
TENNIS_P2_OUTCOME_ID = "122"

MIN_ODDS = 1.01
MAX_ODDS = 100.0

MIN_IMPLIED_SUM = 0.90
MAX_IMPLIED_SUM = 1.20
MIN_VALID_BOOKMAKERS = 2
OUTLIER_FACTOR = 1.50

EXCHANGE_TOKENS = (
    "smarkets",
    "matchbook",
    "betfair_ex",
    "betfair exchange",
)


def _clave_partido(jugador_a, jugador_b):
    a = normalizar_nombre(jugador_a)
    b = normalizar_nombre(jugador_b)

    if not a or not b:
        return None

    return tuple(sorted((a, b)))


def _safe_odds(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if value < MIN_ODDS or value > MAX_ODDS:
        return None

    return value


def _parse_iso(value):
    if not value:
        return None

    try:
        raw = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _latest_time_string(a, b):
    da = _parse_iso(a)
    db = _parse_iso(b)

    if da is None:
        return b
    if db is None:
        return a

    return a if da >= db else b


def _es_exchange(bookmaker):
    key = str(bookmaker.get("key", "")).lower()
    title = str(bookmaker.get("title", "")).lower()
    text = key + " " + title

    return any(
        token in text
        for token in EXCHANGE_TOKENS
    )


def _extraer_linea_h2h(bookmaker, home, away):
    home_norm = normalizar_nombre(home)
    away_norm = normalizar_nombre(away)

    if not home_norm or not away_norm:
        return None

    outcomes = {}

    for market in bookmaker.get("markets", []):
        if market.get("key") != "h2h":
            continue

        for outcome in market.get("outcomes", []):
            name = normalizar_nombre(
                outcome.get("name")
            )
            price = _safe_odds(
                outcome.get("price")
            )

            if not name or price is None:
                continue

            outcomes[name] = price

    if (
        home_norm not in outcomes
        or away_norm not in outcomes
    ):
        return None

    home_odds = outcomes[home_norm]
    away_odds = outcomes[away_norm]

    implied_sum = (
        1.0 / home_odds
        +
        1.0 / away_odds
    )

    if not (
        MIN_IMPLIED_SUM
        <= implied_sum
        <= MAX_IMPLIED_SUM
    ):
        return None

    return {
        "home_odds": home_odds,
        "away_odds": away_odds,
        "implied_sum": implied_sum,
    }


def _filtrar_outliers(lines, field):
    if not lines:
        return [], 0

    prices = [line[field] for line in lines]

    if len(prices) < 4:
        return lines, 0

    median_price = statistics.median(prices)
    max_allowed = median_price * OUTLIER_FACTOR

    filtered = [
        line
        for line in lines
        if line[field] <= max_allowed
    ]

    discarded = len(lines) - len(filtered)

    if not filtered:
        return lines, 0

    return filtered, discarded


def _market_quality(bookmaker_count):
    if bookmaker_count >= 6:
        return "Alta"
    if bookmaker_count >= 3:
        return "Media"
    if bookmaker_count >= MIN_VALID_BOOKMAKERS:
        return "Baja"
    return "Insuficiente"


# =========================================================
# THE ODDS API
# =========================================================

def get_active_atp_sports():
    if not THE_ODDS_API_KEY:
        return []

    response = requests.get(
        f"{PRIMARY_BASE_URL}/sports",
        params={"apiKey": THE_ODDS_API_KEY},
        timeout=20,
    )
    response.raise_for_status()

    sports = response.json()

    return [
        sport["key"]
        for sport in sports
        if (
            str(sport.get("group", "")).lower() == "tennis"
            and str(sport.get("key", "")).startswith("tennis_atp_")
            and sport.get("active", True)
        )
    ]


def _get_primary_odds():
    if not THE_ODDS_API_KEY:
        return {
            "ok": False,
            "events": [],
            "message": "THE_ODDS_API_KEY vacía.",
            "requests_remaining": None,
            "requests_used": None,
        }

    try:
        sport_keys = get_active_atp_sports()

        all_events = []
        remaining = None
        used = None

        for sport_key in sport_keys:
            response = requests.get(
                f"{PRIMARY_BASE_URL}/sports/{sport_key}/odds",
                params={
                    "apiKey": THE_ODDS_API_KEY,
                    "regions": "uk",
                    "markets": "h2h",
                    "oddsFormat": "decimal",
                },
                timeout=20,
            )
            response.raise_for_status()

            remaining = response.headers.get(
                "x-requests-remaining",
                remaining,
            )
            used = response.headers.get(
                "x-requests-used",
                used,
            )

            for event in response.json():
                event = dict(event)
                event["sport_key"] = sport_key
                event["odds_provider"] = "the-odds-api"
                all_events.append(event)

        return {
            "ok": True,
            "events": all_events,
            "message": "",
            "requests_remaining": remaining,
            "requests_used": used,
        }

    except Exception as exc:
        return {
            "ok": False,
            "events": [],
            "message": str(exc),
            "requests_remaining": None,
            "requests_used": None,
        }


# =========================================================
# ODDSPAPI
# =========================================================

def _oddspapi_params(extra=None):
    params = {
        "apiKey": ODDSPAPI_API_KEY,
        "language": "en",
    }

    if extra:
        params.update(extra)

    return params


def _extract_current_player_price(player_block):
    """
    OddsPapi actual: players['0'] suele ser un objeto.
    Soportamos también lista por compatibilidad.
    """
    if isinstance(player_block, dict):
        if player_block.get("active") is False:
            return None
        return _safe_odds(
            player_block.get("price")
        )

    if isinstance(player_block, list):
        for item in reversed(player_block):
            if not isinstance(item, dict):
                continue
            if item.get("active") is False:
                continue

            price = _safe_odds(
                item.get("price")
            )
            if price is not None:
                return price

    return None


def _parse_oddspapi_bookmakers(
    odds_event,
    participant1_name,
    participant2_name,
):
    raw_books = odds_event.get(
        "bookmakerOdds",
        {}
    )

    if not isinstance(raw_books, dict):
        return []

    output = []

    for slug, book in raw_books.items():
        if not isinstance(book, dict):
            continue

        if book.get("bookmakerIsActive") is False:
            continue

        if book.get("suspended") is True:
            continue

        markets = book.get(
            "markets",
            {}
        )

        if not isinstance(markets, dict):
            continue

        market = markets.get(
            TENNIS_WINNER_MARKET_ID
        )

        if not isinstance(market, dict):
            continue

        if market.get("marketActive") is False:
            continue

        outcomes = market.get(
            "outcomes",
            {}
        )

        if not isinstance(outcomes, dict):
            continue

        p1_outcome = outcomes.get(
            TENNIS_P1_OUTCOME_ID,
            {}
        )
        p2_outcome = outcomes.get(
            TENNIS_P2_OUTCOME_ID,
            {}
        )

        p1_players = (
            p1_outcome.get("players", {})
            if isinstance(p1_outcome, dict)
            else {}
        )
        p2_players = (
            p2_outcome.get("players", {})
            if isinstance(p2_outcome, dict)
            else {}
        )

        p1_price = _extract_current_player_price(
            p1_players.get("0")
            if isinstance(p1_players, dict)
            else None
        )
        p2_price = _extract_current_player_price(
            p2_players.get("0")
            if isinstance(p2_players, dict)
            else None
        )

        if p1_price is None or p2_price is None:
            continue

        output.append(
            {
                "key": f"oddspapi_{slug}",
                "title": str(slug),
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {
                                "name": participant1_name,
                                "price": p1_price,
                            },
                            {
                                "name": participant2_name,
                                "price": p2_price,
                            },
                        ],
                    }
                ],
            }
        )

    return output


def _get_oddspapi_odds():
    """
    Dos requests por refresco:
    1) fixtures de tenis con odds en una ventana <48h
    2) odds-by-tournaments para los tournamentIds encontrados

    Así evitamos 1 request por partido.
    """
    if not ODDSPAPI_API_KEY:
        return {
            "ok": False,
            "events": [],
            "message": "ODDSPAPI_API_KEY no configurada.",
            "fixtures": 0,
            "tournaments": 0,
        }

    try:
        now = datetime.now(timezone.utc)

        # Ventana total 42h (<48h).
        date_from = (
            now - timedelta(hours=2)
        ).isoformat().replace("+00:00", "Z")

        date_to = (
            now + timedelta(hours=40)
        ).isoformat().replace("+00:00", "Z")

        fixture_response = requests.get(
            f"{ODDSPAPI_BASE_URL}/fixtures",
            params=_oddspapi_params(
                {
                    "sportId": TENNIS_SPORT_ID,
                    "from": date_from,
                    "to": date_to,
                    "hasOdds": "true",
                }
            ),
            timeout=25,
        )
        fixture_response.raise_for_status()

        fixtures = fixture_response.json()

        if not isinstance(fixtures, list):
            fixtures = []

        # Nos quedamos con fixtures que aún puedan ser pre-match.
        fixture_map = {}

        for fixture in fixtures:
            if not isinstance(fixture, dict):
                continue

            fixture_id = str(
                fixture.get("fixtureId", "")
                or ""
            ).strip()

            p1 = str(
                fixture.get("participant1Name", "")
                or ""
            ).strip()

            p2 = str(
                fixture.get("participant2Name", "")
                or ""
            ).strip()

            tournament_id = fixture.get(
                "tournamentId"
            )

            start_time = fixture.get(
                "startTime"
            )

            if (
                not fixture_id
                or not p1
                or not p2
                or tournament_id is None
            ):
                continue

            fixture_map[fixture_id] = {
                "participant1Name": p1,
                "participant2Name": p2,
                "tournamentId": tournament_id,
                "tournamentName": fixture.get(
                    "tournamentName",
                    "",
                ),
                "startTime": start_time,
                "statusId": fixture.get(
                    "statusId"
                ),
            }

        tournament_ids = sorted(
            {
                str(item["tournamentId"])
                for item in fixture_map.values()
            }
        )

        if not tournament_ids:
            return {
                "ok": True,
                "events": [],
                "message": "",
                "fixtures": len(fixture_map),
                "tournaments": 0,
            }

        odds_params = {
            "tournamentIds": ",".join(
                tournament_ids
            ),
            "language": "en",
            "verbosity": 3,
            "oddsFormat": "decimal",
        }

        books = str(
            ODDSPAPI_BOOKMAKERS
            or ""
        ).strip()

        if books:
            odds_params["bookmakers"] = books

        odds_response = requests.get(
            f"{ODDSPAPI_BASE_URL}/odds-by-tournaments",
            params=_oddspapi_params(
                odds_params
            ),
            timeout=35,
        )
        odds_response.raise_for_status()

        odds_payload = odds_response.json()

        if isinstance(odds_payload, dict):
            # Algunas respuestas pueden envolver la lista.
            for key in ("data", "events", "fixtures"):
                value = odds_payload.get(key)
                if isinstance(value, list):
                    odds_payload = value
                    break

        if not isinstance(odds_payload, list):
            odds_payload = []

        normalized = []

        for odds_event in odds_payload:
            if not isinstance(odds_event, dict):
                continue

            fixture_id = str(
                odds_event.get(
                    "fixtureId",
                    ""
                )
                or ""
            ).strip()

            fixture = fixture_map.get(
                fixture_id
            )

            # Sólo incorporamos los fixtures de nuestra ventana.
            if not fixture:
                continue

            p1 = fixture[
                "participant1Name"
            ]
            p2 = fixture[
                "participant2Name"
            ]

            bookmakers = (
                _parse_oddspapi_bookmakers(
                    odds_event,
                    p1,
                    p2,
                )
            )

            if not bookmakers:
                continue

            normalized.append(
                {
                    "id": f"oddspapi-{fixture_id}",
                    "home_team": p1,
                    "away_team": p2,
                    "commence_time": (
                        odds_event.get("startTime")
                        or fixture.get("startTime")
                    ),
                    "sport_key": (
                        "tennis_oddspapi_"
                        + normalizar_nombre(
                            fixture.get(
                                "tournamentName",
                                "tennis",
                            )
                        ).replace(" ", "_")
                    ),
                    "odds_provider": "oddspapi",
                    "bookmakers": bookmakers,
                }
            )

        return {
            "ok": True,
            "events": normalized,
            "message": "",
            "fixtures": len(fixture_map),
            "tournaments": len(tournament_ids),
        }

    except Exception as exc:
        return {
            "ok": False,
            "events": [],
            "message": str(exc),
            "fixtures": 0,
            "tournaments": 0,
        }


# =========================================================
# MERGE
# =========================================================

def _bookmaker_identity(bookmaker):
    return normalizar_nombre(
        bookmaker.get(
            "title",
            bookmaker.get(
                "key",
                "",
            ),
        )
    )


def _merge_events(events):
    merged = {}

    for event in events:
        key = _clave_partido(
            event.get("home_team"),
            event.get("away_team"),
        )

        if key is None:
            continue

        if key not in merged:
            base = dict(event)
            base["bookmakers"] = list(
                event.get("bookmakers", [])
            )
            base["odds_sources"] = [
                event.get(
                    "odds_provider",
                    "unknown",
                )
            ]
            merged[key] = base
            continue

        target = merged[key]

        target["commence_time"] = (
            _latest_time_string(
                target.get("commence_time"),
                event.get("commence_time"),
            )
        )

        source = event.get(
            "odds_provider",
            "unknown",
        )

        if source not in target["odds_sources"]:
            target["odds_sources"].append(
                source
            )

        existing = {
            _bookmaker_identity(book)
            for book in target.get(
                "bookmakers",
                [],
            )
            if _bookmaker_identity(book)
        }

        for book in event.get(
            "bookmakers",
            [],
        ):
            identity = _bookmaker_identity(
                book
            )

            if not identity:
                continue

            if identity in existing:
                continue

            target["bookmakers"].append(
                book
            )
            existing.add(identity)

    return list(merged.values())


def get_tennis_odds():
    primary = _get_primary_odds()
    secondary = _get_oddspapi_odds()

    combined = _merge_events(
        primary.get("events", [])
        +
        secondary.get("events", [])
    )

    messages = []

    if not primary.get("ok"):
        messages.append(
            "The Odds API: "
            + primary.get(
                "message",
                "error",
            )
        )

    if ODDSPAPI_API_KEY and not secondary.get("ok"):
        messages.append(
            "OddsPapi: "
            + secondary.get(
                "message",
                "error",
            )
        )

    return {
        "ok": bool(
            primary.get("ok")
            or secondary.get("ok")
        ),
        "message": " | ".join(messages),
        "events": combined,
        "requests_remaining": primary.get(
            "requests_remaining"
        ),
        "requests_used": primary.get(
            "requests_used"
        ),
        "providers": {
            "the_odds_api": {
                "ok": primary.get(
                    "ok",
                    False,
                ),
                "events": len(
                    primary.get(
                        "events",
                        [],
                    )
                ),
            },
            "oddspapi": {
                "enabled": bool(
                    ODDSPAPI_API_KEY
                ),
                "ok": secondary.get(
                    "ok",
                    False,
                ),
                "events": len(
                    secondary.get(
                        "events",
                        [],
                    )
                ),
                "fixtures": secondary.get(
                    "fixtures",
                    0,
                ),
                "tournaments": secondary.get(
                    "tournaments",
                    0,
                ),
                "message": secondary.get(
                    "message",
                    "",
                ),
            },
        },
    }


# =========================================================
# SANITIZADOR PROFESIONAL
# =========================================================

def construir_indice_cuotas(events):
    indice = {}

    for event in events:
        home = event.get("home_team")
        away = event.get("away_team")

        clave = _clave_partido(
            home,
            away,
        )

        if clave is None:
            continue

        home_norm = normalizar_nombre(home)
        away_norm = normalizar_nombre(away)

        valid_lines = []
        exchanges_discarded = 0
        invalid_lines_discarded = 0

        for bookmaker in event.get(
            "bookmakers",
            [],
        ):
            if _es_exchange(bookmaker):
                exchanges_discarded += 1
                continue

            line = _extraer_linea_h2h(
                bookmaker,
                home,
                away,
            )

            if line is None:
                invalid_lines_discarded += 1
                continue

            line["casa"] = bookmaker.get(
                "title",
                bookmaker.get(
                    "key",
                    "Bookmaker",
                ),
            )
            line["bookmaker_key"] = (
                bookmaker.get("key")
            )
            valid_lines.append(line)

        home_lines, out_home = (
            _filtrar_outliers(
                valid_lines,
                "home_odds",
            )
        )
        away_lines, out_away = (
            _filtrar_outliers(
                valid_lines,
                "away_odds",
            )
        )

        best_home = (
            max(
                home_lines,
                key=lambda x: x["home_odds"],
            )
            if home_lines
            else None
        )

        best_away = (
            max(
                away_lines,
                key=lambda x: x["away_odds"],
            )
            if away_lines
            else None
        )

        consensus_home = None
        consensus_away = None

        if valid_lines:
            median_home = statistics.median(
                [
                    line["home_odds"]
                    for line in valid_lines
                ]
            )
            median_away = statistics.median(
                [
                    line["away_odds"]
                    for line in valid_lines
                ]
            )

            raw_home = 1.0 / median_home
            raw_away = 1.0 / median_away
            total = raw_home + raw_away

            if total > 0:
                consensus_home = raw_home / total
                consensus_away = raw_away / total

        valid_count = len(valid_lines)

        market_ok = (
            valid_count >= MIN_VALID_BOOKMAKERS
            and best_home is not None
            and best_away is not None
        )

        cuotas = {}

        if best_home is not None:
            cuotas[home_norm] = {
                "cuota": best_home["home_odds"],
                "casa": best_home["casa"],
            }

        if best_away is not None:
            cuotas[away_norm] = {
                "cuota": best_away["away_odds"],
                "casa": best_away["casa"],
            }

        indice[clave] = {
            "home_team": home,
            "away_team": away,
            "commence_time": event.get(
                "commence_time"
            ),
            "sport_key": event.get(
                "sport_key"
            ),
            "odds_sources": event.get(
                "odds_sources",
                [
                    event.get(
                        "odds_provider",
                        "unknown",
                    )
                ],
            ),
            "cuotas": cuotas,
            "market_ok": market_ok,
            "market_quality": _market_quality(
                valid_count
            ),
            "valid_bookmakers": valid_count,
            "exchanges_discarded": exchanges_discarded,
            "invalid_lines_discarded": invalid_lines_discarded,
            "outliers_discarded": max(
                out_home,
                out_away,
            ),
            "consensus": {
                home_norm: consensus_home,
                away_norm: consensus_away,
            },
        }

    return indice


def buscar_mejores_cuotas(
    indice,
    jugador_a,
    jugador_b,
):
    clave = _clave_partido(
        jugador_a,
        jugador_b,
    )

    if clave is None:
        return None

    event = indice.get(clave)

    if not event:
        return None

    if not event.get(
        "market_ok",
        False,
    ):
        return None

    nombre_a = normalizar_nombre(
        jugador_a
    )
    nombre_b = normalizar_nombre(
        jugador_b
    )

    cuota_a = event[
        "cuotas"
    ].get(nombre_a)
    cuota_b = event[
        "cuotas"
    ].get(nombre_b)

    if not cuota_a or not cuota_b:
        return None

    consensus = event.get(
        "consensus",
        {},
    )

    return {
        "jugador_a": jugador_a,
        "jugador_b": jugador_b,
        "cuota_a": cuota_a["cuota"],
        "casa_a": cuota_a["casa"],
        "cuota_b": cuota_b["cuota"],
        "casa_b": cuota_b["casa"],
        "commence_time": event.get(
            "commence_time"
        ),
        "sport_key": event.get(
            "sport_key"
        ),
        "odds_sources": event.get(
            "odds_sources",
            [],
        ),
        "calidad_mercado": event.get(
            "market_quality",
            "N/D",
        ),
        "casas_validas": event.get(
            "valid_bookmakers",
            0,
        ),
        "outliers_descartados": event.get(
            "outliers_discarded",
            0,
        ),
        "exchanges_descartados": event.get(
            "exchanges_discarded",
            0,
        ),
        "prob_consenso_a": consensus.get(
            nombre_a
        ),
        "prob_consenso_b": consensus.get(
            nombre_b
        ),
    }
