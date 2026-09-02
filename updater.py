from datetime import datetime
from io import StringIO
import hashlib
import re
import unicodedata

import pandas as pd
import requests

from database import (
    init_db,
    existing_keys,
    get_matches,
    insert_matches,
    set_last_update,
)


START_YEAR = 2020


# ============================================================
# FUENTES HISTORICAS
# ============================================================

HISTORICAL_SOURCES = [
    (
        "https://raw.githubusercontent.com/"
        "Aneeshers/tennis-sackmann-archive/main/atp/"
        "atp_matches_{}.csv"
    ),
    (
        "https://raw.githubusercontent.com/"
        "Aneeshers/tennis-sackmann-archive/main/atp/"
        "atp_matches_qual_chall_{}.csv"
    ),
]


# ============================================================
# FUENTES 2026 ACTUALIZADAS
# TennisMyLife mantiene CSV de temporada + torneos en curso.
# ============================================================

TML_CURRENT_SOURCES = [
    (
        "ATP temporada",
        "https://stats.tennismylife.org/data/{}.csv",
    ),
    (
        "ATP torneos en curso",
        "https://stats.tennismylife.org/data/ongoing_tourneys.csv",
    ),
    (
        "Challenger temporada",
        "https://stats.tennismylife.org/data/{}_challenger.csv",
    ),
    (
        "Challenger en curso",
        "https://stats.tennismylife.org/data/challenger_ongoing_tourneys.csv",
    ),
    (
        "ATP qualifying temporada",
        "https://stats.tennismylife.org/data/atp_quali/{}_atp_quali.csv",
    ),
]


# Fuente antigua. La conservamos como fallback, no como fuente
# principal de actualidad.
LEGACY_CURRENT_SOURCE = (
    "https://raw.githubusercontent.com/"
    "migumax/tennis_atp/master/{}.csv"
)


REQUIRED_COLUMNS = [
    "tourney_date",
    "tourney_name",
    "surface",
    "winner_name",
    "loser_name",
    "winner_rank",
    "loser_rank",
    "w_ace",
    "l_ace",
    "w_df",
    "l_df",
    "w_1stIn",
    "l_1stIn",
    "w_1stWon",
    "l_1stWon",
    "w_2ndWon",
    "l_2ndWon",
    "w_svpt",
    "l_svpt",
    "w_bpWon",
    "l_bpWon",
    "w_bpSaved",
    "l_bpSaved",
]


def descargar_archivo(
    url,
    nombre_fuente=None,
):
    try:
        if nombre_fuente:
            print(
                f"Fuente: {nombre_fuente}"
            )

        print(
            f"Descargando: {url}"
        )

        respuesta = requests.get(
            url,
            timeout=60,
            headers={
                "User-Agent": (
                    "Tennis-Edge-Pro/1.0"
                )
            },
        )

        if respuesta.status_code != 200:
            print(
                "No disponible "
                f"(HTTP {respuesta.status_code})"
            )
            return None

        if len(
            respuesta.content
        ) < 100:
            print(
                "Archivo demasiado pequeno."
            )
            return None

        df = pd.read_csv(
            StringIO(
                respuesta.text
            ),
            low_memory=False,
        )

        print(
            f"OK: {len(df)} filas encontradas"
        )

        return df

    except Exception as exc:
        print(
            "Error descargando archivo:"
        )
        print(exc)

        return None


def normalizar_dataframe(df):
    df = df.copy()

    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    # --------------------------------------------
    # Fecha
    # --------------------------------------------

    fecha_original = (
        df[
            "tourney_date"
        ]
        .astype(
            "string"
        )
        .str.strip()
    )

    fecha_convertida = pd.to_datetime(
        fecha_original,
        format="%Y%m%d",
        errors="coerce",
    )

    mask_invalida = (
        fecha_convertida.isna()
    )

    if mask_invalida.any():
        fecha_convertida.loc[
            mask_invalida
        ] = pd.to_datetime(
            fecha_original.loc[
                mask_invalida
            ],
            errors="coerce",
        )

    df[
        "tourney_date"
    ] = fecha_convertida

    # --------------------------------------------
    # Nombres
    # --------------------------------------------

    for column in (
        "winner_name",
        "loser_name",
        "tourney_name",
    ):
        df[
            column
        ] = (
            df[
                column
            ]
            .astype(
                "string"
            )
            .str.strip()
        )

    # --------------------------------------------
    # Superficie
    # --------------------------------------------

    df[
        "surface"
    ] = (
        df[
            "surface"
        ]
        .astype(
            "string"
        )
        .str.strip()
        .str.title()
    )

    # Sólo partidos que ya tienen ganador/perdedor.
    df = df.dropna(
        subset=[
            "tourney_date",
            "winner_name",
            "loser_name",
        ]
    )

    df = df[
        (
            df[
                "winner_name"
            ]
            .astype(str)
            .str.len()
            > 1
        )
        &
        (
            df[
                "loser_name"
            ]
            .astype(str)
            .str.len()
            > 1
        )
    ]

    return df


def crear_match_keys(df):
    df = df.copy()

    stable = (
        df[
            "tourney_date"
        ]
        .dt.strftime(
            "%Y-%m-%d"
        )
        .fillna("")
        + "|"
        + df[
            "tourney_name"
        ]
        .fillna("")
        .astype(str)
        + "|"
        + df[
            "winner_name"
        ]
        .astype(str)
        + "|"
        + df[
            "loser_name"
        ]
        .astype(str)
    )

    df[
        "match_key"
    ] = stable.map(
        lambda value:
            hashlib.sha1(
                value.encode(
                    "utf-8"
                )
            ).hexdigest()
    )

    return df


def _normalizar_texto(
    value,
):
    if pd.isna(
        value
    ):
        return ""

    value = unicodedata.normalize(
        "NFKD",
        str(value),
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
        value,
    )

    return " ".join(
        value.split()
    )


def _firma_partido(
    fecha,
    winner,
    loser,
):
    fecha = pd.to_datetime(
        fecha,
        errors="coerce",
    )

    if pd.isna(
        fecha
    ):
        return None

    winner = _normalizar_texto(
        winner
    )

    loser = _normalizar_texto(
        loser
    )

    if (
        not winner
        or not loser
    ):
        return None

    return (
        f"{fecha.strftime('%Y-%m-%d')}"
        f"|{winner}"
        f"|{loser}"
    )


def firmas_existentes():
    """
    Evita duplicados aunque dos fuentes usen un nombre de
    torneo ligeramente distinto.

    Para un resultado terminado usamos:
        fecha de torneo + ganador + perdedor
    """
    actual = get_matches()

    if actual.empty:
        return set()

    firmas = set()

    for row in actual.itertuples(
        index=False
    ):
        firma = _firma_partido(
            getattr(
                row,
                "tourney_date",
                None,
            ),
            getattr(
                row,
                "winner_name",
                None,
            ),
            getattr(
                row,
                "loser_name",
                None,
            ),
        )

        if firma:
            firmas.add(
                firma
            )

    return firmas


def descargar_historico(
    year,
):
    frames = []

    for source in HISTORICAL_SOURCES:
        url = source.format(
            year
        )

        df = descargar_archivo(
            url,
            (
                "Sackmann archive "
                f"{year}"
            ),
        )

        if df is not None:
            df = normalizar_dataframe(
                df
            )

            if not df.empty:
                frames.append(
                    df
                )

    if not frames:
        return None

    return pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )


def descargar_fuentes_actuales(
    year,
):
    frames = []

    print()
    print(
        "===================================="
    )
    print(
        f"FUENTES ACTUALIZADAS {year}"
    )
    print(
        "===================================="
    )

    for (
        nombre,
        template,
    ) in TML_CURRENT_SOURCES:
        url = template.format(
            year
        )

        df = descargar_archivo(
            url,
            nombre,
        )

        if df is None:
            continue

        df = normalizar_dataframe(
            df
        )

        if not df.empty:
            frames.append(
                df
            )

    # Fallback antiguo. Puede aportar alguna fila adicional,
    # pero ya no es la referencia principal.
    legacy_url = (
        LEGACY_CURRENT_SOURCE.format(
            year
        )
    )

    legacy = descargar_archivo(
        legacy_url,
        "Fuente legacy",
    )

    if legacy is not None:
        legacy = normalizar_dataframe(
            legacy
        )

        if not legacy.empty:
            frames.append(
                legacy
            )

    if not frames:
        return None

    return pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )


def _quitar_duplicados(
    df,
    firmas_bd,
):
    """
    Primero elimina duplicados entre las fuentes descargadas.
    Después elimina cualquier partido que ya exista en SQLite.
    """
    df = df.copy()

    df[
        "_firma"
    ] = [
        _firma_partido(
            fecha,
            winner,
            loser,
        )
        for (
            fecha,
            winner,
            loser,
        ) in zip(
            df[
                "tourney_date"
            ],
            df[
                "winner_name"
            ],
            df[
                "loser_name"
            ],
        )
    ]

    df = df.dropna(
        subset=[
            "_firma"
        ]
    )

    df = df.drop_duplicates(
        subset=[
            "_firma"
        ],
        keep="first",
    )

    if firmas_bd:
        df = df.loc[
            ~df[
                "_firma"
            ].isin(
                firmas_bd
            )
        ].copy()

    return df.drop(
        columns=[
            "_firma"
        ],
        errors="ignore",
    )


def update_database(
    start_year=START_YEAR,
):
    init_db()

    current_year = (
        datetime.now().year
    )

    frames = []

    print()
    print(
        "===================================="
    )
    print(
        "REVISANDO DATOS HISTORICOS"
    )
    print(
        "===================================="
    )

    # Conservamos el comportamiento histórico que ya te
    # funciona. Esto también permite reparar huecos si un
    # archivo antiguo recibe correcciones.
    for year in range(
        start_year,
        current_year,
    ):
        print()
        print(
            f"Revisando ano {year}"
        )

        df = descargar_historico(
            year
        )

        if df is not None:
            frames.append(
                df
            )

    print()
    print(
        "===================================="
    )
    print(
        f"REVISANDO TEMPORADA {current_year}"
    )
    print(
        "===================================="
    )

    # Archivo histórico del año actual.
    current_history = (
        descargar_historico(
            current_year
        )
    )

    if current_history is not None:
        frames.append(
            current_history
        )

    # Fuentes que cubren la temporada reciente y torneos
    # que todavía están en curso.
    current_live = (
        descargar_fuentes_actuales(
            current_year
        )
    )

    if current_live is not None:
        frames.append(
            current_live
        )

    if not frames:
        return (
            "No se pudieron descargar datos. "
            "Revisa la conexion."
        )

    df = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    df = normalizar_dataframe(
        df
    )

    df = crear_match_keys(
        df
    )

    # Dedupe por firma independiente del nombre del torneo.
    existing_signatures = (
        firmas_existentes()
    )

    new = _quitar_duplicados(
        df,
        existing_signatures,
    )

    # Protección adicional por match_key.
    existing = existing_keys()

    if existing:
        new = new.loc[
            ~new[
                "match_key"
            ].isin(
                existing
            )
        ].copy()

    if not new.empty:
        print()
        print(
            "===================================="
        )
        print(
            f"PARTIDOS NUEVOS: {len(new)}"
        )
        print(
            "===================================="
        )

        # Diagnóstico de fechas.
        print(
            "Fecha nueva minima:",
            new[
                "tourney_date"
            ].min(),
        )

        print(
            "Fecha nueva maxima:",
            new[
                "tourney_date"
            ].max(),
        )

        print()

        ultimos_nuevos = (
            new
            .sort_values(
                "tourney_date",
                ascending=False,
            )
            .head(10)
        )

        for row in ultimos_nuevos.itertuples(
            index=False
        ):
            print(
                f"{row.tourney_date:%Y-%m-%d} | "
                f"{row.winner_name} > "
                f"{row.loser_name} | "
                f"{row.tourney_name}"
            )

        insert_matches(
            new
        )

    else:
        print()
        print(
            "No se han encontrado "
            "partidos nuevos."
        )

    set_last_update()

    return (
        "Actualizacion completada. "
        f"Partidos nuevos anadidos: {len(new)}. "
        "Fuentes: Sackmann archive + "
        "TennisMyLife ATP/Challenger/qualifying "
        "+ torneos en curso."
    )
