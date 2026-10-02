from pathlib import Path
import pandas as pd
import duckdb

RAW = Path("data/raw")
OUT = Path("data/processed")

LEAGUE_NAMES = {
    "E0": "Premier League",
    "D1": "Bundesliga",
    "I1": "Serie A",
    "SP1": "La Liga",
    "F1": "Ligue 1",
    "SC0": "Scottish Premiership",
    "N1": "Eredivisie",
    "P1": "Primeira Liga",
    "T1": "Super Lig",
}

# first season (by start year) with VAR in every league match, Scotland starts in 2022
# which is after the data ends, so it is never treated here
VAR_START = {
    "D1": 2017, "I1": 2017, "P1": 2017,
    "SP1": 2018, "F1": 2018, "N1": 2018, "T1": 2018,
    "E0": 2019,
    "SC0": 2022,
}

KEEP = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "HF", "AF", "HY", "AY", "HR", "AR"]


def load_file(path):
    league, season = path.stem.split("_")
    df = pd.read_csv(path, encoding="latin-1", on_bad_lines="skip")
    df = df[[c for c in KEEP if c in df.columns]]
    df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTHG", "FTAG"])
    df = df.assign(league_code=league, season_start=2000 + int(season[:2]))
    return df


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.concat([load_file(p) for p in sorted(RAW.glob("*.csv"))], ignore_index=True)

    df["date"] = pd.to_datetime(df["Date"], format="mixed", dayfirst=True)
    df["league"] = df["league_code"].map(LEAGUE_NAMES)

    df["home_goals"] = df["FTHG"].astype(int)
    df["away_goals"] = df["FTAG"].astype(int)
    df["total_goals"] = df["home_goals"] + df["away_goals"]
    df["home_margin"] = df["home_goals"] - df["away_goals"]
    df["fouls"] = df["HF"] + df["AF"]
    df["cards"] = df["HY"] + df["AY"] + df["HR"] + df["AR"]

    df["var_start"] = df["league_code"].map(VAR_START)
    df["treated"] = (df["season_start"] >= df["var_start"]).astype(int)

    # rough flag for matches played from the March 2020 shutdown through the 2020 to 2021 season
    df["empty_stadium"] = (
        (df["date"] >= "2020-03-12") & (df["date"] <= "2021-07-31")
    ).astype(int)

    cols = ["league", "league_code", "season_start", "date", "HomeTeam", "AwayTeam",
            "home_goals", "away_goals", "total_goals", "home_margin", "fouls", "cards",
            "var_start", "treated", "empty_stadium"]
    df = df[cols].sort_values(["league", "date"]).reset_index(drop=True)

    df.to_csv(OUT / "matches.csv", index=False)
    con = duckdb.connect(str(OUT / "var.duckdb"))
    con.execute("CREATE OR REPLACE TABLE matches AS SELECT * FROM df")
    con.close()
    return df


if __name__ == "__main__":
    data = build()
    print(data.shape)
    print(data.groupby(["league", "season_start"])["treated"].agg(["count", "mean"]).to_string())
    print()
    print("Share of matches missing fouls or cards, by league")
    print(data.groupby("league")[["fouls", "cards"]].apply(lambda g: g.isna().mean()).round(3))