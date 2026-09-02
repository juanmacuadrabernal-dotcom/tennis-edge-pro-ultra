import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd

DB = Path("tennis_edge.db")


def connect():
    return sqlite3.connect(DB, check_same_thread=False)


def init_db():
    with connect() as con:

        con.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_key TEXT PRIMARY KEY,
            tourney_date TEXT,
            tourney_name TEXT,
            surface TEXT,
            winner_name TEXT,
            loser_name TEXT,
            winner_rank REAL,
            loser_rank REAL,
            w_ace REAL,
            l_ace REAL,
            w_df REAL,
            l_df REAL,
            w_1stIn REAL,
            l_1stIn REAL,
            w_1stWon REAL,
            l_1stWon REAL,
            w_2ndWon REAL,
            l_2ndWon REAL,
            w_svpt REAL,
            l_svpt REAL,
            w_bpWon REAL,
            l_bpWon REAL,
            w_bpSaved REAL,
            l_bpSaved REAL
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)


def existing_keys():

    with connect() as con:

        rows = con.execute(
            "SELECT match_key FROM matches"
        ).fetchall()

    return {row[0] for row in rows}


def insert_matches(df):

    cols = [
        "match_key",
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
        "l_bpSaved"
    ]

    out = df.reindex(columns=cols).copy()

    out["tourney_date"] = pd.to_datetime(
        out["tourney_date"],
        errors="coerce"
    ).astype(str)

    with connect() as con:

        # Guardamos los partidos uno por uno para evitar
        # límites de SQLite y duplicados.

        for _, row in out.iterrows():

            values = tuple(
                None if pd.isna(value) else value
                for value in row
            )

            placeholders = ",".join(
                ["?"] * len(cols)
            )

            sql = f"""
            INSERT OR IGNORE INTO matches
            ({",".join(cols)})
            VALUES ({placeholders})
            """

            con.execute(sql, values)

        con.commit()


def get_matches():

    with connect() as con:

        df = pd.read_sql_query(
            "SELECT * FROM matches ORDER BY tourney_date",
            con
        )

    if not df.empty:

        df["tourney_date"] = pd.to_datetime(
            df["tourney_date"],
            errors="coerce"
        )

    return df


def set_last_update():

    with connect() as con:

        con.execute(
            """
            INSERT OR REPLACE INTO metadata
            (key, value)
            VALUES (?, ?)
            """,
            (
                "last_update",
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )


def get_last_update():

    with connect() as con:

        row = con.execute(
            """
            SELECT value
            FROM metadata
            WHERE key='last_update'
            """
        ).fetchone()

    return row[0] if row else None
def set_model_metrics(metrics):

    with connect() as con:

        con.execute("""
        CREATE TABLE IF NOT EXISTS model_metrics (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        for key, value in metrics.items():

            con.execute(
                """
                INSERT OR REPLACE INTO model_metrics
                (key, value)
                VALUES (?, ?)
                """,
                (key, str(value))
            )

        con.commit()


def get_model_metrics():

    with connect() as con:

        con.execute("""
        CREATE TABLE IF NOT EXISTS model_metrics (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        rows = con.execute(
            "SELECT key, value FROM model_metrics"
        ).fetchall()

    return dict(rows)