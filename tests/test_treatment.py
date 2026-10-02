import pandas as pd
import pytest

EXPECTED_FIRST = {
    "Bundesliga": 2017, "Serie A": 2017, "Primeira Liga": 2017,
    "La Liga": 2018, "Ligue 1": 2018, "Eredivisie": 2018, "Super Lig": 2018,
    "Premier League": 2019,
}


@pytest.fixture(scope="module")
def matches():
    return pd.read_csv("data/processed/matches.csv", parse_dates=["date"])


def test_treatment_switches_on_in_the_right_season(matches):
    for league, year in EXPECTED_FIRST.items():
        d = matches[matches["league"] == league]
        assert (d.loc[d["season_start"] < year, "treated"] == 0).all()
        assert (d.loc[d["season_start"] >= year, "treated"] == 1).all()


def test_scotland_is_never_treated(matches):
    d = matches[matches["league"] == "Scottish Premiership"]
    assert d["treated"].sum() == 0


def test_scores_are_present_and_valid(matches):
    assert matches[["home_goals", "away_goals"]].notna().all().all()
    assert (matches["total_goals"] >= 0).all()


def test_expected_coverage(matches):
    assert matches["league"].nunique() == 9
    assert matches["season_start"].nunique() == 11