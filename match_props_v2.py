from __future__ import annotations

import hashlib
import math
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd


MODEL_VERSION = "PROPS V1.1"


def _clip(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def _safe_float(value, default=0.0) -> float:
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except Exception:
        pass
    return float(default)


def _normalize_surface(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _player_rows(df: pd.DataFrame, player: str) -> pd.DataFrame:
    """Convierte el histórico partido a formato jugador-partido."""
    if df.empty:
        return pd.DataFrame()

    win = df[df["winner_name"].astype(str) == str(player)].copy()
    lose = df[df["loser_name"].astype(str) == str(player)].copy()

    rows = []

    if not win.empty:
        rows.append(
            pd.DataFrame(
                {
                    "tourney_date": win["tourney_date"],
                    "tourney_name": win["tourney_name"],
                    "surface": win["surface"],
                    "opponent": win["loser_name"],
                    "won": 1,
                    "rank": win["winner_rank"],
                    "aces": win["w_ace"],
                    "double_faults": win["w_df"],
                    "svpt": win["w_svpt"],
                    "service_points_won": (
                        pd.to_numeric(win["w_1stWon"], errors="coerce")
                        + pd.to_numeric(win["w_2ndWon"], errors="coerce")
                    ),
                    "opp_aces": win["l_ace"],
                    "opp_double_faults": win["l_df"],
                    "opp_svpt": win["l_svpt"],
                    "opp_service_points_won": (
                        pd.to_numeric(win["l_1stWon"], errors="coerce")
                        + pd.to_numeric(win["l_2ndWon"], errors="coerce")
                    ),
                }
            )
        )

    if not lose.empty:
        rows.append(
            pd.DataFrame(
                {
                    "tourney_date": lose["tourney_date"],
                    "tourney_name": lose["tourney_name"],
                    "surface": lose["surface"],
                    "opponent": lose["winner_name"],
                    "won": 0,
                    "rank": lose["loser_rank"],
                    "aces": lose["l_ace"],
                    "double_faults": lose["l_df"],
                    "svpt": lose["l_svpt"],
                    "service_points_won": (
                        pd.to_numeric(lose["l_1stWon"], errors="coerce")
                        + pd.to_numeric(lose["l_2ndWon"], errors="coerce")
                    ),
                    "opp_aces": lose["w_ace"],
                    "opp_double_faults": lose["w_df"],
                    "opp_svpt": lose["w_svpt"],
                    "opp_service_points_won": (
                        pd.to_numeric(lose["w_1stWon"], errors="coerce")
                        + pd.to_numeric(lose["w_2ndWon"], errors="coerce")
                    ),
                }
            )
        )

    if not rows:
        return pd.DataFrame()

    out = pd.concat(rows, ignore_index=True)
    out["tourney_date"] = pd.to_datetime(out["tourney_date"], errors="coerce")

    numeric = [
        "rank",
        "aces",
        "double_faults",
        "svpt",
        "service_points_won",
        "opp_aces",
        "opp_double_faults",
        "opp_svpt",
        "opp_service_points_won",
    ]

    for col in numeric:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.sort_values("tourney_date").reset_index(drop=True)
    return out


def _weighted_ratio(
    frame: pd.DataFrame,
    numerator: str,
    denominator: str,
    prior_rate: float,
    prior_opportunities: float,
) -> float:
    valid = frame[[numerator, denominator]].dropna().copy()
    valid = valid[valid[denominator] > 0]

    if valid.empty:
        return float(prior_rate)

    n = float(valid[numerator].clip(lower=0).sum())
    d = float(valid[denominator].clip(lower=0).sum())

    if d <= 0:
        return float(prior_rate)

    return float(
        (n + prior_rate * prior_opportunities)
        / (d + prior_opportunities)
    )


def _weighted_mean(values: Iterable[float], default: float) -> float:
    series = pd.to_numeric(pd.Series(list(values)), errors="coerce").dropna()
    if series.empty:
        return float(default)
    return float(series.mean())


def _league_rates(df: pd.DataFrame, surface: Optional[str]) -> Dict[str, float]:
    work = df.copy()
    if surface is not None and "surface" in work.columns:
        surface_df = work[work["surface"].astype(str) == str(surface)]
        if len(surface_df) >= 150:
            work = surface_df

    w_svpt = pd.to_numeric(work.get("w_svpt"), errors="coerce")
    l_svpt = pd.to_numeric(work.get("l_svpt"), errors="coerce")

    ace_num = pd.to_numeric(work.get("w_ace"), errors="coerce").sum(skipna=True)
    ace_num += pd.to_numeric(work.get("l_ace"), errors="coerce").sum(skipna=True)

    df_num = pd.to_numeric(work.get("w_df"), errors="coerce").sum(skipna=True)
    df_num += pd.to_numeric(work.get("l_df"), errors="coerce").sum(skipna=True)

    spw_num = (
        pd.to_numeric(work.get("w_1stWon"), errors="coerce").sum(skipna=True)
        + pd.to_numeric(work.get("w_2ndWon"), errors="coerce").sum(skipna=True)
        + pd.to_numeric(work.get("l_1stWon"), errors="coerce").sum(skipna=True)
        + pd.to_numeric(work.get("l_2ndWon"), errors="coerce").sum(skipna=True)
    )

    svpt = w_svpt.sum(skipna=True) + l_svpt.sum(skipna=True)

    if not math.isfinite(float(svpt)) or float(svpt) <= 0:
        return {
            "ace_rate": 0.085,
            "df_rate": 0.040,
            "avg_svpt": 72.0,
            "serve_point_win_rate": 0.635,
        }

    all_svpt = pd.concat([w_svpt, l_svpt], ignore_index=True).dropna()
    avg_svpt = float(all_svpt.mean()) if not all_svpt.empty else 72.0

    return {
        "ace_rate": _clip(float(ace_num) / float(svpt), 0.015, 0.25),
        "df_rate": _clip(float(df_num) / float(svpt), 0.008, 0.12),
        "avg_svpt": _clip(avg_svpt, 45.0, 110.0),
        "serve_point_win_rate": _clip(float(spw_num) / float(svpt), 0.50, 0.78),
    }


def _profile(
    history: pd.DataFrame,
    surface: Optional[str],
    recent_window: int,
    league: Dict[str, float],
) -> Dict[str, float]:
    if history.empty:
        return {
            "ace_rate": league["ace_rate"],
            "df_rate": league["df_rate"],
            "ace_allowed_rate": league["ace_rate"],
            "df_allowed_rate": league["df_rate"],
            "avg_svpt": league["avg_svpt"],
            "serve_point_win_rate": league["serve_point_win_rate"],
            "return_point_win_rate": 1.0 - league["serve_point_win_rate"],
            "matches": 0,
            "surface_matches": 0,
        }

    recent = history.tail(max(8, int(recent_window))).copy()

    surface_hist = history
    if surface is not None:
        surface_hist = history[history["surface"].astype(str) == str(surface)].copy()

    surface_recent = surface_hist.tail(max(6, min(int(recent_window), 20)))

    overall_ace = _weighted_ratio(
        recent, "aces", "svpt", league["ace_rate"], 500.0
    )
    surface_ace = _weighted_ratio(
        surface_recent, "aces", "svpt", league["ace_rate"], 350.0
    )

    overall_df = _weighted_ratio(
        recent, "double_faults", "svpt", league["df_rate"], 500.0
    )
    surface_df = _weighted_ratio(
        surface_recent, "double_faults", "svpt", league["df_rate"], 350.0
    )

    ace_allowed = _weighted_ratio(
        recent, "opp_aces", "opp_svpt", league["ace_rate"], 550.0
    )
    surface_ace_allowed = _weighted_ratio(
        surface_recent, "opp_aces", "opp_svpt", league["ace_rate"], 400.0
    )

    df_allowed = _weighted_ratio(
        recent, "opp_double_faults", "opp_svpt", league["df_rate"], 650.0
    )
    surface_df_allowed = _weighted_ratio(
        surface_recent,
        "opp_double_faults",
        "opp_svpt",
        league["df_rate"],
        450.0,
    )

    serve_spw = _weighted_ratio(
        recent,
        "service_points_won",
        "svpt",
        league["serve_point_win_rate"],
        700.0,
    )
    surface_serve_spw = _weighted_ratio(
        surface_recent,
        "service_points_won",
        "svpt",
        league["serve_point_win_rate"],
        450.0,
    )

    opp_spw = _weighted_ratio(
        recent,
        "opp_service_points_won",
        "opp_svpt",
        league["serve_point_win_rate"],
        800.0,
    )
    surface_opp_spw = _weighted_ratio(
        surface_recent,
        "opp_service_points_won",
        "opp_svpt",
        league["serve_point_win_rate"],
        500.0,
    )

    if surface is None or surface_recent.empty:
        surface_weight = 0.0
    else:
        surface_weight = _clip(len(surface_recent) / 12.0, 0.15, 0.62)

    ace_rate = (1.0 - surface_weight) * overall_ace + surface_weight * surface_ace
    df_rate = (1.0 - surface_weight) * overall_df + surface_weight * surface_df

    allow_ace = (
        (1.0 - surface_weight) * ace_allowed
        + surface_weight * surface_ace_allowed
    )
    allow_df = (
        (1.0 - surface_weight) * df_allowed
        + surface_weight * surface_df_allowed
    )

    serve_point_win_rate = (
        (1.0 - surface_weight) * serve_spw
        + surface_weight * surface_serve_spw
    )
    opp_serve_point_win_rate = (
        (1.0 - surface_weight) * opp_spw
        + surface_weight * surface_opp_spw
    )

    svpt_recent = recent["svpt"].dropna()
    svpt_surface = surface_recent["svpt"].dropna()

    avg_recent = _weighted_mean(svpt_recent, league["avg_svpt"])
    avg_surface = _weighted_mean(svpt_surface, avg_recent)
    avg_svpt = (
        (1.0 - min(surface_weight, 0.45)) * avg_recent
        + min(surface_weight, 0.45) * avg_surface
    )

    return {
        "ace_rate": _clip(ace_rate, 0.01, 0.28),
        "df_rate": _clip(df_rate, 0.008, 0.13),
        "ace_allowed_rate": _clip(allow_ace, 0.01, 0.28),
        "df_allowed_rate": _clip(allow_df, 0.008, 0.13),
        "avg_svpt": _clip(avg_svpt, 42.0, 115.0),
        "serve_point_win_rate": _clip(serve_point_win_rate, 0.50, 0.78),
        "return_point_win_rate": _clip(1.0 - opp_serve_point_win_rate, 0.20, 0.50),
        "matches": int(len(recent)),
        "surface_matches": int(len(surface_recent)),
    }


def _match_win_from_set_prob(set_prob: float, best_of: int) -> float:
    s = _clip(set_prob, 0.000001, 0.999999)
    q = 1.0 - s

    if int(best_of) == 3:
        return s * s * (3.0 - 2.0 * s)

    if int(best_of) == 5:
        return s**3 * (1.0 + 3.0 * q + 6.0 * q * q)

    raise ValueError("best_of debe ser 3 o 5")


def set_probability_from_match_probability(match_prob: float, best_of: int) -> float:
    target = _clip(_safe_float(match_prob, 0.5), 0.000001, 0.999999)
    lo = 0.000001
    hi = 0.999999

    for _ in range(80):
        mid = (lo + hi) / 2.0
        value = _match_win_from_set_prob(mid, best_of)

        if value < target:
            lo = mid
        else:
            hi = mid

    return float((lo + hi) / 2.0)


def exact_score_probabilities(match_prob_a: float, best_of: int) -> Dict[str, float]:
    best_of = int(best_of)
    s = set_probability_from_match_probability(match_prob_a, best_of)
    q = 1.0 - s

    if best_of == 3:
        probs = {
            "A 2-0": s**2,
            "A 2-1": 2.0 * s**2 * q,
            "B 2-0": q**2,
            "B 2-1": 2.0 * q**2 * s,
        }
    elif best_of == 5:
        probs = {
            "A 3-0": s**3,
            "A 3-1": 3.0 * s**3 * q,
            "A 3-2": 6.0 * s**3 * q**2,
            "B 3-0": q**3,
            "B 3-1": 3.0 * q**3 * s,
            "B 3-2": 6.0 * q**3 * s**2,
        }
    else:
        raise ValueError("best_of debe ser 3 o 5")

    total = sum(probs.values())
    if total > 0:
        probs = {k: float(v / total) for k, v in probs.items()}

    return probs


def _sets_in_score_label(label: str) -> int:
    if "2-0" in label:
        return 2
    if "2-1" in label:
        return 3
    if "3-0" in label:
        return 3
    if "3-1" in label:
        return 4
    if "3-2" in label:
        return 5
    return 0


def expected_sets_from_scores(score_probs: Dict[str, float]) -> float:
    return float(
        sum(float(prob) * _sets_in_score_label(label) for label, prob in score_probs.items())
    )


def total_sets_over_probability(score_probs: Dict[str, float], line: float) -> float:
    line = _safe_float(line, 2.5)
    return _clip(
        sum(
            float(prob)
            for label, prob in score_probs.items()
            if _sets_in_score_label(label) > line
        ),
        0.0,
        1.0,
    )


def suggested_half_line(mean_value: float, minimum: float = 0.5) -> float:
    mean_value = max(0.0, _safe_float(mean_value, 0.0))
    line = math.floor(mean_value) + 0.5
    return float(max(minimum, line))


def poisson_over_probability(mean_value: float, line: float) -> float:
    """Probabilidad P(X > line) con X~Poisson(mean). Pensado para líneas x.5."""
    lam = max(0.000001, _safe_float(mean_value, 0.000001))
    line = _safe_float(line, 0.5)
    threshold = int(math.floor(line) + 1)

    if threshold <= 0:
        return 1.0

    term = math.exp(-lam)
    cdf = term

    for k in range(1, threshold):
        term *= lam / k
        cdf += term

        if term < 1e-15 and k > lam:
            break

    return _clip(1.0 - cdf, 0.0, 1.0)


def market_metrics(probability: float, odds: float) -> Dict[str, float]:
    p = _clip(_safe_float(probability, 0.0), 0.0, 1.0)
    odds = max(1.000001, _safe_float(odds, 1.000001))

    fair = 1.0 / p if p > 0 else 0.0
    implied = 1.0 / odds
    edge = p - implied
    ev = p * odds - 1.0

    return {
        "probability": p,
        "fair_odds": fair,
        "implied_probability": implied,
        "edge": edge,
        "ev": ev,
    }


def push_market_metrics(
    win_probability: float,
    loss_probability: float,
    push_probability: float,
    odds: float,
) -> Dict[str, float]:
    """Métricas para mercados donde el empate devuelve la apuesta."""
    p_win = _clip(_safe_float(win_probability, 0.0), 0.0, 1.0)
    p_loss = _clip(_safe_float(loss_probability, 0.0), 0.0, 1.0)
    p_push = _clip(_safe_float(push_probability, 0.0), 0.0, 1.0)
    total = p_win + p_loss + p_push

    if total > 0:
        p_win /= total
        p_loss /= total
        p_push /= total

    non_push = p_win + p_loss
    conditional = p_win / non_push if non_push > 0 else 0.0
    fair = non_push / p_win if p_win > 0 else 0.0
    odds = max(1.000001, _safe_float(odds, 1.000001))
    implied = 1.0 / odds
    edge = conditional - implied
    ev = p_win * (odds - 1.0) - p_loss

    return {
        "probability": p_win,
        "loss_probability": p_loss,
        "push_probability": p_push,
        "conditional_probability": conditional,
        "fair_odds": fair,
        "implied_probability": implied,
        "edge": edge,
        "ev": ev,
    }


def _player_projection(
    own: Dict[str, float],
    rival: Dict[str, float],
    expected_sets: float,
    league: Dict[str, float],
) -> Dict[str, float]:
    # La base histórica es mayoritariamente BO3. 2.35 sets sirve como
    # unidad de duración base. En BO5 el escalado viene del expected_sets.
    duration_scale = _clip(expected_sets / 2.35, 0.78, 2.25)

    base_svpt = 0.72 * own["avg_svpt"] + 0.28 * rival["avg_svpt"]
    expected_svpt = _clip(base_svpt * duration_scale, 38.0, 185.0)

    own_ace = max(0.005, own["ace_rate"])
    rival_allow = max(0.005, rival["ace_allowed_rate"])
    league_ace = max(0.005, league["ace_rate"])

    ace_matchup_factor = _clip(
        math.sqrt(rival_allow / league_ace),
        0.72,
        1.35,
    )
    ace_rate = _clip(own_ace * ace_matchup_factor, 0.008, 0.30)

    own_df = max(0.004, own["df_rate"])
    rival_df_allow = max(0.004, rival["df_allowed_rate"])
    league_df = max(0.004, league["df_rate"])

    df_matchup_factor = _clip(
        0.90 + 0.10 * (rival_df_allow / league_df),
        0.90,
        1.12,
    )
    df_rate = _clip(own_df * df_matchup_factor, 0.006, 0.14)

    expected_aces = _clip(expected_svpt * ace_rate, 0.2, 35.0)
    expected_df = _clip(expected_svpt * df_rate, 0.2, 16.0)

    ace_line = suggested_half_line(expected_aces)
    df_line = suggested_half_line(expected_df)

    return {
        "expected_aces": expected_aces,
        "expected_double_faults": expected_df,
        "expected_service_points": expected_svpt,
        "ace_rate": ace_rate,
        "double_fault_rate": df_rate,
        "suggested_ace_line": ace_line,
        "suggested_df_line": df_line,
        "suggested_ace_over_probability": poisson_over_probability(expected_aces, ace_line),
        "suggested_df_over_probability": poisson_over_probability(expected_df, df_line),
        "sample_matches": int(own["matches"]),
        "surface_sample_matches": int(own["surface_matches"]),
    }


def _game_hold_probability(point_win_probability: float) -> float:
    """Probabilidad de mantener servicio a partir de P(ganar punto al saque)."""
    p = _clip(_safe_float(point_win_probability, 0.635), 0.40, 0.85)
    q = 1.0 - p
    pre_deuce = p**4 * (1.0 + 4.0 * q + 10.0 * q * q)
    reach_deuce = 20.0 * p**3 * q**3
    from_deuce = p * p / (p * p + q * q)
    return _clip(pre_deuce + reach_deuce * from_deuce, 0.05, 0.995)


def _matchup_service_point_probability(
    server: Dict[str, float],
    returner: Dict[str, float],
    league: Dict[str, float],
) -> float:
    own = server["serve_point_win_rate"]
    allowed_by_returner = 1.0 - returner["return_point_win_rate"]
    baseline = league["serve_point_win_rate"]

    # El saque propio pesa más; el restador corrige el matchup.
    matchup = baseline + 0.68 * (own - baseline) + 0.32 * (allowed_by_returner - baseline)
    return _clip(matchup, 0.50, 0.79)


def _stable_seed(*parts) -> int:
    text = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32 - 1)


def _simulate_single_set(
    rng: np.random.Generator,
    hold_a: float,
    hold_b: float,
    tiebreak_prob_a: float,
    starting_server: int,
):
    games_a = 0
    games_b = 0
    server = int(starting_server)

    while True:
        if games_a == 6 and games_b == 6:
            if rng.random() < tiebreak_prob_a:
                games_a += 1
            else:
                games_b += 1

            # Aproximación suficiente para el servidor inicial del siguiente set.
            server = 1 - server
            return games_a, games_b, server

        if server == 0:
            a_wins_game = rng.random() < hold_a
        else:
            a_wins_game = rng.random() >= hold_b

        if a_wins_game:
            games_a += 1
        else:
            games_b += 1

        server = 1 - server

        if max(games_a, games_b) >= 6 and abs(games_a - games_b) >= 2:
            return games_a, games_b, server


def _distribution_from_weighted_values(values: np.ndarray, weights: np.ndarray) -> Dict[int, float]:
    out: Dict[int, float] = {}
    total_weight = float(weights.sum())
    if total_weight <= 0:
        return out

    for value in np.unique(values):
        mask = values == value
        out[int(value)] = float(weights[mask].sum() / total_weight)

    return out


def _simulate_game_markets(
    *,
    player_a: str,
    player_b: str,
    surface: Optional[str],
    best_of: int,
    match_prob_a: float,
    set_prob_a: float,
    prof_a: Dict[str, float],
    prof_b: Dict[str, float],
    league: Dict[str, float],
    simulations: int = 24000,
) -> Dict[str, object]:
    p_a_serve = _matchup_service_point_probability(prof_a, prof_b, league)
    p_b_serve = _matchup_service_point_probability(prof_b, prof_a, league)
    hold_a = _game_hold_probability(p_a_serve)
    hold_b = _game_hold_probability(p_b_serve)

    seed = _stable_seed(
        player_a,
        player_b,
        surface or "ALL",
        best_of,
        round(match_prob_a, 6),
        round(p_a_serve, 5),
        round(p_b_serve, 5),
    )
    rng = np.random.default_rng(seed)

    sims = max(5000, int(simulations))
    needed_sets = 2 if int(best_of) == 3 else 3

    total_games = np.empty(sims, dtype=np.int16)
    games_a_arr = np.empty(sims, dtype=np.int16)
    games_b_arr = np.empty(sims, dtype=np.int16)
    winner_a_arr = np.empty(sims, dtype=np.int8)

    for i in range(sims):
        sets_a = 0
        sets_b = 0
        games_a = 0
        games_b = 0
        server = int(rng.integers(0, 2))

        while sets_a < needed_sets and sets_b < needed_sets:
            ga, gb, server = _simulate_single_set(
                rng,
                hold_a,
                hold_b,
                set_prob_a,
                server,
            )
            games_a += ga
            games_b += gb

            if ga > gb:
                sets_a += 1
            else:
                sets_b += 1

        games_a_arr[i] = games_a
        games_b_arr[i] = games_b
        total_games[i] = games_a + games_b
        winner_a_arr[i] = 1 if sets_a > sets_b else 0

    raw_prob_a = float(winner_a_arr.mean())
    raw_prob_a = _clip(raw_prob_a, 0.0001, 0.9999)
    target = _clip(match_prob_a, 0.0001, 0.9999)

    # Reponderamos por ganador para que el mercado de juegos respete exactamente
    # la probabilidad principal del Ensemble V4.2.
    weights = np.where(
        winner_a_arr == 1,
        target / raw_prob_a,
        (1.0 - target) / (1.0 - raw_prob_a),
    ).astype(float)

    weight_sum = float(weights.sum())
    expected_games_a = float(np.sum(weights * games_a_arr) / weight_sum)
    expected_games_b = float(np.sum(weights * games_b_arr) / weight_sum)
    expected_total = expected_games_a + expected_games_b
    margin_a = games_a_arr.astype(int) - games_b_arr.astype(int)
    expected_margin_a = float(np.sum(weights * margin_a) / weight_sum)

    total_distribution = _distribution_from_weighted_values(total_games.astype(int), weights)
    margin_distribution = _distribution_from_weighted_values(margin_a, weights)

    total_line = suggested_half_line(expected_total, 12.5 if best_of == 3 else 18.5)

    spread_size = max(0.5, math.floor(abs(expected_margin_a)) - 0.5)
    if expected_margin_a >= 0:
        handicap_a = -spread_size
        handicap_b = spread_size
    else:
        handicap_a = spread_size
        handicap_b = -spread_size

    return {
        "serve_point_win_a": p_a_serve,
        "serve_point_win_b": p_b_serve,
        "hold_probability_a": hold_a,
        "hold_probability_b": hold_b,
        "expected_games_a": expected_games_a,
        "expected_games_b": expected_games_b,
        "expected_total_games": expected_total,
        "expected_game_margin_a": expected_margin_a,
        "total_games_distribution": total_distribution,
        "game_margin_a_distribution": margin_distribution,
        "suggested_total_games_line": total_line,
        "suggested_handicap_a": float(handicap_a),
        "suggested_handicap_b": float(handicap_b),
        "simulation_match_prob_a_raw": raw_prob_a,
        "simulations": sims,
    }


def distribution_over_probability(distribution: Dict[object, float], line: float) -> float:
    line = _safe_float(line, 0.5)
    return _clip(
        sum(float(prob) for value, prob in distribution.items() if float(value) > line),
        0.0,
        1.0,
    )


def distribution_under_probability(distribution: Dict[object, float], line: float) -> float:
    line = _safe_float(line, 0.5)
    return _clip(
        sum(float(prob) for value, prob in distribution.items() if float(value) < line),
        0.0,
        1.0,
    )


def game_handicap_probability(
    margin_distribution: Dict[object, float],
    side: str,
    handicap: float,
) -> float:
    handicap = _safe_float(handicap, 0.0)
    side = str(side).strip().upper()

    if side not in {"A", "B"}:
        raise ValueError("side debe ser A o B")

    total = 0.0
    for margin_a, probability in margin_distribution.items():
        margin = float(margin_a)
        adjusted = margin + handicap if side == "A" else (-margin) + handicap
        if adjusted > 0:
            total += float(probability)

    return _clip(total, 0.0, 1.0)


def _poisson_pmf_vector(mean_value: float) -> np.ndarray:
    lam = max(0.000001, _safe_float(mean_value, 0.000001))
    max_k = int(max(30, math.ceil(lam + 10.0 * math.sqrt(lam + 1.0) + 12.0)))
    probs = np.zeros(max_k + 1, dtype=float)
    probs[0] = math.exp(-lam)

    for k in range(1, max_k + 1):
        probs[k] = probs[k - 1] * lam / k

    total = probs.sum()
    if total > 0:
        probs /= total
    return probs


def more_aces_probabilities(mean_a: float, mean_b: float) -> Dict[str, float]:
    pa = _poisson_pmf_vector(mean_a)
    pb = _poisson_pmf_vector(mean_b)
    size = max(len(pa), len(pb))
    pa = np.pad(pa, (0, size - len(pa)))
    pb = np.pad(pb, (0, size - len(pb)))

    cdf_b = np.cumsum(pb)
    a_more = 0.0
    tie = 0.0

    for k in range(size):
        tie += float(pa[k] * pb[k])
        if k > 0:
            a_more += float(pa[k] * cdf_b[k - 1])

    b_more = max(0.0, 1.0 - a_more - tie)
    total = a_more + b_more + tie

    if total > 0:
        a_more /= total
        b_more /= total
        tie /= total

    return {
        "a_more": float(a_more),
        "b_more": float(b_more),
        "tie": float(tie),
    }


def predict_match_props_v1(
    df: pd.DataFrame,
    player_a: str,
    player_b: str,
    *,
    surface: Optional[str],
    best_of: int,
    match_prob_a: float,
    recent_window: int = 25,
) -> Dict[str, object]:
    """
    Capa estadística independiente del V4.2.

    Usa datos presentes en tennis_edge.db:
      aces, double faults, service points, puntos ganados al saque,
      superficie y rival.

    Añade una simulación de juegos calibrada a la probabilidad V4.2 para:
      total de juegos y hándicap de juegos.

    No modifica ni reentrena el modelo ganador V4.2.
    """
    if df is None or df.empty:
        return {"ok": False, "message": "Histórico vacío para PROPS V1."}

    best_of = int(best_of)
    if best_of not in {3, 5}:
        return {"ok": False, "message": "Formato inválido: usa BO3 o BO5."}

    required = {
        "winner_name",
        "loser_name",
        "surface",
        "w_ace",
        "l_ace",
        "w_df",
        "l_df",
        "w_svpt",
        "l_svpt",
        "w_1stWon",
        "l_1stWon",
        "w_2ndWon",
        "l_2ndWon",
    }

    missing_cols = sorted(required - set(df.columns))
    if missing_cols:
        return {
            "ok": False,
            "message": "Faltan columnas para PROPS V1: " + ", ".join(missing_cols),
        }

    surface = _normalize_surface(surface)
    league = _league_rates(df, surface)

    hist_a = _player_rows(df, player_a)
    hist_b = _player_rows(df, player_b)

    prof_a = _profile(hist_a, surface, recent_window, league)
    prof_b = _profile(hist_b, surface, recent_window, league)

    score_probs = exact_score_probabilities(match_prob_a, best_of)
    expected_sets = expected_sets_from_scores(score_probs)
    set_prob_a = set_probability_from_match_probability(match_prob_a, best_of)

    proj_a = _player_projection(prof_a, prof_b, expected_sets, league)
    proj_b = _player_projection(prof_b, prof_a, expected_sets, league)

    game_markets = _simulate_game_markets(
        player_a=player_a,
        player_b=player_b,
        surface=surface,
        best_of=best_of,
        match_prob_a=float(match_prob_a),
        set_prob_a=set_prob_a,
        prof_a=prof_a,
        prof_b=prof_b,
        league=league,
    )

    aces_more = more_aces_probabilities(
        proj_a["expected_aces"],
        proj_b["expected_aces"],
    )

    return {
        "ok": True,
        "model_version": MODEL_VERSION,
        "best_of": best_of,
        "surface": surface or "Todas",
        "match_prob_a": float(match_prob_a),
        "set_prob_a": set_prob_a,
        "expected_sets": expected_sets,
        "score_probabilities": score_probs,
        "player_a": proj_a,
        "player_b": proj_b,
        "aces_more": aces_more,
        **game_markets,
        "notes": (
            "PROPS V1.1 es una capa estadística separada del Ensemble V4.2. "
            "Aces y dobles faltas usan tasas por punto de servicio; total y hándicap "
            "de juegos se obtienen con simulación de juegos calibrada a la probabilidad V4.2; "
            "el total de sets procede de la distribución de marcador exacto."
        ),
    }
