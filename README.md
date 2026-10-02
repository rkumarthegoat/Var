# Did VAR change how soccer is played?

A natural experiment across nine European leagues, using football-data.co.uk match results from 2011 to 2012 through 2021 to 2022.

## Question

Leagues adopted video assistant referees (VAR) in different seasons. Did adoption change goals, home advantage, fouls, or cards?

## Result

No detectable effect on goals, home goal margin, or cards. Fouls appear to drop after VAR, but the adopting leagues were already trending down before adoption, so the drop is not credited to VAR. With only nine leagues, the design cannot rule out a moderate effect.

Read the full write up in report.html.

## Method

A stacked difference in differences design, where each adoption year is compared only with leagues that had not yet adopted. Uncertainty is checked with a permutation test that reshuffles which league received which adoption year. Data is processed with pandas, stored and summarized in DuckDB with SQL, and modeled with pyfixest.

## Data notes

Belgium and Greece are excluded because their VAR rollouts were gradual or unclear. Fouls and cards are only available for six of the nine leagues. Penalties are not in the data.

## How to rerun

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_pipeline.py
quarto render report.qmd
pytest
```

## Project layout

src holds the ingestion, cleaning, and analysis code. tests checks the treatment variable. outputs holds the figures and results table.