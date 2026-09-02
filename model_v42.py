from collections import defaultdict, deque
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from model import predict_match as predict_match_v1_fallback


MODEL_V42_PATH = Path("tennis_model_v4_2_optimizado.joblib")
STATE_CACHE_PATH = Path("tennis_v42_state.joblib")

RECENT_MATCHES = 25
BASE_ELO = 1500.0
ELO_K = 28.0
FORM_DECAY = 0.90

STAT_NAMES = [
    "serve_points_won",
    "return_points_won",
    "ace_rate",
    "df_rate",
    "first_in_rate",
    "first_won_rate",
    "second_won_rate",
    "bp_won_rate",
    "bp_saved_rate",
]

_MEMORY_STATE = None
_MEMORY_STATE_VERSION = None
_MEMORY_MODEL = None
_MEMORY_MODEL_MTIME = None


def safe_num(value):
    try:
        value = float(value)

        if np.isnan(value):
            return np.nan

        return value
    except Exception:
        return np.nan


def safe_div(a, b):
    a = safe_num(a)
    b = safe_num(b)

    if (
        np.isnan(a)
        or np.isnan(b)
        or b <= 0
    ):
        return np.nan

    return a / b


def simple_mean(history):
    if not history:
        return np.nan

    values = np.asarray(
        list(history),
        dtype=float
    )

    if np.isnan(values).all():
        return np.nan

    return float(
        np.nanmean(values)
    )


def weighted_mean(history, decay=FORM_DECAY):
    if not history:
        return np.nan

    values = np.asarray(
        list(history),
        dtype=float
    )

    valid = ~np.isnan(values)

    if not valid.any():
        return np.nan

    values = values[valid]

    n = len(values)

    powers = np.arange(
        n - 1,
        -1,
        -1,
        dtype=float
    )

    weights = decay ** powers

    return float(
        np.average(
            values,
            weights=weights
        )
    )


def last_valid(history, default=np.nan):
    if not history:
        return default

    for value in reversed(history):
        value = safe_num(value)

        if not np.isnan(value):
            return value

    return default


def rank_momentum(history):
    if not history:
        return 0.0

    values = [
        safe_num(v)
        for v in history
    ]

    values = [
        v
        for v in values
        if not np.isnan(v)
    ]

    if len(values) < 6:
        return 0.0

    recent = values[-3:]

    if len(values) >= 10:
        older = values[-10:-3]
    else:
        older = values[:-3]

    if not older:
        return 0.0

    return float(
        np.mean(older)
        - np.mean(recent)
    )


def expected_probability(elo_a, elo_b):
    return (
        1.0
        /
        (
            1.0
            +
            10 ** (
                (elo_b - elo_a)
                / 400.0
            )
        )
    )


def elo_delta(elo_a, elo_b, result_a):
    expected_a = expected_probability(
        elo_a,
        elo_b
    )

    return ELO_K * (
        result_a
        - expected_a
    )


def player_match_stats(row, side):
    if side == "w":
        own_svpt = row.get("w_svpt")
        opp_svpt = row.get("l_svpt")

        ace = row.get("w_ace")
        df = row.get("w_df")
        first_in = row.get("w_1stIn")
        first_won = row.get("w_1stWon")
        second_won = row.get("w_2ndWon")
        bp_won = row.get("w_bpWon")
        bp_saved = row.get("w_bpSaved")

        opp_first_won = row.get("l_1stWon")
        opp_second_won = row.get("l_2ndWon")

    else:
        own_svpt = row.get("l_svpt")
        opp_svpt = row.get("w_svpt")

        ace = row.get("l_ace")
        df = row.get("l_df")
        first_in = row.get("l_1stIn")
        first_won = row.get("l_1stWon")
        second_won = row.get("l_2ndWon")
        bp_won = row.get("l_bpWon")
        bp_saved = row.get("l_bpSaved")

        opp_first_won = row.get("w_1stWon")
        opp_second_won = row.get("w_2ndWon")

    own_svpt_num = safe_num(
        own_svpt
    )

    opp_svpt_num = safe_num(
        opp_svpt
    )

    first_in_num = safe_num(
        first_in
    )

    first_won_num = safe_num(
        first_won
    )

    second_won_num = safe_num(
        second_won
    )

    opp_first_won_num = safe_num(
        opp_first_won
    )

    opp_second_won_num = safe_num(
        opp_second_won
    )

    second_attempts = np.nan

    if (
        not np.isnan(own_svpt_num)
        and not np.isnan(first_in_num)
    ):
        second_attempts = max(
            own_svpt_num
            - first_in_num,
            0.0
        )

    total_serve_won = np.nan

    if (
        not np.isnan(first_won_num)
        and not np.isnan(second_won_num)
    ):
        total_serve_won = (
            first_won_num
            + second_won_num
        )

    opponent_serve_won = np.nan

    if (
        not np.isnan(opp_first_won_num)
        and not np.isnan(opp_second_won_num)
    ):
        opponent_serve_won = (
            opp_first_won_num
            + opp_second_won_num
        )

    return_points_won = np.nan

    if (
        not np.isnan(opp_svpt_num)
        and opp_svpt_num > 0
        and not np.isnan(opponent_serve_won)
    ):
        return_points_won = (
            opp_svpt_num
            - opponent_serve_won
        ) / opp_svpt_num

    return {
        "serve_points_won": safe_div(
            total_serve_won,
            own_svpt
        ),
        "return_points_won": return_points_won,
        "ace_rate": safe_div(
            ace,
            own_svpt
        ),
        "df_rate": safe_div(
            df,
            own_svpt
        ),
        "first_in_rate": safe_div(
            first_in,
            own_svpt
        ),
        "first_won_rate": safe_div(
            first_won,
            first_in
        ),
        "second_won_rate": safe_div(
            second_won,
            second_attempts
        ),
        "bp_won_rate": safe_div(
            bp_won,
            opp_svpt
        ),
        "bp_saved_rate": safe_div(
            bp_saved,
            own_svpt
        ),
    }


def _h2h_key(a, b):
    return tuple(
        sorted(
            [
                a,
                b
            ]
        )
    )


def _h2h_edge(h2h, a, b):
    record = h2h.get(
        _h2h_key(a, b),
        {}
    )

    a_wins = int(
        record.get(a, 0)
    )

    b_wins = int(
        record.get(b, 0)
    )

    total = a_wins + b_wins

    if total == 0:
        return 0.0

    return (
        a_wins
        - b_wins
    ) / (
        total
        + 4.0
    )


def _h2h_counts(h2h, a, b):
    record = h2h.get(
        _h2h_key(a, b),
        {}
    )

    a_wins = int(
        record.get(a, 0)
    )

    b_wins = int(
        record.get(b, 0)
    )

    return (
        a_wins,
        b_wins
    )


def _freeze_history(history):
    return {
        key: list(values)
        for key, values
        in history.items()
    }


def _freeze_surface_history(history):
    return {
        player: {
            surface: list(values)
            for surface, values
            in surfaces.items()
        }
        for player, surfaces
        in history.items()
    }


def _freeze_stat_history(history):
    return {
        player: {
            stat: list(values)
            for stat, values
            in stats.items()
        }
        for player, stats
        in history.items()
    }


def _freeze_surface_stat_history(history):
    return {
        player: {
            surface: {
                stat: list(values)
                for stat, values
                in stats.items()
            }
            for surface, stats
            in surfaces.items()
        }
        for player, surfaces
        in history.items()
    }


def _build_state(df, data_version):
    x = df.dropna(
        subset=[
            "tourney_date",
            "winner_name",
            "loser_name",
        ]
    ).copy()

    x["tourney_date"] = pd.to_datetime(
        x["tourney_date"],
        errors="coerce"
    )

    x = x.dropna(
        subset=[
            "tourney_date"
        ]
    )

    sort_columns = [
        "tourney_date"
    ]

    for optional in [
        "tourney_name",
        "winner_name",
        "loser_name",
    ]:
        if optional in x.columns:
            sort_columns.append(
                optional
            )

    x = x.sort_values(
        sort_columns,
        kind="stable"
    ).reset_index(
        drop=True
    )

    player_history = defaultdict(
        lambda: deque(
            maxlen=RECENT_MATCHES
        )
    )

    surface_history = defaultdict(
        lambda: defaultdict(
            lambda: deque(
                maxlen=RECENT_MATCHES
            )
        )
    )

    rank_history = defaultdict(
        lambda: deque(
            maxlen=RECENT_MATCHES
        )
    )

    general_elo = defaultdict(
        lambda: BASE_ELO
    )

    surface_elo = defaultdict(
        lambda: defaultdict(
            lambda: BASE_ELO
        )
    )

    opponent_elo_history = defaultdict(
        lambda: deque(
            maxlen=RECENT_MATCHES
        )
    )

    quality_history = defaultdict(
        lambda: deque(
            maxlen=RECENT_MATCHES
        )
    )

    stat_history = defaultdict(
        lambda: {
            name: deque(
                maxlen=RECENT_MATCHES
            )
            for name in STAT_NAMES
        }
    )

    surface_stat_history = defaultdict(
        lambda: defaultdict(
            lambda: {
                name: deque(
                    maxlen=RECENT_MATCHES
                )
                for name in STAT_NAMES
            }
        )
    )

    h2h = {}

    for _, day_matches in x.groupby(
        "tourney_date",
        sort=True
    ):
        general_snapshot = dict(
            general_elo
        )

        surface_snapshot = {
            surface: dict(players)
            for surface, players
            in surface_elo.items()
        }

        general_deltas = defaultdict(
            float
        )

        surface_deltas = defaultdict(
            lambda: defaultdict(
                float
            )
        )

        pending_updates = []

        for _, row in day_matches.iterrows():
            winner = str(
                row["winner_name"]
            ).strip()

            loser = str(
                row["loser_name"]
            ).strip()

            surface = str(
                row.get("surface", "")
            ).strip()

            winner_elo = (
                general_snapshot.get(
                    winner,
                    BASE_ELO
                )
            )

            loser_elo = (
                general_snapshot.get(
                    loser,
                    BASE_ELO
                )
            )

            winner_surface_elo = (
                surface_snapshot
                .get(surface, {})
                .get(
                    winner,
                    BASE_ELO
                )
            )

            loser_surface_elo = (
                surface_snapshot
                .get(surface, {})
                .get(
                    loser,
                    BASE_ELO
                )
            )

            expected_winner = (
                expected_probability(
                    winner_elo,
                    loser_elo
                )
            )

            expected_loser = (
                1.0
                - expected_winner
            )

            winner_stats = (
                player_match_stats(
                    row,
                    "w"
                )
            )

            loser_stats = (
                player_match_stats(
                    row,
                    "l"
                )
            )

            pending_updates.append(
                {
                    "winner": winner,
                    "loser": loser,
                    "surface": surface,
                    "winner_rank": safe_num(
                        row.get(
                            "winner_rank"
                        )
                    ),
                    "loser_rank": safe_num(
                        row.get(
                            "loser_rank"
                        )
                    ),
                    "winner_stats": winner_stats,
                    "loser_stats": loser_stats,
                    "winner_elo": winner_elo,
                    "loser_elo": loser_elo,
                    "expected_winner": expected_winner,
                    "expected_loser": expected_loser,
                }
            )

            general_deltas[
                winner
            ] += elo_delta(
                winner_elo,
                loser_elo,
                1.0
            )

            general_deltas[
                loser
            ] += elo_delta(
                loser_elo,
                winner_elo,
                0.0
            )

            surface_deltas[
                surface
            ][winner] += elo_delta(
                winner_surface_elo,
                loser_surface_elo,
                1.0
            )

            surface_deltas[
                surface
            ][loser] += elo_delta(
                loser_surface_elo,
                winner_surface_elo,
                0.0
            )

        for item in pending_updates:
            winner = item[
                "winner"
            ]

            loser = item[
                "loser"
            ]

            surface = item[
                "surface"
            ]

            opponent_elo_history[
                winner
            ].append(
                item[
                    "loser_elo"
                ]
            )

            opponent_elo_history[
                loser
            ].append(
                item[
                    "winner_elo"
                ]
            )

            quality_history[
                winner
            ].append(
                1.0
                - item[
                    "expected_winner"
                ]
            )

            quality_history[
                loser
            ].append(
                0.0
                - item[
                    "expected_loser"
                ]
            )

            for name in STAT_NAMES:
                stat_history[
                    winner
                ][name].append(
                    item[
                        "winner_stats"
                    ][name]
                )

                stat_history[
                    loser
                ][name].append(
                    item[
                        "loser_stats"
                    ][name]
                )

                surface_stat_history[
                    winner
                ][surface][name].append(
                    item[
                        "winner_stats"
                    ][name]
                )

                surface_stat_history[
                    loser
                ][surface][name].append(
                    item[
                        "loser_stats"
                    ][name]
                )

            player_history[
                winner
            ].append(1)

            player_history[
                loser
            ].append(0)

            surface_history[
                winner
            ][surface].append(1)

            surface_history[
                loser
            ][surface].append(0)

            rank_history[
                winner
            ].append(
                item[
                    "winner_rank"
                ]
            )

            rank_history[
                loser
            ].append(
                item[
                    "loser_rank"
                ]
            )

            key = _h2h_key(
                winner,
                loser
            )

            if key not in h2h:
                h2h[key] = {}

            h2h[key][winner] = (
                int(
                    h2h[key].get(
                        winner,
                        0
                    )
                )
                + 1
            )

        for player, delta in (
            general_deltas.items()
        ):
            general_elo[
                player
            ] = (
                general_snapshot.get(
                    player,
                    BASE_ELO
                )
                + delta
            )

        for surface, deltas in (
            surface_deltas.items()
        ):
            for player, delta in (
                deltas.items()
            ):
                surface_elo[
                    surface
                ][player] = (
                    surface_snapshot
                    .get(surface, {})
                    .get(
                        player,
                        BASE_ELO
                    )
                    + delta
                )

    state = {
        "data_version": str(
            data_version
        ),
        "player_history": (
            _freeze_history(
                player_history
            )
        ),
        "surface_history": (
            _freeze_surface_history(
                surface_history
            )
        ),
        "rank_history": (
            _freeze_history(
                rank_history
            )
        ),
        "general_elo": dict(
            general_elo
        ),
        "surface_elo": {
            surface: dict(players)
            for surface, players
            in surface_elo.items()
        },
        "opponent_elo_history": (
            _freeze_history(
                opponent_elo_history
            )
        ),
        "quality_history": (
            _freeze_history(
                quality_history
            )
        ),
        "stat_history": (
            _freeze_stat_history(
                stat_history
            )
        ),
        "surface_stat_history": (
            _freeze_surface_stat_history(
                surface_stat_history
            )
        ),
        "h2h": h2h,
    }

    try:
        joblib.dump(
            state,
            STATE_CACHE_PATH
        )
    except Exception:
        pass

    return state


def _load_state(df, data_version):
    global _MEMORY_STATE
    global _MEMORY_STATE_VERSION

    version = str(
        data_version
    )

    if (
        _MEMORY_STATE is not None
        and _MEMORY_STATE_VERSION
        == version
    ):
        return _MEMORY_STATE

    if STATE_CACHE_PATH.exists():
        try:
            cached = joblib.load(
                STATE_CACHE_PATH
            )

            if str(
                cached.get(
                    "data_version"
                )
            ) == version:
                _MEMORY_STATE = cached
                _MEMORY_STATE_VERSION = version
                return cached
        except Exception:
            pass

    state = _build_state(
        df,
        version
    )

    _MEMORY_STATE = state
    _MEMORY_STATE_VERSION = version

    return state


def clear_v42_state_cache():
    global _MEMORY_STATE
    global _MEMORY_STATE_VERSION

    _MEMORY_STATE = None
    _MEMORY_STATE_VERSION = None

    try:
        if STATE_CACHE_PATH.exists():
            STATE_CACHE_PATH.unlink()
    except Exception:
        pass


def _load_model_package():
    global _MEMORY_MODEL
    global _MEMORY_MODEL_MTIME

    if not MODEL_V42_PATH.exists():
        return None

    try:
        mtime = MODEL_V42_PATH.stat().st_mtime
    except Exception:
        mtime = None

    if (
        _MEMORY_MODEL is not None
        and _MEMORY_MODEL_MTIME
        == mtime
    ):
        return _MEMORY_MODEL

    try:
        package = joblib.load(
            MODEL_V42_PATH
        )
    except Exception:
        return None

    _MEMORY_MODEL = package
    _MEMORY_MODEL_MTIME = mtime

    return package


def get_v42_status():
    package = _load_model_package()

    if package is None:
        return {
            "ok": False,
            "message": (
                "No se encuentra "
                "tennis_model_v4_2_optimizado.joblib"
            ),
        }

    alpha = float(
        package.get(
            "ensemble_alpha_v42",
            1.0
        )
    )

    return {
        "ok": True,
        "version": package.get(
            "version",
            "V4.2"
        ),
        "feature_set": package.get(
            "feature_set",
            ""
        ),
        "features": len(
            package.get(
                "features",
                []
            )
        ),
        "alpha_v42": alpha,
        "alpha_v1": (
            1.0 - alpha
        ),
    }


def _player_general_stats(
    state,
    player
):
    history = state[
        "stat_history"
    ].get(
        player,
        {}
    )

    return {
        name: weighted_mean(
            history.get(
                name,
                []
            )
        )
        for name in STAT_NAMES
    }


def _player_surface_stats(
    state,
    player,
    surface,
    general_stats
):
    if not surface:
        return general_stats.copy()

    surface_results = (
        state[
            "surface_history"
        ]
        .get(player, {})
        .get(surface, [])
    )

    if len(surface_results) < 3:
        return general_stats.copy()

    history = (
        state[
            "surface_stat_history"
        ]
        .get(player, {})
        .get(surface, {})
    )

    return {
        name: weighted_mean(
            history.get(
                name,
                []
            )
        )
        for name in STAT_NAMES
    }


def _surface_forms(
    state,
    player,
    surface,
    form_simple,
    form_weighted
):
    if not surface:
        return (
            form_simple,
            form_weighted
        )

    history = (
        state[
            "surface_history"
        ]
        .get(player, {})
        .get(surface, [])
    )

    simple = simple_mean(
        history
    )

    weighted = weighted_mean(
        history
    )

    if (
        len(history) < 3
        or np.isnan(simple)
    ):
        simple = form_simple

    if (
        len(history) < 3
        or np.isnan(weighted)
    ):
        weighted = form_weighted

    return (
        simple,
        weighted
    )


def _player_features(
    state,
    player,
    surface
):
    results = (
        state[
            "player_history"
        ].get(
            player,
            []
        )
    )

    ranks = (
        state[
            "rank_history"
        ].get(
            player,
            []
        )
    )

    form_simple = simple_mean(
        results
    )

    form_weighted = weighted_mean(
        results
    )

    (
        surface_form_simple,
        surface_form_weighted,
    ) = _surface_forms(
        state,
        player,
        surface,
        form_simple,
        form_weighted
    )

    rank = last_valid(
        ranks,
        999.0
    )

    rank_mom = rank_momentum(
        ranks
    )

    elo = float(
        state[
            "general_elo"
        ].get(
            player,
            BASE_ELO
        )
    )

    if surface:
        surface_elo = float(
            state[
                "surface_elo"
            ]
            .get(surface, {})
            .get(
                player,
                BASE_ELO
            )
        )
    else:
        surface_elo = elo

    quality_form = weighted_mean(
        state[
            "quality_history"
        ].get(
            player,
            []
        )
    )

    avg_opponent_elo = weighted_mean(
        state[
            "opponent_elo_history"
        ].get(
            player,
            []
        )
    )

    general_stats = _player_general_stats(
        state,
        player
    )

    surface_stats = _player_surface_stats(
        state,
        player,
        surface,
        general_stats
    )

    return {
        "form_simple": form_simple,
        "form_weighted": form_weighted,
        "surface_form_simple": (
            surface_form_simple
        ),
        "surface_form_weighted": (
            surface_form_weighted
        ),
        "rank": rank,
        "rank_momentum": rank_mom,
        "elo": elo,
        "surface_elo": surface_elo,
        "quality_form": quality_form,
        "avg_opponent_elo": (
            avg_opponent_elo
        ),
        "stats": general_stats,
        "surface_stats": (
            surface_stats
        ),
    }


def _confidence_label(probability):
    confidence = max(
        probability,
        1.0 - probability
    )

    if confidence >= 0.80:
        return "💎 Elite"

    if confidence >= 0.75:
        return "🔥 Muy fuerte"

    if confidence >= 0.70:
        return "🟢 Fuerte"

    if confidence >= 0.65:
        return "🟡 Interesante"

    return "⚪ Normal"


def predict_match_v42(
    df,
    a,
    b,
    surface=None,
    recent_window=25,
    use_elo=True,
    data_version=""
):
    package = _load_model_package()

    if package is None:
        fallback = predict_match_v1_fallback(
            df,
            a,
            b,
            surface=surface,
            recent_window=recent_window,
            use_elo=use_elo
        )

        if fallback.get(
            "ok"
        ):
            fallback[
                "model_version"
            ] = "V1 fallback"

            fallback[
                "model_warning"
            ] = (
                "No se encontró el modelo V4.2."
            )

        return fallback

    state = _load_state(
        df,
        data_version
    )

    sa = _player_features(
        state,
        a,
        surface
    )

    sb = _player_features(
        state,
        b,
        surface
    )

    if (
        np.isnan(
            sa[
                "form_simple"
            ]
        )
        or
        np.isnan(
            sb[
                "form_simple"
            ]
        )
    ):
        return {
            "ok": False,
            "message": (
                "No hay historial suficiente "
                "para ambos jugadores."
            ),
        }

    h2h_edge = _h2h_edge(
        state[
            "h2h"
        ],
        a,
        b
    )

    feature_values = {
        "rank_diff": (
            sb["rank"]
            - sa["rank"]
        ),

        "rank_momentum_diff": (
            sa[
                "rank_momentum"
            ]
            - sb[
                "rank_momentum"
            ]
        ),

        "form_diff": (
            sa["form_simple"]
            - sb["form_simple"]
        ),

        "weighted_form_diff": (
            sa[
                "form_weighted"
            ]
            - sb[
                "form_weighted"
            ]
        ),

        "surface_weighted_form_diff": (
            sa[
                "surface_form_weighted"
            ]
            - sb[
                "surface_form_weighted"
            ]
        ),

        "elo_diff": (
            sa["elo"]
            - sb["elo"]
        ),

        "surface_elo_diff": (
            sa[
                "surface_elo"
            ]
            - sb[
                "surface_elo"
            ]
        ),

        "quality_form_diff": (
            sa[
                "quality_form"
            ]
            - sb[
                "quality_form"
            ]
        ),

        "avg_opponent_elo_diff": (
            sa[
                "avg_opponent_elo"
            ]
            - sb[
                "avg_opponent_elo"
            ]
        ),

        "serve_points_won_diff": (
            sa[
                "stats"
            ][
                "serve_points_won"
            ]
            - sb[
                "stats"
            ][
                "serve_points_won"
            ]
        ),

        "return_points_won_diff": (
            sa[
                "stats"
            ][
                "return_points_won"
            ]
            - sb[
                "stats"
            ][
                "return_points_won"
            ]
        ),

        "surface_serve_points_won_diff": (
            sa[
                "surface_stats"
            ][
                "serve_points_won"
            ]
            - sb[
                "surface_stats"
            ][
                "serve_points_won"
            ]
        ),

        "surface_return_points_won_diff": (
            sa[
                "surface_stats"
            ][
                "return_points_won"
            ]
            - sb[
                "surface_stats"
            ][
                "return_points_won"
            ]
        ),

        "ace_rate_diff": (
            sa[
                "stats"
            ][
                "ace_rate"
            ]
            - sb[
                "stats"
            ][
                "ace_rate"
            ]
        ),

        "df_rate_diff": (
            sa[
                "stats"
            ][
                "df_rate"
            ]
            - sb[
                "stats"
            ][
                "df_rate"
            ]
        ),

        "first_in_rate_diff": (
            sa[
                "stats"
            ][
                "first_in_rate"
            ]
            - sb[
                "stats"
            ][
                "first_in_rate"
            ]
        ),

        "first_won_rate_diff": (
            sa[
                "stats"
            ][
                "first_won_rate"
            ]
            - sb[
                "stats"
            ][
                "first_won_rate"
            ]
        ),

        "second_won_rate_diff": (
            sa[
                "stats"
            ][
                "second_won_rate"
            ]
            - sb[
                "stats"
            ][
                "second_won_rate"
            ]
        ),

        "h2h_edge": h2h_edge,
    }

    v42_features = package.get(
        "features",
        []
    )

    medians = package.get(
        "feature_medians",
        {}
    )

    v42_row = {}

    for feature in v42_features:
        value = safe_num(
            feature_values.get(
                feature,
                np.nan
            )
        )

        if np.isnan(value):
            value = safe_num(
                medians.get(
                    feature,
                    0.0
                )
            )

        if np.isnan(value):
            value = 0.0

        v42_row[
            feature
        ] = value

    X42 = pd.DataFrame(
        [
            v42_row
        ],
        columns=v42_features
    )

    model_v42 = package[
        "model"
    ]

    prob_v42 = float(
        model_v42.predict_proba(
            X42
        )[0, 1]
    )

    # --------------------------------------------------
    # COMPONENTE V1 DEL ENSEMBLE
    # --------------------------------------------------
    # El V1 del optimizador se entrenó con el ranking
    # disponible en cada partido. Para live usamos el
    # último ranking conocido de la base.
    # --------------------------------------------------

    v1_model = package.get(
        "v1_model_for_ensemble"
    )

    alpha = float(
        package.get(
            "ensemble_alpha_v42",
            1.0
        )
    )

    prob_v1 = None

    if v1_model is not None:
        v1_values = {
            "rank_diff": (
                sb["rank"]
                - sa["rank"]
            ),
            "form_diff": (
                sa[
                    "form_simple"
                ]
                - sb[
                    "form_simple"
                ]
            ),
            "surface_form_diff": (
                sa[
                    "surface_form_simple"
                ]
                - sb[
                    "surface_form_simple"
                ]
            ),
            "elo_diff": (
                sa["elo"]
                - sb["elo"]
            ),
        }

        v1_medians = package.get(
            "v1_feature_medians",
            {}
        )

        for key, value in (
            v1_values.items()
        ):
            value = safe_num(value)

            if np.isnan(value):
                value = safe_num(
                    v1_medians.get(
                        key,
                        0.0
                    )
                )

            if np.isnan(value):
                value = 0.0

            v1_values[
                key
            ] = value

        X1 = pd.DataFrame(
            [
                v1_values
            ],
            columns=[
                "rank_diff",
                "form_diff",
                "surface_form_diff",
                "elo_diff",
            ]
        )

        prob_v1 = float(
            v1_model.predict_proba(
                X1
            )[0, 1]
        )

        prob_a = (
            alpha
            * prob_v42
            +
            (
                1.0
                - alpha
            )
            * prob_v1
        )
    else:
        prob_a = prob_v42

    prob_a = float(
        min(
            max(
                prob_a,
                0.01
            ),
            0.99
        )
    )

    prob_b = (
        1.0
        - prob_a
    )

    a_wins, b_wins = _h2h_counts(
        state[
            "h2h"
        ],
        a,
        b
    )

    comparison = [
        {
            "Factor": "Forma reciente",
            "Jugador A": (
                f"{sa['form_simple']:.1%}"
            ),
            "Jugador B": (
                f"{sb['form_simple']:.1%}"
            ),
        },
        {
            "Factor": "Forma ponderada",
            "Jugador A": (
                f"{sa['form_weighted']:.1%}"
            ),
            "Jugador B": (
                f"{sb['form_weighted']:.1%}"
            ),
        },
        {
            "Factor": (
                "Forma en superficie"
            ),
            "Jugador A": (
                f"{sa['surface_form_weighted']:.1%}"
            ),
            "Jugador B": (
                f"{sb['surface_form_weighted']:.1%}"
            ),
        },
        {
            "Factor": "Ranking reciente",
            "Jugador A": (
                f"{sa['rank']:.0f}"
            ),
            "Jugador B": (
                f"{sb['rank']:.0f}"
            ),
        },
        {
            "Factor": "Elo general",
            "Jugador A": (
                f"{sa['elo']:.0f}"
            ),
            "Jugador B": (
                f"{sb['elo']:.0f}"
            ),
        },
        {
            "Factor": "Elo superficie",
            "Jugador A": (
                f"{sa['surface_elo']:.0f}"
            ),
            "Jugador B": (
                f"{sb['surface_elo']:.0f}"
            ),
        },
        {
            "Factor": (
                "% puntos de saque ganados"
            ),
            "Jugador A": (
                f"{sa['stats']['serve_points_won']:.1%}"
                if not np.isnan(
                    sa[
                        "stats"
                    ][
                        "serve_points_won"
                    ]
                )
                else "N/D"
            ),
            "Jugador B": (
                f"{sb['stats']['serve_points_won']:.1%}"
                if not np.isnan(
                    sb[
                        "stats"
                    ][
                        "serve_points_won"
                    ]
                )
                else "N/D"
            ),
        },
        {
            "Factor": (
                "% puntos al resto ganados"
            ),
            "Jugador A": (
                f"{sa['stats']['return_points_won']:.1%}"
                if not np.isnan(
                    sa[
                        "stats"
                    ][
                        "return_points_won"
                    ]
                )
                else "N/D"
            ),
            "Jugador B": (
                f"{sb['stats']['return_points_won']:.1%}"
                if not np.isnan(
                    sb[
                        "stats"
                    ][
                        "return_points_won"
                    ]
                )
                else "N/D"
            ),
        },
    ]

    model_name = (
        f"Ensemble V4.2 "
        f"({alpha:.0%} V4.2 + "
        f"{1.0 - alpha:.0%} V1)"
    )

    explanation = (
        "Predicción del Ensemble V4.2, que combina "
        "forma reciente y ponderada, ranking y momentum, "
        "Elo general y por superficie, calidad de rivales, "
        "saque, devolución y H2H histórico. "
        f"Probabilidad V4.2 pura: {prob_v42:.1%}. "
        + (
            f"Probabilidad V1: {prob_v1:.1%}. "
            if prob_v1 is not None
            else ""
        )
        + f"Resultado final: {prob_a:.1%} para Jugador A."
    )

    return {
        "ok": True,
        "prob_a": prob_a,
        "prob_b": prob_b,
        "prob_v42": prob_v42,
        "prob_v1": prob_v1,
        "ensemble_alpha": alpha,
        "confidence_label": (
            _confidence_label(
                prob_a
            )
        ),
        "comparison": comparison,
        "h2h": {
            "a_wins": a_wins,
            "b_wins": b_wins,
            "total": (
                a_wins
                + b_wins
            ),
        },
        "elo_a": (
            sa[
                "surface_elo"
            ]
            if surface
            else sa["elo"]
        ),
        "elo_b": (
            sb[
                "surface_elo"
            ]
            if surface
            else sb["elo"]
        ),
        "general_elo_a": sa["elo"],
        "general_elo_b": sb["elo"],
        "surface_elo_a": (
            sa[
                "surface_elo"
            ]
        ),
        "surface_elo_b": (
            sb[
                "surface_elo"
            ]
        ),
        "model_version": model_name,
        "explanation": explanation,
    }
