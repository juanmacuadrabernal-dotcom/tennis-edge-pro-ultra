# BUILD: V13.5.4 · MOBILE SAFE + TOP PICKS QUALITY + EUROPE/MADRID DATE
import os
import html
import textwrap
import sqlite3
import hashlib
from pathlib import Path
import requests
import streamlit as st
import pandas as pd
import numpy as np

from upcoming_matches import get_upcoming_matches
from player_resolver import resolver_partido
from odds_api import get_tennis_odds, construir_indice_cuotas, buscar_mejores_cuotas
from player_news import analyse_physical_status
from database import init_db, get_matches, get_last_update
from updater import update_database
from model_v42 import (
    predict_match_v42,
    get_v42_status,
    clear_v42_state_cache,
)
from ratings import player_elo_table
from bet_tracker import (
    evaluar_pick_automatico,
    resolver_picks_live,
    resolver_picks_pendientes,
    get_track_record,
)


st.set_page_config(
    page_title="Tennis Edge Pro",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded"
)


def aplicar_estilo_premium():
    st.markdown(
        r"""
        <style>
        :root {
            --tep-bg: #06111d;
            --tep-panel: rgba(11, 26, 43, 0.86);
            --tep-border: rgba(112, 169, 216, 0.15);
            --tep-text: #f4f8fb;
            --tep-muted: #8fa3b8;
            --tep-cyan: #20d6e8;
            --tep-blue: #2f7df6;
            --tep-green: #35e07b;
            --tep-orange: #ff8a2a;
        }

        html, body, [class*="css"] {
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at 78% 0%, rgba(31,111,235,.12), transparent 34%),
                radial-gradient(circle at 12% 30%, rgba(20,184,166,.08), transparent 28%),
                linear-gradient(180deg,#06111d 0%,#071522 55%,#06111d 100%);
            color: var(--tep-text);
        }

        /* Ocultamos el chrome de Streamlit para que se sienta como una app propia. */
        header[data-testid="stHeader"] {
            height: 0 !important;
            min-height: 0 !important;
            background: transparent !important;
        }
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {
            display: none !important;
        }

        .block-container {
            max-width: 1720px;
            padding-top: 1.7rem;
            padding-bottom: 4rem;
            padding-left: 1.55rem;
            padding-right: 1.55rem;
        }

        [data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 50% 95%, rgba(30,144,255,.12), transparent 30%),
                linear-gradient(180deg,#071522 0%,#06101b 100%);
            border-right: 1px solid rgba(105,170,220,.14);
        }

        .tep-brand {display:flex;align-items:center;gap:.72rem;margin:.15rem 0 1.15rem;padding:.1rem .15rem;}
        .tep-logo {width:44px;height:44px;display:flex;align-items:center;justify-content:center;border-radius:14px;font-size:25px;background:linear-gradient(135deg,#18d7c6,#39e75f);box-shadow:0 0 28px rgba(32,214,232,.22);}
        .tep-brand-title {font-weight:800;font-size:1.08rem;letter-spacing:-.02em;color:#fff;}
        .tep-brand-title span {color:var(--tep-cyan);}
        .tep-brand-sub {color:var(--tep-muted);font-size:.72rem;margin-top:1px;}
        .tep-nav-active {display:flex;gap:.65rem;align-items:center;padding:.76rem .9rem;border:1px solid rgba(32,214,232,.55);border-radius:12px;background:linear-gradient(90deg,rgba(0,151,196,.23),rgba(0,111,181,.12));color:#eefcff;font-weight:700;margin-bottom:.45rem;}
        .tep-nav-item {display:block;padding:.64rem .9rem;color:#aebdcb !important;text-decoration:none !important;border-radius:10px;margin:.12rem 0;font-size:.9rem;}
        .tep-nav-item:hover {background:rgba(255,255,255,.04);color:white !important;}
        .tep-sidebar-card {border:1px solid rgba(112,169,216,.17);border-radius:14px;padding:1rem;background:rgba(10,28,45,.62);margin-top:1rem;}
        .tep-dot {display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--tep-green);margin-right:6px;box-shadow:0 0 10px rgba(53,224,123,.7);}

        /* Navegación REAL de Streamlit, estilizada como menú premium. */
        [data-testid="stSidebar"] div[role="radiogroup"] {gap:.28rem;}
        [data-testid="stSidebar"] div[role="radiogroup"] > label {
            width:100%;
            padding:.68rem .78rem;
            border:1px solid transparent;
            border-radius:11px;
            background:transparent;
            transition:.16s ease;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
            background:rgba(255,255,255,.045);
            border-color:rgba(112,169,216,.12);
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            background:linear-gradient(90deg,rgba(0,151,196,.23),rgba(0,111,181,.12));
            border-color:rgba(32,214,232,.55);
            box-shadow:0 0 20px rgba(32,214,232,.06);
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {display:none!important;}
        [data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"] {display:none!important;}
        [data-testid="stSidebar"] div[data-baseweb="radio"] > div:first-child {display:none!important;}
        [data-testid="stSidebar"] div[role="radiogroup"] p {font-weight:650;color:#b8c7d4;margin:0;}
        [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {color:#f2fcff;font-weight:800;}

        .tep-header {display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin:0 0 1.15rem;}
        .tep-title {font-weight:850;font-size:2rem;line-height:1.05;letter-spacing:-.035em;color:#fff;}
        .tep-subtitle {color:var(--tep-muted);margin-top:.42rem;font-size:.92rem;}
        .tep-status-wrap {display:flex;flex-wrap:wrap;justify-content:flex-end;gap:.55rem;}
        .tep-chip {min-width:116px;padding:.58rem .78rem;border:1px solid rgba(112,169,216,.15);background:rgba(10,26,42,.74);border-radius:10px;}
        .tep-chip-label {color:#8297aa;font-size:.68rem;}
        .tep-chip-value {margin-top:.15rem;font-size:.9rem;font-weight:760;color:#fff;}
        .tep-chip-value.green {color:var(--tep-green);}.tep-chip-value.cyan{color:var(--tep-cyan);}.tep-chip-value.orange{color:var(--tep-orange);}

        .tep-kpi-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.8rem;margin-bottom:1.15rem;}
        .tep-kpi {position:relative;overflow:hidden;min-height:118px;border:1px solid rgba(112,169,216,.15);border-radius:14px;background:linear-gradient(145deg,rgba(14,34,55,.92),rgba(8,23,39,.84));padding:1rem 1.05rem;box-shadow:0 12px 30px rgba(0,0,0,.10);}
        .tep-kpi:after {content:"";position:absolute;right:-34px;bottom:-52px;width:120px;height:120px;border-radius:50%;background:radial-gradient(circle,rgba(32,214,232,.11),transparent 68%);}
        .tep-kpi-top {display:flex;align-items:center;gap:.65rem;}.tep-kpi-icon{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(32,214,232,.12);border:1px solid rgba(32,214,232,.18);font-size:20px;}
        .tep-kpi-label{color:#aebdcb;font-size:.78rem;}.tep-kpi-value{color:#fff;font-size:1.55rem;font-weight:850;letter-spacing:-.025em;margin-top:.15rem;}.tep-kpi-foot{color:#73899d;font-size:.72rem;margin-top:.45rem;}
        .tep-positive{color:var(--tep-green)!important;}.tep-orange{color:var(--tep-orange)!important;}.tep-cyan{color:var(--tep-cyan)!important;}

        .tep-section-title {font-size:1.05rem;font-weight:800;color:#fff;margin:1.05rem 0 .7rem;display:flex;align-items:center;gap:.5rem;}
        .tep-section-title:after {content:"";height:1px;flex:1;margin-left:.35rem;background:linear-gradient(90deg,rgba(57,202,226,.18),transparent);}

        div[data-testid="stMetric"] {border:1px solid rgba(112,169,216,.15);border-radius:13px;padding:.78rem .9rem;background:linear-gradient(145deg,rgba(14,34,55,.88),rgba(8,23,39,.78));}
        div[data-testid="stMetric"] label {color:#8fa3b8!important;}
        div[data-testid="stDataFrame"] {border:1px solid rgba(112,169,216,.14);border-radius:14px;overflow:hidden;background:rgba(8,23,39,.72);box-shadow:0 10px 28px rgba(0,0,0,.08);}
        div[data-testid="stExpander"] {border:1px solid rgba(112,169,216,.14);border-radius:12px;background:rgba(8,23,39,.60);}
        div[data-testid="stAlert"] {border-radius:12px;border-color:rgba(112,169,216,.16);}

        .stButton>button,.stDownloadButton>button {min-height:42px;border-radius:10px!important;border:1px solid rgba(62,183,222,.25)!important;background:linear-gradient(180deg,rgba(16,50,76,.95),rgba(10,35,56,.95))!important;color:#f3fbff!important;font-weight:700!important;box-shadow:none!important;}
        .stButton>button:hover,.stDownloadButton>button:hover {border-color:rgba(32,214,232,.75)!important;background:linear-gradient(180deg,rgba(18,72,98,.98),rgba(11,48,75,.98))!important;transform:translateY(-1px);}
        .stButton>button[kind="primary"] {background:linear-gradient(90deg,#0d99bc,#176be8)!important;border-color:rgba(57,220,240,.55)!important;}

        div[data-baseweb="select"]>div,div[data-testid="stNumberInput"] input,div[data-testid="stTextInput"] input {background:rgba(8,24,40,.92)!important;border-color:rgba(112,169,216,.16)!important;border-radius:10px!important;}
        [data-testid="stProgressBar"]>div>div>div {background:linear-gradient(90deg,var(--tep-cyan),var(--tep-blue))!important;}
        hr{border-color:rgba(112,169,216,.11)!important;} h1,h2,h3{letter-spacing:-.025em;} h2{font-size:1.32rem!important;} h3{font-size:1.05rem!important;}


        .tep-dash-grid {
            display:grid;
            grid-template-columns:minmax(0,1.05fr) minmax(0,1.35fr) minmax(285px,.78fr);
            gap:.85rem;
            margin-top:.85rem;
            align-items:stretch;
        }
        .tep-card {
            position:relative;
            overflow:hidden;
            border:1px solid rgba(112,169,216,.16);
            border-radius:15px;
            background:
                radial-gradient(circle at 95% 0%,rgba(31,111,235,.08),transparent 32%),
                linear-gradient(145deg,rgba(13,31,50,.94),rgba(7,21,36,.94));
            box-shadow:0 14px 34px rgba(0,0,0,.12);
        }
        .tep-card-head {
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:.7rem;
            padding:.92rem 1rem .72rem;
            border-bottom:1px solid rgba(112,169,216,.11);
        }
        .tep-card-title {font-size:.94rem;font-weight:800;color:#fff;}
        .tep-card-tag {
            padding:.25rem .5rem;
            border-radius:7px;
            color:#21d9cd;
            background:rgba(17,202,190,.10);
            border:1px solid rgba(17,202,190,.15);
            font-size:.66rem;
            font-weight:700;
        }
        .tep-feature-body {padding:1rem 1rem .9rem;}
        .tep-match-time {text-align:center;color:#dbe8f1;font-size:.82rem;font-weight:700;margin:.15rem 0 .85rem;}
        .tep-match-time span {display:block;color:#7f94a7;font-size:.68rem;font-weight:500;margin-top:.15rem;}
        .tep-players {display:grid;grid-template-columns:1fr 54px 1fr;gap:.5rem;align-items:center;}
        .tep-player {text-align:center;}
        .tep-avatar {
            width:76px;height:76px;margin:0 auto .55rem;border-radius:50%;
            display:flex;align-items:center;justify-content:center;
            position:relative;overflow:hidden;
            background:linear-gradient(145deg,rgba(24,216,198,.18),rgba(35,109,246,.18));
            border:2px solid rgba(41,215,222,.42);
            box-shadow:
                0 0 0 4px rgba(30,147,218,.05),
                0 0 30px rgba(32,214,232,.11);
            font-size:1.15rem;font-weight:850;color:#eafcff;
        }
        .tep-avatar .tep-avatar-initials {
            position:absolute;
            inset:0;
            display:flex;
            align-items:center;
            justify-content:center;
            z-index:1;
        }
        .tep-avatar img {
            position:absolute;
            inset:0;
            width:100%;
            height:100%;
            object-fit:cover;
            object-position:center;
            border-radius:50%;
            z-index:2;
            background:#0a1d2d;
        }
        .tep-player-name {
            font-size:.86rem!important;
            font-weight:800!important;
            color:#f6fbff!important;
            white-space:normal!important;
            line-height:1.16!important;
            min-height:2em;
            overflow:visible!important;
        }
        .tep-player-name {font-size:.88rem;font-weight:800;color:#f6fbff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
        .tep-player-meta {font-size:.68rem;color:#8196a9;margin-top:.16rem;}
        .tep-vs {
            width:42px;height:42px;margin:auto;border-radius:50%;
            display:flex;align-items:center;justify-content:center;
            border:1px solid rgba(142,180,211,.28);color:#dbe7ef;
            background:rgba(5,18,31,.7);font-size:.78rem;font-weight:800;
        }
        .tep-prob-title {text-align:center;font-size:.72rem;color:#a9bbc9;margin:1rem 0 .4rem;}
        .tep-probbar {display:grid;grid-template-columns:var(--left) calc(100% - var(--left));height:34px;border-radius:8px;overflow:hidden;border:1px solid rgba(70,171,219,.16);}
        .tep-prob-a,.tep-prob-b {display:flex;align-items:center;font-weight:850;font-size:.84rem;padding:0 .65rem;}
        .tep-prob-a {background:linear-gradient(90deg,#0faeaa,#18c7ba);justify-content:flex-start;color:white;}
        .tep-prob-b {background:linear-gradient(90deg,#1768dc,#2488fa);justify-content:flex-end;color:white;}
        .tep-feature-foot {margin-top:.75rem;padding:.62rem;border-radius:9px;text-align:center;background:rgba(255,255,255,.025);color:#aebfcd;font-size:.72rem;}

        .tep-picks {padding:.25rem .78rem .55rem;}
        .tep-pick-head,.tep-pick-row {
            display:grid;
            grid-template-columns:minmax(150px,1.4fr) .86fr .52fr .55fr .72fr;
            align-items:center;
            gap:.5rem;
        }
        .tep-pick-head {padding:.4rem .4rem .45rem;color:#71879a;font-size:.63rem;border-bottom:1px solid rgba(112,169,216,.08);}
        .tep-pick-row {padding:.57rem .4rem;border-bottom:1px solid rgba(112,169,216,.07);}
        .tep-pick-row:last-child {border-bottom:0;}
        .tep-pick-name {font-size:.76rem;font-weight:800;color:#eef8ff;}
        .tep-pick-sub {font-size:.61rem;color:#71879a;margin-top:.12rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
        .tep-mini-prob {height:5px;border-radius:5px;background:#172c3d;overflow:hidden;margin-top:.25rem;}
        .tep-mini-prob span {display:block;height:100%;background:linear-gradient(90deg,#16c5bd,#25badd);border-radius:5px;}
        .tep-num {font-size:.72rem;color:#e9f4fb;}
        .tep-ev-good {font-size:.72rem;color:#36e47e;font-weight:800;}
        .tep-badge {
            display:inline-flex;align-items:center;justify-content:center;
            padding:.24rem .45rem;border-radius:6px;font-size:.62rem;font-weight:800;
            background:rgba(35,194,88,.12);color:#42e985;border:1px solid rgba(35,194,88,.14);
        }
        .tep-badge.medium {background:rgba(245,177,36,.11);color:#ffc83f;border-color:rgba(245,177,36,.14);}
        .tep-empty {padding:1.3rem 1rem;color:#8297aa;font-size:.78rem;text-align:center;}

        .tep-right-stack {display:grid;grid-template-rows:1fr 1fr;gap:.85rem;height:100%;}
        .tep-mini-card {border:1px solid rgba(112,169,216,.16);border-radius:15px;background:linear-gradient(145deg,rgba(13,31,50,.94),rgba(7,21,36,.94));padding:.9rem 1rem;}
        .tep-mini-title {font-size:.86rem;font-weight:800;color:#fff;margin-bottom:.75rem;}
        .tep-profit-value {font-size:1.32rem;font-weight:880;color:#2ee081;letter-spacing:-.025em;}
        .tep-profit-sub {font-size:.68rem;color:#7d91a4;margin-top:.2rem;}
        .tep-fake-line {height:74px;margin-top:.75rem;position:relative;border-bottom:1px solid rgba(112,169,216,.1);background:linear-gradient(180deg,transparent,rgba(20,205,196,.03));}
        .tep-fake-line svg {width:100%;height:100%;display:block;}
        .tep-confidence-wrap {display:flex;align-items:center;gap:1rem;}
        .tep-donut {
            --a:0deg;--b:0deg;
            width:92px;height:92px;border-radius:50%;
            background:conic-gradient(#14c9bf 0 var(--a),#f0b621 var(--a) var(--b),#ff654f var(--b) 360deg);
            position:relative;flex:0 0 92px;
        }
        .tep-donut:after {content:"";position:absolute;inset:16px;border-radius:50%;background:#0a1c2d;border:1px solid rgba(112,169,216,.10);}
        .tep-donut-center {position:absolute;inset:0;display:flex;align-items:center;justify-content:center;z-index:2;flex-direction:column;color:#fff;font-size:.9rem;font-weight:850;}
        .tep-donut-center span {font-size:.58rem;color:#8094a7;font-weight:500;}
        .tep-legend {display:grid;gap:.38rem;flex:1;}
        .tep-leg {display:flex;align-items:center;justify-content:space-between;gap:.5rem;font-size:.67rem;color:#a8bac8;}
        .tep-leg-left {display:flex;align-items:center;gap:.38rem;}
        .tep-leg-dot {width:7px;height:7px;border-radius:50%;background:#14c9bf;}
        .tep-leg-dot.yellow {background:#f0b621}.tep-leg-dot.red{background:#ff654f}
        .tep-leg b {color:#e9f3fa;font-size:.68rem;}

        .tep-lower-grid {display:grid;grid-template-columns:1fr;gap:.85rem;margin-top:.85rem;}
        .tep-perf-summary {
            display:grid;grid-template-columns:1.3fr repeat(5,.65fr);
            gap:.4rem;align-items:center;padding:.42rem .75rem;
            font-size:.69rem;border-bottom:1px solid rgba(112,169,216,.07);
        }
        .tep-perf-summary.head {color:#74899c;background:rgba(255,255,255,.018);font-size:.62rem;}
        .tep-perf-summary strong {font-size:.72rem;color:#edf7fd;}
        .tep-perf-level {display:flex;align-items:center;gap:.45rem;color:#dce8f0;}
        .tep-section-subhead {display:flex;align-items:center;justify-content:space-between;padding:.85rem 1rem .55rem;}
        .tep-section-subhead h3 {margin:0!important;font-size:.91rem!important;}
        .tep-note {font-size:.65rem;color:#70869a;}

        @media(max-width:1250px){
            .tep-dash-grid{grid-template-columns:1fr 1.25fr;}
            .tep-right-stack{grid-column:1/-1;grid-template-columns:1fr 1fr;grid-template-rows:auto;}
        }
        @media(max-width:850px){
            .tep-dash-grid{grid-template-columns:1fr;}
            .tep-right-stack{grid-column:auto;grid-template-columns:1fr;}
            .tep-pick-head,.tep-pick-row{grid-template-columns:1.4fr .8fr .55fr .55fr;}
            .tep-pick-head > :last-child,.tep-pick-row > :last-child{display:none;}

            /* =====================================================
               V13.5.2 · NAVEGACIÓN MÓVIL · MENÚ SEGURO
               En escritorio ocultamos el chrome de Streamlit, pero
               en móvil necesitamos conservar el control nativo que
               abre/cierra el sidebar.
               ===================================================== */
            header[data-testid="stHeader"] {
                display:block !important;
                height:3.45rem !important;
                min-height:3.45rem !important;
                background:rgba(6,17,29,.96) !important;
                border-bottom:1px solid rgba(112,169,216,.14) !important;
                backdrop-filter:blur(12px);
                -webkit-backdrop-filter:blur(12px);
                z-index:999998 !important;
            }

            /* CLAVE V13.5.2:
               arriba ocultamos stToolbar globalmente. En móvil lo
               recuperamos porque el control para reabrir el sidebar
               puede vivir dentro de este contenedor. */
            [data-testid="stToolbar"] {
                display:flex !important;
                visibility:visible !important;
                opacity:1 !important;
                pointer-events:auto !important;
                z-index:1000002 !important;
            }

            [data-testid="stSidebarCollapsedControl"],
            [data-testid="stSidebarCollapseButton"] {
                display:flex !important;
                visibility:visible !important;
                opacity:1 !important;
                pointer-events:auto !important;
                z-index:1000001 !important;
            }

            [data-testid="stSidebarCollapsedControl"] {
                position:fixed !important;
                top:.48rem !important;
                left:.55rem !important;
            }

            [data-testid="stSidebarCollapsedControl"] button,
            [data-testid="stSidebarCollapseButton"] button,
            button[data-testid="stSidebarCollapseButton"],
            button[data-testid="stSidebarCollapsedControl"],
            header[data-testid="stHeader"] button[kind="headerNoPadding"] {
                display:flex !important;
                align-items:center !important;
                justify-content:center !important;
                width:42px !important;
                height:42px !important;
                min-width:42px !important;
                min-height:42px !important;
                border-radius:11px !important;
                border:1px solid rgba(32,214,232,.34) !important;
                background:linear-gradient(145deg,rgba(13,49,72,.97),rgba(7,31,50,.97)) !important;
                color:#f4fbff !important;
                box-shadow:0 8px 24px rgba(0,0,0,.22) !important;
            }

            /* V13.5.1:
               NO forzamos el ancho del sidebar.
               Streamlit controla su ancho + transform de apertura/cierre.
               Al forzar 88vw, al cerrarlo quedaba una franja visible
               de ~40-50 px en iPhone (justo lo que veíamos en pantalla). */
            [data-testid="stSidebar"] {
                z-index:1000000 !important;
                box-shadow:18px 0 48px rgba(0,0,0,.34) !important;
            }

            [data-testid="stSidebar"] > div:first-child {
                padding-top:.65rem !important;
            }

            .block-container {
                padding-top:4.25rem !important;
                padding-left:.9rem !important;
                padding-right:.9rem !important;
                padding-bottom:3rem !important;
            }

            .tep-title{font-size:1.65rem;}
            .tep-kpi-grid{grid-template-columns:1fr 1fr;gap:.65rem;}
            .tep-kpi{min-height:105px;padding:.85rem .9rem;}
            .tep-kpi-value{font-size:1.3rem;}
            .tep-status-wrap{width:100%;}
            .tep-chip{flex:1 1 125px;min-width:0;}
        }

        @media(max-width:560px){
            .tep-kpi-grid{grid-template-columns:1fr;}
            .tep-pick-head,.tep-pick-row{grid-template-columns:1.35fr .75fr .52fr;}
            .tep-pick-head > :nth-child(4),.tep-pick-row > :nth-child(4){display:none;}
            .tep-player-name{font-size:.78rem!important;}
            .tep-players{grid-template-columns:1fr 44px 1fr;}
            .tep-avatar{width:66px;height:66px;}
        }

        @media(max-width:1000px){.tep-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.tep-header{flex-direction:column;}.tep-status-wrap{justify-content:flex-start;}}
        </style>
        """,
        unsafe_allow_html=True
    )


def _fmt_roi(value):
    try:
        return f"{float(value):+.1%}"
    except Exception:
        return "-"


def _fmt_units(value):
    try:
        return f"{float(value):+.2f} u"
    except Exception:
        return "0.00 u"


def render_dashboard_header(estado_v42, track):
    summary = track.get("summary", {})
    picks = track.get("picks", pd.DataFrame())
    if not picks.empty and "match_confidence" in picks.columns:
        conf = pd.to_numeric(picks["match_confidence"], errors="coerce").dropna()
        confianza_media = conf.mean() if not conf.empty else 0.0
    else:
        confianza_media = 0.0

    modelo = estado_v42.get("version", "V4.2") if estado_v42.get("ok") else "V1 backup"
    estado_modelo = "Activo" if estado_v42.get("ok") else "Backup"
    st.markdown(
        f"""
        <div class="tep-header">
          <div><div class="tep-title">Dashboard</div><div class="tep-subtitle">Predicciones, value, resultados y rendimiento de Tennis Edge Pro.</div></div>
          <div class="tep-status-wrap">
            <div class="tep-chip"><div class="tep-chip-label">Modelo</div><div class="tep-chip-value green">● {estado_modelo} · {modelo}</div></div>
            <div class="tep-chip"><div class="tep-chip-label">Confianza media picks</div><div class="tep-chip-value cyan">{confianza_media:.0%}</div></div>
            <div class="tep-chip"><div class="tep-chip-label">Picks pendientes</div><div class="tep-chip-value orange">{int(summary.get('pending',0))}</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_dashboard_kpis(df, estado_v42, track, last_update):
    summary = track.get("summary", {})
    roi = float(summary.get("roi", 0.0) or 0.0)
    profit = float(summary.get("profit", 0.0) or 0.0)
    pending = int(summary.get("pending", 0) or 0)
    model_value = (
        f"{estado_v42.get('alpha_v42',0):.0%}/{estado_v42.get('alpha_v1',0):.0%}"
        if estado_v42.get("ok") else "Backup"
    )
    color_roi = "tep-positive" if roi >= 0 else "tep-orange"
    st.markdown(
        f"""
        <div class="tep-kpi-grid">
          <div class="tep-kpi"><div class="tep-kpi-top"><div class="tep-kpi-icon">🧠</div><div><div class="tep-kpi-label">Ensemble producción</div><div class="tep-kpi-value tep-cyan">{model_value}</div></div></div><div class="tep-kpi-foot">V4.2 + V1 · {estado_v42.get('features',0)} features</div></div>
          <div class="tep-kpi"><div class="tep-kpi-top"><div class="tep-kpi-icon">🎾</div><div><div class="tep-kpi-label">Partidos históricos</div><div class="tep-kpi-value">{len(df):,}</div></div></div><div class="tep-kpi-foot">Base actualizada · {last_update}</div></div>
          <div class="tep-kpi"><div class="tep-kpi-top"><div class="tep-kpi-icon">⭐</div><div><div class="tep-kpi-label">Picks activos</div><div class="tep-kpi-value">{pending}</div></div></div><div class="tep-kpi-foot">Tracker automático · 1 unidad/pick</div></div>
          <div class="tep-kpi"><div class="tep-kpi-top"><div class="tep-kpi-icon">📈</div><div><div class="tep-kpi-label">ROI / Beneficio</div><div class="tep-kpi-value {color_roi}">{_fmt_roi(roi)}</div></div></div><div class="tep-kpi-foot">Beneficio acumulado: {_fmt_units(profit)}</div></div>
        </div>
        """,
        unsafe_allow_html=True
    )


def _html_block(value):
    """
    Streamlit interpreta HTML con 4+ espacios iniciales como bloque de código.
    Normalizamos la indentación antes de enviarlo a st.markdown.
    """
    return textwrap.dedent(
        str(value)
    ).strip()


def _normalizar_nombre_foto(value):
    import unicodedata
    import re

    value = unicodedata.normalize(
        "NFKD",
        str(value or "")
    )

    value = "".join(
        c
        for c in value
        if not unicodedata.combining(c)
    ).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    return " ".join(
        value.split()
    )


@st.cache_data(
    ttl=7 * 24 * 60 * 60,
    show_spinner=False
)
def obtener_atp_id_wikidata(nombre_jugador):
    """
    Resuelve el ATP Player ID oficial usando Wikidata P536.
    Si no hay coincidencia segura, devuelve None.
    """
    nombre = str(
        nombre_jugador
        or ""
    ).strip()

    if len(nombre) < 3:
        return None

    try:
        search_response = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": nombre,
                "language": "en",
                "uselang": "en",
                "type": "item",
                "limit": 8,
                "format": "json",
            },
            headers={
                "User-Agent": "TennisEdgePro/1.0"
            },
            timeout=4,
        )

        search_response.raise_for_status()

        resultados = (
            search_response.json()
            .get(
                "search",
                []
            )
        )

        if not resultados:
            return None

        nombre_norm = (
            _normalizar_nombre_foto(
                nombre
            )
        )

        candidatos = sorted(
            resultados,
            key=lambda item: (
                0
                if (
                    _normalizar_nombre_foto(
                        item.get(
                            "label",
                            ""
                        )
                    )
                    ==
                    nombre_norm
                )
                else 1,
                0
                if "tennis" in str(
                    item.get(
                        "description",
                        ""
                    )
                ).lower()
                else 1,
            )
        )

        ids = [
            item.get(
                "id"
            )
            for item in candidatos
            if item.get(
                "id"
            )
        ]

        if not ids:
            return None

        entity_response = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetentities",
                "ids": "|".join(
                    ids
                ),
                "props": "claims",
                "format": "json",
            },
            headers={
                "User-Agent": "TennisEdgePro/1.0"
            },
            timeout=4,
        )

        entity_response.raise_for_status()

        entities = (
            entity_response.json()
            .get(
                "entities",
                {}
            )
        )

        for qid in ids:
            claims = (
                entities
                .get(
                    qid,
                    {}
                )
                .get(
                    "claims",
                    {}
                )
            )

            for claim in claims.get(
                "P536",
                []
            ):
                try:
                    atp_id = str(
                        claim[
                            "mainsnak"
                        ][
                            "datavalue"
                        ][
                            "value"
                        ]
                    ).strip()

                    if atp_id:
                        return atp_id

                except Exception:
                    continue

    except Exception:
        return None

    return None


def foto_oficial_atp(nombre_jugador):
    """
    Devuelve el headshot oficial alojado por ATP Tour.
    """
    atp_id = obtener_atp_id_wikidata(
        nombre_jugador
    )

    if not atp_id:
        return None

    return (
        "https://www.atptour.com/"
        "-/media/alias/player-headshot/"
        f"{str(atp_id).lower()}"
    )


def _avatar_jugador_html(nombre):
    initials = html.escape(
        _initials(
            nombre
        )
    )

    foto = foto_oficial_atp(
        nombre
    )

    img = ""

    if foto:
        foto_segura = html.escape(
            foto,
            quote=True
        )

        nombre_seguro = html.escape(
            str(nombre),
            quote=True
        )

        img = (
            "<img "
            f"src='{foto_segura}' "
            f"alt='{nombre_seguro}' "
            "loading='lazy' "
            "referrerpolicy='no-referrer' "
            "onerror=\"this.style.display='none';\">"
        )

    return (
        "<div class='tep-avatar'>"
        f"<span class='tep-avatar-initials'>{initials}</span>"
        f"{img}"
        "</div>"
    )


def _initials(name):
    text = str(name or "").strip()
    if not text:
        return "?"
    parts = [p for p in text.replace(".", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return text[:2].upper()


def _pct_from_text(value):
    try:
        return float(str(value).replace("%", "").replace(",", ".")) / 100.0
    except Exception:
        return 0.5


def _dashboard_profit_svg(values):
    vals = []
    for value in values:
        try:
            vals.append(float(value))
        except Exception:
            pass

    if len(vals) < 2:
        vals = [0.0, 0.0]

    cumulative = []
    total = 0.0
    for value in vals[-30:]:
        total += value
        cumulative.append(total)

    if len(cumulative) == 1:
        cumulative.append(cumulative[0])

    min_v = min(cumulative)
    max_v = max(cumulative)
    span = max(max_v - min_v, 1.0)

    points = []
    n = len(cumulative)
    for idx, value in enumerate(cumulative):
        x = 4 + (idx / max(n - 1, 1)) * 92
        y = 64 - ((value - min_v) / span) * 50
        points.append(f"{x:.1f},{y:.1f}")

    return " ".join(points)


def render_dashboard_premium_v13(
    df,
    estado_v42,
    track,
    last_update,
    ventana,
    usar_elo,
    data_version,
):
    render_dashboard_header(
        estado_v42,
        track
    )

    render_dashboard_kpis(
        df,
        estado_v42,
        track,
        last_update
    )

    # Cargamos partidos + cuotas automáticamente para que el Dashboard
    # tenga contenido real, como el mockup original.
    filas = []
    odds_result = {"ok": False, "events": []}

    try:
        with st.spinner(
            "Preparando dashboard con partidos y cuotas..."
        ):
            _, odds_result, filas, _ = (
                _cargar_predicciones_para_paginas(
                    df,
                    ventana,
                    usar_elo,
                    data_version
                )
            )
    except Exception:
        filas = []

    raw = (
        pd.DataFrame(
            filas
        )
        if filas
        else pd.DataFrame()
    )

    # -----------------------------------------------------
    # MATCH DESTACADO
    # -----------------------------------------------------
    featured_html = _html_block(
        """
        <div class="tep-card">
          <div class="tep-card-head">
            <div class="tep-card-title">Próximo partido destacado</div>
            <div class="tep-card-tag">Sin partido disponible</div>
          </div>
          <div class="tep-empty">Carga de próximos partidos no disponible en este momento.</div>
        </div>
        """
    )

    if not raw.empty:
        orden = raw.copy()
        orden["_fecha_sort"] = pd.to_datetime(
            orden["Fecha"],
            errors="coerce"
        )
        orden["_hora_sort"] = (
            orden["Hora"]
            .astype(str)
        )

        # Priorizamos partidos con mercado y después por confianza.
        orden = orden.sort_values(
            [
                "_market_available",
                "_match_confidence",
                "_fecha_sort",
            ],
            ascending=[
                False,
                False,
                True,
            ]
        )

        featured = orden.iloc[0]

        j1_raw = str(
            featured.get(
                "_player1_full",
                featured[
                    "Jugador 1"
                ]
            )
        )

        j2_raw = str(
            featured.get(
                "_player2_full",
                featured[
                    "Jugador 2"
                ]
            )
        )

        j1 = html.escape(
            j1_raw
        )

        j2 = html.escape(
            j2_raw
        )

        avatar_j1 = _avatar_jugador_html(
            j1_raw
        )

        avatar_j2 = _avatar_jugador_html(
            j2_raw
        )

        torneo = html.escape(
            str(
                featured.get(
                    "Torneo",
                    "-"
                )
            )
        )

        tour = html.escape(
            str(
                featured.get(
                    "Tour",
                    ""
                )
            )
        )

        surface = html.escape(
            str(
                featured.get(
                    "Superficie",
                    "-"
                )
            )
        )

        hora = html.escape(
            str(
                featured.get(
                    "Hora",
                    "-"
                )
            )
        )

        fecha = html.escape(
            str(
                featured.get(
                    "Fecha",
                    "-"
                )
            )
        )

        pa = _pct_from_text(
            featured[
                "Prob. J1"
            ]
        )
        pb = _pct_from_text(
            featured[
                "Prob. J2"
            ]
        )

        left = max(
            min(
                pa * 100.0,
                96.0
            ),
            4.0
        )

        featured_html = _html_block(
            f"""
            <div class="tep-card">
          <div class="tep-card-head">
            <div class="tep-card-title">Próximo partido destacado</div>
            <div class="tep-card-tag">{tour} · {torneo}</div>
          </div>
          <div class="tep-feature-body">
            <div class="tep-match-time">{fecha} · {hora}<span>{surface}</span></div>
            <div class="tep-players">
              <div class="tep-player">
                {avatar_j1}
                <div class="tep-player-name">{j1}</div>
                <div class="tep-player-meta">Jugador A</div>
              </div>
              <div class="tep-vs">VS</div>
              <div class="tep-player">
                {avatar_j2}
                <div class="tep-player-name">{j2}</div>
                <div class="tep-player-meta">Jugador B</div>
              </div>
            </div>
            <div class="tep-prob-title">Probabilidad de victoria · Ensemble V4.2</div>
            <div class="tep-probbar" style="--left:{left:.1f}%;">
              <div class="tep-prob-a">{pa:.1%}</div>
              <div class="tep-prob-b">{pb:.1%}</div>
            </div>
            <div class="tep-feature-foot">
              Favorito: <b>{html.escape(str(featured.get("Favorito","-")))}</b>
              · Confianza: {html.escape(str(featured.get("Confianza","-")))}
            </div>
          </div>
            </div>
            """
        )

    # -----------------------------------------------------
    # TOP PICKS VISUALES
    # -----------------------------------------------------
    top_rows = []

    if not raw.empty:
        fechas = pd.to_datetime(
            raw[
                "Fecha"
            ],
            errors="coerce"
        )

        hoy = pd.Timestamp.now(tz="Europe/Madrid").date()

        top = raw.loc[
            (
                fechas.dt.date
                ==
                hoy
            )
            &
            (
                raw[
                    "_pick_qualifies"
                ]
                ==
                True
            )
        ].copy()

        top = top.sort_values(
            "_value_score",
            ascending=False
        ).head(5)

        for _, row in top.iterrows():
            prob = float(
                row.get(
                    "_pick_probability",
                    0.0
                )
                or 0.0
            )

            odds = float(
                row.get(
                    "_pick_odds",
                    0.0
                )
                or 0.0
            )

            ev = float(
                row.get(
                    "_pick_ev",
                    0.0
                )
                or 0.0
            )

            level = str(
                row.get(
                    "_value_category",
                    "VALUE"
                )
            )

            badge_class = (
                ""
                if float(
                    row.get(
                        "_value_score",
                        0.0
                    )
                    or 0.0
                ) >= 65
                else "medium"
            )

            matchup = (
                f"{row.get('Jugador 1','')} vs "
                f"{row.get('Jugador 2','')}"
            )

            top_rows.append(
                _html_block(
                    f"""
                    <div class="tep-pick-row">
                  <div>
                    <div class="tep-pick-name">⭐ {html.escape(str(row.get("_pick_selection","-")))}</div>
                    <div class="tep-pick-sub">{html.escape(matchup)}</div>
                  </div>
                  <div class="tep-num">
                    {prob:.1%}
                    <div class="tep-mini-prob"><span style="width:{max(min(prob*100,100),0):.1f}%"></span></div>
                  </div>
                  <div class="tep-num">{odds:.2f}</div>
                  <div class="tep-ev-good">{ev:+.1%}</div>
                  <div><span class="tep-badge {badge_class}">{html.escape(level.replace("💎 ","").replace("🔥 ","").replace("🟢 ","").replace("🟡 ",""))}</span></div>
                    </div>
                    """
                )
            )

    if top_rows:
        top_body = "".join(
            top_rows
        )
    else:
        top_body = (
            '<div class="tep-empty">'
            'Hoy no hay picks que superen simultáneamente '
            'confianza ≥70%, EV ≥+5% y mercado validado.'
            '</div>'
        )

    top_html = _html_block(
        f"""
        <div class="tep-card">
      <div class="tep-card-head">
        <div class="tep-card-title">Top Picks</div>
        <div class="tep-card-tag">{len(top_rows)} hoy</div>
      </div>
      <div class="tep-picks">
        <div class="tep-pick-head">
          <div>Pick</div><div>Probabilidad</div><div>Cuota</div><div>EV</div><div>Confianza</div>
        </div>
        {top_body}
      </div>
        </div>
        """
    )

    # -----------------------------------------------------
    # PERFORMANCE REAL
    # -----------------------------------------------------
    picks = track.get(
        "picks",
        pd.DataFrame()
    )

    settled = pd.DataFrame()

    if (
        isinstance(
            picks,
            pd.DataFrame
        )
        and not picks.empty
        and "status" in picks.columns
    ):
        settled = picks[
            picks[
                "status"
            ].isin(
                [
                    "WON",
                    "LOST"
                ]
            )
        ].copy()

    summary = track.get(
        "summary",
        {}
    )

    profit = float(
        summary.get(
            "profit",
            0.0
        )
        or 0.0
    )

    roi = float(
        summary.get(
            "roi",
            0.0
        )
        or 0.0
    )

    profits = (
        pd.to_numeric(
            settled.get(
                "profit",
                pd.Series(
                    dtype=float
                )
            ),
            errors="coerce"
        )
        .fillna(
            0.0
        )
        .tolist()
    )

    polyline = _dashboard_profit_svg(
        profits
    )

    total_picks = (
        len(
            picks
        )
        if isinstance(
            picks,
            pd.DataFrame
        )
        else 0
    )

    conf_hi = 0
    conf_mid = 0
    conf_low = 0

    if (
        isinstance(
            picks,
            pd.DataFrame
        )
        and not picks.empty
        and "match_confidence" in picks.columns
    ):
        conf_values = pd.to_numeric(
            picks[
                "match_confidence"
            ],
            errors="coerce"
        ).dropna()

        conf_hi = int(
            (
                conf_values
                >= 0.75
            ).sum()
        )

        conf_mid = int(
            (
                (
                    conf_values
                    >= 0.70
                )
                &
                (
                    conf_values
                    < 0.75
                )
            ).sum()
        )

        conf_low = max(
            len(
                conf_values
            )
            -
            conf_hi
            -
            conf_mid,
            0
        )

    conf_total = max(
        conf_hi
        + conf_mid
        + conf_low,
        1
    )

    hi_pct = (
        conf_hi
        / conf_total
        * 100
    )
    mid_pct = (
        conf_mid
        / conf_total
        * 100
    )
    low_pct = (
        conf_low
        / conf_total
        * 100
    )

    a_deg = (
        hi_pct
        / 100
        * 360
    )
    b_deg = (
        (
            hi_pct
            + mid_pct
        )
        / 100
        * 360
    )

    right_html = _html_block(
        f"""
        <div class="tep-right-stack">
      <div class="tep-mini-card">
        <div class="tep-mini-title">Evolución del beneficio</div>
        <div class="tep-profit-value">{profit:+.2f} u</div>
        <div class="tep-profit-sub">ROI acumulado {roi:+.1%} · resultados reales del tracker</div>
        <div class="tep-fake-line">
          <svg viewBox="0 0 100 70" preserveAspectRatio="none" aria-hidden="true">
            <polyline fill="none" stroke="#19cec4" stroke-width="2.2" points="{polyline}" />
          </svg>
        </div>
      </div>
      <div class="tep-mini-card">
        <div class="tep-mini-title">Distribución por confianza</div>
        <div class="tep-confidence-wrap">
          <div class="tep-donut" style="--a:{a_deg:.1f}deg;--b:{b_deg:.1f}deg;">
            <div class="tep-donut-center">{total_picks}<span>Picks</span></div>
          </div>
          <div class="tep-legend">
            <div class="tep-leg"><div class="tep-leg-left"><span class="tep-leg-dot"></span>Muy fuerte / Elite</div><b>{hi_pct:.1f}%</b></div>
            <div class="tep-leg"><div class="tep-leg-left"><span class="tep-leg-dot yellow"></span>Fuerte 70–74.9%</div><b>{mid_pct:.1f}%</b></div>
            <div class="tep-leg"><div class="tep-leg-left"><span class="tep-leg-dot red"></span>Otros</div><b>{low_pct:.1f}%</b></div>
          </div>
        </div>
      </div>
        </div>
        """
    )

    dashboard_html = (
        '<div class="tep-dash-grid">'
        + featured_html
        + top_html
        + right_html
        + '</div>'
    )

    st.markdown(
        dashboard_html,
        unsafe_allow_html=True
    )

    # -----------------------------------------------------
    # RENDIMIENTO POR CONFIANZA + PICKS RECIENTES
    # -----------------------------------------------------
    st.markdown(
        '<div class="tep-lower-grid">',
        unsafe_allow_html=True
    )

    by_conf = track.get(
        "by_confidence",
        pd.DataFrame()
    )

    st.markdown(
        _html_block(
            """
            <div class="tep-card">
              <div class="tep-section-subhead">
                <h3>Rendimiento por confianza</h3>
                <span class="tep-note">Track Record real · 1 unidad por pick</span>
              </div>
            """
        ),
        unsafe_allow_html=True
    )

    if (
        isinstance(
            by_conf,
            pd.DataFrame
        )
        and not by_conf.empty
    ):
        st.dataframe(
            by_conf,
            hide_index=True,
            use_container_width=True,
        )
    else:
        # Mientras todavía no haya suficientes picks LIVE liquidados,
        # mostramos el benchmark histórico del Ensemble V4.2 obtenido
        # en el test final intacto. Es referencia de modelo, NO ROI real.
        st.markdown(
            _html_block(
                """
                <div style="
                    margin:.1rem .9rem .65rem;
                    padding:.65rem .8rem;
                    border:1px solid rgba(38,170,232,.16);
                    background:rgba(18,97,151,.10);
                    border-radius:9px;
                    color:#9fc6df;
                    font-size:.69rem;
                ">
                    🧪 <b style="color:#dff5ff;">Benchmark histórico V4.2</b>
                    · Test final intacto. Se sustituirá automáticamente por
                    el Track Record real cuando haya suficientes picks liquidados.
                    <span style="color:#6f8ca2;">No representa ROI real ni garantiza resultados futuros.</span>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        benchmark_conf = pd.DataFrame(
            [
                {
                    "Nivel": "🟢 Fuerte ≥70%",
                    "Acierto histórico": "78.27%",
                    "Cobertura": "33.95%",
                    "Picks test": "7,634",
                },
                {
                    "Nivel": "🔥 Muy fuerte ≥75%",
                    "Acierto histórico": "81.18%",
                    "Cobertura": "20.96%",
                    "Picks test": "4,713",
                },
                {
                    "Nivel": "💎 Elite ≥80%",
                    "Acierto histórico": "85.30%",
                    "Cobertura": "11.07%",
                    "Picks test": "2,489",
                },
            ]
        )

        st.dataframe(
            benchmark_conf,
            hide_index=True,
            use_container_width=True,
        )

    st.markdown(
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        _html_block(
            """
            <div class="tep-card" style="margin-top:.85rem;">
              <div class="tep-section-subhead">
                <h3>Picks recientes</h3>
                <span class="tep-note">Últimos registros del tracker</span>
              </div>
            """
        ),
        unsafe_allow_html=True
    )

    if (
        isinstance(
            picks,
            pd.DataFrame
        )
        and not picks.empty
    ):
        recent_cols = [
            c
            for c in [
                "event_date",
                "tournament",
                "selection",
                "prob_selection",
                "odds",
                "bookmaker",
                "ev",
                "market_quality",
                "status",
                "live_score",
                "profit",
            ]
            if c in picks.columns
        ]

        recent = (
            picks[
                recent_cols
            ]
            .head(
                8
            )
            .copy()
        )

        if "prob_selection" in recent.columns:
            recent[
                "prob_selection"
            ] = pd.to_numeric(
                recent[
                    "prob_selection"
                ],
                errors="coerce"
            ).map(
                lambda x:
                    "-"
                    if pd.isna(
                        x
                    )
                    else f"{x:.1%}"
            )

        if "ev" in recent.columns:
            recent[
                "ev"
            ] = pd.to_numeric(
                recent[
                    "ev"
                ],
                errors="coerce"
            ).map(
                lambda x:
                    "-"
                    if pd.isna(
                        x
                    )
                    else f"{x:+.1%}"
            )

        if "profit" in recent.columns:
            recent[
                "profit"
            ] = pd.to_numeric(
                recent[
                    "profit"
                ],
                errors="coerce"
            ).map(
                lambda x:
                    "-"
                    if pd.isna(
                        x
                    )
                    else f"{x:+.2f} u"
            )

        recent = recent.rename(
            columns={
                "event_date": "Fecha",
                "tournament": "Torneo",
                "selection": "Pick",
                "prob_selection": "Probabilidad",
                "odds": "Cuota",
                "bookmaker": "Casa",
                "ev": "EV",
                "market_quality": "Mercado",
                "status": "Resultado",
                "live_score": "Marcador",
                "profit": "Beneficio",
            }
        )

        st.dataframe(
            recent,
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.markdown(
            '<div class="tep-empty">Todavía no hay picks registrados.</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '</div></div>',
        unsafe_allow_html=True
    )


def render_performance_preview(track):
    picks = track.get("picks", pd.DataFrame())
    if picks.empty or "status" not in picks.columns:
        return
    settled = picks[picks["status"].isin(["WON","LOST"])].copy()
    if settled.empty:
        return
    if "id" in settled.columns:
        settled = settled.sort_values("id")
    settled["profit_num"] = pd.to_numeric(settled["profit"], errors="coerce").fillna(0.0)
    settled["Beneficio acumulado"] = settled["profit_num"].cumsum()
    settled["Pick #"] = range(1, len(settled)+1)
    c1,c2 = st.columns([2,1])
    with c1:
        st.markdown('<div class="tep-section-title">📈 Evolución del beneficio</div>', unsafe_allow_html=True)
        st.line_chart(settled.set_index("Pick #")[["Beneficio acumulado"]], height=220)
    with c2:
        st.markdown('<div class="tep-section-title">🎯 Distribución de resultados</div>', unsafe_allow_html=True)
        wins = int((settled["status"]=="WON").sum())
        losses = int((settled["status"]=="LOST").sum())
        total = max(wins+losses,1)
        st.metric("Acierto", f"{wins/total:.1%}")
        st.metric("Ganados / Perdidos", f"{wins} / {losses}")


aplicar_estilo_premium()
init_db()


@st.cache_data(ttl=600)
def load_data():
    return get_matches()


@st.cache_data(ttl=300)
def load_upcoming_matches():
    return get_upcoming_matches()


@st.cache_data(ttl=900)
def load_tennis_odds():
    result = get_tennis_odds()
    result["_fetched_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    return result


@st.cache_data(ttl=1800, show_spinner=False)
def load_physical_status(player):
    return analyse_physical_status(player)


@st.cache_data(ttl=1800, show_spinner=False)
def resolver_partido_cached(
    jugador_a_api,
    jugador_b_api,
    data_version
):
    df_local = load_data()

    return resolver_partido(
        jugador_a_api,
        jugador_b_api,
        df_local
    )


@st.cache_data(ttl=1800, show_spinner=False)
def predict_match_cached(
    jugador_a,
    jugador_b,
    superficie_modelo,
    recent_window,
    use_elo,
    data_version
):
    df_local = load_data()

    return predict_match_v42(
        df_local,
        jugador_a,
        jugador_b,
        surface=superficie_modelo,
        recent_window=recent_window,
        use_elo=use_elo,
        data_version=data_version
    )



# =========================================================
# PRE-MATCH ODDS LOCK
# =========================================================
#
# Regla:
# - antes del inicio -> guardamos la última cuota válida vista
# - después del inicio -> JAMÁS usamos la cuota actual de la API
# - después del inicio -> sólo usamos el último snapshot pre-match guardado
# - si no existe snapshot pre-match -> no calculamos EV / Top Pick
#
# La base se crea al lado de app.py y persiste entre reinicios.
PREMATCH_ODDS_DB = (
    Path(__file__)
    .resolve()
    .with_name("prematch_odds.db")
)


def _connect_prematch_odds():
    conn = sqlite3.connect(
        PREMATCH_ODDS_DB,
        timeout=10,
    )
    conn.row_factory = sqlite3.Row
    return conn


def _init_prematch_odds_db():
    with _connect_prematch_odds() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prematch_odds (
                match_key TEXT PRIMARY KEY,

                fixture_id TEXT,
                fixture_alt_id TEXT,
                event_date TEXT,
                start_time TEXT,
                tournament TEXT,

                player_a TEXT NOT NULL,
                player_b TEXT NOT NULL,

                odds_a REAL NOT NULL,
                bookmaker_a TEXT,
                odds_b REAL NOT NULL,
                bookmaker_b TEXT,

                market_quality TEXT,
                valid_bookmakers INTEGER,
                outliers_discarded INTEGER,
                exchanges_discarded INTEGER,
                consensus_a REAL,
                consensus_b REAL,

                sport_key TEXT,
                odds_commence_time TEXT,

                captured_at TEXT NOT NULL,
                locked_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_prematch_odds_start
            ON prematch_odds(start_time)
            """
        )


def _odds_name_key(value):
    value = str(
        value
        or ""
    ).strip().lower()

    return " ".join(
        value.split()
    )


def _prematch_match_key(
    partido,
    player_a,
    player_b
):
    # Live Tennis API expone id y match_id.
    # Priorizamos match_id y conservamos el fallback.
    match_id = str(
        partido.get(
            "match_id"
        )
        or ""
    ).strip()

    fixture_id = str(
        partido.get(
            "id"
        )
        or ""
    ).strip()

    if match_id:
        return f"match:{match_id}"

    if fixture_id:
        return f"fixture:{fixture_id}"

    # Fallback determinista para que siga siendo estable
    # aunque un proveedor no entregue IDs.
    players = sorted(
        [
            _odds_name_key(
                player_a
            ),
            _odds_name_key(
                player_b
            ),
        ]
    )

    raw = "|".join(
        [
            str(
                partido.get(
                    "event_date",
                    ""
                )
            ),
            str(
                partido.get(
                    "start_time",
                    ""
                )
            ),
            str(
                partido.get(
                    "tournament",
                    ""
                )
            ),
            players[0],
            players[1],
        ]
    )

    digest = hashlib.sha1(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()

    return f"fallback:{digest}"


def _utc_timestamp(value):
    if value is None:
        return None

    try:
        parsed = pd.to_datetime(
            value,
            utc=True,
            errors="coerce",
        )

        if pd.isna(
            parsed
        ):
            return None

        return parsed

    except Exception:
        return None


def _inicio_mercado(
    partido,
    datos_cuotas=None
):
    """
    Devuelve el comienzo más conservador disponible.

    Si Live Tennis y The Odds API difieren, usamos la hora
    más temprana. Esto evita que una cuota in-play pueda
    colarse como pre-match.
    """
    candidates = []

    fixture_start = _utc_timestamp(
        partido.get(
            "start_time"
        )
    )

    if fixture_start is not None:
        candidates.append(
            fixture_start
        )

    if datos_cuotas:
        odds_start = _utc_timestamp(
            datos_cuotas.get(
                "commence_time"
            )
        )

        if odds_start is not None:
            candidates.append(
                odds_start
            )

    if not candidates:
        return None

    return min(
        candidates
    )


def _partido_ya_empezo(
    partido,
    datos_cuotas=None
):
    """
    Nunca depende de una cuota para decidir si el partido
    está en juego. Usa status + hora prevista.
    """
    status = str(
        partido.get(
            "status",
            ""
        )
        or ""
    ).strip().lower()

    closed_statuses = {
        "live",
        "in_progress",
        "in progress",
        "started",
        "playing",
        "completed",
        "finished",
        "retired",
        "walkover",
        "wo",
        "default",
        "cancelled",
        "canceled",
        "abandoned",
    }

    if status in closed_statuses:
        return True

    inicio = _inicio_mercado(
        partido,
        datos_cuotas
    )

    if inicio is None:
        # Sin hora fiable no afirmamos que haya empezado.
        # El fixture normal de nuestra API sí trae start_time.
        return False

    ahora = pd.Timestamp.now(
        tz="UTC"
    )

    return bool(
        ahora
        >=
        inicio
    )


def _load_prematch_snapshot(
    match_key
):
    _init_prematch_odds_db()

    with _connect_prematch_odds() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM prematch_odds
            WHERE match_key = ?
            """,
            (
                match_key,
            )
        ).fetchone()

    return row


def _snapshot_to_market(
    row,
    *,
    locked
):
    if row is None:
        return None

    return {
        "jugador_a": row[
            "player_a"
        ],
        "jugador_b": row[
            "player_b"
        ],

        "cuota_a": float(
            row[
                "odds_a"
            ]
        ),
        "casa_a": (
            row[
                "bookmaker_a"
            ]
            or ""
        ),

        "cuota_b": float(
            row[
                "odds_b"
            ]
        ),
        "casa_b": (
            row[
                "bookmaker_b"
            ]
            or ""
        ),

        "commence_time": (
            row[
                "odds_commence_time"
            ]
            or row[
                "start_time"
            ]
        ),

        "sport_key": (
            row[
                "sport_key"
            ]
            or ""
        ),

        "calidad_mercado": (
            row[
                "market_quality"
            ]
            or "N/D"
        ),

        "casas_validas": int(
            row[
                "valid_bookmakers"
            ]
            or 0
        ),

        "outliers_descartados": int(
            row[
                "outliers_discarded"
            ]
            or 0
        ),

        "exchanges_descartados": int(
            row[
                "exchanges_discarded"
            ]
            or 0
        ),

        "prob_consenso_a": row[
            "consensus_a"
        ],

        "prob_consenso_b": row[
            "consensus_b"
        ],

        # Metadatos propios.
        "prematch_only": True,
        "prematch_locked": bool(
            locked
        ),
        "prematch_snapshot": True,
        "captured_at": row[
            "captured_at"
        ],
        "locked_at": row[
            "locked_at"
        ],
        "odds_source": (
            "LOCKED_PREMATCH"
            if locked
            else "CACHED_PREMATCH"
        ),
    }


def _save_prematch_snapshot(
    partido,
    player_a,
    player_b,
    datos_cuotas
):
    """
    Sólo debe llamarse ANTES del inicio.
    Cada actualización válida reemplaza a la anterior:
    al final tendremos la última cuota pre-match capturada.
    """
    _init_prematch_odds_db()

    match_key = _prematch_match_key(
        partido,
        player_a,
        player_b
    )

    captured_at = pd.Timestamp.now(
        tz="UTC"
    ).isoformat()

    fixture_id = str(
        partido.get(
            "match_id"
        )
        or ""
    ).strip()

    fixture_alt_id = str(
        partido.get(
            "id"
        )
        or ""
    ).strip()

    with _connect_prematch_odds() as conn:
        conn.execute(
            """
            INSERT INTO prematch_odds (
                match_key,
                fixture_id,
                fixture_alt_id,
                event_date,
                start_time,
                tournament,
                player_a,
                player_b,
                odds_a,
                bookmaker_a,
                odds_b,
                bookmaker_b,
                market_quality,
                valid_bookmakers,
                outliers_discarded,
                exchanges_discarded,
                consensus_a,
                consensus_b,
                sport_key,
                odds_commence_time,
                captured_at,
                locked_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, NULL
            )
            ON CONFLICT(match_key)
            DO UPDATE SET
                fixture_id = excluded.fixture_id,
                fixture_alt_id = excluded.fixture_alt_id,
                event_date = excluded.event_date,
                start_time = excluded.start_time,
                tournament = excluded.tournament,
                player_a = excluded.player_a,
                player_b = excluded.player_b,
                odds_a = excluded.odds_a,
                bookmaker_a = excluded.bookmaker_a,
                odds_b = excluded.odds_b,
                bookmaker_b = excluded.bookmaker_b,
                market_quality = excluded.market_quality,
                valid_bookmakers = excluded.valid_bookmakers,
                outliers_discarded = excluded.outliers_discarded,
                exchanges_discarded = excluded.exchanges_discarded,
                consensus_a = excluded.consensus_a,
                consensus_b = excluded.consensus_b,
                sport_key = excluded.sport_key,
                odds_commence_time = excluded.odds_commence_time,
                captured_at = excluded.captured_at
            """,
            (
                match_key,
                fixture_id,
                fixture_alt_id,
                str(
                    partido.get(
                        "event_date",
                        ""
                    )
                ),
                str(
                    partido.get(
                        "start_time",
                        ""
                    )
                ),
                str(
                    partido.get(
                        "tournament",
                        ""
                    )
                ),
                player_a,
                player_b,
                float(
                    datos_cuotas[
                        "cuota_a"
                    ]
                ),
                str(
                    datos_cuotas.get(
                        "casa_a",
                        ""
                    )
                ),
                float(
                    datos_cuotas[
                        "cuota_b"
                    ]
                ),
                str(
                    datos_cuotas.get(
                        "casa_b",
                        ""
                    )
                ),
                str(
                    datos_cuotas.get(
                        "calidad_mercado",
                        "N/D"
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
                int(
                    datos_cuotas.get(
                        "exchanges_descartados",
                        0
                    )
                    or 0
                ),
                datos_cuotas.get(
                    "prob_consenso_a"
                ),
                datos_cuotas.get(
                    "prob_consenso_b"
                ),
                str(
                    datos_cuotas.get(
                        "sport_key",
                        ""
                    )
                ),
                str(
                    datos_cuotas.get(
                        "commence_time",
                        ""
                    )
                ),
                captured_at,
            )
        )

    return captured_at


def resolver_cuotas_prematch(
    partido,
    player_a,
    player_b,
    datos_cuotas_actuales
):
    """
    Único punto de entrada para cuotas dentro de la app.

    PRE-MATCH:
      guarda/refresca la última cuota válida.

    POST-INICIO:
      ignora por completo datos_cuotas_actuales,
      aunque The Odds API siga devolviendo una línea LIVE.
      Sólo devuelve el snapshot pre-match persistido.
    """
    match_key = _prematch_match_key(
        partido,
        player_a,
        player_b
    )

    empezado = _partido_ya_empezo(
        partido,
        datos_cuotas_actuales
    )

    snapshot = _load_prematch_snapshot(
        match_key
    )

    if empezado:
        if snapshot is None:
            # Regla crítica:
            # nunca sustituimos un snapshot inexistente
            # por una cuota in-play.
            return None

        locked_at = pd.Timestamp.now(
            tz="UTC"
        ).isoformat()

        if not snapshot[
            "locked_at"
        ]:
            with _connect_prematch_odds() as conn:
                conn.execute(
                    """
                    UPDATE prematch_odds
                    SET locked_at = ?
                    WHERE match_key = ?
                      AND locked_at IS NULL
                    """,
                    (
                        locked_at,
                        match_key,
                    )
                )

            snapshot = _load_prematch_snapshot(
                match_key
            )

        return _snapshot_to_market(
            snapshot,
            locked=True
        )

    # Todavía no ha empezado.
    # Si existe una línea válida actual, ésta se convierte
    # en nuestro snapshot pre-match más reciente.
    if datos_cuotas_actuales:
        captured_at = _save_prematch_snapshot(
            partido,
            player_a,
            player_b,
            datos_cuotas_actuales
        )

        result = dict(
            datos_cuotas_actuales
        )

        result.update(
            {
                "prematch_only": True,
                "prematch_locked": False,
                "prematch_snapshot": False,
                "captured_at": captured_at,
                "locked_at": None,
                "odds_source": "CURRENT_PREMATCH",
            }
        )

        return result

    # Si temporalmente desaparece el mercado antes del inicio,
    # podemos seguir enseñando el último snapshot válido,
    # sin convertirlo en una cuota LIVE.
    if snapshot is not None:
        return _snapshot_to_market(
            snapshot,
            locked=False
        )

    return None


def normalizar_superficie(superficie):
    if not superficie:
        return None

    superficie = str(superficie).strip().lower()

    mapa = {
        "hard": "Hard",
        "clay": "Clay",
        "grass": "Grass"
    }

    return mapa.get(superficie)


def formatear_hora_utc(start_time):
    if not start_time:
        return ""

    try:
        fecha = pd.to_datetime(start_time, utc=True)
        return fecha.strftime("%H:%M UTC")
    except Exception:
        return str(start_time)


def calcular_value_score(
    ev,
    pick_probability,
    market_quality,
    valid_bookmakers
):
    """
    Score 0-100 para PRIORIZAR picks, no para estimar
    una probabilidad de ganar.

    45 puntos -> EV
    25 puntos -> confianza global del partido
    20 puntos -> calidad del mercado
    10 puntos -> número de casas válidas
    """
    ev = max(
        float(ev or 0.0),
        0.0
    )

    pick_probability = max(
        min(
            float(
                pick_probability
                or 0.0
            ),
            1.0
        ),
        0.0
    )

    valid_bookmakers = max(
        int(
            valid_bookmakers
            or 0
        ),
        0
    )

    ev_component = (
        min(
            ev,
            0.25
        )
        / 0.25
        * 45.0
    )

    confidence_component = (
        min(
            max(
                (
                    pick_probability
                    - 0.60
                )
                / 0.25,
                0.0
            ),
            1.0
        )
        * 25.0
    )

    quality_points = {
        "Alta": 20.0,
        "Media": 13.0,
        "Baja": 6.0,
    }.get(
        str(
            market_quality
            or ""
        ).strip(),
        0.0
    )

    books_component = (
        min(
            valid_bookmakers,
            8
        )
        / 8.0
        * 10.0
    )

    return round(
        min(
            ev_component
            + confidence_component
            + quality_points
            + books_component,
            100.0
        ),
        1
    )


def categoria_value_score(score):
    score = float(
        score
        or 0.0
    )

    if score >= 80:
        return "💎 ELITE VALUE"

    if score >= 65:
        return "🔥 VALUE FUERTE"

    if score >= 50:
        return "🟢 VALUE"

    return "🟡 VALUE"


def generar_predicciones_proximos(
    df,
    partidos,
    indice_cuotas=None,
    recent_window=25,
    use_elo=True,
    data_version=""
):
    filas = []
    no_resueltos = []

    for partido in partidos:
        jugador_a_api = partido.get("player1")
        jugador_b_api = partido.get("player2")

        try:
            resolucion = resolver_partido_cached(
                jugador_a_api,
                jugador_b_api,
                data_version
            )
        except Exception as exc:
            no_resueltos.append(
                {
                    "partido": f"{jugador_a_api} vs {jugador_b_api}",
                    "motivo": f"Error del resolver: {exc}"
                }
            )
            continue

        if not resolucion.get("ok"):
            no_resueltos.append(
                {
                    "partido": f"{jugador_a_api} vs {jugador_b_api}",
                    "motivo": (
                        f"{jugador_a_api} → {resolucion.get('jugador_a')} | "
                        f"{jugador_b_api} → {resolucion.get('jugador_b')}"
                    )
                }
            )
            continue

        jugador_a = resolucion["jugador_a"]
        jugador_b = resolucion["jugador_b"]

        superficie_modelo = normalizar_superficie(
            partido.get("surface")
        )

        try:
            prediccion = predict_match_cached(
                jugador_a,
                jugador_b,
                superficie_modelo,
                recent_window,
                use_elo,
                data_version
            )
        except Exception as exc:
            no_resueltos.append(
                {
                    "partido": f"{jugador_a_api} vs {jugador_b_api}",
                    "motivo": f"Error del modelo: {exc}"
                }
            )
            continue

        if not prediccion.get("ok"):
            no_resueltos.append(
                {
                    "partido": f"{jugador_a_api} vs {jugador_b_api}",
                    "motivo": prediccion.get(
                        "message",
                        "El modelo no pudo generar predicción."
                    )
                }
            )
            continue

        pa = float(prediccion["prob_a"])
        pb = float(prediccion["prob_b"])

        favorito = jugador_a_api if pa >= pb else jugador_b_api
        prob_favorito = max(pa, pb)

        datos_cuotas_actuales = None

        if indice_cuotas:
            datos_cuotas_actuales = buscar_mejores_cuotas(
                indice_cuotas,
                jugador_a,
                jugador_b
            )

        # Protección PRE-MATCH:
        # después del inicio ignoramos las cuotas actuales de la API
        # y recuperamos únicamente el último snapshot guardado.
        datos_cuotas = resolver_cuotas_prematch(
            partido,
            jugador_a,
            jugador_b,
            datos_cuotas_actuales
        )

        partido_iniciado = _partido_ya_empezo(
            partido,
            datos_cuotas_actuales
        )

        cuota_a = None
        cuota_b = None
        casa_a = ""
        casa_b = ""
        ev_a = None
        ev_b = None

        pick_auto = {
            "qualifies": False,
            "label": "-",
            "reason": "SIN_MERCADO",
        }

        if datos_cuotas:
            cuota_a = float(datos_cuotas["cuota_a"])
            cuota_b = float(datos_cuotas["cuota_b"])
            casa_a = datos_cuotas["casa_a"]
            casa_b = datos_cuotas["casa_b"]

            ev_a = (pa * cuota_a) - 1
            ev_b = (pb * cuota_b) - 1

            if not partido_iniciado:
                pick_auto = evaluar_pick_automatico(
                    partido,
                    jugador_a,
                    jugador_b,
                    pa,
                    pb,
                    datos_cuotas,
                    prediccion,
                    df
                )
            else:
                # Puede seguir mostrándose la cuota pre-match congelada,
                # pero un partido ya iniciado NUNCA puede crear un pick nuevo.
                pick_auto = {
                    "qualifies": False,
                    "inserted": False,
                    "label": "🔒 Cuota PRE-MATCH congelada",
                    "reason": "PARTIDO_INICIADO",
                }

        pick_selection = (
            pick_auto.get(
                "selection"
            )
            if pick_auto.get(
                "qualifies",
                False
            )
            else None
        )

        if pick_selection == jugador_a:
            pick_probability = pa
        elif pick_selection == jugador_b:
            pick_probability = pb
        else:
            pick_probability = None

        pick_ev = (
            float(
                pick_auto.get(
                    "ev"
                )
            )
            if pick_auto.get(
                "qualifies",
                False
            )
            else None
        )

        market_quality = (
            datos_cuotas.get(
                "calidad_mercado",
                "N/D"
            )
            if datos_cuotas
            else "N/D"
        )

        valid_bookmakers = (
            int(
                datos_cuotas.get(
                    "casas_validas",
                    0
                )
                or 0
            )
            if datos_cuotas
            else 0
        )

        value_score = (
            calcular_value_score(
                pick_ev,
                pick_probability,
                market_quality,
                valid_bookmakers
            )
            if pick_ev is not None
            else 0.0
        )

        filas.append(
            {
                "Fecha": partido.get("event_date", ""),
                "Hora": formatear_hora_utc(
                    partido.get("start_time")
                ),
                "Torneo": partido.get(
                    "tournament",
                    "Desconocido"
                ),
                "Tour": str(
                    partido.get("tour", "")
                ).upper(),
                "Superficie": superficie_modelo or "Todas",
                "Jugador 1": jugador_a_api,
                "Prob. J1": f"{pa * 100:.1f}%",
                "Mejor cuota J1": (
                    (
                        "🔒 "
                        if (
                            datos_cuotas
                            and datos_cuotas.get(
                                "prematch_locked",
                                False
                            )
                        )
                        else ""
                    )
                    + f"{cuota_a:.2f}"
                    if cuota_a is not None
                    else "Esperando mercado"
                ),
                "Casa J1": casa_a or "-",
                "EV J1": (
                    f"{ev_a * 100:+.1f}%"
                    if ev_a is not None
                    else "-"
                ),
                "Jugador 2": jugador_b_api,
                "Prob. J2": f"{pb * 100:.1f}%",
                "Mejor cuota J2": (
                    (
                        "🔒 "
                        if (
                            datos_cuotas
                            and datos_cuotas.get(
                                "prematch_locked",
                                False
                            )
                        )
                        else ""
                    )
                    + f"{cuota_b:.2f}"
                    if cuota_b is not None
                    else "Esperando mercado"
                ),
                "Casa J2": casa_b or "-",
                "EV J2": (
                    f"{ev_b * 100:+.1f}%"
                    if ev_b is not None
                    else "-"
                ),
                "Favorito": favorito,
                "Prob. favorito": f"{prob_favorito * 100:.1f}%",
                "Confianza": prediccion.get(
                    "confidence_label",
                    "Sin dato"
                ),
                "Pick automático": (
                    pick_auto.get(
                        "label",
                        "-"
                    )
                ),

                # Campos internos para TOP PICKS.
                # Se eliminan de la tabla general antes
                # de mostrarla.
                "_player1_full": jugador_a,
                "_player2_full": jugador_b,
                "_player1_live_id": partido.get(
                    "player1_id"
                ),
                "_player2_live_id": partido.get(
                    "player2_id"
                ),

                "_odds_prematch_locked": bool(
                    datos_cuotas.get(
                        "prematch_locked",
                        False
                    )
                    if datos_cuotas
                    else False
                ),
                "_odds_captured_at": (
                    datos_cuotas.get(
                        "captured_at"
                    )
                    if datos_cuotas
                    else None
                ),
                "_odds_source": (
                    datos_cuotas.get(
                        "odds_source",
                        "-"
                    )
                    if datos_cuotas
                    else "-"
                ),

                "_pick_qualifies": bool(
                    pick_auto.get(
                        "qualifies",
                        False
                    )
                ),
                "_pick_selection": (
                    pick_selection
                ),
                "_pick_probability": (
                    pick_probability
                ),
                "_pick_odds": (
                    float(
                        pick_auto.get(
                            "odds"
                        )
                    )
                    if pick_auto.get(
                        "qualifies",
                        False
                    )
                    else None
                ),
                "_pick_ev": (
                    pick_ev
                ),
                "_pick_reason": (
                    pick_auto.get(
                        "reason",
                        "SIN_CLASIFICAR"
                    )
                ),
                "_candidate_selection": (
                    pick_auto.get(
                        "candidate_selection"
                    )
                ),
                "_candidate_probability": (
                    pick_auto.get(
                        "candidate_probability"
                    )
                ),
                "_candidate_odds": (
                    pick_auto.get(
                        "candidate_odds"
                    )
                ),
                "_candidate_ev": (
                    pick_auto.get(
                        "candidate_ev"
                    )
                ),
                "_best_ev_raw": (
                    max(
                        ev_a,
                        ev_b
                    )
                    if datos_cuotas
                    else None
                ),
                "_market_available": (
                    bool(
                        datos_cuotas
                    )
                ),
                "_match_confidence": (
                    prob_favorito
                ),
                "_market_quality": (
                    market_quality
                ),
                "_valid_bookmakers": (
                    valid_bookmakers
                ),
                "_value_score": (
                    value_score
                ),
                "_value_category": (
                    categoria_value_score(
                        value_score
                    )
                    if pick_auto.get(
                        "qualifies",
                        False
                    )
                    else "-"
                ),
                "_pick_bookmaker": (
                    casa_a
                    if pick_selection == jugador_a
                    else (
                        casa_b
                        if pick_selection == jugador_b
                        else ""
                    )
                )
            }
        )

    return filas, no_resueltos



def _cargar_predicciones_para_paginas(df, ventana, usar_elo, data_version):
    proximos = load_upcoming_matches()
    odds_result = load_tennis_odds()

    indice_cuotas = (
        construir_indice_cuotas(
            odds_result.get("events", [])
        )
        if odds_result.get("ok")
        else {}
    )

    filas, no_resueltos = generar_predicciones_proximos(
        df,
        proximos,
        indice_cuotas,
        recent_window=ventana,
        use_elo=usar_elo,
        data_version=data_version,
    )

    return proximos, odds_result, filas, no_resueltos


def render_top_picks_page(df, ventana, usar_elo, data_version):
    st.markdown('<div class="tep-section-title">🏆 Top Picks del Día</div>', unsafe_allow_html=True)
    st.caption(
        "Top Pick = probabilidad de LA SELECCIÓN ≥60%, cuota 1.50–3.00, EV ≥+5% y mercado validado. "
        "🔒 Las cuotas son exclusivamente PRE-MATCH: al comenzar el partido se congela "
        "el último snapshot válido y nunca se usan cuotas LIVE. "
        "El Value Score ordena oportunidades; no es una probabilidad de ganar."
    )

    c1, c2, c3 = st.columns([1,1,3])
    with c1:
        if st.button("🔄 REFRESCAR PICKS", type="primary", use_container_width=True, key="top_refresh"):
            load_upcoming_matches.clear()
            load_tennis_odds.clear()
            resolver_partido_cached.clear()
            predict_match_cached.clear()
    with c2:
        if st.button("💰 REFRESCAR CUOTAS", use_container_width=True, key="top_odds_refresh"):
            load_tennis_odds.clear()

    try:
        with st.spinner("Calculando Top Picks con V4.2 y cuotas actuales..."):
            proximos, odds_result, filas, no_resueltos = _cargar_predicciones_para_paginas(
                df, ventana, usar_elo, data_version
            )

        if not filas:
            st.info("No hay predicciones disponibles en este momento.")
            return

        raw = pd.DataFrame(filas)
        fechas = pd.to_datetime(raw["Fecha"], errors="coerce")
        hoy = pd.Timestamp.now(tz="Europe/Madrid").date()
        mask = (fechas.dt.date == hoy) & (raw["_pick_qualifies"] == True)
        top = raw.loc[mask].copy().sort_values("_value_score", ascending=False)

        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Partidos analizados", len(raw))
        m2.metric("Mercados válidos", int(raw["_market_available"].sum()))
        m3.metric("Picks del día", len(top))
        m4.metric("Cuotas disponibles", len(odds_result.get("events", [])) if odds_result.get("ok") else 0)

        if top.empty:
            st.info("Hoy no hay picks que pasen todos los filtros de value.")
        else:
            top["Ranking"] = range(1, len(top)+1)
            top["Partido"] = top["Jugador 1"] + " vs " + top["Jugador 2"]
            top["Pick"] = top["_pick_selection"]
            top["Prob. modelo"] = top["_pick_probability"].map(lambda x: f"{float(x):.1%}")
            top["Confianza"] = top["_match_confidence"].map(lambda x: f"{float(x):.1%}")
            top["Cuota"] = top["_pick_odds"].map(lambda x: f"{float(x):.2f}")
            top["EV"] = top["_pick_ev"].map(lambda x: f"{float(x):+.1%}")
            top["Score"] = top["_value_score"].map(lambda x: f"{float(x):.1f}/100")
            top["Nivel"] = top["_value_category"]
            top["Mercado"] = top["_market_quality"]
            top["Casas"] = top["_valid_bookmakers"]
            top["Casa"] = top["_pick_bookmaker"]

            best = top.iloc[0]
            b1,b2,b3,b4 = st.columns(4)
            b1.metric("🥇 Mejor pick", str(best["_pick_selection"]))
            b2.metric("Cuota", f"{float(best['_pick_odds']):.2f}")
            b3.metric("EV", f"{float(best['_pick_ev']):+.1%}")
            b4.metric("Value Score", f"{float(best['_value_score']):.1f}/100")

            st.dataframe(
                top[[
                    "Ranking","Nivel","Hora","Torneo","Partido","Pick","Prob. modelo",
                    "Confianza","Cuota","Casa","EV","Mercado","Casas","Score"
                ]].head(10),
                hide_index=True,
                use_container_width=True,
            )

        with st.expander("🧪 Diagnóstico del motor · embudo de Top Picks"):
            reason_labels = {
                "TOP_PICK": "🏆 Top Pick",
                "SIN_MERCADO": "❌ Sin mercado pre-match",
                "PARTIDO_INICIADO": "🔒 Partido iniciado",
                "CUOTA_FUERA_RANGO": "↔️ Cuota fuera de 1.50–3.00",
                "PROB_SELECCION_BAJA": "📉 Prob. selección <60%",
                "EV_INSUFICIENTE": "🧮 EV < +5%",
                "POCAS_CASAS": "🏦 Menos de 2 casas",
                "SIN_CLASIFICAR": "❔ Sin clasificar",
            }

            today_mask = (
                pd.to_datetime(
                    raw["Fecha"],
                    errors="coerce"
                ).dt.date
                ==
                hoy
            )

            diag_today = raw.loc[
                today_mask
            ].copy()

            total_today = len(
                diag_today
            )

            market_today = int(
                diag_today[
                    "_market_available"
                ].sum()
            ) if total_today else 0

            final_today = int(
                diag_today[
                    "_pick_qualifies"
                ].sum()
            ) if total_today else 0

            f1, f2, f3 = st.columns(3)
            f1.metric("Partidos de hoy", total_today)
            f2.metric("Con mercado pre-match", market_today)
            f3.metric("Top Picks finales", final_today)

            if total_today:
                reason_counts = (
                    diag_today[
                        "_pick_reason"
                    ]
                    .fillna(
                        "SIN_CLASIFICAR"
                    )
                    .value_counts()
                )

                funnel_rows = []

                for reason, count in reason_counts.items():
                    funnel_rows.append(
                        {
                            "Resultado": reason_labels.get(
                                str(reason),
                                str(reason)
                            ),
                            "Partidos": int(count),
                            "% de hoy": (
                                f"{int(count) / total_today:.1%}"
                                if total_today
                                else "-"
                            ),
                        }
                    )

                st.dataframe(
                    pd.DataFrame(
                        funnel_rows
                    ),
                    hide_index=True,
                    use_container_width=True,
                )

            diag = diag_today[[
                "Fecha","Hora","Jugador 1","Jugador 2",
                "_candidate_selection",
                "_candidate_probability",
                "_candidate_odds",
                "_candidate_ev",
                "_pick_reason",
                "_market_quality",
                "_valid_bookmakers",
                "_pick_qualifies",
            ]].copy()

            if not diag.empty:
                diag["Partido"] = (
                    diag["Jugador 1"]
                    + " vs "
                    + diag["Jugador 2"]
                )

                diag["Candidato"] = diag[
                    "_candidate_selection"
                ].fillna("-")

                diag["Prob. candidato"] = diag[
                    "_candidate_probability"
                ].map(
                    lambda x: "-"
                    if pd.isna(x)
                    else f"{float(x):.1%}"
                )

                diag["Cuota candidato"] = diag[
                    "_candidate_odds"
                ].map(
                    lambda x: "-"
                    if pd.isna(x)
                    else f"{float(x):.2f}"
                )

                diag["EV candidato"] = diag[
                    "_candidate_ev"
                ].map(
                    lambda x: "-"
                    if pd.isna(x)
                    else f"{float(x):+.1%}"
                )

                diag["Motivo"] = diag[
                    "_pick_reason"
                ].map(
                    lambda x: reason_labels.get(
                        str(x),
                        str(x)
                    )
                )

                diag["Top Pick"] = diag[
                    "_pick_qualifies"
                ].map(
                    lambda x: "🏆"
                    if x
                    else "-"
                )

                st.dataframe(
                    diag[[
                        "Hora",
                        "Partido",
                        "Candidato",
                        "Prob. candidato",
                        "Cuota candidato",
                        "EV candidato",
                        "Motivo",
                        "_market_quality",
                        "_valid_bookmakers",
                        "Top Pick",
                    ]].rename(
                        columns={
                            "_market_quality": "Calidad mercado",
                            "_valid_bookmakers": "Casas",
                        }
                    ),
                    hide_index=True,
                    use_container_width=True,
                )

    except Exception as exc:
        st.error("No se pudieron calcular los Top Picks.")
        st.caption(str(exc))


def render_rendimiento_page(df):
    st.markdown('<div class="tep-section-title">📈 Rendimiento / Track Record</div>', unsafe_allow_html=True)

    # Liquidación conservadora antes de mostrar cifras.
    try:
        resolver_picks_live()
        resolver_picks_pendientes(df)
    except Exception:
        pass

    track = get_track_record()
    resumen = track.get("summary", {})
    r1,r2,r3,r4,r5 = st.columns(5)
    r1.metric("Picks", int(resumen.get("total",0)))
    r2.metric("Pendientes", int(resumen.get("pending",0)))
    r3.metric("Hit rate", f"{float(resumen.get('hit_rate',0)):.1%}" if resumen.get("settled") else "-")
    r4.metric("Beneficio", f"{float(resumen.get('profit',0)):+.2f} u")
    r5.metric("ROI", f"{float(resumen.get('roi',0)):+.1%}" if resumen.get("settled") else "-")

    render_performance_preview(track)

    by_conf = track.get("by_confidence", pd.DataFrame())
    if isinstance(by_conf, pd.DataFrame) and not by_conf.empty:
        st.markdown('<div class="tep-section-title">🎯 Rendimiento por confianza</div>', unsafe_allow_html=True)
        st.dataframe(by_conf, hide_index=True, use_container_width=True)

    picks = track.get("picks", pd.DataFrame())
    if isinstance(picks, pd.DataFrame) and not picks.empty:
        cols = [c for c in [
            "event_date","tournament","selection","prob_selection","odds","bookmaker","ev",
            "market_quality","valid_bookmakers","status","live_status","live_score",
            "result_winner","result_source","verification_note","profit"
        ] if c in picks.columns]
        tabla = picks[cols].head(50).copy()
        for c in ["prob_selection","ev"]:
            if c in tabla.columns:
                tabla[c] = pd.to_numeric(tabla[c], errors="coerce")
        if "prob_selection" in tabla.columns:
            tabla["prob_selection"] = tabla["prob_selection"].map(lambda x: "-" if pd.isna(x) else f"{x:.1%}")
        if "ev" in tabla.columns:
            tabla["ev"] = tabla["ev"].map(lambda x: "-" if pd.isna(x) else f"{x:+.1%}")
        if "profit" in tabla.columns:
            tabla["profit"] = tabla["profit"].map(lambda x: "-" if pd.isna(x) else f"{float(x):+.2f} u")
        tabla = tabla.rename(columns={
            "event_date":"Fecha","tournament":"Torneo","selection":"Pick","prob_selection":"Prob. modelo",
            "odds":"Cuota","bookmaker":"Casa","ev":"EV","market_quality":"Mercado","valid_bookmakers":"Casas válidas",
            "status":"Estado","live_status":"Estado live","live_score":"Marcador","result_winner":"Ganador real",
            "result_source":"Fuente","verification_note":"Verificación","profit":"Beneficio"
        })
        st.markdown('<div class="tep-section-title">🧾 Historial de picks</div>', unsafe_allow_html=True)
        st.dataframe(tabla, hide_index=True, use_container_width=True)
    else:
        st.info("Todavía no hay picks registrados.")


def render_resultados_live_page(df):
    st.markdown('<div class="tep-section-title">⚡ Resultados Live</div>', unsafe_allow_html=True)
    st.caption("El tracker sólo liquida un pick después de verificar partido, jugadores, horario, estado y formato de sets.")

    c1,c2 = st.columns([1,3])
    with c1:
        if st.button("⚡ COMPROBAR AHORA", type="primary", use_container_width=True, key="live_page_force"):
            info = resolver_picks_live(force=True, max_checks=20)
            st.session_state["live_page_info"] = info
    info = st.session_state.get("live_page_info")
    if info:
        a,b,c,d = st.columns(4)
        a.metric("Consultados", int(info.get("checked",0)))
        b.metric("Liquidados", int(info.get("resolved",0)))
        c.metric("VOID", int(info.get("voided",0)))
        d.metric("Verificación fallida", int(info.get("verification_failed",0)))
        if info.get("rate_limited"):
            st.warning("La API ha alcanzado temporalmente su límite.")

    track = get_track_record()
    picks = track.get("picks", pd.DataFrame())
    if picks.empty:
        st.info("No hay picks registrados.")
        return

    pending = picks[picks["status"] == "PENDING"].copy() if "status" in picks.columns else pd.DataFrame()
    st.metric("Picks pendientes", len(pending))
    if pending.empty:
        st.success("No hay picks pendientes de liquidar.")
        return

    cols = [c for c in [
        "event_date","tournament","player_a","player_b","selection","odds","status","live_status",
        "live_score","api_player1","api_player2","api_scheduled_time","verification_note","last_live_check_at"
    ] if c in pending.columns]
    st.dataframe(
        pending[cols].head(50).rename(columns={
            "event_date":"Fecha","tournament":"Torneo","player_a":"Jugador A","player_b":"Jugador B",
            "selection":"Pick","odds":"Cuota","status":"Estado tracker","live_status":"Estado API",
            "live_score":"Marcador API","api_player1":"API jugador 1","api_player2":"API jugador 2",
            "api_scheduled_time":"Hora API","verification_note":"Verificación","last_live_check_at":"Última comprobación"
        }),
        hide_index=True,
        use_container_width=True,
    )


# =========================================================
# V13.5.2 · NAVEGACIÓN SEGURA
# El sidebar sigue existiendo, pero además tenemos un selector
# superior que evita quedarse bloqueado si Safari/Chrome ocultan
# el botón nativo de Streamlit.
# =========================================================
NAV_OPTIONS = [
    "⌂  Dashboard",
    "▣  Próximos partidos",
    "☆  Top Picks",
    "▥  Rendimiento",
    "◉  Resultados live",
    "◈  Modelo / Analizador",
]

if "tep_nav" not in st.session_state:
    st.session_state["tep_nav"] = NAV_OPTIONS[0]

if "tep_nav_mobile_safe" not in st.session_state:
    st.session_state["tep_nav_mobile_safe"] = st.session_state["tep_nav"]


def _sync_nav_mobile_safe():
    st.session_state["tep_nav"] = st.session_state["tep_nav_mobile_safe"]


def _sync_nav_sidebar_safe():
    st.session_state["tep_nav_mobile_safe"] = st.session_state["tep_nav"]


st.selectbox(
    "☰  MENÚ",
    NAV_OPTIONS,
    key="tep_nav_mobile_safe",
    on_change=_sync_nav_mobile_safe,
    help="Menú de navegación siempre disponible aunque el sidebar esté cerrado.",
)

pagina_actual = st.session_state["tep_nav"]


with st.sidebar:
    st.markdown(
        """
        <div class="tep-brand">
          <div class="tep-logo">🎾</div>
          <div><div class="tep-brand-title">Tennis Edge <span>Pro</span></div><div class="tep-brand-sub">Prediction & Value Engine</div></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.radio(
        "Navegación",
        NAV_OPTIONS,
        label_visibility="collapsed",
        key="tep_nav",
        on_change=_sync_nav_sidebar_safe,
    )

    pagina_actual = st.session_state["tep_nav"]
    last = get_last_update() or "Sin actualizar"

    if st.button(
        "🔄 ACTUALIZAR DATOS",
        use_container_width=True
    ):
        with st.spinner(
            "Descargando y consolidando partidos..."
        ):
            msg = update_database()

        load_data.clear()
        load_upcoming_matches.clear()
        resolver_partido_cached.clear()
        predict_match_cached.clear()
        clear_v42_state_cache()

        try:
            live_update = resolver_picks_live(
                force=True,
                max_checks=20
            )

            df_actualizado_tracker = get_matches()

            liquidados_hist = resolver_picks_pendientes(
                df_actualizado_tracker
            )

            liquidados = (
                int(
                    live_update.get(
                        "resolved",
                        0
                    )
                )
                + int(
                    liquidados_hist
                )
            )
        except Exception:
            liquidados = 0

        st.success(msg)

        if liquidados:
            st.success(
                f"📈 {liquidados} picks pendientes "
                "han sido liquidados automáticamente."
            )

    superficie = st.selectbox(
        "Superficie del partido",
        ["Hard", "Clay", "Grass", "Todas"]
    )

    ventana = 25
    usar_elo = True

    st.caption(
        "🧠 Ensemble V4.2: ventana fija de 25 partidos "
        "y Elo general + Elo por superficie."
    )

    st.caption(
        "El modelo de producción se mantiene fijo. "
        "El reentrenamiento se hace fuera de la app "
        "con el optimizador V4.2."
    )

    estado_v42 = get_v42_status()

    if estado_v42.get("ok"):
        st.success(
            "✅ Ensemble V4.2 activo"
        )
        st.caption(
            f"{estado_v42.get('alpha_v42', 0):.0%} V4.2 + "
            f"{estado_v42.get('alpha_v1', 0):.0%} V1 · "
            f"{estado_v42.get('features', 0)} features"
        )
    else:
        st.warning(
            "⚠️ V4.2 no encontrado: usando V1 de respaldo."
        )


    st.markdown(
        f"""
        <div class="tep-sidebar-card">
          <div style="font-size:.72rem;color:#8297aa;">MODELO</div>
          <div style="margin-top:.25rem;font-weight:800;"><span class="tep-dot"></span>{'Activo' if estado_v42.get('ok') else 'Backup'}</div>
          <div style="font-size:.72rem;color:#8297aa;margin-top:.75rem;">Última actualización</div>
          <div style="font-size:.85rem;color:#eaf4fa;margin-top:.15rem;">{last}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

df = load_data()

if df.empty:
    st.warning(
        "La base de datos está vacía. "
        "Pulsa ACTUALIZAR DATOS."
    )
    st.stop()


data_version = (
    f"{get_last_update() or 'sin_actualizar'}:"
    f"{len(df)}"
)

track_dashboard = get_track_record()
estado_v42_dashboard = get_v42_status()
last_dashboard = get_last_update() or "Sin actualizar"

if pagina_actual == "⌂  Dashboard":
    render_dashboard_premium_v13(
        df,
        estado_v42_dashboard,
        track_dashboard,
        last_dashboard,
        ventana,
        usar_elo,
        data_version,
    )

# =====================================================
# PRÓXIMOS PARTIDOS ATP + CHALLENGER
# AUTO-REFRESH DE CUOTAS
# =====================================================

if hasattr(st, "fragment"):
    _decorador_proximos = st.fragment(run_every=3600)
else:
    def _decorador_proximos(func):
        return func


@_decorador_proximos
def render_proximos_partidos(df, ventana, usar_elo):
    # =====================================================
    # PRÓXIMOS PARTIDOS ATP + CHALLENGER
    # =====================================================

    st.markdown('<div id="proximos-partidos"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tep-section-title">📅 Próximos partidos ATP + Challenger</div>', unsafe_allow_html=True)

    col_upcoming_1, col_upcoming_2, col_upcoming_3, col_upcoming_4 = st.columns(
        [1, 1, 1, 2]
    )

    with col_upcoming_1:
        if st.button(
            "📡 CARGAR PARTIDOS",
            type="primary",
            use_container_width=True,
            key="cargar_partidos_auto"
        ):
            st.session_state["mostrar_proximos"] = True
            load_upcoming_matches.clear()

    with col_upcoming_2:
        if st.button(
            "🔄 ACTUALIZAR CUOTAS",
            use_container_width=True,
            key="actualizar_cuotas_auto"
        ):
            st.session_state["mostrar_proximos"] = True
            load_tennis_odds.clear()

    with col_upcoming_3:
        if st.button(
            "⚡ RESULTADOS LIVE",
            use_container_width=True,
            key="actualizar_resultados_live"
        ):
            live_manual = resolver_picks_live(
                force=True,
                max_checks=20
            )

            st.session_state[
                "ultimo_live_manual"
            ] = live_manual

    with col_upcoming_4:
        st.caption(
            "Cuotas: snapshot PRE-MATCH cada 15 min. "
            "Resultados: Live Tennis API comprueba picks "
            "pendientes automáticamente y el botón ⚡ permite "
            "forzar una comprobación inmediata."
        )


    if st.session_state.get("mostrar_proximos", False):
        try:
            with st.spinner(
                "Cargando próximos partidos y calculando predicciones..."
            ):
                proximos = load_upcoming_matches()

                odds_result = load_tennis_odds()

                if odds_result.get("ok"):
                    indice_cuotas = construir_indice_cuotas(
                        odds_result.get("events", [])
                    )
                else:
                    indice_cuotas = {}

                filas_proximos, no_resueltos = (
                    generar_predicciones_proximos(
                        df,
                        proximos,
                        indice_cuotas,
                        recent_window=ventana,
                        use_elo=usar_elo,
                        data_version=data_version
                    )
                )

            if not proximos:
                st.warning(
                    "La API no ha devuelto próximos partidos "
                    "ATP o Challenger."
                )

            elif not filas_proximos:
                st.warning(
                    "Se recibieron partidos, pero el modelo "
                    "no pudo generar predicciones."
                )

            else:
                st.success(
                    f"✅ {len(filas_proximos)} de "
                    f"{len(proximos)} partidos predichos."
                )

                if odds_result.get("ok"):
                    fecha_odds = odds_result.get("_fetched_at", "")

                    try:
                        hora_odds = pd.to_datetime(
                            fecha_odds,
                            utc=True
                        ).strftime("%H:%M UTC")
                    except Exception:
                        hora_odds = "N/D"

                    st.caption(
                        "💰 Cuotas automáticas activas · "
                        f"Eventos con cuotas: "
                        f"{len(odds_result.get('events', []))} · "
                        f"Créditos restantes: "
                        f"{odds_result.get('requests_remaining', 'N/D')} · "
                        f"Última consulta: {hora_odds} · "
                        "Auto-refresh: 60 min"
                    )
                else:
                    st.warning(
                        "No se pudieron cargar las cuotas automáticas. "
                        "Las predicciones siguen disponibles."
                    )
                    st.caption(
                        odds_result.get("message", "")
                    )

                tabla_proximos_raw = pd.DataFrame(
                    filas_proximos
                )

                # =========================================
                # TOP PICKS DEL DÍA
                # =========================================

                st.markdown('<div id="top-picks"></div>', unsafe_allow_html=True)
                st.markdown('<div class="tep-section-title">🏆 Top Picks del Día</div>', unsafe_allow_html=True)

                hoy = pd.Timestamp.now(tz="Europe/Madrid").date()

                fechas_parseadas = pd.to_datetime(
                    tabla_proximos_raw[
                        "Fecha"
                    ],
                    errors="coerce"
                )

                mask_hoy = (
                    fechas_parseadas.dt.date
                    ==
                    hoy
                )

                mask_value = (
                    tabla_proximos_raw[
                        "_pick_qualifies"
                    ]
                    ==
                    True
                )

                top_hoy = (
                    tabla_proximos_raw[
                        mask_hoy
                        &
                        mask_value
                    ]
                    .copy()
                    .sort_values(
                        "_value_score",
                        ascending=False
                    )
                )

                with st.expander(
                    "🧪 Comprobar motor de Top Picks",
                    expanded=False
                ):
                    total_cargados = len(
                        tabla_proximos_raw
                    )

                    total_hoy = int(
                        mask_hoy.sum()
                    )

                    mercados_validos = int(
                        tabla_proximos_raw[
                            "_market_available"
                        ].sum()
                    )

                    confianza_70 = int(
                        (
                            tabla_proximos_raw[
                                "_match_confidence"
                            ]
                            >= 0.70
                        ).sum()
                    )

                    ev_5 = int(
                        (
                            tabla_proximos_raw[
                                "_best_ev_raw"
                            ]
                            .fillna(
                                -999.0
                            )
                            >= 0.05
                        ).sum()
                    )

                    top_count = int(
                        (
                            mask_hoy
                            &
                            mask_value
                        ).sum()
                    )

                    d1, d2, d3, d4, d5 = st.columns(5)

                    d1.metric(
                        "Partidos cargados",
                        total_cargados
                    )

                    d2.metric(
                        "Partidos de hoy",
                        total_hoy
                    )

                    d3.metric(
                        "Mercado válido",
                        mercados_validos
                    )

                    d4.metric(
                        "Confianza ≥70%",
                        confianza_70
                    )

                    d5.metric(
                        "Top Picks finales",
                        top_count
                    )

                    st.caption(
                        f"Partidos con EV bruto ≥+5%: {ev_5}. "
                        "Para entrar en Top Picks deben cumplirse "
                        "a la vez: partido de hoy + mercado válido + "
                        "confianza ≥70% + mejor EV ≥+5%."
                    )

                    diagnostico = (
                        tabla_proximos_raw[
                            [
                                "Fecha",
                                "Hora",
                                "Jugador 1",
                                "Jugador 2",
                                "_match_confidence",
                                "_best_ev_raw",
                                "_market_available",
                                "_market_quality",
                                "_valid_bookmakers",
                                "_pick_qualifies",
                            ]
                        ]
                        .copy()
                    )

                    diagnostico[
                        "Confianza"
                    ] = diagnostico[
                        "_match_confidence"
                    ].apply(
                        lambda value:
                            f"{float(value):.1%}"
                    )

                    diagnostico[
                        "Mejor EV"
                    ] = diagnostico[
                        "_best_ev_raw"
                    ].apply(
                        lambda value:
                            (
                                "-"
                                if pd.isna(value)
                                else f"{float(value):+.1%}"
                            )
                    )

                    diagnostico[
                        "Mercado válido"
                    ] = diagnostico[
                        "_market_available"
                    ].apply(
                        lambda value:
                            "✅"
                            if value
                            else "❌"
                    )

                    diagnostico[
                        "Top Pick"
                    ] = diagnostico[
                        "_pick_qualifies"
                    ].apply(
                        lambda value:
                            "🏆"
                            if value
                            else "-"
                    )

                    diagnostico[
                        "Calidad mercado"
                    ] = diagnostico[
                        "_market_quality"
                    ]

                    diagnostico[
                        "Casas"
                    ] = diagnostico[
                        "_valid_bookmakers"
                    ]

                    diagnostico[
                        "Partido"
                    ] = (
                        diagnostico[
                            "Jugador 1"
                        ]
                        + " vs "
                        + diagnostico[
                            "Jugador 2"
                        ]
                    )

                    diagnostico = diagnostico[
                        [
                            "Fecha",
                            "Hora",
                            "Partido",
                            "Confianza",
                            "Mejor EV",
                            "Mercado válido",
                            "Calidad mercado",
                            "Casas",
                            "Top Pick",
                        ]
                    ]

                    st.dataframe(
                        diagnostico,
                        hide_index=True,
                        use_container_width=True
                    )

                if top_hoy.empty:
                    st.info(
                        "Hoy no hay ningún pick que supere "
                        "los filtros mínimos: confianza ≥70%, "
                        "EV ≥+5% y mercado validado."
                    )

                else:
                    top_hoy[
                        "Ranking"
                    ] = range(
                        1,
                        len(top_hoy) + 1
                    )

                    top_hoy[
                        "Pick"
                    ] = top_hoy[
                        "_pick_selection"
                    ]

                    top_hoy[
                        "Prob. pick"
                    ] = top_hoy[
                        "_pick_probability"
                    ].apply(
                        lambda value:
                            f"{float(value):.1%}"
                    )

                    top_hoy[
                        "Confianza partido"
                    ] = top_hoy[
                        "_match_confidence"
                    ].apply(
                        lambda value:
                            f"{float(value):.1%}"
                    )

                    top_hoy[
                        "Cuota"
                    ] = top_hoy[
                        "_pick_odds"
                    ].apply(
                        lambda value:
                            f"{float(value):.2f}"
                    )

                    top_hoy[
                        "EV"
                    ] = top_hoy[
                        "_pick_ev"
                    ].apply(
                        lambda value:
                            f"{float(value):+.1%}"
                    )

                    top_hoy[
                        "Score"
                    ] = top_hoy[
                        "_value_score"
                    ].apply(
                        lambda value:
                            f"{float(value):.1f}/100"
                    )

                    top_hoy[
                        "Nivel"
                    ] = top_hoy[
                        "_value_category"
                    ]

                    top_hoy[
                        "Mercado"
                    ] = top_hoy[
                        "_market_quality"
                    ]

                    top_hoy[
                        "Casas"
                    ] = top_hoy[
                        "_valid_bookmakers"
                    ]

                    top_hoy[
                        "Casa"
                    ] = top_hoy[
                        "_pick_bookmaker"
                    ]

                    top_hoy[
                        "Partido"
                    ] = (
                        top_hoy[
                            "Jugador 1"
                        ]
                        + " vs "
                        + top_hoy[
                            "Jugador 2"
                        ]
                    )

                    mejor = top_hoy.iloc[
                        0
                    ]

                    tp1, tp2, tp3, tp4 = (
                        st.columns(4)
                    )

                    tp1.metric(
                        "🥇 Mejor pick",
                        str(
                            mejor[
                                "_pick_selection"
                            ]
                        )
                    )

                    tp2.metric(
                        "Cuota",
                        f"{float(mejor['_pick_odds']):.2f}"
                    )

                    tp3.metric(
                        "EV",
                        f"{float(mejor['_pick_ev']):+.1%}"
                    )

                    tp4.metric(
                        "Value Score",
                        f"{float(mejor['_value_score']):.1f}/100"
                    )

                    tabla_top = top_hoy[
                        [
                            "Ranking",
                            "Nivel",
                            "Hora",
                            "Torneo",
                            "Partido",
                            "Pick",
                            "Prob. pick",
                            "Confianza partido",
                            "Cuota",
                            "Casa",
                            "EV",
                            "Mercado",
                            "Casas",
                            "Score",
                        ]
                    ].head(
                        10
                    )

                    st.dataframe(
                        tabla_top,
                        hide_index=True,
                        use_container_width=True
                    )

                    st.caption(
                        "El Value Score sirve únicamente para "
                        "ordenar oportunidades: combina EV, "
                        "confianza del partido, calidad del mercado "
                        "y número de casas. No es una probabilidad "
                        "de que la apuesta gane."
                    )

                st.markdown(
                    "## 📋 Todos los próximos partidos"
                )

                columnas_publicas = [
                    col
                    for col in tabla_proximos_raw.columns
                    if not str(col).startswith(
                        "_"
                    )
                ]

                tabla_proximos = (
                    tabla_proximos_raw[
                        columnas_publicas
                    ]
                )

                st.dataframe(
                    tabla_proximos,
                    hide_index=True,
                    use_container_width=True
                )

                st.caption(
                    "📌 Pick automático: el tracker registra "
                    "como máximo 1 selección por partido cuando "
                    "la confianza del encuentro es ≥70% y el "
                    "mejor EV disponible es ≥+5%. "
                    "Stake virtual fijo: 1 unidad."
                )

                # -----------------------------------------
                # TRACK RECORD
                # -----------------------------------------

                # Primero intentamos liquidación directa con
                # Live Tennis API. El fragmento se ejecuta cada
                # 60 minutos y el tracker además aplica un throttle
                # de 30 minutos por pick para proteger la cuota.
                live_auto = resolver_picks_live()

                # Fallback: si el resultado ya llegó a nuestra
                # base histórica, también puede liquidarse por H2H.
                resolver_picks_pendientes(
                    df
                )

                live_manual = st.session_state.pop(
                    "ultimo_live_manual",
                    None
                )

                live_info = (
                    live_manual
                    if live_manual is not None
                    else live_auto
                )

                if live_info.get(
                    "resolved",
                    0
                ):
                    st.success(
                        "⚡ "
                        f"{live_info['resolved']} pick(s) "
                        "liquidados directamente con "
                        "Live Tennis API."
                    )

                if live_info.get(
                    "voided",
                    0
                ):
                    st.info(
                        "↩️ "
                        f"{live_info['voided']} pick(s) "
                        "cancelados marcados VOID."
                    )

                if live_info.get(
                    "rate_limited",
                    False
                ):
                    st.warning(
                        "Live Tennis API ha alcanzado su "
                        "límite temporal. El tracker seguirá "
                        "intentándolo en el próximo ciclo."
                    )

                track = get_track_record()
                resumen = track[
                    "summary"
                ]

                st.markdown('<div id="track-record"></div>', unsafe_allow_html=True)
                st.markdown('<div class="tep-section-title">📈 Track Record</div>', unsafe_allow_html=True)

                tr1, tr2, tr3, tr4, tr5 = (
                    st.columns(5)
                )

                tr1.metric(
                    "Picks",
                    resumen[
                        "total"
                    ]
                )

                tr2.metric(
                    "Pendientes",
                    resumen[
                        "pending"
                    ]
                )

                tr3.metric(
                    "Hit rate",
                    (
                        f"{resumen['hit_rate']:.1%}"
                        if resumen[
                            "settled"
                        ]
                        else "-"
                    )
                )

                tr4.metric(
                    "Beneficio",
                    (
                        f"{resumen['profit']:+.2f} u"
                    )
                )

                tr5.metric(
                    "ROI",
                    (
                        f"{resumen['roi']:+.1%}"
                        if resumen[
                            "settled"
                        ]
                        else "-"
                    )
                )

                if not track[
                    "by_confidence"
                ].empty:
                    st.markdown(
                        "### 🎯 Rendimiento por confianza"
                    )

                    st.dataframe(
                        track[
                            "by_confidence"
                        ],
                        hide_index=True,
                        use_container_width=True
                    )

                picks_track = track[
                    "picks"
                ]

                if not picks_track.empty:
                    tabla_track = (
                        picks_track[
                            [
                                "event_date",
                                "tournament",
                                "selection",
                                "prob_selection",
                                "odds",
                                "bookmaker",
                                "ev",
                                "market_quality",
                                "valid_bookmakers",
                                "status",
                                "live_status",
                                "live_score",
                                "result_winner",
                                "result_source",
                                "verification_note",
                                "api_player1",
                                "api_player2",
                                "api_scheduled_time",
                                "profit",
                            ]
                        ]
                        .head(30)
                        .copy()
                    )

                    tabla_track[
                        "prob_selection"
                    ] = tabla_track[
                        "prob_selection"
                    ].apply(
                        lambda value:
                            f"{float(value):.1%}"
                    )

                    tabla_track[
                        "ev"
                    ] = tabla_track[
                        "ev"
                    ].apply(
                        lambda value:
                            f"{float(value):+.1%}"
                    )

                    tabla_track[
                        "odds"
                    ] = tabla_track[
                        "odds"
                    ].apply(
                        lambda value:
                            f"{float(value):.2f}"
                    )

                    tabla_track[
                        "profit"
                    ] = tabla_track[
                        "profit"
                    ].apply(
                        lambda value:
                            (
                                "-"
                                if pd.isna(value)
                                else f"{float(value):+.2f} u"
                            )
                    )

                    tabla_track = (
                        tabla_track.rename(
                            columns={
                                "event_date": "Fecha",
                                "tournament": "Torneo",
                                "selection": "Pick",
                                "prob_selection": "Prob. modelo",
                                "odds": "Cuota",
                                "bookmaker": "Casa",
                                "ev": "EV",
                                "market_quality": "Mercado",
                                "valid_bookmakers": "Casas válidas",
                                "status": "Estado",
                                "live_status": "Estado live",
                                "live_score": "Marcador",
                                "result_winner": "Ganador real",
                                "result_source": "Fuente",
                                "verification_note": "Verificación",
                                "api_player1": "API jugador 1",
                                "api_player2": "API jugador 2",
                                "api_scheduled_time": "Hora API",
                                "profit": "Beneficio",
                            }
                        )
                    )

                    st.dataframe(
                        tabla_track,
                        hide_index=True,
                        use_container_width=True
                    )

                else:
                    st.info(
                        "Todavía no hay picks registrados. "
                        "Aparecerán automáticamente cuando "
                        "un partido cumpla los filtros de value."
                    )

                st.markdown('<div id="resultados-live"></div>', unsafe_allow_html=True)
                with st.expander(
                    "🛡️ Comprobar verificación de resultados",
                    expanded=False
                ):
                    st.caption(
                        "Aquí puedes comprobar qué está aceptando o rechazando "
                        "el tracker antes de tocar WON/LOST/ROI."
                    )

                    picks_diag = track[
                        "picks"
                    ].copy()

                    if picks_diag.empty:
                        st.info(
                            "Todavía no hay picks registrados."
                        )
                    else:
                        cols_diag = [
                            "event_date",
                            "tournament",
                            "player_a",
                            "player_b",
                            "selection",
                            "status",
                            "live_status",
                            "live_score",
                            "api_player1",
                            "api_player2",
                            "api_scheduled_time",
                            "verification_note",
                            "result_source",
                        ]

                        cols_diag = [
                            col
                            for col in cols_diag
                            if col in picks_diag.columns
                        ]

                        tabla_diag = (
                            picks_diag[
                                cols_diag
                            ]
                            .head(30)
                            .copy()
                        )

                        tabla_diag = tabla_diag.rename(
                            columns={
                                "event_date": "Fecha",
                                "tournament": "Torneo",
                                "player_a": "Jugador A",
                                "player_b": "Jugador B",
                                "selection": "Pick",
                                "status": "Estado tracker",
                                "live_status": "Estado API",
                                "live_score": "Marcador API",
                                "api_player1": "API jugador 1",
                                "api_player2": "API jugador 2",
                                "api_scheduled_time": "Hora API",
                                "verification_note": "Verificación",
                                "result_source": "Fuente",
                            }
                        )

                        st.dataframe(
                            tabla_diag,
                            hide_index=True,
                            use_container_width=True
                        )

                        st.markdown(
                            "**Qué deberías ver ahora:** "
                            "un Grand Slam con 2-0, 2-1, 1-2 o 0-2 "
                            "debe seguir `PENDING` y mostrar una nota "
                            "de verificación indicando que el marcador "
                            "es imposible para BO5. En Masters 1000, "
                            "ATP 500, ATP 250 y Challenger, un 2-0 o 2-1 "
                            "sí es un final normal."
                        )

                st.markdown("### 🔍 Análisis completo de un próximo partido")

                opciones_partidos = []

                for partido in proximos:
                    jugador_1 = partido.get("player1", "")
                    jugador_2 = partido.get("player2", "")
                    torneo = partido.get("tournament", "Torneo")
                    fecha = partido.get("event_date", "")

                    etiqueta = (
                        f"{fecha} · {torneo} · "
                        f"{jugador_1} vs {jugador_2}"
                    )

                    opciones_partidos.append(
                        (etiqueta, partido)
                    )

                if opciones_partidos:
                    etiquetas = [
                        item[0]
                        for item in opciones_partidos
                    ]

                    partido_elegido_label = st.selectbox(
                        "Selecciona un partido",
                        etiquetas,
                        key="proximo_partido_seleccionado"
                    )

                    partido_elegido = next(
                        partido
                        for etiqueta, partido in opciones_partidos
                        if etiqueta == partido_elegido_label
                    )

                    incluir_fisico_proximo = st.checkbox(
                        "🩺 Incluir estado físico y noticias",
                        value=False,
                        key="incluir_fisico_proximo",
                        help=(
                            "Déjalo desactivado para un análisis casi inmediato. "
                            "Actívalo solo cuando quieras consultar noticias "
                            "y riesgo físico."
                        )
                    )

                    if st.button(
                        "🔍 ANÁLISIS COMPLETO",
                        use_container_width=True,
                        key="analisis_completo_proximo"
                    ):
                        jugador_a_api = partido_elegido.get("player1")
                        jugador_b_api = partido_elegido.get("player2")

                        resolucion = resolver_partido_cached(
                            jugador_a_api,
                            jugador_b_api,
                            data_version
                        )

                        if not resolucion.get("ok"):
                            st.error(
                                "No se pudieron resolver correctamente "
                                "los jugadores de este partido."
                            )
                        else:
                            jugador_a = resolucion["jugador_a"]
                            jugador_b = resolucion["jugador_b"]

                            superficie_detalle = normalizar_superficie(
                                partido_elegido.get("surface")
                            )

                            resultado_detalle = predict_match_cached(
                                jugador_a,
                                jugador_b,
                                superficie_detalle,
                                ventana,
                                usar_elo,
                                data_version
                            )

                            if not resultado_detalle.get("ok"):
                                st.error(
                                    resultado_detalle.get(
                                        "message",
                                        "El modelo no pudo analizar este partido."
                                    )
                                )
                            else:
                                pa_detalle = float(
                                    resultado_detalle["prob_a"]
                                )
                                pb_detalle = float(
                                    resultado_detalle["prob_b"]
                                )

                                favorito_detalle = (
                                    jugador_a
                                    if pa_detalle >= pb_detalle
                                    else jugador_b
                                )

                                st.markdown(
                                    f"## 🎾 {jugador_a_api} vs {jugador_b_api}"
                                )

                                st.caption(
                                    f"{partido_elegido.get('tournament', '')} · "
                                    f"{partido_elegido.get('event_date', '')} · "
                                    f"{formatear_hora_utc(partido_elegido.get('start_time'))} · "
                                    f"{superficie_detalle or 'Todas'}"
                                )

                                d1, d2 = st.columns(2)

                                with d1:
                                    st.metric(
                                        jugador_a,
                                        f"{pa_detalle * 100:.1f}%"
                                    )
                                    st.progress(
                                        int(pa_detalle * 100)
                                    )

                                with d2:
                                    st.metric(
                                        jugador_b,
                                        f"{pb_detalle * 100:.1f}%"
                                    )
                                    st.progress(
                                        int(pb_detalle * 100)
                                    )

                                st.success(
                                    f"🏆 FAVORITO ESTADÍSTICO: "
                                    f"**{favorito_detalle}**"
                                )

                                st.caption(
                                    "Confianza del modelo: "
                                    + resultado_detalle.get(
                                        "confidence_label",
                                        "Sin dato"
                                    )
                                )

                                st.caption(
                                    "🧠 "
                                    + resultado_detalle.get(
                                        "model_version",
                                        "Modelo activo"
                                    )
                                )

                                st.markdown(
                                    "### 💰 Cuotas automáticas, edge y EV"
                                )

                                datos_cuotas_actuales_detalle = (
                                    buscar_mejores_cuotas(
                                        indice_cuotas,
                                        jugador_a,
                                        jugador_b
                                    )
                                    if indice_cuotas
                                    else None
                                )

                                datos_cuotas_detalle = resolver_cuotas_prematch(
                                    partido_elegido,
                                    jugador_a,
                                    jugador_b,
                                    datos_cuotas_actuales_detalle
                                )

                                if datos_cuotas_detalle:
                                    if datos_cuotas_detalle.get(
                                        "prematch_locked",
                                        False
                                    ):
                                        captura = datos_cuotas_detalle.get(
                                            "captured_at",
                                            ""
                                        )

                                        st.info(
                                            "🔒 CUOTA PRE-MATCH CONGELADA. "
                                            "El partido ya ha comenzado: la app está ignorando "
                                            "cualquier cuota LIVE y conserva exclusivamente la "
                                            "última cuota válida capturada antes del inicio."
                                            + (
                                                f" Capturada: {captura}"
                                                if captura
                                                else ""
                                            )
                                        )
                                    else:
                                        st.caption(
                                            "🟢 Mercado PRE-MATCH. La última cuota válida "
                                            "se guarda automáticamente y quedará congelada "
                                            "al comenzar el partido."
                                        )
                                    cuota_detalle_a = float(
                                        datos_cuotas_detalle["cuota_a"]
                                    )
                                    cuota_detalle_b = float(
                                        datos_cuotas_detalle["cuota_b"]
                                    )

                                    casa_detalle_a = (
                                        datos_cuotas_detalle["casa_a"]
                                    )
                                    casa_detalle_b = (
                                        datos_cuotas_detalle["casa_b"]
                                    )

                                    implied_detalle_a = (
                                        1 / cuota_detalle_a
                                    )
                                    implied_detalle_b = (
                                        1 / cuota_detalle_b
                                    )

                                    edge_detalle_a = (
                                        pa_detalle
                                        - implied_detalle_a
                                    )
                                    edge_detalle_b = (
                                        pb_detalle
                                        - implied_detalle_b
                                    )

                                    ev_detalle_a = (
                                        pa_detalle
                                        * cuota_detalle_a
                                    ) - 1

                                    ev_detalle_b = (
                                        pb_detalle
                                        * cuota_detalle_b
                                    ) - 1

                                    cuota_justa_a = (
                                        1 / pa_detalle
                                        if pa_detalle > 0
                                        else 0
                                    )
                                    cuota_justa_b = (
                                        1 / pb_detalle
                                        if pb_detalle > 0
                                        else 0
                                    )

                                    valor_col_1, valor_col_2 = (
                                        st.columns(2)
                                    )

                                    with valor_col_1:
                                        st.subheader(
                                            jugador_a_api
                                        )

                                        st.metric(
                                            "Mejor cuota disponible",
                                            f"{cuota_detalle_a:.2f}",
                                            help=(
                                                "Casa: "
                                                f"{casa_detalle_a}"
                                            )
                                        )

                                        st.caption(
                                            f"Casa: {casa_detalle_a}"
                                        )

                                        st.write(
                                            "🎯 Cuota justa del modelo: "
                                            f"**{cuota_justa_a:.2f}**"
                                        )

                                        st.write(
                                            "🏦 Prob. implícita cuota: "
                                            f"**{implied_detalle_a * 100:.1f}%**"
                                        )

                                        st.write(
                                            "⚡ Edge modelo vs cuota: "
                                            f"**{edge_detalle_a * 100:+.1f}%**"
                                        )

                                        st.write(
                                            "💸 EV: "
                                            f"**{ev_detalle_a * 100:+.1f}%**"
                                        )

                                        if ev_detalle_a > 0.05:
                                            st.success(
                                                "🟢 VALOR POSITIVO CLARO "
                                                "SEGÚN EL MODELO"
                                            )
                                        elif ev_detalle_a > 0:
                                            st.warning(
                                                "🟡 VALOR POSITIVO PEQUEÑO "
                                                "SEGÚN EL MODELO"
                                            )
                                        else:
                                            st.error(
                                                "🔴 SIN VALOR SEGÚN EL MODELO"
                                            )

                                    with valor_col_2:
                                        st.subheader(
                                            jugador_b_api
                                        )

                                        st.metric(
                                            "Mejor cuota disponible",
                                            f"{cuota_detalle_b:.2f}",
                                            help=(
                                                "Casa: "
                                                f"{casa_detalle_b}"
                                            )
                                        )

                                        st.caption(
                                            f"Casa: {casa_detalle_b}"
                                        )

                                        st.write(
                                            "🎯 Cuota justa del modelo: "
                                            f"**{cuota_justa_b:.2f}**"
                                        )

                                        st.write(
                                            "🏦 Prob. implícita cuota: "
                                            f"**{implied_detalle_b * 100:.1f}%**"
                                        )

                                        st.write(
                                            "⚡ Edge modelo vs cuota: "
                                            f"**{edge_detalle_b * 100:+.1f}%**"
                                        )

                                        st.write(
                                            "💸 EV: "
                                            f"**{ev_detalle_b * 100:+.1f}%**"
                                        )

                                        if ev_detalle_b > 0.05:
                                            st.success(
                                                "🟢 VALOR POSITIVO CLARO "
                                                "SEGÚN EL MODELO"
                                            )
                                        elif ev_detalle_b > 0:
                                            st.warning(
                                                "🟡 VALOR POSITIVO PEQUEÑO "
                                                "SEGÚN EL MODELO"
                                            )
                                        else:
                                            st.error(
                                                "🔴 SIN VALOR SEGÚN EL MODELO"
                                            )

                                else:
                                    if _partido_ya_empezo(
                                        partido_elegido,
                                        datos_cuotas_actuales_detalle
                                    ):
                                        st.warning(
                                            "🔒 Partido iniciado y no existe un snapshot "
                                            "PRE-MATCH guardado. Por seguridad la app NO usa "
                                            "la cuota LIVE y no calcula EV para este partido."
                                        )
                                    else:
                                        st.info(
                                            "Todavía no hay cuota PRE-MATCH automática "
                                            "disponible para este partido. La app volverá a "
                                            "comprobar el mercado y no calcula EV sin una "
                                            "cuota real prepartido."
                                        )

                                st.markdown(
                                    "### 📊 Factores analizados"
                                )

                                tabla_detalle = pd.DataFrame(
                                    resultado_detalle["comparison"]
                                )

                                st.dataframe(
                                    tabla_detalle,
                                    hide_index=True,
                                    use_container_width=True
                                )

                                st.markdown(
                                    "### 🥊 Enfrentamientos directos"
                                )

                                h_detalle = resultado_detalle["h2h"]

                                st.write(
                                    f"**{jugador_a}: "
                                    f"{h_detalle['a_wins']}** — "
                                    f"**{jugador_b}: "
                                    f"{h_detalle['b_wins']}** · "
                                    f"Total: {h_detalle['total']}"
                                )

                                if usar_elo:
                                    st.markdown("### ⚡ Elo")

                                    elo1, elo2 = st.columns(2)

                                    elo1.metric(
                                        jugador_a,
                                        f"{resultado_detalle['elo_a']:.0f}"
                                    )

                                    elo2.metric(
                                        jugador_b,
                                        f"{resultado_detalle['elo_b']:.0f}"
                                    )

                                st.markdown(
                                    "### 🎯 Lectura del modelo"
                                )

                                st.write(
                                    resultado_detalle["explanation"]
                                )

                                if incluir_fisico_proximo:
                                    st.markdown(
                                        "### 🩺 Estado físico y noticias recientes"
                                    )

                                    with st.spinner(
                                        "Buscando noticias recientes..."
                                    ):
                                        physical_detalle_a = (
                                            load_physical_status(
                                                jugador_a
                                            )
                                        )

                                        physical_detalle_b = (
                                            load_physical_status(
                                                jugador_b
                                            )
                                        )

                                    ph1, ph2 = st.columns(2)

                                    with ph1:
                                        st.subheader(jugador_a)

                                        st.metric(
                                            "Riesgo físico",
                                            f"{physical_detalle_a['score']}/100"
                                        )

                                        st.progress(
                                            physical_detalle_a["score"]
                                        )

                                        st.write(
                                            physical_detalle_a["status"]
                                        )

                                        if physical_detalle_a["high_alerts"]:
                                            st.warning(
                                                "⚠️ Alertas físicas importantes"
                                            )

                                            for article in physical_detalle_a["high_alerts"]:
                                                st.write(
                                                    f"🔴 {article['title']} "
                                                    f"({article['source']})"
                                                )

                                        elif physical_detalle_a["medium_alerts"]:
                                            st.warning(
                                                "⚠️ Posibles alertas físicas"
                                            )

                                            for article in physical_detalle_a["medium_alerts"]:
                                                st.write(
                                                    f"🟠 {article['title']} "
                                                    f"({article['source']})"
                                                )

                                        else:
                                            st.success(
                                                "🟢 Sin alertas físicas recientes "
                                                "detectadas."
                                            )

                                    with ph2:
                                        st.subheader(jugador_b)

                                        st.metric(
                                            "Riesgo físico",
                                            f"{physical_detalle_b['score']}/100"
                                        )

                                        st.progress(
                                            physical_detalle_b["score"]
                                        )

                                        st.write(
                                            physical_detalle_b["status"]
                                        )

                                        if physical_detalle_b["high_alerts"]:
                                            st.warning(
                                                "⚠️ Alertas físicas importantes"
                                            )

                                            for article in physical_detalle_b["high_alerts"]:
                                                st.write(
                                                    f"🔴 {article['title']} "
                                                    f"({article['source']})"
                                                )

                                        elif physical_detalle_b["medium_alerts"]:
                                            st.warning(
                                                "⚠️ Posibles alertas físicas"
                                            )

                                            for article in physical_detalle_b["medium_alerts"]:
                                                st.write(
                                                    f"🟠 {article['title']} "
                                                    f"({article['source']})"
                                                )

                                        else:
                                            st.success(
                                                "🟢 Sin alertas físicas recientes "
                                                "detectadas."
                                            )


                                else:
                                    st.caption(
                                        "⚡ Análisis rápido activo: "
                                        "noticias y estado físico omitidos."
                                    )

                if no_resueltos:
                    with st.expander(
                        f"⚠️ Partidos no resueltos: "
                        f"{len(no_resueltos)}"
                    ):
                        for item in no_resueltos:
                            st.write(
                                f"**{item['partido']}**"
                            )
                            st.caption(
                                item["motivo"]
                            )

        except Exception as exc:
            st.error(
                "No se pudieron cargar los próximos partidos."
            )
            st.caption(str(exc))



if pagina_actual == "▣  Próximos partidos":
    render_proximos_partidos(
        df,
        ventana,
        usar_elo
    )

elif pagina_actual == "☆  Top Picks":
    render_top_picks_page(
        df,
        ventana,
        usar_elo,
        data_version,
    )

elif pagina_actual == "▥  Rendimiento":
    render_rendimiento_page(df)

elif pagina_actual == "◉  Resultados live":
    render_resultados_live_page(df)


# =====================================================
# ANALIZADOR MANUAL
# =====================================================

if pagina_actual == "◈  Modelo / Analizador":
    st.markdown('<div class="tep-section-title">🎯 Analizador manual</div>', unsafe_allow_html=True)

    players = sorted(
        set(df["winner_name"].dropna())
        | set(df["loser_name"].dropna())
    )

    c1, c2 = st.columns(2)

    with c1:
        player_a = st.selectbox(
            "👤 JUGADOR A",
            players
        )

    with c2:
        player_b = st.selectbox(
            "👤 JUGADOR B",
            players,
            index=min(
                1,
                len(players) - 1
            )
        )


    st.markdown(
        "## 💰 Cuotas de la casa de apuestas"
    )

    q1, q2 = st.columns(2)

    with q1:
        cuota_a = st.number_input(
            f"Cuota de {player_a}",
            min_value=1.01,
            value=1.50,
            step=0.01,
            format="%.2f"
        )

    with q2:
        cuota_b = st.number_input(
            f"Cuota de {player_b}",
            min_value=1.01,
            value=2.50,
            step=0.01,
            format="%.2f"
        )


    if st.button(
        "🚀 ANALIZAR PARTIDO",
        type="primary",
        use_container_width=True
    ):
        if player_a == player_b:
            st.error(
                "Selecciona dos jugadores diferentes."
            )
            st.stop()

        result = predict_match_cached(
            player_a,
            player_b,
            (
                None
                if superficie == "Todas"
                else superficie
            ),
            ventana,
            usar_elo,
            data_version
        )

        if not result["ok"]:
            st.error(result["message"])
            st.stop()

        with st.spinner(
            "Buscando noticias recientes sobre los jugadores..."
        ):
            physical_a = load_physical_status(
                player_a
            )
            physical_b = load_physical_status(
                player_b
            )

        pa = result["prob_a"]
        pb = result["prob_b"]

        fav = (
            player_a
            if pa >= pb
            else player_b
        )

        st.markdown(
            "## 🔮 Probabilidad estimada"
        )

        x, y = st.columns(2)

        with x:
            st.metric(
                player_a,
                f"{pa * 100:.1f}%"
            )
            st.progress(
                int(pa * 100)
            )

        with y:
            st.metric(
                player_b,
                f"{pb * 100:.1f}%"
            )
            st.progress(
                int(pb * 100)
            )

        st.markdown(
            "## 💰 Análisis de cuotas y valor esperado"
        )

        implied_a = 1 / cuota_a
        implied_b = 1 / cuota_b

        ev_a = (pa * cuota_a) - 1
        ev_b = (pb * cuota_b) - 1

        edge_a = pa - implied_a
        edge_b = pb - implied_b

        ca, cb = st.columns(2)

        with ca:
            st.subheader(player_a)

            st.write(
                f"💰 Cuota: **{cuota_a:.2f}**"
            )

            st.write(
                "📊 Probabilidad del modelo: "
                f"**{pa * 100:.1f}%**"
            )

            st.write(
                "🏦 Probabilidad implícita: "
                f"**{implied_a * 100:.1f}%**"
            )

            st.write(
                "⚡ Ventaja estimada: "
                f"**{edge_a * 100:+.1f}%**"
            )

            st.write(
                "💸 Valor esperado (EV): "
                f"**{ev_a * 100:+.1f}%**"
            )

            if ev_a > 0.05:
                st.success(
                    "🟢 POSIBLE VALOR POSITIVO "
                    "SEGÚN EL MODELO"
                )
            elif ev_a > 0:
                st.warning(
                    "🟡 VALOR POSITIVO PEQUEÑO "
                    "SEGÚN EL MODELO"
                )
            else:
                st.error(
                    "🔴 SIN VALOR SEGÚN EL MODELO"
                )

        with cb:
            st.subheader(player_b)

            st.write(
                f"💰 Cuota: **{cuota_b:.2f}**"
            )

            st.write(
                "📊 Probabilidad del modelo: "
                f"**{pb * 100:.1f}%**"
            )

            st.write(
                "🏦 Probabilidad implícita: "
                f"**{implied_b * 100:.1f}%**"
            )

            st.write(
                "⚡ Ventaja estimada: "
                f"**{edge_b * 100:+.1f}%**"
            )

            st.write(
                "💸 Valor esperado (EV): "
                f"**{ev_b * 100:+.1f}%**"
            )

            if ev_b > 0.05:
                st.success(
                    "🟢 POSIBLE VALOR POSITIVO "
                    "SEGÚN EL MODELO"
                )
            elif ev_b > 0:
                st.warning(
                    "🟡 VALOR POSITIVO PEQUEÑO "
                    "SEGÚN EL MODELO"
                )
            else:
                st.error(
                    "🔴 SIN VALOR SEGÚN EL MODELO"
                )

        st.success(
            f"🏆 FAVORITO ESTADÍSTICO: **{fav}**"
        )

        st.caption(
            "Confianza del modelo: "
            + result["confidence_label"]
        )

        st.caption(
            "🧠 "
            + result.get(
                "model_version",
                "Modelo activo"
            )
        )

        st.markdown(
            "## 📊 Factores analizados"
        )

        table = pd.DataFrame(
            result["comparison"]
        )

        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True
        )

        st.markdown(
            "## 🥊 Enfrentamientos directos"
        )

        h = result["h2h"]

        st.write(
            f"**{player_a}: {h['a_wins']}** — "
            f"**{player_b}: {h['b_wins']}** "
            f" ·  Total: {h['total']}"
        )

        if usar_elo:
            st.markdown(
                "## ⚡ Elo"
            )

            e1, e2 = st.columns(2)

            e1.metric(
                player_a,
                f"{result['elo_a']:.0f}"
            )

            e2.metric(
                player_b,
                f"{result['elo_b']:.0f}"
            )

        st.markdown(
            "## 🎯 Cómo leer el resultado"
        )

        st.write(
            result["explanation"]
        )

        # =================================================
        # ESTADO FÍSICO
        # =================================================

        st.markdown(
            "## 🩺 Estado físico y noticias recientes"
        )

        phys1, phys2 = st.columns(2)

        with phys1:
            st.subheader(player_a)

            st.metric(
                "Riesgo físico",
                f"{physical_a['score']}/100"
            )

            st.progress(
                physical_a["score"]
            )

            st.write(
                physical_a["status"]
            )

            if physical_a["high_alerts"]:
                st.warning(
                    "⚠️ Alertas físicas importantes detectadas"
                )

                for article in physical_a["high_alerts"]:
                    st.write(
                        f"🔴 {article['title']} "
                        f"({article['source']})"
                    )

            elif physical_a["medium_alerts"]:
                st.warning(
                    "⚠️ Posibles alertas físicas"
                )

                for article in physical_a["medium_alerts"]:
                    st.write(
                        f"🟠 {article['title']} "
                        f"({article['source']})"
                    )

            else:
                st.success(
                    "🟢 No se han detectado alertas físicas recientes "
                    "en las fuentes analizadas."
                )

        with phys2:
            st.subheader(player_b)

            st.metric(
                "Riesgo físico",
                f"{physical_b['score']}/100"
            )

            st.progress(
                physical_b["score"]
            )

            st.write(
                physical_b["status"]
            )

            if physical_b["high_alerts"]:
                st.warning(
                    "⚠️ Alertas físicas importantes detectadas"
                )

                for article in physical_b["high_alerts"]:
                    st.write(
                        f"🔴 {article['title']} "
                        f"({article['source']})"
                    )

            elif physical_b["medium_alerts"]:
                st.warning(
                    "⚠️ Posibles alertas físicas"
                )

                for article in physical_b["medium_alerts"]:
                    st.write(
                        f"🟠 {article['title']} "
                        f"({article['source']})"
                    )

            else:
                st.success(
                    "🟢 No se han detectado alertas físicas recientes "
                    "en las fuentes analizadas."
                )


st.divider()

st.caption(
    "⚠️ Herramienta educativa y estadística. "
    "Las probabilidades son estimaciones, no garantías "
    "de resultado ni de beneficio económico."
)
