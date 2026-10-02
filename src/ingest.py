from pathlib import Path
import requests

LEAGUES = ["E0", "D1", "I1", "SP1", "F1", "SC0", "N1", "P1", "T1"]
SEASONS = ["1112", "1213", "1314", "1415", "1516", "1617",
           "1718", "1819", "1920", "2021", "2122"]
RAW = Path("data/raw")


def download_all():
    RAW.mkdir(parents=True, exist_ok=True)
    for league in LEAGUES:
        for season in SEASONS:
            dest = RAW / f"{league}_{season}.csv"
            if dest.exists():
                continue
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                dest.write_bytes(r.content)
            else:
                print(f"Failed {league} {season} ({r.status_code})")


if __name__ == "__main__":
    download_all()
    print(len(list(RAW.glob("*.csv"))), "files downloaded")