import pandas as pd

def elo_ratings(df, surface=None, base=1500.0, k=28.0):
    x = df.copy().sort_values("tourney_date")
    if surface:
        x = x[x["surface"].fillna("") == surface]

    ratings = {}
    for _, r in x.iterrows():
        w, l = r["winner_name"], r["loser_name"]
        rw, rl = ratings.get(w, base), ratings.get(l, base)
        expected = 1 / (1 + 10 ** ((rl-rw)/400))
        ratings[w] = rw + k * (1-expected)
        ratings[l] = rl + k * (0-expected)
    return ratings

def player_elo_table(df, players, surface=None):
    r = elo_ratings(df, surface)
    return {p: float(r.get(p, 1500.0)) for p in players}
