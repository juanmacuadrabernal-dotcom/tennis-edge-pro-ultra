import statistics

import requests

from api_config import THE_ODDS_API_KEY
from player_resolver import normalizar_nombre


BASE_URL = "https://api.the-odds-api.com/v4"

MIN_ODDS = 1.01
MAX_ODDS = 100.0

# Una línea individual de una casa se considera razonable si
# la suma de probabilidades implícitas de ambos jugadores cae
# dentro de este rango.
MIN_IMPLIED_SUM = 0.90
MAX_IMPLIED_SUM = 1.20

# Para calcular VALUE exigimos al menos dos casas válidas.
MIN_VALID_BOOKMAKERS = 2

# Si tenemos varias casas, descartamos una cuota que se aleje
# demasiado por arriba de la mediana del mercado.
OUTLIER_FACTOR = 1.50

# Exchanges: pueden llevar comisión, liquidez o precios no
# equivalentes a una cuota deportiva tradicional.
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

    return tuple(
        sorted(
            (a, b)
        )
    )


def _safe_odds(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if (
        value < MIN_ODDS
        or value > MAX_ODDS
    ):
        return None

    return value


def _es_exchange(bookmaker):
    key = str(
        bookmaker.get(
            "key",
            ""
        )
    ).lower()

    title = str(
        bookmaker.get(
            "title",
            ""
        )
    ).lower()

    text = (
        key
        + " "
        + title
    )

    return any(
        token in text
        for token in EXCHANGE_TOKENS
    )


def _extraer_linea_h2h(
    bookmaker,
    home,
    away
):
    """
    Devuelve una línea completa y coherente de una casa:
    cuota home + cuota away.

    Si falta uno de los dos lados o la línea tiene un
    overround/underround anómalo, se descarta.
    """
    home_norm = normalizar_nombre(
        home
    )

    away_norm = normalizar_nombre(
        away
    )

    if not home_norm or not away_norm:
        return None

    outcomes = {}

    for market in bookmaker.get(
        "markets",
        []
    ):
        if market.get("key") != "h2h":
            continue

        for outcome in market.get(
            "outcomes",
            []
        ):
            name = normalizar_nombre(
                outcome.get("name")
            )

            price = _safe_odds(
                outcome.get("price")
            )

            if (
                not name
                or price is None
            ):
                continue

            outcomes[
                name
            ] = price

    if (
        home_norm not in outcomes
        or away_norm not in outcomes
    ):
        return None

    home_odds = outcomes[
        home_norm
    ]

    away_odds = outcomes[
        away_norm
    ]

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


def _filtrar_outliers(
    lines,
    field
):
    """
    Conserva las mejores cuotas reales, pero evita aceptar
    una cuota aislada extremadamente superior al mercado.
    """
    if not lines:
        return [], 0

    prices = [
        line[field]
        for line in lines
    ]

    # Con pocas casas no aplicamos filtro estadístico.
    if len(prices) < 4:
        return lines, 0

    median_price = statistics.median(
        prices
    )

    max_allowed = (
        median_price
        * OUTLIER_FACTOR
    )

    filtered = [
        line
        for line in lines
        if line[field] <= max_allowed
    ]

    discarded = (
        len(lines)
        - len(filtered)
    )

    # Protección: nunca nos quedamos sin mercado por el filtro.
    if not filtered:
        return lines, 0

    return (
        filtered,
        discarded
    )


def _market_quality(
    bookmaker_count
):
    if bookmaker_count >= 6:
        return "Alta"

    if bookmaker_count >= 3:
        return "Media"

    if bookmaker_count >= MIN_VALID_BOOKMAKERS:
        return "Baja"

    return "Insuficiente"


def get_active_atp_sports():
    if not THE_ODDS_API_KEY:
        return []

    response = requests.get(
        f"{BASE_URL}/sports",
        params={
            "apiKey": THE_ODDS_API_KEY
        },
        timeout=20
    )

    response.raise_for_status()

    sports = response.json()

    return [
        sport["key"]
        for sport in sports
        if (
            str(
                sport.get(
                    "group",
                    ""
                )
            ).lower()
            == "tennis"
            and str(
                sport.get(
                    "key",
                    ""
                )
            ).startswith(
                "tennis_atp_"
            )
            and sport.get(
                "active",
                True
            )
        )
    ]


def get_tennis_odds():
    if not THE_ODDS_API_KEY:
        return {
            "ok": False,
            "message": (
                "THE_ODDS_API_KEY está vacía."
            ),
            "events": [],
            "requests_remaining": None,
            "requests_used": None
        }

    try:
        sport_keys = (
            get_active_atp_sports()
        )

        if not sport_keys:
            return {
                "ok": True,
                "message": (
                    "No hay competiciones ATP "
                    "activas con cuotas."
                ),
                "events": [],
                "requests_remaining": None,
                "requests_used": None
            }

        all_events = []
        remaining = None
        used = None

        for sport_key in sport_keys:
            response = requests.get(
                (
                    f"{BASE_URL}/sports/"
                    f"{sport_key}/odds"
                ),
                params={
                    "apiKey": (
                        THE_ODDS_API_KEY
                    ),
                    "regions": "uk",
                    "markets": "h2h",
                    "oddsFormat": "decimal"
                },
                timeout=20
            )

            response.raise_for_status()

            remaining = (
                response.headers.get(
                    "x-requests-remaining",
                    remaining
                )
            )

            used = (
                response.headers.get(
                    "x-requests-used",
                    used
                )
            )

            for event in response.json():
                event[
                    "sport_key"
                ] = sport_key

                all_events.append(
                    event
                )

        return {
            "ok": True,
            "message": "",
            "events": all_events,
            "requests_remaining": remaining,
            "requests_used": used
        }

    except Exception as exc:
        return {
            "ok": False,
            "message": str(exc),
            "events": [],
            "requests_remaining": None,
            "requests_used": None
        }


def construir_indice_cuotas(events):
    """
    Construye un índice saneado de mercados.

    Reglas:
    1. Solo H2H completo.
    2. Excluye exchanges.
    3. Descarta líneas incoherentes.
    4. Filtra cuotas aisladas demasiado alejadas.
    5. Conserva la mejor cuota válida de cada jugador.
    """
    indice = {}

    for event in events:
        home = event.get(
            "home_team"
        )

        away = event.get(
            "away_team"
        )

        clave = _clave_partido(
            home,
            away
        )

        if clave is None:
            continue

        home_norm = normalizar_nombre(
            home
        )

        away_norm = normalizar_nombre(
            away
        )

        valid_lines = []
        exchanges_discarded = 0
        invalid_lines_discarded = 0

        for bookmaker in event.get(
            "bookmakers",
            []
        ):
            if _es_exchange(
                bookmaker
            ):
                exchanges_discarded += 1
                continue

            line = _extraer_linea_h2h(
                bookmaker,
                home,
                away
            )

            if line is None:
                invalid_lines_discarded += 1
                continue

            line[
                "casa"
            ] = bookmaker.get(
                "title",
                bookmaker.get(
                    "key",
                    "Bookmaker"
                )
            )

            line[
                "bookmaker_key"
            ] = bookmaker.get(
                "key"
            )

            valid_lines.append(
                line
            )

        # Filtro robusto por cada lado.
        home_lines, out_home = (
            _filtrar_outliers(
                valid_lines,
                "home_odds"
            )
        )

        away_lines, out_away = (
            _filtrar_outliers(
                valid_lines,
                "away_odds"
            )
        )

        best_home = None

        if home_lines:
            best_home = max(
                home_lines,
                key=lambda x: x[
                    "home_odds"
                ]
            )

        best_away = None

        if away_lines:
            best_away = max(
                away_lines,
                key=lambda x: x[
                    "away_odds"
                ]
            )

        # Consenso del mercado a partir de la mediana.
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

            raw_home = (
                1.0 / median_home
            )

            raw_away = (
                1.0 / median_away
            )

            total = (
                raw_home
                + raw_away
            )

            if total > 0:
                consensus_home = (
                    raw_home
                    / total
                )

                consensus_away = (
                    raw_away
                    / total
                )

        valid_count = len(
            valid_lines
        )

        market_ok = (
            valid_count
            >= MIN_VALID_BOOKMAKERS
            and best_home is not None
            and best_away is not None
        )

        cuotas = {}

        if best_home is not None:
            cuotas[
                home_norm
            ] = {
                "cuota": best_home[
                    "home_odds"
                ],
                "casa": best_home[
                    "casa"
                ]
            }

        if best_away is not None:
            cuotas[
                away_norm
            ] = {
                "cuota": best_away[
                    "away_odds"
                ],
                "casa": best_away[
                    "casa"
                ]
            }

        indice[
            clave
        ] = {
            "home_team": home,
            "away_team": away,
            "commence_time": event.get(
                "commence_time"
            ),
            "sport_key": event.get(
                "sport_key"
            ),
            "cuotas": cuotas,
            "market_ok": market_ok,
            "market_quality": (
                _market_quality(
                    valid_count
                )
            ),
            "valid_bookmakers": (
                valid_count
            ),
            "exchanges_discarded": (
                exchanges_discarded
            ),
            "invalid_lines_discarded": (
                invalid_lines_discarded
            ),
            "outliers_discarded": (
                max(
                    out_home,
                    out_away
                )
            ),
            "consensus": {
                home_norm: (
                    consensus_home
                ),
                away_norm: (
                    consensus_away
                ),
            },
        }

    return indice


def buscar_mejores_cuotas(
    indice,
    jugador_a,
    jugador_b
):
    clave = _clave_partido(
        jugador_a,
        jugador_b
    )

    if clave is None:
        return None

    event = indice.get(
        clave
    )

    if not event:
        return None

    # Si solo existe una casa o el mercado no pasó
    # los filtros de calidad, no calculamos VALUE.
    if not event.get(
        "market_ok",
        False
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
    ].get(
        nombre_a
    )

    cuota_b = event[
        "cuotas"
    ].get(
        nombre_b
    )

    if not cuota_a or not cuota_b:
        return None

    consensus = event.get(
        "consensus",
        {}
    )

    return {
        "jugador_a": jugador_a,
        "jugador_b": jugador_b,

        "cuota_a": cuota_a[
            "cuota"
        ],
        "casa_a": cuota_a[
            "casa"
        ],

        "cuota_b": cuota_b[
            "cuota"
        ],
        "casa_b": cuota_b[
            "casa"
        ],

        "commence_time": event.get(
            "commence_time"
        ),

        "sport_key": event.get(
            "sport_key"
        ),

        # Metadatos nuevos. La app antigua puede
        # ignorarlos sin romperse.
        "calidad_mercado": event.get(
            "market_quality",
            "N/D"
        ),

        "casas_validas": event.get(
            "valid_bookmakers",
            0
        ),

        "outliers_descartados": event.get(
            "outliers_discarded",
            0
        ),

        "exchanges_descartados": event.get(
            "exchanges_discarded",
            0
        ),

        "prob_consenso_a": (
            consensus.get(
                nombre_a
            )
        ),

        "prob_consenso_b": (
            consensus.get(
                nombre_b
            )
        ),
    }
