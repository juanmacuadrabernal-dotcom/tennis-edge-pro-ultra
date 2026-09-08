
# ============================================================
# TENNIS EDGE PRO · ANALYZER ONLY V1
# ------------------------------------------------------------
# Objetivo:
# - Una sola función: análisis individual.
# - Sin Radar, Jornada, Live, Top Picks, tracker ni APIs de cuotas.
# - Mantiene el motor Ensemble V4.2 exactamente como estaba.
# ============================================================

import streamlit as st
import pandas as pd

from database import (
    init_db,
    get_matches,
    get_last_update,
)
from model_v42 import (
    predict_match_v42,
    get_v42_status,
)
from player_news import analyse_physical_status


st.set_page_config(
    page_title="Tennis Edge Pro · Analyzer",
    page_icon="🎾",
    layout="wide",
)


# ============================================================
# ESTILO
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --tep-bg: #071522;
        --tep-card: #0b2031;
        --tep-card-2: #0d2638;
        --tep-border: rgba(115, 175, 215, .16);
        --tep-text: #f5f9fc;
        --tep-muted: #91a7b8;
        --tep-green: #35e07b;
        --tep-cyan: #25c8e8;
        --tep-blue: #4c9cff;
        --tep-orange: #ffb54a;
        --tep-red: #ff6470;
    }

    .stApp {
        background:
            radial-gradient(circle at 82% 0%, rgba(44,104,171,.13), transparent 28%),
            linear-gradient(180deg, #071522 0%, #06131f 100%);
    }

    .block-container {
        max-width: 1280px;
        padding-top: 1.4rem;
        padding-bottom: 3rem;
    }

    .tep-hero {
        border: 1px solid var(--tep-border);
        border-radius: 18px;
        padding: 1.2rem 1.35rem;
        margin-bottom: 1rem;
        background:
            radial-gradient(circle at 90% 10%, rgba(53,224,123,.10), transparent 32%),
            linear-gradient(145deg, rgba(11,38,49,.96), rgba(7,24,38,.96));
    }

    .tep-eyebrow {
        color: var(--tep-green);
        font-size: .72rem;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
    }

    .tep-title {
        color: var(--tep-text);
        font-size: 2.25rem;
        line-height: 1.05;
        font-weight: 900;
        margin-top: .25rem;
    }

    .tep-sub {
        color: var(--tep-muted);
        font-size: .98rem;
        margin-top: .4rem;
    }

    .tep-panel {
        border: 1px solid var(--tep-border);
        border-radius: 16px;
        padding: 1rem;
        background: linear-gradient(145deg, rgba(13,38,56,.96), rgba(8,25,39,.96));
    }

    .tep-label {
        color: var(--tep-muted);
        font-size: .75rem;
        text-transform: uppercase;
        letter-spacing: .08em;
        font-weight: 800;
    }

    .tep-big-prob {
        font-size: 2.55rem;
        line-height: 1;
        font-weight: 900;
        margin: .2rem 0;
    }

    .tep-green { color: var(--tep-green); }
    .tep-blue { color: var(--tep-blue); }

    .tep-value-positive {
        border: 1px solid rgba(53,224,123,.38);
        background: rgba(53,224,123,.08);
        border-radius: 14px;
        padding: .85rem 1rem;
    }

    .tep-value-negative {
        border: 1px solid rgba(255,100,112,.28);
        background: rgba(255,100,112,.06);
        border-radius: 14px;
        padding: .85rem 1rem;
    }

    div[data-testid="stMetric"] {
        border: 1px solid var(--tep-border);
        background: rgba(10,31,47,.78);
        padding: .8rem;
        border-radius: 14px;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: .7rem;
            padding-right: .7rem;
            padding-top: .7rem;
        }
        .tep-title { font-size: 1.75rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATOS / CACHÉ
# ============================================================

init_db()


@st.cache_data(ttl=600)
def load_data():
    return get_matches()


@st.cache_data(ttl=1800, show_spinner=False)
def load_physical_status(player):
    return analyse_physical_status(player)


@st.cache_data(ttl=1800, show_spinner=False)
def predict_match_cached(
    player_a,
    player_b,
    surface,
    recent_window,
    use_elo,
    data_version,
):
    df_local = load_data()

    return predict_match_v42(
        df_local,
        player_a,
        player_b,
        surface=surface,
        recent_window=recent_window,
        use_elo=use_elo,
        data_version=data_version,
    )


df = load_data()

if df.empty:
    st.error("La base histórica está vacía.")
    st.stop()


data_version = (
    f"{get_last_update() or 'sin_actualizar'}:"
    f"{len(df)}"
)

model_status = get_v42_status()


# ============================================================
# CABECERA
# ============================================================

st.markdown(
    """
    <div class="tep-hero">
      <div class="tep-eyebrow">Tennis Edge Pro · Analyzer</div>
      <div class="tep-title">Analiza un partido. Nada más.</div>
      <div class="tep-sub">
        Ensemble V4.2 + histórico ATP/Challenger + superficie + forma +
        Elo + saque/devolución + H2H + valor esperado.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

a, b, c = st.columns(3)

with a:
    st.metric(
        "Base histórica",
        f"{len(df):,}".replace(",", "."),
    )

with b:
    st.metric(
        "Modelo",
        (
            "✅ V4.2 activo"
            if model_status.get("ok")
            else "⚠️ Backup"
        ),
    )

with c:
    st.metric(
        "Última actualización",
        str(get_last_update() or "Sin actualizar"),
    )


# ============================================================
# CONFIGURACIÓN DEL PARTIDO
# ============================================================

players = sorted(
    set(df["winner_name"].dropna().astype(str))
    | set(df["loser_name"].dropna().astype(str))
)

st.markdown("## 🎾 Partido")

p1, p2, s1 = st.columns([1.2, 1.2, .8])

with p1:
    player_a = st.selectbox(
        "Jugador A",
        players,
        key="analyzer_player_a",
    )

with p2:
    player_b = st.selectbox(
        "Jugador B",
        players,
        index=min(1, len(players) - 1),
        key="analyzer_player_b",
    )

with s1:
    surface = st.selectbox(
        "Superficie",
        ["Hard", "Clay", "Grass", "Todas"],
        key="analyzer_surface",
    )


st.markdown("## 💰 Cuotas")

q1, q2, q3 = st.columns([1, 1, 1])

with q1:
    cuota_a = st.number_input(
        f"Cuota · {player_a}",
        min_value=1.01,
        value=1.50,
        step=0.01,
        format="%.2f",
        key="analyzer_odds_a",
    )

with q2:
    cuota_b = st.number_input(
        f"Cuota · {player_b}",
        min_value=1.01,
        value=2.50,
        step=0.01,
        format="%.2f",
        key="analyzer_odds_b",
    )

with q3:
    incluir_fisico = st.checkbox(
        "Consultar noticias / físico",
        value=True,
        help=(
            "El modelo base no cambia. Esta consulta añade contexto "
            "externo sobre lesiones o alertas recientes."
        ),
    )


analizar = st.button(
    "🚀 ANALIZAR PARTIDO",
    type="primary",
    use_container_width=True,
)


# ============================================================
# RESULTADO
# ============================================================

if analizar:
    if player_a == player_b:
        st.error("Selecciona dos jugadores diferentes.")
        st.stop()

    superficie_modelo = (
        None
        if surface == "Todas"
        else surface
    )

    with st.spinner("Calculando Ensemble V4.2..."):
        result = predict_match_cached(
            player_a,
            player_b,
            superficie_modelo,
            25,
            True,
            data_version,
        )

    if not result.get("ok"):
        st.error(
            result.get(
                "message",
                "El modelo no pudo analizar el partido.",
            )
        )
        st.stop()

    physical_a = None
    physical_b = None

    if incluir_fisico:
        with st.spinner(
            "Buscando contexto físico y noticias recientes..."
        ):
            physical_a = load_physical_status(
                player_a
            )
            physical_b = load_physical_status(
                player_b
            )

    pa = float(result["prob_a"])
    pb = float(result["prob_b"])

    favorito = (
        player_a
        if pa >= pb
        else player_b
    )

    confianza = result.get(
        "confidence_label",
        "Sin dato",
    )

    cuota_justa_a = (
        1.0 / pa
        if pa > 0
        else None
    )

    cuota_justa_b = (
        1.0 / pb
        if pb > 0
        else None
    )

    implied_a = 1.0 / cuota_a
    implied_b = 1.0 / cuota_b

    edge_a = pa - implied_a
    edge_b = pb - implied_b

    ev_a = (
        pa * cuota_a
    ) - 1.0

    ev_b = (
        pb * cuota_b
    ) - 1.0

    # --------------------------------------------------------
    # PROBABILIDAD
    # --------------------------------------------------------

    st.divider()
    st.markdown("## 🔮 Probabilidad de victoria")

    r1, r2, rf = st.columns([1, 1, .8])

    with r1:
        st.markdown(
            f"""
            <div class="tep-panel">
              <div class="tep-label">Jugador A</div>
              <div style="font-size:1.15rem;font-weight:850;color:#fff;">
                {player_a}
              </div>
              <div class="tep-big-prob tep-green">{pa:.1%}</div>
              <div style="color:#91a7b8;">
                Cuota justa: {cuota_justa_a:.2f}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(int(pa * 100))

    with r2:
        st.markdown(
            f"""
            <div class="tep-panel">
              <div class="tep-label">Jugador B</div>
              <div style="font-size:1.15rem;font-weight:850;color:#fff;">
                {player_b}
              </div>
              <div class="tep-big-prob tep-blue">{pb:.1%}</div>
              <div style="color:#91a7b8;">
                Cuota justa: {cuota_justa_b:.2f}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(int(pb * 100))

    with rf:
        st.metric(
            "Favorito",
            favorito,
        )
        st.metric(
            "Confianza",
            confianza,
        )
        st.caption(
            result.get(
                "model_version",
                "Modelo activo",
            )
        )

    # --------------------------------------------------------
    # VALUE
    # --------------------------------------------------------

    st.markdown("## 💎 Valor de mercado")

    v1, v2 = st.columns(2)

    with v1:
        st.subheader(player_a)

        st.metric(
            "Cuota actual",
            f"{cuota_a:.2f}",
        )
        st.metric(
            "Cuota justa",
            f"{cuota_justa_a:.2f}",
        )
        st.metric(
            "Prob. modelo",
            f"{pa:.1%}",
        )
        st.metric(
            "Prob. implícita",
            f"{implied_a:.1%}",
        )
        st.metric(
            "Edge",
            f"{edge_a:+.1%}",
        )
        st.metric(
            "EV",
            f"{ev_a:+.1%}",
        )

        if ev_a >= 0.10:
            st.success("🔥 VALUE FUERTE según el modelo")
        elif ev_a >= 0.05:
            st.success("🟢 VALUE POSITIVO según el modelo")
        elif ev_a > 0:
            st.warning("🟡 VALUE PEQUEÑO según el modelo")
        else:
            st.error("🔴 SIN VALUE según el modelo")

    with v2:
        st.subheader(player_b)

        st.metric(
            "Cuota actual",
            f"{cuota_b:.2f}",
        )
        st.metric(
            "Cuota justa",
            f"{cuota_justa_b:.2f}",
        )
        st.metric(
            "Prob. modelo",
            f"{pb:.1%}",
        )
        st.metric(
            "Prob. implícita",
            f"{implied_b:.1%}",
        )
        st.metric(
            "Edge",
            f"{edge_b:+.1%}",
        )
        st.metric(
            "EV",
            f"{ev_b:+.1%}",
        )

        if ev_b >= 0.10:
            st.success("🔥 VALUE FUERTE según el modelo")
        elif ev_b >= 0.05:
            st.success("🟢 VALUE POSITIVO según el modelo")
        elif ev_b > 0:
            st.warning("🟡 VALUE PEQUEÑO según el modelo")
        else:
            st.error("🔴 SIN VALUE según el modelo")

    # --------------------------------------------------------
    # FACTORES DEL MODELO
    # --------------------------------------------------------

    st.markdown("## 📊 Factores analizados")

    comparison = pd.DataFrame(
        result.get(
            "comparison",
            [],
        )
    )

    if not comparison.empty:
        st.dataframe(
            comparison,
            hide_index=True,
            use_container_width=True,
        )

    # --------------------------------------------------------
    # H2H / ELO
    # --------------------------------------------------------

    h = result.get(
        "h2h",
        {},
    )

    h1, h2 = st.columns(2)

    with h1:
        st.markdown("### 🥊 H2H")
        st.write(
            f"**{player_a}: {h.get('a_wins', 0)}** — "
            f"**{player_b}: {h.get('b_wins', 0)}**"
        )
        st.caption(
            f"Total enfrentamientos en datos: {h.get('total', 0)}"
        )

    with h2:
        st.markdown("### ⚡ Elo")
        e1, e2 = st.columns(2)

        e1.metric(
            player_a,
            f"{float(result.get('elo_a', 0)):.0f}",
        )

        e2.metric(
            player_b,
            f"{float(result.get('elo_b', 0)):.0f}",
        )

    # --------------------------------------------------------
    # EXPLICACIÓN
    # --------------------------------------------------------

    st.markdown("## 🧠 Lectura del modelo")

    st.write(
        result.get(
            "explanation",
            "",
        )
    )

    # --------------------------------------------------------
    # FÍSICO / NOTICIAS
    # --------------------------------------------------------

    if incluir_fisico:
        st.markdown("## 🩺 Estado físico y noticias")

        ph1, ph2 = st.columns(2)

        for col, player, physical in [
            (ph1, player_a, physical_a),
            (ph2, player_b, physical_b),
        ]:
            with col:
                st.subheader(player)

                if not physical:
                    st.info("Sin datos físicos disponibles.")
                    continue

                score = int(
                    physical.get(
                        "score",
                        0,
                    )
                    or 0
                )

                st.metric(
                    "Riesgo físico",
                    f"{score}/100",
                )

                st.progress(
                    min(
                        max(
                            score,
                            0,
                        ),
                        100,
                    )
                )

                st.write(
                    physical.get(
                        "status",
                        "Sin estado",
                    )
                )

                high_alerts = (
                    physical.get(
                        "high_alerts",
                        [],
                    )
                    or []
                )

                medium_alerts = (
                    physical.get(
                        "medium_alerts",
                        [],
                    )
                    or []
                )

                if high_alerts:
                    st.warning(
                        "⚠️ Alertas físicas importantes"
                    )

                    for article in high_alerts:
                        st.write(
                            f"🔴 {article.get('title', 'Alerta')} "
                            f"({article.get('source', 'fuente')})"
                        )

                elif medium_alerts:
                    st.warning(
                        "⚠️ Posibles alertas físicas"
                    )

                    for article in medium_alerts:
                        st.write(
                            f"🟠 {article.get('title', 'Alerta')} "
                            f"({article.get('source', 'fuente')})"
                        )

                else:
                    st.success(
                        "🟢 Sin alertas físicas recientes detectadas."
                    )


st.divider()

st.caption(
    "⚠️ Herramienta estadística. Las probabilidades son estimaciones, "
    "no garantías de resultado ni de beneficio económico."
)
