import warnings
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
import pyfixest as pf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

DB = "data/processed/var.duckdb"
OUT = Path("outputs")
OUT.mkdir(exist_ok=True)

OUTCOMES = {
    "total_goals": "Goals per match",
    "home_margin": "Home goal margin",
    "fouls": "Fouls per match",
    "cards": "Cards per match",
}

PRE = 5            # seasons before adoption in each stack
POST = 1           # seasons after adoption, so the adoption season plus one more
MIN_COVERAGE = 0.9 # a league needs data for 90 percent of matches to be used for an outcome
N_PERM = 300       # number of placebo reshuffles

PANEL_SQL = """
SELECT league, season_start,
       AVG(total_goals) AS total_goals,
       AVG(home_margin) AS home_margin,
       AVG(fouls) AS fouls,
       AVG(cards) AS cards
FROM matches
GROUP BY league, season_start
ORDER BY league, season_start
"""


def load():
    con = duckdb.connect(DB, read_only=True)
    panel = con.execute(PANEL_SQL).df()
    matches = con.execute("SELECT * FROM matches").df()
    con.close()
    return panel, matches


def plot_trends(panel):
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    for ax, (col, label) in zip(axes.ravel(), OUTCOMES.items()):
        sns.lineplot(data=panel, x="season_start", y=col, hue="league",
                     marker="o", ax=ax, legend=(col == "total_goals"))
        ax.set_title(label)
        ax.set_xlabel("Season start year")
        ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(OUT / "trends.png", dpi=150)
    plt.close(fig)


def prep(matches, y):
    """Keep only leagues that have enough data for this outcome."""
    d = matches.dropna(subset=[y])
    coverage = d.groupby("league").size() / matches.groupby("league").size()
    keep = coverage[coverage >= MIN_COVERAGE].index
    return d[d["league"].isin(keep)]


def stack(d, var_start):
    """Stacked design. Each adoption year gets its own block with the leagues that
    adopted that year versus leagues that had not adopted by the end of the window."""
    d = d.assign(var_start=d["league"].map(var_start))
    pieces = []
    for g in sorted(d["var_start"].unique()):
        if g > d["season_start"].max():
            continue
        treated = d[d["var_start"] == g]
        controls = d[d["var_start"] > g + POST]
        if treated.empty or controls.empty:
            continue
        s = pd.concat([treated, controls])
        s = s[(s["season_start"] >= g - PRE) & (s["season_start"] <= g + POST)].copy()
        s["cohort"] = g
        s["rel"] = s["season_start"] - g
        s["is_treated"] = (s["var_start"] == g).astype(int)
        s["D"] = s["is_treated"] * (s["rel"] >= 0).astype(int)
        s["fe_league"] = s["cohort"].astype(str) + "_" + s["league"]
        s["fe_season"] = s["cohort"].astype(str) + "_" + s["season_start"].astype(str)
        pieces.append(s)
    if not pieces:
        return None
    return pd.concat(pieces, ignore_index=True)


def k_name(k):
    return f"k_m{abs(k)}" if k < 0 else f"k_p{k}"


def event_study(s, y):
    ks = [k for k in range(-PRE, POST + 1) if k != -1]
    s = s.copy()
    for k in ks:
        s[k_name(k)] = ((s["rel"] == k) & (s["is_treated"] == 1)).astype(int)
    terms = " + ".join(k_name(k) for k in ks)
    fit = pf.feols(f"{y} ~ {terms} + empty_stadium | fe_league + fe_season",
                   data=s, vcov={"CRV1": "league"})
    t = fit.tidy()
    rows = [{"k": -1, "est": 0.0, "lo": 0.0, "hi": 0.0}]
    for k in ks:
        r = t.loc[k_name(k)]
        rows.append({"k": k, "est": r["Estimate"], "lo": r["2.5%"], "hi": r["97.5%"]})
    return pd.DataFrame(rows).sort_values("k")


def plot_event_studies(es):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for ax, (y, label) in zip(axes.ravel(), OUTCOMES.items()):
        df = es.get(y)
        if df is None:
            ax.set_visible(False)
            continue
        ax.axhline(0, color="grey", lw=1)
        ax.axvline(-0.5, color="grey", lw=1, ls=":")
        ax.errorbar(df["k"], df["est"],
                    yerr=[df["est"] - df["lo"], df["hi"] - df["est"]],
                    fmt="o", capsize=3)
        ax.set_title(label)
        ax.set_xlabel("Seasons since VAR adoption")
    fig.tight_layout()
    fig.savefig(OUT / "event_study.png", dpi=150)
    plt.close(fig)


def pooled_effect(s, y):
    fit = pf.feols(f"{y} ~ D + empty_stadium | fe_league + fe_season",
                   data=s, vcov={"CRV1": "league"})
    return fit.tidy().loc["D"]


def permutation_p(d, y, observed, seed=1):
    """Reshuffle which league got which adoption year and see how often a fake
    assignment produces an effect as large as the real one."""
    rng = np.random.default_rng(seed)
    first = d.drop_duplicates("league")
    leagues = first["league"].tolist()
    years = first["var_start"].to_numpy()
    ests = []
    for _ in range(N_PERM):
        fake = dict(zip(leagues, rng.permutation(years)))
        s = stack(d, fake)
        if s is None:
            continue
        try:
            fit = pf.feols(f"{y} ~ D + empty_stadium | fe_league + fe_season",
                           data=s, vcov="iid")
            ests.append(fit.coef()["D"])
        except Exception:
            continue
    ests = np.array(ests)
    return (np.sum(np.abs(ests) >= abs(observed)) + 1) / (len(ests) + 1), len(ests)


def main():
    panel, matches = load()
    plot_trends(panel)

    results, es = [], {}
    for y, label in OUTCOMES.items():
        d = prep(matches, y)
        vs = d.drop_duplicates("league").set_index("league")["var_start"].to_dict()
        s = stack(d, vs)
        if s is None:
            print("No usable stack for", label)
            continue
        t = pooled_effect(s, y)
        p, n_ok = permutation_p(d, y, t["Estimate"])
        es[y] = event_study(s, y)
        results.append({
            "outcome": label,
            "leagues_used": d["league"].nunique(),
            "estimate": t["Estimate"],
            "ci_low": t["2.5%"],
            "ci_high": t["97.5%"],
            "permutation_p": p,
        })
        print("done", label, "with", n_ok, "valid reshuffles")

    plot_event_studies(es)
    res = pd.DataFrame(results).round(3)
    res.to_csv(OUT / "results.csv", index=False)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()