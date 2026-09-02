import sqlite3
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

from live_results import get_live_match_result


DB_PATH = Path("tennis_edge.db")

MIN_MATCH_CONFIDENCE = 0.70
MIN_EV = 0.05
STAKE = 1.0
LIVE_CHECK_MINUTES = 30
MAX_LIVE_CHECKS_PER_RUN = 8


def _connect():
    conn = sqlite3.connect(
        DB_PATH
    )

    conn.row_factory = (
        sqlite3.Row
    )

    return conn


def init_tracker():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS betting_picks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pick_key TEXT NOT NULL UNIQUE,

                fixture_id TEXT,
                event_date TEXT,
                tournament TEXT,
                tour TEXT,
                surface TEXT,

                player_a TEXT NOT NULL,
                player_b TEXT NOT NULL,
                selection TEXT NOT NULL,

                prob_a REAL NOT NULL,
                prob_b REAL NOT NULL,
                prob_selection REAL NOT NULL,
                match_confidence REAL NOT NULL,
                confidence_label TEXT,

                odds REAL NOT NULL,
                bookmaker TEXT,
                fair_odds REAL,
                implied_prob REAL,
                edge REAL,
                ev REAL NOT NULL,

                market_quality TEXT,
                valid_bookmakers INTEGER,
                outliers_discarded INTEGER,

                model_version TEXT,

                stake REAL NOT NULL DEFAULT 1.0,
                status TEXT NOT NULL DEFAULT 'PENDING',
                result_winner TEXT,
                profit REAL,

                h2h_count_at_pick INTEGER NOT NULL DEFAULT 0,

                recorded_at TEXT NOT NULL,
                settled_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_betting_picks_status
            ON betting_picks(status)
            """
        )

        # Migración segura para instalaciones que ya
        # tienen la tabla creada.
        existing_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(betting_picks)"
            ).fetchall()
        }

        migrations = {
            "start_time": "TEXT",
            "last_live_check_at": "TEXT",
            "live_status": "TEXT",
            "live_score": "TEXT",
            "result_source": "TEXT",
            "fixture_alt_id": "TEXT",
            "api_match_id": "TEXT",
            "api_player1": "TEXT",
            "api_player2": "TEXT",
            "api_scheduled_time": "TEXT",
            "live_verified": "INTEGER NOT NULL DEFAULT 0",
            "verification_note": "TEXT",
        }

        for column, sql_type in migrations.items():
            if column not in existing_columns:
                conn.execute(
                    f"""
                    ALTER TABLE betting_picks
                    ADD COLUMN {column} {sql_type}
                    """
                )


def _clean(value):
    if value is None:
        return ""

    return str(
        value
    ).strip()


def _fixture_ids_from_partido(
    partido
):
    """
    Conservamos los dos identificadores si existen.

    En distintas versiones del adaptador local hemos
    manejado tanto 'id' como 'match_id'. El resolver LIVE
    probará ambos, pero SOLO aceptará uno si además los
    jugadores devueltos por la API coinciden.
    """
    primary = _clean(
        partido.get(
            "id"
        )
    )

    secondary = _clean(
        partido.get(
            "match_id"
        )
    )

    if not primary:
        primary = secondary

    if (
        secondary
        ==
        primary
    ):
        secondary = ""

    return (
        primary,
        secondary
    )


def _normalize_name(
    value
):
    value = unicodedata.normalize(
        "NFKD",
        _clean(
            value
        )
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(
            char
        )
    ).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    return " ".join(
        value.split()
    )


def _name_fingerprint(
    value
):
    """
    Ordenar tokens permite validar también nombres tipo
    'Bu Yunchaokete' vs 'Yunchaokete Bu'.
    """
    normalized = _normalize_name(
        value
    )

    if not normalized:
        return ()

    return tuple(
        sorted(
            normalized.split()
        )
    )


def _same_player_pair(
    expected_a,
    expected_b,
    api_a,
    api_b
):
    expected = sorted(
        [
            _name_fingerprint(
                expected_a
            ),
            _name_fingerprint(
                expected_b
            ),
        ]
    )

    received = sorted(
        [
            _name_fingerprint(
                api_a
            ),
            _name_fingerprint(
                api_b
            ),
        ]
    )

    if (
        not all(expected)
        or
        not all(received)
    ):
        return False

    return (
        expected
        ==
        received
    )


def _scheduled_time_is_future(
    value
):
    parsed = _parse_iso(
        value
    )

    if parsed is None:
        return False

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return (
        parsed
        >
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=5
        )
    )


def repair_unverified_live_settlements():
    """
    IMPORTANTE:
    Las versiones anteriores liquidaban basándose solo
    en ID + status. Los resultados LIVE antiguos no
    tienen la nueva verificación de jugadores.

    Los reabrimos UNA vez como PENDING. Si realmente
    terminaron, el nuevo resolver los volverá a liquidar
    tras verificar ID + jugadores + horario.
    """
    init_tracker()

    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE betting_picks
            SET
                status = 'PENDING',
                result_winner = NULL,
                profit = NULL,
                settled_at = NULL,
                live_status = NULL,
                live_score = NULL,
                result_source = NULL,
                last_live_check_at = NULL,
                verification_note = (
                    'Reabierto: resultado LIVE previo sin verificacion de jugadores'
                )
            WHERE
                result_source = 'live_api'
                AND COALESCE(
                    live_verified,
                    0
                ) = 0
                AND status IN (
                    'WON',
                    'LOST',
                    'VOID'
                )
            """
        )

        return int(
            cursor.rowcount
            or 0
        )


def _match_key(
    partido,
    player_a,
    player_b
):
    event_date = _clean(
        partido.get(
            "event_date"
        )
    ).lower()

    tournament = _clean(
        partido.get(
            "tournament"
        )
    ).lower()

    fixture_id, _ = (
        _fixture_ids_from_partido(
            partido
        )
    )

    fixture_id = fixture_id.lower()

    players = sorted(
        [
            _clean(
                player_a
            ).lower(),
            _clean(
                player_b
            ).lower(),
        ]
    )

    # El ID de fixture ayuda, pero no dependemos
    # exclusivamente de él para evitar duplicados.
    return "|".join(
        [
            event_date,
            tournament,
            players[0],
            players[1],
            fixture_id,
        ]
    )


def _pair_mask(
    df,
    player_a,
    player_b
):
    if (
        "winner_name"
        not in df.columns
        or
        "loser_name"
        not in df.columns
    ):
        return pd.Series(
            False,
            index=df.index
        )

    return (
        (
            (
                df["winner_name"]
                ==
                player_a
            )
            &
            (
                df["loser_name"]
                ==
                player_b
            )
        )
        |
        (
            (
                df["winner_name"]
                ==
                player_b
            )
            &
            (
                df["loser_name"]
                ==
                player_a
            )
        )
    )


def contar_h2h_actual(
    df,
    player_a,
    player_b
):
    return int(
        _pair_mask(
            df,
            player_a,
            player_b
        ).sum()
    )


def _categoria_value(ev):
    if ev >= 0.15:
        return "💎"

    if ev >= 0.10:
        return "🔥"

    return "🟢"


def evaluar_pick_automatico(
    partido,
    player_a,
    player_b,
    prob_a,
    prob_b,
    datos_cuotas,
    prediccion,
    df
):
    """
    Registra como máximo UN pick por partido.

    Regla inicial:
    - confianza del partido >= 70%
    - EV del lado elegido >= +5%
    - mercado ya validado por odds_api.py
    - elegimos el lado con mayor EV
    """
    if not datos_cuotas:
        return {
            "qualifies": False,
            "inserted": False,
            "label": "-",
        }

    prob_a = float(
        prob_a
    )

    prob_b = float(
        prob_b
    )

    cuota_a = float(
        datos_cuotas[
            "cuota_a"
        ]
    )

    cuota_b = float(
        datos_cuotas[
            "cuota_b"
        ]
    )

    ev_a = (
        prob_a
        * cuota_a
        - 1.0
    )

    ev_b = (
        prob_b
        * cuota_b
        - 1.0
    )

    match_confidence = max(
        prob_a,
        prob_b
    )

    if match_confidence < (
        MIN_MATCH_CONFIDENCE
    ):
        return {
            "qualifies": False,
            "inserted": False,
            "label": "-",
        }

    candidates = [
        {
            "selection": player_a,
            "prob": prob_a,
            "odds": cuota_a,
            "bookmaker": (
                datos_cuotas[
                    "casa_a"
                ]
            ),
            "ev": ev_a,
        },
        {
            "selection": player_b,
            "prob": prob_b,
            "odds": cuota_b,
            "bookmaker": (
                datos_cuotas[
                    "casa_b"
                ]
            ),
            "ev": ev_b,
        },
    ]

    best = max(
        candidates,
        key=lambda item: item[
            "ev"
        ]
    )

    if best["ev"] < MIN_EV:
        return {
            "qualifies": False,
            "inserted": False,
            "label": "-",
        }

    implied_prob = (
        1.0
        / best[
            "odds"
        ]
    )

    fair_odds = (
        1.0
        / best[
            "prob"
        ]
        if best[
            "prob"
        ] > 0
        else None
    )

    edge = (
        best["prob"]
        - implied_prob
    )

    pick_key = _match_key(
        partido,
        player_a,
        player_b
    )

    h2h_count = (
        contar_h2h_actual(
            df,
            player_a,
            player_b
        )
    )

    recorded_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    inserted = False

    fixture_id_primary, fixture_id_alt = (
        _fixture_ids_from_partido(
            partido
        )
    )

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO betting_picks (
                pick_key,
                fixture_id,
                event_date,
                start_time,
                tournament,
                tour,
                surface,
                player_a,
                player_b,
                selection,
                prob_a,
                prob_b,
                prob_selection,
                match_confidence,
                confidence_label,
                odds,
                bookmaker,
                fair_odds,
                implied_prob,
                edge,
                ev,
                market_quality,
                valid_bookmakers,
                outliers_discarded,
                model_version,
                stake,
                status,
                h2h_count_at_pick,
                recorded_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, 'PENDING', ?, ?
            )
            """,
            (
                pick_key,
                fixture_id_primary,
                _clean(
                    partido.get(
                        "event_date"
                    )
                ),
                _clean(
                    partido.get(
                        "start_time"
                    )
                ),
                _clean(
                    partido.get(
                        "tournament"
                    )
                ),
                _clean(
                    partido.get(
                        "tour"
                    )
                ),
                _clean(
                    partido.get(
                        "surface"
                    )
                ),
                player_a,
                player_b,
                best[
                    "selection"
                ],
                prob_a,
                prob_b,
                best[
                    "prob"
                ],
                match_confidence,
                _clean(
                    prediccion.get(
                        "confidence_label"
                    )
                ),
                best[
                    "odds"
                ],
                best[
                    "bookmaker"
                ],
                fair_odds,
                implied_prob,
                edge,
                best[
                    "ev"
                ],
                _clean(
                    datos_cuotas.get(
                        "calidad_mercado"
                    )
                ),
                int(
                    datos_cuotas.get(
                        "casas_validas",
                        0
                    )
                    or 0
                ),
                int(
                    datos_cuotas.get(
                        "outliers_descartados",
                        0
                    )
                    or 0
                ),
                _clean(
                    prediccion.get(
                        "model_version"
                    )
                ),
                STAKE,
                h2h_count,
                recorded_at,
            )
        )

        inserted = (
            cursor.rowcount
            == 1
        )

        conn.execute(
            """
            UPDATE betting_picks
            SET
                fixture_id = ?,
                fixture_alt_id = ?
            WHERE pick_key = ?
            """,
            (
                fixture_id_primary,
                fixture_id_alt,
                pick_key,
            )
        )

    icon = _categoria_value(
        best["ev"]
    )

    label = (
        f"{icon} "
        f"{best['selection']} "
        f"@{best['odds']:.2f}"
    )

    return {
        "qualifies": True,
        "inserted": inserted,
        "label": label,
        "selection": best[
            "selection"
        ],
        "odds": best[
            "odds"
        ],
        "ev": best[
            "ev"
        ],
    }


def _pending_picks():
    init_tracker()

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM betting_picks
            WHERE status = 'PENDING'
            ORDER BY id
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def _parse_iso(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )
    except Exception:
        return None


def _event_date_allows_check(
    event_date
):
    """
    No gastamos una llamada de API en picks de días futuros.
    Para el día actual sí permitimos comprobar; el throttle
    evita repetir llamadas continuamente.
    """
    if not event_date:
        return True

    try:
        pick_date = pd.to_datetime(
            event_date,
            errors="coerce"
        )

        if pd.isna(
            pick_date
        ):
            return True

        today_utc = datetime.now(
            timezone.utc
        ).date()

        return (
            pick_date.date()
            <= today_utc
        )
    except Exception:
        return True


def _live_check_due(
    pick,
    force=False
):
    if force:
        return True

    if not _event_date_allows_check(
        pick.get(
            "event_date"
        )
    ):
        return False

    last_check = _parse_iso(
        pick.get(
            "last_live_check_at"
        )
    )

    if last_check is None:
        return True

    if last_check.tzinfo is None:
        last_check = last_check.replace(
            tzinfo=timezone.utc
        )

    return (
        datetime.now(
            timezone.utc
        )
        - last_check
        >= timedelta(
            minutes=LIVE_CHECK_MINUTES
        )
    )


def _settle_live_pick(
    pick,
    winner_name,
    live_status,
    live_score
):
    won = (
        winner_name
        ==
        pick[
            "selection"
        ]
    )

    stake = float(
        pick[
            "stake"
        ]
        or STAKE
    )

    odds = float(
        pick[
            "odds"
        ]
    )

    profit = (
        stake
        * (
            odds - 1.0
        )
        if won
        else -stake
    )

    settled_at = datetime.now(
        timezone.utc
    ).isoformat()

    with _connect() as conn:
        conn.execute(
            """
            UPDATE betting_picks
            SET
                status = ?,
                result_winner = ?,
                profit = ?,
                settled_at = ?,
                last_live_check_at = ?,
                live_status = ?,
                live_score = ?,
                result_source = 'live_api',
                live_verified = 1,
                verification_note = (
                    'OK: ID + jugadores + estado verificados'
                )
            WHERE id = ?
            """,
            (
                (
                    "WON"
                    if won
                    else "LOST"
                ),
                winner_name,
                profit,
                settled_at,
                settled_at,
                live_status,
                live_score,
                pick[
                    "id"
                ],
            )
        )


def _void_live_pick(
    pick,
    live_status,
    live_score
):
    settled_at = datetime.now(
        timezone.utc
    ).isoformat()

    with _connect() as conn:
        conn.execute(
            """
            UPDATE betting_picks
            SET
                status = 'VOID',
                profit = 0.0,
                settled_at = ?,
                last_live_check_at = ?,
                live_status = ?,
                live_score = ?,
                result_source = 'live_api',
                live_verified = 1,
                verification_note = (
                    'OK: cancelacion verificada'
                )
            WHERE id = ?
            """,
            (
                settled_at,
                settled_at,
                live_status,
                live_score,
                pick[
                    "id"
                ],
            )
        )


def _normalize_tournament_name(value):
    return _normalize_name(value)


def _is_mens_grand_slam(tournament):
    """
    Los cuatro Grand Slams de singles masculino se juegan
    al mejor de 5 sets.
    """
    name = _normalize_tournament_name(
        tournament
    )

    grand_slams = (
        "australian open",
        "roland garros",
        "french open",
        "wimbledon",
        "us open",
        "u s open",
    )

    return any(
        token in name
        for token in grand_slams
    )


def _sets_needed_to_win(
    tournament,
    tour
):
    """
    Formato esperado para Tennis Edge Pro:

    ATP Grand Slam:
        BO5 -> 3 sets para ganar.

    ATP Masters 1000 / ATP 500 / ATP 250:
        BO3 -> 2 sets para ganar.

    Challenger:
        BO3 -> 2 sets para ganar.

    Si en el futuro añadimos otra competición con un formato
    especial, se amplía aquí de forma explícita.
    """
    if _is_mens_grand_slam(
        tournament
    ):
        return 3

    tour_name = _normalize_name(
        tour
    )

    if tour_name in (
        "atp",
        "challenger",
    ):
        return 2

    # La app actual sólo trabaja con ATP + Challenger.
    # Para cualquier torneo no clasificado preferimos el
    # formato estándar BO3 antes que inventar un BO5.
    return 2


def _special_finish(
    status,
    event_status
):
    """
    Excepciones donde un partido puede terminar antes de que
    el ganador alcance el número normal de sets:
    retirada, walkover, default/descalificación, abandono.
    """
    text = " ".join(
        [
            _normalize_name(status),
            _normalize_name(event_status),
        ]
    )

    tokens = (
        "retired",
        "retirement",
        "walkover",
        "walk over",
        "wo",
        "default",
        "defaulted",
        "disqualified",
        "disqualification",
        "abandoned",
        "abandono",
        "retirado",
    )

    return any(
        token in text
        for token in tokens
    )


def _completed_score_is_sane(
    pick,
    result
):
    """
    Filtro anti-falsos-resultados para TODO el circuito
    que maneja Tennis Edge Pro.

    Formatos normales:
    - Grand Slam ATP: BO5 -> 3-0 / 3-1 / 3-2
    - Masters 1000: BO3 -> 2-0 / 2-1
    - ATP 500: BO3 -> 2-0 / 2-1
    - ATP 250: BO3 -> 2-0 / 2-1
    - Challenger: BO3 -> 2-0 / 2-1

    Excepciones válidas:
    retirada, walkover, default/descalificación, abandono.

    Si el marcador no se puede verificar con seguridad,
    NO liquidamos automáticamente.
    """
    status = result.get(
        "status",
        ""
    )

    event_status = result.get(
        "event_status",
        ""
    )

    if _special_finish(
        status,
        event_status
    ):
        return (
            True,
            "OK: final especial (retirada/WO/default)"
        )

    sets_won = result.get(
        "sets_won"
    )

    if (
        not isinstance(
            sets_won,
            (list, tuple)
        )
        or len(
            sets_won
        ) != 2
        or sets_won[0] is None
        or sets_won[1] is None
    ):
        return (
            False,
            "Marcador de sets no verificable"
        )

    try:
        sets_p1 = int(
            sets_won[0]
        )

        sets_p2 = int(
            sets_won[1]
        )
    except Exception:
        return (
            False,
            "Marcador de sets inválido"
        )

    winner = result.get(
        "winner"
    )

    if winner == 1:
        winner_sets = sets_p1
        loser_sets = sets_p2
    elif winner == 2:
        winner_sets = sets_p2
        loser_sets = sets_p1
    else:
        return (
            False,
            "Completed sin winner 1/2"
        )

    sets_needed = _sets_needed_to_win(
        pick.get(
            "tournament"
        ),
        pick.get(
            "tour"
        )
    )

    if winner_sets != sets_needed:
        format_name = (
            "BO5"
            if sets_needed == 3
            else "BO3"
        )

        return (
            False,
            (
                f"Final imposible para {format_name}: "
                f"{sets_p1}-{sets_p2}; "
                f"el ganador necesita {sets_needed} sets"
            )
        )

    if loser_sets < 0:
        return (
            False,
            "Marcador final inválido"
        )

    if loser_sets >= sets_needed:
        return (
            False,
            (
                "Marcador final imposible: "
                f"{sets_p1}-{sets_p2}"
            )
        )

    if sets_needed == 3:
        valid_loser_sets = (
            0,
            1,
            2,
        )
    else:
        valid_loser_sets = (
            0,
            1,
        )

    if loser_sets not in valid_loser_sets:
        return (
            False,
            (
                "Marcador final inválido para el formato: "
                f"{sets_p1}-{sets_p2}"
            )
        )

    tournament = _clean(
        pick.get(
            "tournament"
        )
    )

    tour = _clean(
        pick.get(
            "tour"
        )
    )

    format_name = (
        "BO5"
        if sets_needed == 3
        else "BO3"
    )

    return (
        True,
        (
            f"OK: {format_name} verificado "
            f"({sets_p1}-{sets_p2}) "
            f"| {tour} | {tournament}"
        )
    )


def resolver_picks_live(
    force=False,
    max_checks=MAX_LIVE_CHECKS_PER_RUN
):
    """
    Resolver LIVE con doble seguridad:

    1) El ID solicitado debe devolver el mismo ID.
    2) Los DOS jugadores devueltos por la API deben ser
       exactamente el mismo emparejamiento del pick.
    3) Si scheduled_time sigue en el futuro, NO se liquida.
    4) Sólo completed + winner 1/2 puede ser WON/LOST.

    Si existen 'id' y 'match_id', probamos ambos hasta
    encontrar el que verifica correctamente el partido.
    """
    repaired = (
        repair_unverified_live_settlements()
    )

    pending = _pending_picks()

    stats = {
        "checked": 0,
        "resolved": 0,
        "voided": 0,
        "live": 0,
        "upcoming": 0,
        "errors": 0,
        "verification_failed": 0,
        "rate_limited": False,
        "repaired": repaired,
    }

    if not pending:
        return stats

    for pick in pending:
        if stats[
            "checked"
        ] >= max_checks:
            break

        if not _live_check_due(
            pick,
            force=force
        ):
            continue

        candidate_ids = []

        for candidate in (
            _clean(
                pick.get(
                    "fixture_id"
                )
            ),
            _clean(
                pick.get(
                    "fixture_alt_id"
                )
            ),
        ):
            if (
                candidate
                and candidate
                not in candidate_ids
            ):
                candidate_ids.append(
                    candidate
                )

        if not candidate_ids:
            continue

        verified_result = None
        verified_id = None
        last_note = ""

        for candidate_id in candidate_ids:
            if stats[
                "checked"
            ] >= max_checks:
                break

            result = get_live_match_result(
                candidate_id
            )

            stats[
                "checked"
            ] += 1

            now_iso = datetime.now(
                timezone.utc
            ).isoformat()

            if not result.get(
                "ok"
            ):
                if result.get(
                    "rate_limited"
                ):
                    stats[
                        "rate_limited"
                    ] = True
                    break

                stats[
                    "errors"
                ] += 1
                last_note = (
                    "API sin resultado valido "
                    f"para ID {candidate_id}"
                )
                continue

            api_match_id = _clean(
                result.get(
                    "match_id"
                )
            )

            api_p1 = _clean(
                result.get(
                    "player1_name"
                )
            )

            api_p2 = _clean(
                result.get(
                    "player2_name"
                )
            )

            if (
                api_match_id
                and api_match_id
                != _clean(
                    candidate_id
                )
            ):
                last_note = (
                    "ID respondido no coincide "
                    f"({candidate_id} -> {api_match_id})"
                )
                continue

            if not _same_player_pair(
                pick[
                    "player_a"
                ],
                pick[
                    "player_b"
                ],
                api_p1,
                api_p2
            ):
                last_note = (
                    "Jugadores API no coinciden: "
                    f"{api_p1} vs {api_p2}"
                )
                continue

            if _scheduled_time_is_future(
                result.get(
                    "scheduled_time"
                )
            ):
                last_note = (
                    "Horario API aun esta en el futuro"
                )
                continue

            verified_result = result
            verified_id = candidate_id
            break

        if stats[
            "rate_limited"
        ]:
            break

        now_iso = datetime.now(
            timezone.utc
        ).isoformat()

        if verified_result is None:
            stats[
                "verification_failed"
            ] += 1

            with _connect() as conn:
                conn.execute(
                    """
                    UPDATE betting_picks
                    SET
                        last_live_check_at = ?,
                        verification_note = ?
                    WHERE id = ?
                    """,
                    (
                        now_iso,
                        last_note,
                        pick[
                            "id"
                        ],
                    )
                )

            continue

        status = str(
            verified_result.get(
                "status",
                ""
            )
            or ""
        ).lower()

        winner = verified_result.get(
            "winner"
        )

        score_sane = True
        score_note = ""

        if status == "completed":
            score_sane, score_note = (
                _completed_score_is_sane(
                    pick,
                    verified_result
                )
            )

            if not score_sane:
                stats[
                    "verification_failed"
                ] += 1

                now_iso = datetime.now(
                    timezone.utc
                ).isoformat()

                with _connect() as conn:
                    conn.execute(
                        """
                        UPDATE betting_picks
                        SET
                            last_live_check_at = ?,
                            live_status = ?,
                            live_score = ?,
                            verification_note = ?
                        WHERE id = ?
                        """,
                        (
                            now_iso,
                            status,
                            _clean(
                                verified_result.get(
                                    "score_text"
                                )
                            ),
                            score_note,
                            pick[
                                "id"
                            ],
                        )
                    )

                # Sigue PENDING. Nunca se liquida con
                # un resultado BO5 imposible.
                continue

        event_status = str(
            verified_result.get(
                "event_status",
                ""
            )
            or ""
        ).lower()

        live_score = _clean(
            verified_result.get(
                "score_text"
            )
        )

        api_p1 = _clean(
            verified_result.get(
                "player1_name"
            )
        )

        api_p2 = _clean(
            verified_result.get(
                "player2_name"
            )
        )

        api_scheduled = _clean(
            verified_result.get(
                "scheduled_time"
            )
        )

        with _connect() as conn:
            conn.execute(
                """
                UPDATE betting_picks
                SET
                    fixture_id = ?,
                    last_live_check_at = ?,
                    live_status = ?,
                    live_score = ?,
                    api_match_id = ?,
                    api_player1 = ?,
                    api_player2 = ?,
                    api_scheduled_time = ?,
                    verification_note = ?
                WHERE id = ?
                """,
                (
                    _clean(
                        verified_id
                    ),
                    now_iso,
                    status,
                    live_score,
                    _clean(
                        verified_result.get(
                            "match_id"
                        )
                    ),
                    api_p1,
                    api_p2,
                    api_scheduled,
                    (
                        score_note
                        if score_note
                        else "OK: partido verificado"
                    ),
                    pick[
                        "id"
                    ],
                )
            )

        if (
            status == "cancelled"
            or event_status == "cancelled"
        ):
            _void_live_pick(
                pick,
                status,
                live_score
            )

            stats[
                "voided"
            ] += 1
            continue

        if status == "completed":
            if winner == 1:
                winner_name = pick[
                    "player_a"
                ]
            elif winner == 2:
                winner_name = pick[
                    "player_b"
                ]
            else:
                # Completed sin ganador explícito:
                # no se adivina jamás.
                stats[
                    "verification_failed"
                ] += 1
                continue

            _settle_live_pick(
                pick,
                winner_name,
                status,
                live_score
            )

            stats[
                "resolved"
            ] += 1

        elif status == "live":
            stats[
                "live"
            ] += 1

        else:
            stats[
                "upcoming"
            ] += 1

    return stats


def resolver_picks_pendientes(df):
    """
    Un pick se liquida cuando aparece un NUEVO H2H
    respecto al número de enfrentamientos que existían
    cuando se registró.

    Esto evita depender de tourney_date, que en nuestros
    históricos puede ser la fecha de inicio del torneo.
    """
    pending = _pending_picks()

    if not pending:
        return 0

    resolved = 0

    today_utc = datetime.now(
        timezone.utc
    ).date()

    for pick in pending:
        # Protección extra:
        # la base histórica NO liquida partidos del día
        # actual. Para esos usamos la API LIVE verificada.
        event_date = pd.to_datetime(
            pick.get(
                "event_date"
            ),
            errors="coerce"
        )

        if (
            not pd.isna(
                event_date
            )
            and event_date.date()
            >= today_utc
        ):
            continue

        player_a = pick[
            "player_a"
        ]

        player_b = pick[
            "player_b"
        ]

        pair = df[
            _pair_mask(
                df,
                player_a,
                player_b
            )
        ].copy()

        old_count = int(
            pick[
                "h2h_count_at_pick"
            ]
            or 0
        )

        if len(pair) <= old_count:
            continue

        if "tourney_date" in (
            pair.columns
        ):
            pair[
                "_tracker_date"
            ] = pd.to_datetime(
                pair[
                    "tourney_date"
                ],
                errors="coerce"
            )

            sort_cols = [
                "_tracker_date"
            ]

            if "match_key" in pair.columns:
                sort_cols.append(
                    "match_key"
                )

            pair = pair.sort_values(
                sort_cols,
                kind="stable"
            )

        result_row = pair.iloc[-1]

        winner = _clean(
            result_row[
                "winner_name"
            ]
        )

        won = (
            winner
            ==
            pick[
                "selection"
            ]
        )

        stake = float(
            pick[
                "stake"
            ]
            or STAKE
        )

        odds = float(
            pick[
                "odds"
            ]
        )

        if won:
            profit = (
                stake
                * (
                    odds
                    - 1.0
                )
            )
        else:
            profit = (
                -stake
            )

        settled_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        with _connect() as conn:
            conn.execute(
                """
                UPDATE betting_picks
                SET
                    status = ?,
                    result_winner = ?,
                    profit = ?,
                    settled_at = ?,
                    result_source = 'historical_db'
                WHERE id = ?
                """,
                (
                    (
                        "WON"
                        if won
                        else "LOST"
                    ),
                    winner,
                    profit,
                    settled_at,
                    pick[
                        "id"
                    ],
                )
            )

        resolved += 1

    return resolved


def get_track_record():
    init_tracker()

    with _connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM betting_picks
            ORDER BY id DESC
            """,
            conn
        )

    if df.empty:
        return {
            "summary": {
                "total": 0,
                "pending": 0,
                "settled": 0,
                "wins": 0,
                "losses": 0,
                "hit_rate": 0.0,
                "profit": 0.0,
                "roi": 0.0,
            },
            "picks": df,
            "by_confidence": (
                pd.DataFrame()
            ),
        }

    pending = int(
        (
            df[
                "status"
            ]
            ==
            "PENDING"
        ).sum()
    )

    settled_df = df[
        df[
            "status"
        ].isin(
            [
                "WON",
                "LOST",
                "VOID"
            ]
        )
    ].copy()

    settled = len(
        settled_df
    )

    graded_df = settled_df[
        settled_df[
            "status"
        ].isin(
            [
                "WON",
                "LOST"
            ]
        )
    ].copy()

    wins = int(
        (
            graded_df[
                "status"
            ]
            ==
            "WON"
        ).sum()
    )

    losses = int(
        (
            graded_df[
                "status"
            ]
            ==
            "LOST"
        ).sum()
    )

    profit = float(
        settled_df[
            "profit"
        ].fillna(
            0.0
        ).sum()
    )

    total_staked = float(
        graded_df[
            "stake"
        ].fillna(
            STAKE
        ).sum()
    )

    graded = len(
        graded_df
    )

    hit_rate = (
        wins
        / graded
        if graded
        else 0.0
    )

    roi = (
        profit
        / total_staked
        if total_staked > 0
        else 0.0
    )

    def bucket(value):
        value = float(
            value
        )

        if value >= 0.80:
            return "💎 Elite ≥80%"

        if value >= 0.75:
            return "🔥 Muy fuerte 75-79.9%"

        if value >= 0.70:
            return "🟢 Fuerte 70-74.9%"

        return "Otros"

    by_confidence = pd.DataFrame()

    if len(graded_df):
        settled_df = graded_df.copy()

        settled_df[
            "bucket"
        ] = settled_df[
            "match_confidence"
        ].apply(
            bucket
        )

        rows = []

        for name, group in (
            settled_df.groupby(
                "bucket"
            )
        ):
            n = len(group)

            g_wins = int(
                (
                    group[
                        "status"
                    ]
                    ==
                    "WON"
                ).sum()
            )

            g_profit = float(
                group[
                    "profit"
                ].fillna(
                    0.0
                ).sum()
            )

            g_stake = float(
                group[
                    "stake"
                ].fillna(
                    STAKE
                ).sum()
            )

            rows.append(
                {
                    "Nivel": name,
                    "Picks": n,
                    "Hit rate": (
                        f"{g_wins / n:.1%}"
                    ),
                    "Beneficio": (
                        f"{g_profit:+.2f} u"
                    ),
                    "ROI": (
                        f"{g_profit / g_stake:+.1%}"
                        if g_stake > 0
                        else "-"
                    ),
                }
            )

        by_confidence = (
            pd.DataFrame(
                rows
            )
        )

    return {
        "summary": {
            "total": len(df),
            "pending": pending,
            "settled": settled,
            "wins": wins,
            "losses": losses,
            "hit_rate": hit_rate,
            "profit": profit,
            "roi": roi,
        },
        "picks": df,
        "by_confidence": (
            by_confidence
        ),
    }


init_tracker()
