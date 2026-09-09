# ============================================================
# TENNIS EDGE PRO · WEB ANALYZER PREMIUM
# ------------------------------------------------------------
# Web de una sola función:
# - Analizador individual V4.2
# - ATP + Challenger histórico
# - Probabilidad, cuota justa, Edge y EV
# - Factores del modelo, H2H, Elo
# - Noticias / riesgo físico opcional
#
# NO incluye Radar, Jornada, Top Picks, Live ni APIs de cuotas.
# ============================================================

import html
import textwrap

import pandas as pd
import streamlit as st

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



def render_html(value, unsafe_allow_html=True, **kwargs):
    """
    Renderiza HTML sin que Streamlit interprete ninguna línea
    indentada como bloque de código Markdown.

    Importante:
    dedent() por sí solo no basta cuando hay HTML anidado.
    Por eso eliminamos la sangría de CADA línea.
    """
    raw = textwrap.dedent(str(value)).strip()

    cleaned = "\n".join(
        line.strip()
        for line in raw.splitlines()
        if line.strip()
    )

    st.markdown(
        cleaned,
        unsafe_allow_html=unsafe_allow_html,
        **kwargs,
    )


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Tennis Edge Pro · Analyzer",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# DESIGN SYSTEM
# ============================================================

render_html(
    r"""
    <style>
    /* ---------- STREAMLIT RESET ---------- */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] {
        background: transparent;
        height: 0;
    }

    html, body, [class*="css"] {
        font-family:
            Inter, ui-sans-serif, system-ui, -apple-system,
            BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    :root {
        --paper: #f7f4ec;
        --paper-2: #fffdf8;
        --ink: #17201b;
        --muted: #69716c;
        --green: #0d5a3d;
        --green-2: #167351;
        --green-soft: #e9f2ec;
        --green-pale: #f2f7f3;
        --gold: #b99249;
        --gold-soft: #efe4c9;
        --red: #bc3b3b;
        --red-soft: #f8e8e5;
        --line: #dedbd1;
        --shadow: 0 12px 36px rgba(28, 45, 37, .08);
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(13,90,61,.05), transparent 24rem),
            radial-gradient(circle at 95% 18%, rgba(185,146,73,.07), transparent 25rem),
            var(--paper);
        color: var(--ink);
    }

    .block-container {
        max-width: 1500px;
        padding-top: 0 !important;
        padding-bottom: 2.5rem;
        padding-left: 2.2rem;
        padding-right: 2.2rem;
    }

    /* ---------- TOP BAR ---------- */
    .tep-topbar {
        margin: 0 -2.2rem 1.2rem;
        padding: 1.1rem 2.2rem;
        background: rgba(255,253,248,.96);
        border-bottom: 1px solid var(--line);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        position: sticky;
        top: 0;
        z-index: 50;
        backdrop-filter: blur(12px);
    }

    .tep-brand {
        display: flex;
        align-items: center;
        gap: .8rem;
        min-width: 240px;
    }

    .tep-mark {
        font-size: 1.7rem;
        line-height: 1;
        filter: sepia(.45);
    }

    .tep-brand-name {
        font-family: Georgia, "Times New Roman", serif;
        font-size: 1.65rem;
        font-weight: 700;
        letter-spacing: -.03em;
        color: #13231b;
    }

    .tep-nav {
        display: flex;
        gap: .5rem;
        align-items: center;
        justify-content: center;
        flex: 1;
    }

    .tep-nav-pill {
        padding: .55rem .85rem;
        border-radius: 999px;
        color: #5f6862;
        font-size: .88rem;
        font-weight: 700;
    }

    .tep-nav-pill.active {
        color: var(--green);
        background: var(--green-soft);
    }

    .tep-status {
        display: flex;
        align-items: center;
        gap: .55rem;
        padding: .5rem .75rem;
        border-radius: 12px;
        border: 1px solid #d8ded9;
        background: #fbfcfa;
        color: #48544c;
        font-size: .78rem;
        white-space: nowrap;
    }

    .tep-dot {
        width: .56rem;
        height: .56rem;
        border-radius: 50%;
        background: #1aa66a;
        box-shadow: 0 0 0 4px rgba(26,166,106,.10);
        display: inline-block;
    }

    /* ---------- HERO ---------- */
    .tep-hero {
        border: 1px solid var(--line);
        background:
            linear-gradient(115deg, rgba(255,253,248,.98), rgba(247,244,236,.94)),
            var(--paper-2);
        border-radius: 22px;
        padding: 1.55rem 1.7rem 1.4rem;
        box-shadow: var(--shadow);
        margin-bottom: 1rem;
        position: relative;
        overflow: hidden;
    }

    .tep-hero::after {
        content: "🎾";
        position: absolute;
        right: 1.5rem;
        top: .35rem;
        font-size: 6.5rem;
        opacity: .06;
        transform: rotate(-18deg);
    }

    .tep-eyebrow {
        font-size: .70rem;
        text-transform: uppercase;
        letter-spacing: .19em;
        color: var(--gold);
        font-weight: 900;
    }

    .tep-title {
        font-family: Georgia, "Times New Roman", serif;
        font-size: clamp(2.1rem, 4.3vw, 4rem);
        line-height: .98;
        letter-spacing: -.045em;
        color: #11251c;
        margin: .35rem 0 .45rem;
        max-width: 850px;
    }

    .tep-subtitle {
        color: #68706b;
        max-width: 830px;
        font-size: .98rem;
        line-height: 1.55;
    }

    .tep-model-chip {
        display: inline-flex;
        margin-top: .9rem;
        padding: .42rem .68rem;
        border-radius: 999px;
        background: var(--green-soft);
        color: var(--green);
        border: 1px solid #cfe0d5;
        font-size: .76rem;
        font-weight: 850;
    }

    /* ---------- SECTION / CARDS ---------- */
    .tep-card {
        border: 1px solid var(--line);
        background: rgba(255,253,248,.96);
        border-radius: 18px;
        box-shadow: 0 8px 28px rgba(28,45,37,.045);
        padding: 1.05rem 1.1rem;
        min-height: 100%;
    }

    .tep-card-title {
        font-family: Georgia, "Times New Roman", serif;
        color: #183026;
        font-size: 1.16rem;
        font-weight: 700;
        margin-bottom: .18rem;
    }

    .tep-card-sub {
        color: var(--muted);
        font-size: .78rem;
        margin-bottom: .65rem;
    }

    .tep-divider {
        height: 1px;
        background: var(--line);
        margin: .8rem 0;
    }

    .tep-kicker {
        color: var(--gold);
        text-transform: uppercase;
        letter-spacing: .14em;
        font-size: .67rem;
        font-weight: 900;
    }

    /* ---------- PROBABILITY ---------- */
    .tep-match-card {
        border: 1px solid #d7d7cd;
        background:
            radial-gradient(circle at 50% 0%, rgba(13,90,61,.08), transparent 52%),
            #fffdf9;
        border-radius: 22px;
        padding: 1.35rem 1.35rem 1.15rem;
        box-shadow: var(--shadow);
        margin-top: .35rem;
        margin-bottom: 1rem;
    }

    .tep-match-head {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        gap: .8rem;
        align-items: center;
    }

    .tep-player {
        padding: .5rem .55rem;
    }

    .tep-player.right {
        text-align: right;
    }

    .tep-player-label {
        color: var(--muted);
        font-size: .72rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: .08em;
    }

    .tep-player-name {
        font-family: Georgia, "Times New Roman", serif;
        font-size: clamp(1.35rem, 2.3vw, 2.1rem);
        line-height: 1.03;
        color: #142219;
        font-weight: 700;
        margin-top: .18rem;
    }

    .tep-vs {
        width: 2.7rem;
        height: 2.7rem;
        border-radius: 50%;
        background: #163c2d;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 900;
        font-size: .75rem;
        box-shadow: 0 5px 18px rgba(13,90,61,.18);
    }

    .tep-prob-row {
        display: grid;
        grid-template-columns: 110px 1fr 110px;
        align-items: center;
        gap: .8rem;
        margin-top: .9rem;
    }

    .tep-prob {
        font-size: 2.15rem;
        font-weight: 950;
        color: var(--green);
        letter-spacing: -.05em;
    }

    .tep-prob.b {
        color: #262f2a;
        text-align: right;
    }

    .tep-bar {
        height: 14px;
        background: #e2e4df;
        border-radius: 999px;
        overflow: hidden;
        display: flex;
    }

    .tep-bar-a {
        height: 100%;
        background: linear-gradient(90deg, #0d5a3d, #1d825d);
    }

    .tep-bar-b {
        height: 100%;
        background: #bdc5bf;
    }

    .tep-prob-caption {
        text-align: center;
        margin-top: .35rem;
        color: var(--muted);
        font-size: .68rem;
        text-transform: uppercase;
        letter-spacing: .14em;
        font-weight: 850;
    }

    /* ---------- MARKET CARDS ---------- */
    .tep-market-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0,1fr));
        gap: .8rem;
        margin-top: .8rem;
    }

    .tep-market {
        border: 1px solid var(--line);
        background: #fbfaf5;
        border-radius: 15px;
        padding: .9rem;
    }

    .tep-market.positive {
        background: #f0f7f2;
        border-color: #bfd7c7;
    }

    .tep-market.negative {
        background: #fbf1ee;
        border-color: #ebd0ca;
    }

    .tep-market-name {
        font-family: Georgia, "Times New Roman", serif;
        font-weight: 700;
        color: #1b2922;
        font-size: 1.03rem;
    }

    .tep-market-kpis {
        display: grid;
        grid-template-columns: repeat(3,1fr);
        gap: .5rem;
        margin-top: .65rem;
    }

    .tep-mini-label {
        color: var(--muted);
        font-size: .64rem;
        text-transform: uppercase;
        letter-spacing: .08em;
        font-weight: 800;
    }

    .tep-mini-value {
        color: #16211c;
        font-size: 1.03rem;
        font-weight: 900;
        margin-top: .08rem;
    }

    .tep-mini-value.ev-positive { color: #137046; }
    .tep-mini-value.ev-negative { color: #b63d3d; }

    /* ---------- KPI STRIP ---------- */
    .tep-kpi-strip {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: .65rem;
        margin-bottom: 1rem;
    }

    .tep-kpi {
        background: rgba(255,253,248,.95);
        border: 1px solid var(--line);
        border-radius: 15px;
        padding: .8rem .9rem;
    }

    .tep-kpi-label {
        color: var(--muted);
        font-size: .66rem;
        letter-spacing: .08em;
        text-transform: uppercase;
        font-weight: 800;
    }

    .tep-kpi-value {
        color: #173225;
        font-size: 1.18rem;
        font-weight: 900;
        margin-top: .18rem;
    }

    /* ---------- STREAMLIT WIDGETS ---------- */
    div[data-testid="stSelectbox"] label,
    div[data-testid="stNumberInput"] label,
    div[data-testid="stCheckbox"] label {
        color: #344039 !important;
        font-size: .78rem !important;
        font-weight: 800 !important;
    }

    div[data-baseweb="select"] > div,
    div[data-testid="stNumberInput"] input {
        background: #fffdf8 !important;
        border-color: #d9d8cf !important;
        border-radius: 12px !important;
        color: #17201b !important;
    }

    .stButton > button[kind="primary"] {
        min-height: 3.1rem;
        border: 0 !important;
        border-radius: 12px !important;
        background: linear-gradient(135deg, #0d5a3d, #167351) !important;
        color: #fff !important;
        font-weight: 900 !important;
        letter-spacing: .02em;
        box-shadow: 0 9px 22px rgba(13,90,61,.16);
    }

    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px);
        filter: brightness(1.03);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 14px;
        overflow: hidden;
    }

    div[data-testid="stMetric"] {
        border: 1px solid var(--line);
        border-radius: 14px;
        background: #fffdf8;
        padding: .7rem .8rem;
    }

    div[data-testid="stMetricLabel"] {
        color: var(--muted);
    }

    /* ---------- NEWS ---------- */
    .tep-news {
        padding: .75rem .8rem;
        border-radius: 12px;
        border: 1px solid var(--line);
        background: #faf9f5;
        margin-bottom: .55rem;
    }

    .tep-risk-low { color: #147247; font-weight: 900; }
    .tep-risk-mid { color: #a57217; font-weight: 900; }
    .tep-risk-high { color: #b93b3b; font-weight: 900; }

    /* ---------- FOOTER ---------- */
    .tep-footer {
        margin-top: 1.5rem;
        border-top: 1px solid var(--line);
        padding: 1rem .2rem 0;
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        color: #7a817c;
        font-size: .72rem;
    }


    /* ---------- RESPONSIVE ---------- */
    @media (max-width: 900px) {
        .block-container {
            padding-left: .8rem;
            padding-right: .8rem;
        }

        .tep-topbar {
            margin-left: -.8rem;
            margin-right: -.8rem;
            padding-left: .9rem;
            padding-right: .9rem;
        }

        .tep-nav { display: none; }
        .tep-brand { min-width: 0; }
        .tep-brand-name { font-size: 1.28rem; }

        .tep-status {
            font-size: .68rem;
            padding: .4rem .55rem;
        }

        .tep-kpi-strip {
            grid-template-columns: repeat(2, 1fr);
        }

        .tep-prob-row {
            grid-template-columns: 70px 1fr 70px;
        }

        .tep-prob {
            font-size: 1.55rem;
        }

        .tep-market-grid {
            grid-template-columns: 1fr;
        }

        .tep-match-head {
            grid-template-columns: 1fr 2.3rem 1fr;
        }

        .tep-player-name {
            font-size: 1.15rem;
        }

        .tep-footer {
            flex-direction: column;
        }
    }

    @media (max-width: 560px) {
        .tep-status .tep-status-text { display: none; }
        .tep-kpi-strip { grid-template-columns: 1fr 1fr; }
        .tep-hero { padding: 1.15rem; }
        .tep-title { font-size: 2rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATA
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

last_update = str(
    get_last_update()
    or "Sin actualizar"
)

data_version = (
    f"{last_update}:{len(df)}"
)

model_status = get_v42_status()

players = sorted(
    set(
        df["winner_name"]
        .dropna()
        .astype(str)
    )
    |
    set(
        df["loser_name"]
        .dropna()
        .astype(str)
    )
)


# ============================================================
# HELPERS
# ============================================================

def esc(value):
    return html.escape(
        str(value or "")
    )


def value_class(ev):
    if ev > 0:
        return "positive"
    return "negative"


def ev_class(ev):
    if ev > 0:
        return "ev-positive"
    return "ev-negative"


def value_text(ev):
    if ev >= 0.10:
        return "VALUE FUERTE"
    if ev >= 0.05:
        return "VALUE POSITIVO"
    if ev > 0:
        return "VALUE PEQUEÑO"
    return "SIN VALUE"


def risk_class(score):
    score = int(
        score or 0
    )

    if score >= 60:
        return "tep-risk-high"
    if score >= 25:
        return "tep-risk-mid"
    return "tep-risk-low"


def render_market(
    player,
    probability,
    odds,
    fair_odds,
    edge,
    ev,
):
    render_html(
        f"""
        <div class="tep-market {value_class(ev)}">
          <div class="tep-kicker">{value_text(ev)}</div>
          <div class="tep-market-name">{esc(player)}</div>
          <div class="tep-market-kpis">
            <div>
              <div class="tep-mini-label">Tu cuota</div>
              <div class="tep-mini-value">{odds:.2f}</div>
            </div>
            <div>
              <div class="tep-mini-label">Cuota justa</div>
              <div class="tep-mini-value">{fair_odds:.2f}</div>
            </div>
            <div>
              <div class="tep-mini-label">EV</div>
              <div class="tep-mini-value {ev_class(ev)}">{ev:+.1%}</div>
            </div>
          </div>
          <div class="tep-divider"></div>
          <div style="display:flex;justify-content:space-between;gap:.8rem;">
            <span style="color:#6e756f;font-size:.74rem;">Prob. modelo</span>
            <strong style="color:#173225;">{probability:.1%}</strong>
          </div>
          <div style="display:flex;justify-content:space-between;gap:.8rem;margin-top:.2rem;">
            <span style="color:#6e756f;font-size:.74rem;">Edge</span>
            <strong class="{ev_class(edge)}">{edge:+.1%}</strong>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TOP NAV
# ============================================================

model_text = (
    "V4.2 activo"
    if model_status.get("ok")
    else "Backup"
)

render_html(
    f"""
    <div class="tep-topbar">
      <div class="tep-brand">
        <div class="tep-mark">🎾</div>
        <div class="tep-brand-name">Tennis Edge Pro</div>
      </div>

      <div class="tep-nav">
        <div class="tep-nav-pill active">Analizador</div>
        <div class="tep-nav-pill">ATP + Challenger</div>
        <div class="tep-nav-pill">Modelo V4.2</div>
      </div>

      <div class="tep-status">
        <span class="tep-dot"></span>
        <span class="tep-status-text">{esc(model_text)} · {esc(last_update)}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HERO
# ============================================================

render_html(
    f"""
    <section class="tep-hero">
      <div class="tep-eyebrow">Tennis intelligence · Match analyzer</div>
      <div class="tep-title">Los datos hablan antes del primer saque.</div>
      <div class="tep-subtitle">
        Compara dos jugadores con el Ensemble V4.2 usando histórico ATP y
        Challenger, forma reciente, Elo general y por superficie,
        saque/resto, calidad de rivales y enfrentamientos directos.
      </div>
      <div class="tep-model-chip">
        🎾 {esc(model_text)} · {len(df):,} partidos en la base
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)


render_html(
    f"""
    <div class="tep-kpi-strip">
      <div class="tep-kpi">
        <div class="tep-kpi-label">Base histórica</div>
        <div class="tep-kpi-value">{len(df):,}</div>
      </div>
      <div class="tep-kpi">
        <div class="tep-kpi-label">Modelo</div>
        <div class="tep-kpi-value">{esc(model_text)}</div>
      </div>
      <div class="tep-kpi">
        <div class="tep-kpi-label">Ventana reciente</div>
        <div class="tep-kpi-value">25 partidos</div>
      </div>
      <div class="tep-kpi">
        <div class="tep-kpi-label">Cobertura</div>
        <div class="tep-kpi-value">ATP + CH</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# MATCH CONFIGURATION
# ============================================================

render_html(
    """
    <div class="tep-card" style="margin-bottom:.9rem;">
      <div class="tep-kicker">Nuevo análisis</div>
      <div class="tep-card-title">Configura el enfrentamiento</div>
      <div class="tep-card-sub">
        Selecciona jugadores, superficie e introduce las cuotas que quieras comprobar.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

p1, p2, ps = st.columns(
    [1.2, 1.2, .75]
)

with p1:
    player_a = st.selectbox(
        "Jugador A",
        players,
        key="web_player_a",
    )

with p2:
    player_b = st.selectbox(
        "Jugador B",
        players,
        index=min(
            1,
            len(players) - 1,
        ),
        key="web_player_b",
    )

with ps:
    surface = st.selectbox(
        "Superficie",
        [
            "Hard",
            "Clay",
            "Grass",
            "Todas",
        ],
        key="web_surface",
    )

q1, q2, q3, q4 = st.columns(
    [1, 1, .85, 1.15]
)

with q1:
    cuota_a = st.number_input(
        f"Cuota · {player_a}",
        min_value=1.01,
        value=1.50,
        step=0.01,
        format="%.2f",
        key="web_odds_a",
    )

with q2:
    cuota_b = st.number_input(
        f"Cuota · {player_b}",
        min_value=1.01,
        value=2.50,
        step=0.01,
        format="%.2f",
        key="web_odds_b",
    )

with q3:
    incluir_fisico = st.checkbox(
        "Noticias / físico",
        value=True,
        help=(
            "Añade contexto externo de lesiones/noticias. "
            "No modifica el motor V4.2."
        ),
        key="web_physical",
    )

with q4:
    analizar = st.button(
        "ANALIZAR PARTIDO  →",
        type="primary",
        use_container_width=True,
        key="web_analyze",
    )


# ============================================================
# RUN + SESSION PERSISTENCE
# ============================================================

if analizar:
    if player_a == player_b:
        st.error(
            "Selecciona dos jugadores diferentes."
        )
    else:
        surface_model = (
            None
            if surface == "Todas"
            else surface
        )

        with st.spinner(
            "Analizando partido con Ensemble V4.2..."
        ):
            result = predict_match_cached(
                player_a,
                player_b,
                surface_model,
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
        else:
            physical_a = None
            physical_b = None

            if incluir_fisico:
                with st.spinner(
                    "Revisando noticias y contexto físico..."
                ):
                    physical_a = load_physical_status(
                        player_a
                    )
                    physical_b = load_physical_status(
                        player_b
                    )

            st.session_state[
                "tep_web_analysis"
            ] = {
                "player_a": player_a,
                "player_b": player_b,
                "surface": surface,
                "cuota_a": float(cuota_a),
                "cuota_b": float(cuota_b),
                "incluir_fisico": bool(
                    incluir_fisico
                ),
                "result": result,
                "physical_a": physical_a,
                "physical_b": physical_b,
            }


payload = st.session_state.get(
    "tep_web_analysis"
)


# ============================================================
# OUTPUT
# ============================================================

if payload:
    a_name = payload["player_a"]
    b_name = payload["player_b"]
    a_odds = float(
        payload["cuota_a"]
    )
    b_odds = float(
        payload["cuota_b"]
    )
    shown_surface = payload[
        "surface"
    ]
    result = payload[
        "result"
    ]

    pa = float(
        result["prob_a"]
    )
    pb = float(
        result["prob_b"]
    )

    fair_a = (
        1 / pa
        if pa > 0
        else 0
    )
    fair_b = (
        1 / pb
        if pb > 0
        else 0
    )

    implied_a = (
        1 / a_odds
    )
    implied_b = (
        1 / b_odds
    )

    edge_a = (
        pa - implied_a
    )
    edge_b = (
        pb - implied_b
    )

    ev_a = (
        pa * a_odds
        - 1
    )
    ev_b = (
        pb * b_odds
        - 1
    )

    confidence = result.get(
        "confidence_label",
        "Sin dato",
    )

    favorite = (
        a_name
        if pa >= pb
        else b_name
    )

    render_html(
        f"""
        <div class="tep-match-card">
          <div class="tep-kicker">
            Resultado · {esc(shown_surface)}
          </div>

          <div class="tep-match-head">
            <div class="tep-player">
              <div class="tep-player-label">Jugador A</div>
              <div class="tep-player-name">{esc(a_name)}</div>
            </div>

            <div class="tep-vs">VS</div>

            <div class="tep-player right">
              <div class="tep-player-label">Jugador B</div>
              <div class="tep-player-name">{esc(b_name)}</div>
            </div>
          </div>

          <div class="tep-prob-row">
            <div class="tep-prob">{pa:.1%}</div>
            <div class="tep-bar">
              <div class="tep-bar-a" style="width:{pa*100:.2f}%"></div>
              <div class="tep-bar-b" style="width:{pb*100:.2f}%"></div>
            </div>
            <div class="tep-prob b">{pb:.1%}</div>
          </div>

          <div class="tep-prob-caption">
            Probabilidad de victoria · Favorito: {esc(favorite)} · Confianza: {esc(confidence)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # MARKET
    render_html(
        """
        <div class="tep-kicker">Mercado</div>
        <div class="tep-card-title">Cuota justa, Edge y valor esperado</div>
        <div class="tep-card-sub">
            La cuota justa procede de la probabilidad del modelo.
            El EV se calcula con la cuota introducida manualmente.
        </div>
        """,
        unsafe_allow_html=True,
    )

    mv1, mv2 = st.columns(2)

    with mv1:
        render_market(
            a_name,
            pa,
            a_odds,
            fair_a,
            edge_a,
            ev_a,
        )

    with mv2:
        render_market(
            b_name,
            pb,
            b_odds,
            fair_b,
            edge_b,
            ev_b,
        )

    # MAIN ANALYTICS GRID
    render_html(
        "<div style='height:.8rem'></div>",
        unsafe_allow_html=True,
    )

    left, mid, right = st.columns(
        [1, 1, 1]
    )

    h2h = result.get(
        "h2h",
        {},
    )

    with left:
        render_html(
            f"""
            <div class="tep-card">
              <div class="tep-kicker">Head to Head</div>
              <div class="tep-card-title">Enfrentamientos directos</div>
              <div class="tep-card-sub">
                Partidos encontrados en el histórico cargado.
              </div>
              <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:.7rem;align-items:center;margin-top:.8rem;">
                <div style="text-align:center;">
                  <div style="font-size:2rem;font-weight:950;color:#0d5a3d;">
                    {int(h2h.get('a_wins',0))}
                  </div>
                  <div style="font-size:.72rem;color:#68706b;">{esc(a_name)}</div>
                </div>
                <div style="color:#aaa89f;font-weight:800;">—</div>
                <div style="text-align:center;">
                  <div style="font-size:2rem;font-weight:950;color:#28322d;">
                    {int(h2h.get('b_wins',0))}
                  </div>
                  <div style="font-size:.72rem;color:#68706b;">{esc(b_name)}</div>
                </div>
              </div>
              <div class="tep-divider"></div>
              <div style="text-align:center;color:#747a75;font-size:.75rem;">
                Total: {int(h2h.get('total',0))} enfrentamientos
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with mid:
        elo_a = float(
            result.get(
                "elo_a",
                0,
            )
            or 0
        )
        elo_b = float(
            result.get(
                "elo_b",
                0,
            )
            or 0
        )

        max_elo = max(
            elo_a,
            elo_b,
            1,
        )

        render_html(
            f"""
            <div class="tep-card">
              <div class="tep-kicker">Rating</div>
              <div class="tep-card-title">Elo del enfrentamiento</div>
              <div class="tep-card-sub">
                Elo utilizado para la superficie seleccionada.
              </div>

              <div style="margin-top:.7rem;">
                <div style="display:flex;justify-content:space-between;font-size:.78rem;">
                  <strong>{esc(a_name)}</strong><span>{elo_a:.0f}</span>
                </div>
                <div class="tep-bar" style="height:9px;margin:.28rem 0 .65rem;">
                  <div class="tep-bar-a" style="width:{elo_a/max_elo*100:.1f}%"></div>
                </div>

                <div style="display:flex;justify-content:space-between;font-size:.78rem;">
                  <strong>{esc(b_name)}</strong><span>{elo_b:.0f}</span>
                </div>
                <div class="tep-bar" style="height:9px;margin:.28rem 0 .3rem;">
                  <div class="tep-bar-a" style="width:{elo_b/max_elo*100:.1f}%;background:#62736a;"></div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        render_html(
            f"""
            <div class="tep-card">
              <div class="tep-kicker">Modelo</div>
              <div class="tep-card-title">Lectura rápida</div>
              <div class="tep-card-sub">
                Resumen de la señal principal.
              </div>

              <div style="margin-top:.75rem;color:#3f4a43;font-size:.84rem;line-height:1.55;">
                <strong style="color:#0d5a3d;">{esc(favorite)}</strong>
                parte como favorito con una probabilidad de
                <strong>{max(pa,pb):.1%}</strong>.
              </div>

              <div class="tep-divider"></div>

              <div style="display:flex;justify-content:space-between;font-size:.77rem;">
                <span style="color:#747b76;">Confianza</span>
                <strong>{esc(confidence)}</strong>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:.77rem;margin-top:.3rem;">
                <span style="color:#747b76;">Versión</span>
                <strong>{esc(result.get('model_version','V4.2'))}</strong>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # FACTORS
    render_html(
        "<div style='height:.8rem'></div>",
        unsafe_allow_html=True,
    )

    factors_col, explanation_col = st.columns(
        [1.35, .85]
    )

    with factors_col:
        render_html(
            """
            <div class="tep-kicker">Inside the model</div>
            <div class="tep-card-title">Comparativa estadística</div>
            <div class="tep-card-sub">
                Factores utilizados por el Ensemble V4.2 para comparar ambos jugadores.
            </div>
            """,
            unsafe_allow_html=True,
        )

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
        else:
            st.info(
                "No hay tabla comparativa disponible."
            )

    with explanation_col:
        explanation = result.get(
            "explanation",
            "",
        )

        render_html(
            f"""
            <div class="tep-card">
              <div class="tep-kicker">Interpretación</div>
              <div class="tep-card-title">Qué está viendo V4.2</div>
              <div style="color:#536059;font-size:.82rem;line-height:1.62;margin-top:.5rem;">
                {esc(explanation)}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # PHYSICAL
    if payload.get(
        "incluir_fisico"
    ):
        render_html(
            "<div style='height:.8rem'></div>",
            unsafe_allow_html=True,
        )

        render_html(
            """
            <div class="tep-kicker">Contexto externo</div>
            <div class="tep-card-title">Estado físico y noticias recientes</div>
            <div class="tep-card-sub">
                Esta capa no altera directamente la probabilidad V4.2; añade contexto para revisar el partido.
            </div>
            """,
            unsafe_allow_html=True,
        )

        ph1, ph2 = st.columns(2)

        for col, name, physical in [
            (
                ph1,
                a_name,
                payload.get(
                    "physical_a"
                ),
            ),
            (
                ph2,
                b_name,
                payload.get(
                    "physical_b"
                ),
            ),
        ]:
            with col:
                if not physical:
                    render_html(
                        f"""
                        <div class="tep-card">
                          <div class="tep-card-title">{esc(name)}</div>
                          <div class="tep-card-sub">Sin datos físicos disponibles.</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    continue

                score = int(
                    physical.get(
                        "score",
                        0,
                    )
                    or 0
                )

                status = physical.get(
                    "status",
                    "Sin estado",
                )

                render_html(
                    f"""
                    <div class="tep-card">
                      <div class="tep-kicker">Riesgo físico</div>
                      <div class="tep-card-title">{esc(name)}</div>
                      <div class="{risk_class(score)}" style="font-size:1.55rem;margin:.2rem 0;">
                        {score}/100
                      </div>
                      <div style="color:#5f6862;font-size:.8rem;line-height:1.5;">
                        {esc(status)}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
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

                alerts = (
                    high_alerts
                    if high_alerts
                    else medium_alerts
                )

                if alerts:
                    for article in alerts:
                        render_html(
                            f"""
                            <div class="tep-news">
                              <strong>{esc(article.get('title','Alerta'))}</strong><br>
                              <span style="color:#777f7a;font-size:.72rem;">
                                {esc(article.get('source','Fuente'))}
                              </span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                else:
                    st.success(
                        "Sin alertas físicas recientes detectadas."
                    )

else:
    render_html(
        """
        <div class="tep-card" style="margin-top:.2rem;text-align:center;padding:1.5rem;">
          <div style="font-size:1.9rem;">🎾</div>
          <div class="tep-card-title" style="margin-top:.3rem;">
            El análisis aparecerá aquí
          </div>
          <div class="tep-card-sub" style="margin-bottom:0;">
            Selecciona dos jugadores, introduce las cuotas y pulsa “Analizar partido”.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# FOOTER
# ============================================================

render_html(
    """
    <div class="tep-footer">
      <div>
        <strong style="font-family:Georgia,serif;color:#294033;">🎾 Tennis Edge Pro</strong>
        · Match Analyzer
      </div>
      <div>
        Herramienta estadística · Las probabilidades son estimaciones,
        no garantías de resultado ni de beneficio económico.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
