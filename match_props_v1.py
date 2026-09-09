from __future__ import annotations

import math
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd


MODEL_VERSION = "PROPS V1"


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
                    "opp_aces": win["l_ace"],
                    "opp_double_faults": win["l_df"],
                    "opp_svpt": win["l_svpt"],
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
                    "opp_aces": lose["w_ace"],
                    "opp_double_faults": lose["w_df"],
                    "opp_svpt": lose["w_svpt"],
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
        "opp_aces",
        "opp_double_faults",
        "opp_svpt",
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


def _weighted_mean(
    values: Iterable[float],
    default: float,
) -> float:
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

    ace_num = pd.to_numeric(work.get("w_ace"), errors="coerce").sum(skipna=True)
    ace_num += pd.to_numeric(work.get("l_ace"), errors="coerce").sum(skipna=True)

    df_num = pd.to_numeric(work.get("w_df"), errors="coerce").sum(skipna=True)
    df_num += pd.to_numeric(work.get("l_df"), errors="coerce").sum(skipna=True)

    svpt = pd.to_numeric(work.get("w_svpt"), errors="coerce").sum(skipna=True)
    svpt += pd.to_numeric(work.get("l_svpt"), errors="coerce").sum(skipna=True)

    if not math.isfinite(float(svpt)) or float(svpt) <= 0:
        return {
            "ace_rate": 0.085,
            "df_rate": 0.040,
            "avg_svpt": 72.0,
        }

    all_svpt = pd.concat(
        [
            pd.to_numeric(work.get("w_svpt"), errors="coerce"),
            pd.to_numeric(work.get("l_svpt"), errors="coerce"),
        ],
        ignore_index=True,
    ).dropna()

    avg_svpt = float(all_svpt.mean()) if not all_svpt.empty else 72.0

    return {
        "ace_rate": _clip(float(ace_num) / float(svpt), 0.015, 0.25),
        "df_rate": _clip(float(df_num) / float(svpt), 0.008, 0.12),
        "avg_svpt": _clip(avg_svpt, 45.0, 110.0),
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
            "matches": 0,
            "surface_matches": 0,
        }

    recent = history.tail(max(8, int(recent_window))).copy()

    surface_hist = history
    if surface is not None:
        surface_hist = history[history["surface"].astype(str) == str(surface)].copy()

    surface_recent = surface_hist.tail(max(6, min(int(recent_window), 20)))

    overall_ace = _weighted_ratio(
        recent,
        "aces",
        "svpt",
        league["ace_rate"],
        500.0,
    )
    surface_ace = _weighted_ratio(
        surface_recent,
        "aces",
        "svpt",
        league["ace_rate"],
        350.0,
    )

    overall_df = _weighted_ratio(
        recent,
        "double_faults",
        "svpt",
        league["df_rate"],
        500.0,
    )
    surface_df = _weighted_ratio(
        surface_recent,
        "double_faults",
        "svpt",
        league["df_rate"],
        350.0,
    )

    ace_allowed = _weighted_ratio(
        recent,
        "opp_aces",
        "opp_svpt",
        league["ace_rate"],
        550.0,
    )
    surface_ace_allowed = _weighted_ratio(
        surface_recent,
        "opp_aces",
        "opp_svpt",
        league["ace_rate"],
        400.0,
    )

    df_allowed = _weighted_ratio(
        recent,
        "opp_double_faults",
        "opp_svpt",
        league["df_rate"],
        650.0,
    )
    surface_df_allowed = _weighted_ratio(
        surface_recent,
        "opp_double_faults",
        "opp_svpt",
        league["df_rate"],
        450.0,
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


def expected_sets_from_scores(score_probs: Dict[str, float]) -> float:
    total = 0.0
    for label, prob in score_probs.items():
        if "2-0" in label:
            sets = 2
        elif "2-1" in label:
            sets = 3
        elif "3-0" in label:
            sets = 3
        elif "3-1" in label:
            sets = 4
        elif "3-2" in label:
            sets = 5
        else:
            continue
        total += float(prob) * sets
    return float(total)


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

    # CDF hasta threshold-1, calculada recursivamente para no depender de scipy.
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

    # Interacción sacador-returner. El propio jugador manda, el rival ajusta.
    own_ace = max(0.005, own["ace_rate"])
    rival_allow = max(0.005, rival["ace_allowed_rate"])
    league_ace = max(0.005, league["ace_rate"])

    ace_matchup_factor = _clip(
        math.sqrt(rival_allow / league_ace),
        0.72,
        1.35,
    )
    ace_rate = _clip(own_ace * ace_matchup_factor, 0.008, 0.30)

    # Doble falta depende mucho más del servidor que del restador.
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
        "suggested_ace_over_probability": poisson_over_probability(
            expected_aces,
            ace_line,
        ),
        "suggested_df_over_probability": poisson_over_probability(
            expected_df,
            df_line,
        ),
        "sample_matches": int(own["matches"]),
        "surface_sample_matches": int(own["surface_matches"]),
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

    Usa datos ya presentes en tennis_edge.db:
      aces, double faults, service points, surface y rival.

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

    proj_a = _player_projection(prof_a, prof_b, expected_sets, league)
    proj_b = _player_projection(prof_b, prof_a, expected_sets, league)

    return {
        "ok": True,
        "model_version": MODEL_VERSION,
        "best_of": best_of,
        "surface": surface or "Todas",
        "match_prob_a": float(match_prob_a),
        "set_prob_a": set_probability_from_match_probability(
            match_prob_a,
            best_of,
        ),
        "expected_sets": expected_sets,
        "score_probabilities": score_probs,
        "player_a": proj_a,
        "player_b": proj_b,
        "notes": (
            "PROPS V1 es una capa estadística separada del Ensemble V4.2. "
            "Aces y dobles faltas se proyectan a partir de tasas por punto de "
            "servicio, superficie, forma reciente, rival y duración esperada."
        ),
    }
