"""
Tennis Edge Pro · Odds Engine V7 One-Book-Per-Request

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

# OddsPapi Tennis IDs verified against current 2026 docs/examples.
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


def _oddspapi_list_payload(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        if payload.get("fixtureId"):
            return [payload]

        for key in (
            "data",
            "events",
            "fixtures",
            "items",
            "results",
        ):
            value = payload.get(key)

            if isinstance(value, list):
                return value

            if (
                isinstance(value, dict)
                and value.get("fixtureId")
            ):
                return [value]

    return []


def _oddspapi_get(path, params=None, timeout=25):
    """
    Request helper that preserves the useful API error body.
    This avoids another blind '400 Client Error'.
    """
    merged = {
        "apiKey": ODDSPAPI_API_KEY,
    }

    if params:
        merged.update(params)

    response = requests.get(
        f"{ODDSPAPI_BASE_URL}/{path}",
        params=merged,
        timeout=timeout,
    )

    if response.status_code != 200:
        body = str(
            response.text
            or ""
        ).strip()

        if len(body) > 500:
            body = body[:500] + "..."

        raise RuntimeError(
            f"OddsPapi {path}: HTTP {response.status_code}"
            + (
                f" · {body}"
                if body
                else ""
            )
        )

    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(
            f"OddsPapi {path}: JSON inválido"
        ) from exc


def _oddspapi_account():
    """
    /account no consume cuota según OddsPapi.
    Lo usamos como preflight para validar la key y comprobar
    que Tennis (sportId 12) está disponible en la suscripción.
    """
    payload = _oddspapi_get(
        "account",
        timeout=20,
    )

    subscriptions = (
        payload.get("subscriptions", [])
        if isinstance(payload, dict)
        else []
    )

    active = None

    for sub in subscriptions:
        if (
            isinstance(sub, dict)
            and sub.get("is_active")
        ):
            active = sub
            break

    if active is None and subscriptions:
        active = subscriptions[0]

    active = (
        active
        if isinstance(active, dict)
        else {}
    )

    sport_ids = active.get(
        "sport_ids",
        []
    ) or []

    sport_ids = {
        str(value)
        for value in sport_ids
    }

    if (
        sport_ids
        and str(TENNIS_SPORT_ID)
        not in sport_ids
    ):
        raise RuntimeError(
            "OddsPapi account: tu suscripción no incluye "
            "Tennis (sportId 12)."
        )

    bookmaker_map = active.get(
        "bookmakers",
        {}
    )

    bookmaker_slugs = []

    if isinstance(bookmaker_map, dict):
        bookmaker_slugs = [
            str(slug).strip()
            for slug in bookmaker_map.keys()
            if str(slug).strip()
        ]

    return {
        "request_limit": active.get(
            "request_limit"
        ),
        "request_count": active.get(
            "request_count"
        ),
        "bookmakers": bookmaker_slugs,
        "sport_ids": sorted(sport_ids),
    }


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
    market_id,
    p1_outcome_id,
    p2_outcome_id,
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
            str(market_id)
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
            str(p1_outcome_id),
            {}
        )
        p2_outcome = outcomes.get(
            str(p2_outcome_id),
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


def _merge_oddspapi_raw_events(target, incoming):
    """
    Fusiona respuestas de OddsPapi del mismo fixture obtenidas
    desde casas distintas. odds-by-tournaments exige EXACTAMENTE
    una casa por petición.
    """
    for item in incoming:
        if not isinstance(item, dict):
            continue

        fixture_id = str(
            item.get("fixtureId", "")
            or ""
        ).strip()

        if not fixture_id:
            continue

        if fixture_id not in target:
            clone = dict(item)
            clone["bookmakerOdds"] = dict(
                item.get("bookmakerOdds", {})
                if isinstance(
                    item.get("bookmakerOdds"),
                    dict
                )
                else {}
            )
            target[fixture_id] = clone
            continue

        existing = target[fixture_id]

        existing_books = existing.get(
            "bookmakerOdds",
            {}
        )

        if not isinstance(existing_books, dict):
            existing_books = {}

        new_books = item.get(
            "bookmakerOdds",
            {}
        )

        if isinstance(new_books, dict):
            existing_books.update(new_books)

        existing[
            "bookmakerOdds"
        ] = existing_books


def _get_oddspapi_odds():
    """
    V7 · OddsPapi eficiente y compatible con el endpoint real.

    /odds-by-tournaments exige EXACTAMENTE UNA casa por petición.
    Por eso:
      1) /account -> obtenemos las casas incluidas en la suscripción.
      2) /fixtures -> obtenemos tenis pre-match con odds.
      3) Hacemos una llamada por casa, máximo 2 casas.
      4) Fusionamos ambas respuestas por fixture.

    Con 2 casas seguimos cumpliendo MIN_VALID_BOOKMAKERS=2.
    Si la cuenta sólo incluye 1 casa, OddsPapi servirá para análisis,
    pero sus mercados no serán Top Pick salvo que el mismo partido
    también tenga otra casa válida procedente de The Odds API.
    """
    if not ODDSPAPI_API_KEY:
        return {
            "ok": False,
            "events": [],
            "message": "ODDSPAPI_API_KEY no configurada.",
            "fixtures": 0,
            "tournaments": 0,
            "account": {},
            "bookmakers_used": [],
        }

    try:
        account = _oddspapi_account()

        account_books = [
            str(x).strip()
            for x in account.get(
                "bookmakers",
                []
            )
            if str(x).strip()
        ]

        secret_books = [
            x.strip()
            for x in str(
                ODDSPAPI_BOOKMAKERS
                or ""
            ).split(",")
            if x.strip()
        ]

        # Si el usuario especificó casas y pertenecen a su cuenta,
        # respetamos esa preferencia. Si no, usamos las de /account.
        if secret_books:
            allowed = set(account_books)
            chosen_books = [
                x
                for x in secret_books
                if (
                    not allowed
                    or x in allowed
                )
            ]
        else:
            chosen_books = list(
                account_books
            )

        # Máximo 2: suficiente para nuestro filtro profesional y
        # protege la cuota del plan.
        chosen_books = chosen_books[:2]

        if not chosen_books:
            return {
                "ok": False,
                "events": [],
                "message": (
                    "OddsPapi account no devuelve bookmakers "
                    "disponibles en la suscripción."
                ),
                "fixtures": 0,
                "tournaments": 0,
                "account": account,
                "bookmakers_used": [],
            }

        now = datetime.now(
            timezone.utc
        )

        date_from = now.strftime(
            "%Y-%m-%d"
        )
        date_to = (
            now + timedelta(days=2)
        ).strftime(
            "%Y-%m-%d"
        )

        # Para hasOdds basta consultar la primera casa disponible.
        fixture_params = {
            "sportId": TENNIS_SPORT_ID,
            "from": date_from,
            "to": date_to,
            "statusId": 0,
            "hasOdds": "true",
            "bookmakers": chosen_books[0],
            "language": "en",
        }

        fixtures_payload = _oddspapi_get(
            "fixtures",
            params=fixture_params,
            timeout=30,
        )

        fixtures = _oddspapi_list_payload(
            fixtures_payload
        )

        fixture_map = {}

        for fixture in fixtures:
            if not isinstance(
                fixture,
                dict
            ):
                continue

            fixture_id = str(
                fixture.get(
                    "fixtureId",
                    ""
                )
                or ""
            ).strip()

            p1 = str(
                fixture.get(
                    "participant1Name",
                    ""
                )
                or ""
            ).strip()

            p2 = str(
                fixture.get(
                    "participant2Name",
                    ""
                )
                or ""
            ).strip()

            tournament_id = fixture.get(
                "tournamentId"
            )

            if (
                not fixture_id
                or not p1
                or not p2
                or tournament_id is None
            ):
                continue

            fixture_map[
                fixture_id
            ] = {
                "participant1Name": p1,
                "participant2Name": p2,
                "tournamentId": tournament_id,
                "tournamentName": fixture.get(
                    "tournamentName",
                    "",
                ),
                "startTime": fixture.get(
                    "startTime"
                ),
            }

        tournament_ids = sorted(
            {
                str(
                    item[
                        "tournamentId"
                    ]
                )
                for item in fixture_map.values()
            }
        )

        if not tournament_ids:
            return {
                "ok": True,
                "events": [],
                "message": "",
                "fixtures": len(
                    fixture_map
                ),
                "tournaments": 0,
                "account": account,
                "bookmakers_used": chosen_books,
            }

        merged_raw = {}

        for bookmaker in chosen_books:
            odds_params = {
                "tournamentIds": ",".join(
                    tournament_ids
                ),
                # Endpoint real: EXACTAMENTE una casa por llamada.
                "bookmakers": bookmaker,
                "language": "en",
                "verbosity": 3,
                "oddsFormat": "decimal",
            }

            odds_payload = _oddspapi_get(
                "odds-by-tournaments",
                params=odds_params,
                timeout=40,
            )

            odds_rows = (
                _oddspapi_list_payload(
                    odds_payload
                )
            )

            _merge_oddspapi_raw_events(
                merged_raw,
                odds_rows,
            )

        normalized = []

        for fixture_id, odds_event in merged_raw.items():
            fixture = fixture_map.get(
                fixture_id
            )

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
                    TENNIS_WINNER_MARKET_ID,
                    TENNIS_P1_OUTCOME_ID,
                    TENNIS_P2_OUTCOME_ID,
                )
            )

            if not bookmakers:
                continue

            normalized.append(
                {
                    "id": (
                        f"oddspapi-{fixture_id}"
                    ),
                    "home_team": p1,
                    "away_team": p2,
                    "commence_time": (
                        odds_event.get(
                            "startTime"
                        )
                        or fixture.get(
                            "startTime"
                        )
                    ),
                    "sport_key": (
                        "tennis_oddspapi_"
                        + normalizar_nombre(
                            fixture.get(
                                "tournamentName",
                                "tennis",
                            )
                        ).replace(
                            " ",
                            "_"
                        )
                    ),
                    "odds_provider": (
                        "oddspapi"
                    ),
                    "bookmakers": bookmakers,
                }
            )

        warning = ""

        if len(chosen_books) < 2:
            warning = (
                "OddsPapi: la suscripción sólo aporta 1 bookmaker; "
                "Top Picks exige 2 casas válidas."
            )

        return {
            "ok": True,
            "events": normalized,
            "message": warning,
            "fixtures": len(
                fixture_map
            ),
            "tournaments": len(
                tournament_ids
            ),
            "account": account,
            "bookmakers_used": chosen_books,
        }

    except Exception as exc:
        return {
            "ok": False,
            "events": [],
            "message": str(exc),
            "fixtures": 0,
            "tournaments": 0,
            "account": {},
            "bookmakers_used": [],
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
                "account": secondary.get(
                    "account",
                    {},
                ),
                "bookmakers_used": secondary.get(
                    "bookmakers_used",
                    [],
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
