# DataFlow — CSV Analysis Pipeline

A lightweight Python web app that lets you upload tabular files, configure parsing parameters, run a multi-step analysis pipeline, and explore an interactive dashboard of charts and statistics.

## Quick Start

```bash
# 1. Install dependencies (already available in most Python environments)
pip install flask pandas numpy matplotlib seaborn

# 2. Run the app
python app.py

# 3. Open in browser
http://localhost:5050
```

## Features

### File Support
- CSV, TSV, TXT (delimited text)
- XLSX / XLS (Excel)
- Multi-file upload (drag & drop or file picker)

### Configurable Parameters
| Parameter | Description |
|---|---|
| Delimiter | Comma, semicolon, tab, pipe, space, or auto-detect |
| Encoding | UTF-8, Latin-1, CP-1252 |
| Decimal separator | Period or comma |
| Skip rows | Skip N header/comment rows |
| Thousands separator | e.g. `_` or `,` in numbers |
| Drop duplicates | Remove exact duplicate rows |
| Drop NA | Remove rows with missing values |
| Fill NA | Replace missing values with a fixed value |
| Normalise | Scale all numeric columns to [0, 1] |

### Pipeline Steps
1. **Load** — Parse files with the configured parameters
2. **Clean** — Handle duplicates and missing values
3. **Transform** — Auto-infer numeric types, optional normalisation
4. **Visualise** — Generate charts (see below)
5. **Summarise** — Compute `.describe()` statistics

### Generated Charts
- Missing-value heatmap
- Distribution histograms (KDE overlay)
- Correlation heatmap
- Box plots
- Top-N bar charts for categorical columns

### Dashboard
- **Dashboard tab** — All charts in a responsive grid, each downloadable as PNG
- **Statistics tab** — Full `.describe()` table for every file
- **Export** — Download results as JSON

## File Structure
```
dataflow/
├── app.py              ← Flask backend + pipeline logic
├── templates/
│   └── index.html      ← Single-page frontend
└── README.md
```

## Extending the Pipeline
Add new steps in `app.py` by defining a `step_*` function and calling it inside the `run()` thread in the `/run` route. Each step receives the `dfs` dict `{filename: DataFrame}` and the `params` dict.
