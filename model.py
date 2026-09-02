from pathlib import Path
from datetime import datetime
from collections import defaultdict, deque

import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, log_loss, brier_score_loss

from database import set_model_metrics
from ratings import elo_ratings


# =========================================================
# CONFIGURACIÓN
# =========================================================

MODEL_PATH = Path("tennis_model.joblib")

FEATURES = [
    "rank_diff",
    "form_diff",
    "surface_form_diff",
    "elo_diff"
]

BASE_ELO = 1500.0
ELO_K = 28.0

RECENT_MATCHES = 25


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def safe_surface(value):

    if pd.isna(value):
        return ""

    return str(value).strip()


def safe_rank(value):

    try:

        value = float(value)

        if np.isnan(value):
            return 999.0

        return value

    except Exception:

        return 999.0


def get_form(history):

    if not history:
        return None

    return sum(history) / len(history)


# =========================================================
# ENTRENAMIENTO OPTIMIZADO
# =========================================================

def train_model(df):

    if len(df) < 100:

        return {
            "ok": False,
            "message": "No hay suficientes partidos."
        }


    print()
    print("====================================")
    print("PREPARANDO ENTRENAMIENTO OPTIMIZADO")
    print("====================================")


    # -----------------------------------------------------
    # LIMPIAR Y ORDENAR DATOS
    # -----------------------------------------------------

    x = df.dropna(
        subset=[
            "tourney_date",
            "winner_name",
            "loser_name"
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


    x = x.sort_values(
        "tourney_date"
    ).reset_index(
        drop=True
    )


    total_matches = len(x)


    print(
        f"🎾 Partidos disponibles: {total_matches}"
    )

    print(
        "⚡ Procesando historial en memoria..."
    )


    # =====================================================
    # HISTORIALES EN MEMORIA
    # =====================================================

    # Últimos resultados generales
    player_history = defaultdict(
        lambda: deque(
            maxlen=RECENT_MATCHES
        )
    )


    # Últimos resultados por superficie
    surface_history = defaultdict(
        lambda: defaultdict(
            lambda: deque(
                maxlen=RECENT_MATCHES
            )
        )
    )


    # Rankings recientes
    player_ranks = defaultdict(
        lambda: deque(
            maxlen=RECENT_MATCHES
        )
    )


    # Elo que se actualiza cronológicamente
    elos = defaultdict(
        lambda: BASE_ELO
    )


    # Datos que usaremos para entrenar
    rows = []
    labels = []


    # =====================================================
    # RECORRER PARTIDOS UNA SOLA VEZ
    # =====================================================

    for index, row in x.iterrows():


        # Mostrar progreso cada 1.000 partidos

        if index % 1000 == 0:

            progress = (
                index / total_matches
            ) * 100

            print(
                f"⚡ Procesando: "
                f"{index}/{total_matches} "
                f"({progress:.1f}%)"
            )


        winner = row["winner_name"]
        loser = row["loser_name"]

        surface = safe_surface(
            row.get("surface", "")
        )


        # -------------------------------------------------
        # HISTORIAL GENERAL ANTES DEL PARTIDO
        # -------------------------------------------------

        winner_history = player_history[
            winner
        ]

        loser_history = player_history[
            loser
        ]


        winner_form = get_form(
            winner_history
        )

        loser_form = get_form(
            loser_history
        )


        # -------------------------------------------------
        # HISTORIAL POR SUPERFICIE
        # -------------------------------------------------

        winner_surface_history = (
            surface_history[winner][surface]
        )

        loser_surface_history = (
            surface_history[loser][surface]
        )


        winner_surface_form = get_form(
            winner_surface_history
        )

        loser_surface_form = get_form(
            loser_surface_history
        )


        # -------------------------------------------------
        # RANKING
        # -------------------------------------------------

        winner_rank = safe_rank(
            row.get(
                "winner_rank",
                np.nan
            )
        )

        loser_rank = safe_rank(
            row.get(
                "loser_rank",
                np.nan
            )
        )


        # -------------------------------------------------
        # ELO ANTES DEL PARTIDO
        # -------------------------------------------------

        winner_elo = elos[winner]

        loser_elo = elos[loser]


        # =================================================
        # CREAR EJEMPLOS DE ENTRENAMIENTO
        # =================================================

        # Necesitamos historial de ambos jugadores

        if (
            winner_form is not None
            and loser_form is not None
        ):


            # ---------------------------------------------
            # FORMA POR SUPERFICIE
            # ---------------------------------------------

            # Si no hay suficiente historial en superficie,
            # usamos la forma general como respaldo.

            if (
                winner_surface_form is None
                or len(winner_surface_history) < 3
            ):

                winner_surface_form = winner_form


            if (
                loser_surface_form is None
                or len(loser_surface_history) < 3
            ):

                loser_surface_form = loser_form


            # ---------------------------------------------
            # FEATURES
            # ---------------------------------------------

            rank_diff = (
                loser_rank
                -
                winner_rank
            )


            form_diff = (
                winner_form
                -
                loser_form
            )


            surface_form_diff = (
                winner_surface_form
                -
                loser_surface_form
            )


            elo_diff = (
                winner_elo
                -
                loser_elo
            )


            features = [

                rank_diff,

                form_diff,

                surface_form_diff,

                elo_diff

            ]


            # ---------------------------------------------
            # ORIENTACIÓN NORMAL
            # Winner = Jugador A
            # Label = 1
            # ---------------------------------------------

            rows.append(
                features
            )

            labels.append(
                1
            )


            # ---------------------------------------------
            # ORIENTACIÓN INVERSA
            # Loser = Jugador A
            # Label = 0
            # ---------------------------------------------

            rows.append(
                [

                    -rank_diff,

                    -form_diff,

                    -surface_form_diff,

                    -elo_diff

                ]
            )

            labels.append(
                0
            )


        # =================================================
        # ACTUALIZAR ELO DESPUÉS DEL PARTIDO
        # =================================================

        expected_winner = (

            1

            /

            (

                1

                +

                10 ** (
                    (
                        loser_elo
                        -
                        winner_elo
                    )
                    /
                    400
                )

            )

        )


        elos[winner] = (

            winner_elo

            +

            ELO_K

            *

            (
                1
                -
                expected_winner
            )

        )


        elos[loser] = (

            loser_elo

            +

            ELO_K

            *

            (
                0
                -
                (
                    1
                    -
                    expected_winner
                )
            )

        )


        # =================================================
        # ACTUALIZAR HISTORIALES
        # =================================================

        # Winner = victoria

        player_history[winner].append(
            1
        )

        player_history[loser].append(
            0
        )


        # Superficie

        surface_history[winner][surface].append(
            1
        )

        surface_history[loser][surface].append(
            0
        )


        # Rankings

        player_ranks[winner].append(
            winner_rank
        )

        player_ranks[loser].append(
            loser_rank
        )


    # =====================================================
    # COMPROBAR DATOS GENERADOS
    # =====================================================

    if len(rows) < 200:

        return {
            "ok": False,
            "message": (
                "No hay suficiente historial útil "
                "para entrenar."
            )
        }


    print()
    print(
        f"🧠 Ejemplos generados: {len(rows)}"
    )


    # =====================================================
    # CREAR DATASET
    # =====================================================

    data = pd.DataFrame(
        rows,
        columns=FEATURES
    )


    y = np.array(
        labels
    )


    # =====================================================
    # VALIDACIÓN TEMPORAL
    # =====================================================

    cut = int(
        len(data) * 0.8
    )


    Xtr = data.iloc[
        :cut
    ]

    Xte = data.iloc[
        cut:
    ]


    ytr = y[
        :cut
    ]

    yte = y[
        cut:
    ]


    # =====================================================
    # ENTRENAR MODELO
    # =====================================================

    print()
    print(
        "🧠 ENTRENANDO MODELO..."
    )


    clf = HistGradientBoostingClassifier(

        max_iter=180,

        learning_rate=0.05,

        max_leaf_nodes=12,

        random_state=42

    )


    clf.fit(
        Xtr,
        ytr
    )


    # =====================================================
    # VALIDACIÓN
    # =====================================================

    probabilities = clf.predict_proba(
        Xte
    )[:, 1]


    accuracy = accuracy_score(
        yte,
        probabilities >= 0.5
    )


    ll = log_loss(
        yte,
        probabilities
    )


    brier = brier_score_loss(
        yte,
        probabilities
    )


    # =====================================================
    # GUARDAR MODELO
    # =====================================================

    joblib.dump(
        clf,
        MODEL_PATH
    )


    # =====================================================
    # GUARDAR MÉTRICAS
    # =====================================================

    set_model_metrics({

        "accuracy": float(
            accuracy
        ),

        "log_loss": float(
            ll
        ),

        "brier": float(
            brier
        ),

        "trained_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "samples": len(
            data
        )

    })


    print()
    print(
        "===================================="
    )

    print(
        "ENTRENAMIENTO COMPLETADO"
    )

    print(
        "===================================="
    )

    print(
        f"📊 Accuracy: "
        f"{accuracy:.2%}"
    )

    print(
        f"📦 Ejemplos: "
        f"{len(data)}"
    )


    return {

        "ok": True,

        "accuracy": float(
            accuracy
        )

    }


# =========================================================
# ESTADÍSTICAS PARA PREDICCIÓN
# =========================================================

def _stats(
    df,
    player,
    surface,
    n
):


    x = df.copy()


    total = x[

        (
            x["winner_name"]
            ==
            player
        )

        |

        (
            x["loser_name"]
            ==
            player
        )

    ].sort_values(

        "tourney_date",

        ascending=False

    ).head(
        n
    )


    if total.empty:

        return None


    # =====================================================
    # BUSCAR PARTIDOS EN LA SUPERFICIE
    # =====================================================

    if surface:

        surface_matches = x[

            x["surface"]
            .fillna("")
            ==
            surface

        ]


        surface_matches = surface_matches[

            (
                surface_matches[
                    "winner_name"
                ]
                ==
                player
            )

            |

            (
                surface_matches[
                    "loser_name"
                ]
                ==
                player
            )

        ].sort_values(

            "tourney_date",

            ascending=False

        ).head(
            n
        )


        # Si hay suficientes partidos en superficie,
        # usamos esos.

        if len(surface_matches) >= 5:

            use = surface_matches

        else:

            use = total


    else:

        use = total


    # =====================================================
    # FORMA
    # =====================================================

    wins = int(

        (
            use[
                "winner_name"
            ]
            ==
            player
        ).sum()

    )


    form = wins / len(
        use
    )


    # =====================================================
    # RANKING
    # =====================================================

    ranks = pd.concat(

        [

            use.loc[

                use[
                    "winner_name"
                ]
                ==
                player,

                "winner_rank"

            ],

            use.loc[

                use[
                    "loser_name"
                ]
                ==
                player,

                "loser_rank"

            ]

        ]

    )


    ranks = pd.to_numeric(

        ranks,

        errors="coerce"

    ).dropna()


    # =====================================================
    # ESTADÍSTICAS DE PARTIDO
    # =====================================================

    def mean_stat(col):


        winner_values = use.loc[

            use[
                "winner_name"
            ]
            ==
            player,

            "w_" + col

        ]


        loser_values = use.loc[

            use[
                "loser_name"
            ]
            ==
            player,

            "l_" + col

        ]


        values = pd.concat(

            [

                winner_values,

                loser_values

            ]

        )


        values = pd.to_numeric(

            values,

            errors="coerce"

        )


        return values.mean()


    return {

        "matches": len(
            use
        ),

        "wins": wins,

        "form": form,

        "rank": (
            ranks.mean()
            if len(ranks)
            else 999.0
        ),

        "aces": mean_stat(
            "ace"
        ),

        "df": mean_stat(
            "df"
        ),

        "first": mean_stat(
            "1stWon"
        ),

        "second": mean_stat(
            "2ndWon"
        ),

        "break": mean_stat(
            "bpWon"
        )

    }


# =========================================================
# HEAD TO HEAD
# =========================================================

def _h2h(
    df,
    a,
    b,
    surface=None
):


    x = df[

        (

            (
                df[
                    "winner_name"
                ]
                ==
                a
            )

            &

            (
                df[
                    "loser_name"
                ]
                ==
                b
            )

        )

        |

        (

            (
                df[
                    "winner_name"
                ]
                ==
                b
            )

            &

            (
                df[
                    "loser_name"
                ]
                ==
                a
            )

        )

    ]


    if surface:

        surface_matches = x[

            x[
                "surface"
            ]
            .fillna("")
            ==
            surface

        ]


        if not surface_matches.empty:

            x = surface_matches


    a_wins = int(

        (
            x[
                "winner_name"
            ]
            ==
            a
        ).sum()

    ) if not x.empty else 0


    b_wins = int(

        (
            x[
                "winner_name"
            ]
            ==
            b
        ).sum()

    ) if not x.empty else 0


    return (
        a_wins,
        b_wins
    )


# =========================================================
# PREDICCIÓN DEL PARTIDO
# =========================================================

def predict_match(
    df,
    a,
    b,
    surface=None,
    recent_window=25,
    use_elo=True
):


    sa = _stats(
        df,
        a,
        surface,
        recent_window
    )


    sb = _stats(
        df,
        b,
        surface,
        recent_window
    )


    if not sa or not sb:

        return {

            "ok": False,

            "message": (
                "No hay historial suficiente "
                "para ambos jugadores."
            )

        }


    # =====================================================
    # ELO
    # =====================================================

    ratings = elo_ratings(

        df,

        surface
        if use_elo
        else None

    )


    elo_a = ratings.get(
        a,
        BASE_ELO
    )


    elo_b = ratings.get(
        b,
        BASE_ELO
    )


    # =====================================================
    # FEATURES
    # =====================================================

    rank_diff = (

        sb["rank"]
        -
        sa["rank"]

    )


    form_diff = (

        sa["form"]
        -
        sb["form"]

    )


    # En predicción, _stats ya usa la superficie cuando
    # hay suficientes partidos. Por tanto calculamos una
    # diferencia equivalente de forma.

    surface_form_diff = (

        sa["form"]
        -
        sb["form"]

    )


    elo_diff = (

        elo_a
        -
        elo_b

    )


    features = pd.DataFrame(

        [

            [

                rank_diff,

                form_diff,

                surface_form_diff,

                elo_diff

            ]

        ],

        columns=FEATURES

    )


    # =====================================================
    # MODELO
    # =====================================================

    if MODEL_PATH.exists():

        clf = joblib.load(
            MODEL_PATH
        )


        prob_a = float(

            clf.predict_proba(
                features
            )[0, 1]

        )


    else:


        z = (

            0.012
            *
            rank_diff

            +

            2.2
            *
            form_diff

            +

            0.8
            *
            surface_form_diff

            +

            0.002
            *
            elo_diff

        )


        prob_a = float(

            1
            /
            (
                1
                +
                np.exp(
                    -z
                )
            )

        )


    # =====================================================
    # HEAD TO HEAD
    # =====================================================

    a_wins, b_wins = _h2h(

        df,
        a,
        b,
        surface

    )


    if a_wins + b_wins >= 2:


        h2h_probability = (

            a_wins
            /
            (
                a_wins
                +
                b_wins
            )

        )


        prob_a = (

            0.92
            *
            prob_a

            +

            0.08
            *
            h2h_probability

        )


    # Seguridad

    prob_a = min(

        max(
            prob_a,
            0.01
        ),

        0.99

    )


    prob_b = (

        1
        -
        prob_a

    )


    difference = abs(

        prob_a
        -
        prob_b

    )


    if difference > 0.25:

        confidence = "Alta"

    elif difference > 0.10:

        confidence = "Media"

    else:

        confidence = "Baja"


    # =====================================================
    # TABLA DE COMPARACIÓN
    # =====================================================

    comparison = [

        {

            "Factor": "Forma reciente",

            "Jugador A":
                f"{sa['form']:.1%}",

            "Jugador B":
                f"{sb['form']:.1%}"

        },

        {

            "Factor":
                "Partidos analizados",

            "Jugador A":
                sa["matches"],

            "Jugador B":
                sb["matches"]

        },

        {

            "Factor":
                "Ranking medio reciente",

            "Jugador A":
                f"{sa['rank']:.0f}",

            "Jugador B":
                f"{sb['rank']:.0f}"

        },

        {

            "Factor":
                "Aces / partido",

            "Jugador A":
                f"{sa['aces']:.2f}",

            "Jugador B":
                f"{sb['aces']:.2f}"

        },

        {

            "Factor":
                "Dobles faltas / partido",

            "Jugador A":
                f"{sa['df']:.2f}",

            "Jugador B":
                f"{sb['df']:.2f}"

        },

        {

            "Factor":
                "Puntos ganados 1er saque",

            "Jugador A":
                f"{sa['first']:.2f}",

            "Jugador B":
                f"{sb['first']:.2f}"

        },

        {

            "Factor":
                "Puntos ganados 2º saque",

            "Jugador A":
                f"{sa['second']:.2f}",

            "Jugador B":
                f"{sb['second']:.2f}"

        }

    ]


    # =====================================================
    # EXPLICACIÓN
    # =====================================================

    explanation = (

        f"El modelo da ventaja a "

        f"{'Jugador A' if prob_a >= 0.5 else 'Jugador B'} "

        f"por la combinación de ranking, "

        f"forma reciente, rendimiento disponible "

        f"y Elo. "

        f"La diferencia de probabilidades es de "

        f"{difference * 100:.1f} "

        f"puntos porcentuales."

    )


    return {

        "ok": True,

        "prob_a": prob_a,

        "prob_b": prob_b,

        "confidence_label": confidence,

        "comparison": comparison,

        "h2h": {

            "a_wins": a_wins,

            "b_wins": b_wins,

            "total": (
                a_wins
                +
                b_wins
            )

        },

        "elo_a": elo_a,

        "elo_b": elo_b,

        "explanation": explanation

    }