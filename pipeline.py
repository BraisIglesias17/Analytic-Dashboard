import io
import base64
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from utils import PALETTE,fig_to_b64

class Pipeline():


    def __init__(self,state_lock,pipeline_state):

        self.state_lock=state_lock
        self.pipeline_state=pipeline_state
        
    def log(self,msg):
        with self.state_lock:
            self.pipeline_state["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def set_progress(self,p):
        with self.state_lock:
            self.pipeline_state["progress"] = p


    def step_load_files(self,files, params):
        """Load CSV/TSV/Excel files from uploaded list."""
        self.log(f"Loading {len(files)} file(s)…")
        dfs = {}
        for f in files:
            path = Path(f)
            ext = path.suffix.lower()
            try:
                if ext in (".csv", ".tsv", ".txt"):
                    df = pd.read_csv(
                        f,
                        sep=params["delimiter"] if params["delimiter"] != "auto" else None,
                        engine="python",
                        encoding=params.get("encoding", "utf-8"),
                        skiprows=int(params.get("skip_rows", 0)),
                        decimal=params.get("decimal", "."),
                        thousands=params.get("thousands", None) or None,
                    )
                elif ext in (".xlsx", ".xls"):
                    df = pd.read_excel(f, sheet_name=0)
                else:
                    self.log(f"  ⚠ Skipping unsupported file: {path.name}")
                    continue
                dfs[path.name] = df
                self.log(f"  ✓ {path.name}: {df.shape[0]} rows × {df.shape[1]} cols")
            except Exception as e:
                self.log(f"  ✗ {path.name}: {e}")
        return dfs

    def step_clean(self,dfs, params):
        """Clean dataframes according to parameters."""
        self.log("Cleaning data…")
        cleaned = {}
        for name, df in dfs.items():
            original_rows = len(df)
            if params.get("drop_duplicates"):
                df = df.drop_duplicates()
            if params.get("drop_na"):
                strategy = params.get("na_strategy", "any")
                df = df.dropna(how=strategy)
            elif params.get("fill_na"):
                fill_val = params.get("fill_value", "0")
                try:
                    fill_val = float(fill_val)
                except ValueError:
                    pass
                df = df.fillna(fill_val)
            cleaned[name] = df
            self.log(f"  ✓ {name}: {original_rows} → {len(df)} rows")
        return cleaned

    def step_transform(self,dfs, params):
        """Numeric coercion, type inference, optional normalisation."""
        self.log("Transforming data…")
        transformed = {}
        for name, df in dfs.items():
            # Auto-cast object columns to numeric where possible
            for col in df.select_dtypes(include="object").columns:
                converted = pd.to_numeric(df[col], errors="ignore")
                if converted.dtype != object:
                    df[col] = converted
            # Normalise numeric cols (0-1) if requested
            if params.get("normalize"):
                num_cols = df.select_dtypes(include=np.number).columns
                for col in num_cols:
                    cmin, cmax = df[col].min(), df[col].max()
                    if cmax != cmin:
                        df[col] = (df[col] - cmin) / (cmax - cmin)
            transformed[name] = df
            self.log(f"  ✓ {name}: types inferred, {len(df.select_dtypes(include=np.number).columns)} numeric cols")
        return transformed


    def step_visualise(self,dfs, params):
        """Generate a dashboard of charts for each dataframe."""
        self.log("Generating visualisations…")
        charts = []

        for name, df in dfs.items():
            num_df = df.select_dtypes(include=np.number)
            cat_df = df.select_dtypes(exclude=np.number)

            # ── 1. Missing-value heatmap ──────────────────────────────────────
            fig, ax = plt.subplots(figsize=(10, 3))
            fig.patch.set_facecolor("#0D0D14")
            missing = df.isnull().mean().to_frame().T
            cmap = matplotlib.colors.LinearSegmentedColormap.from_list("miss", ["#1E1E30", "#FF6B6B"])
            sns.heatmap(missing, ax=ax, cmap=cmap, vmin=0, vmax=1,
                        linewidths=0.5, cbar_kws={"label": "Missing ratio"}, annot=True, fmt=".0%")
            ax.set_title(f"{name} — Missing Values", fontsize=13, pad=12, color="#E0E0F0")
            ax.set_ylabel("")
            charts.append({"title": f"{name} — Missing Values", "img": fig_to_b64(fig)})

            if num_df.empty:
                self.log(f"  ⚠ {name}: no numeric columns, skipping distribution charts")
                continue

            # ── 2. Distribution grid ─────────────────────────────────────────
            cols = num_df.columns[:8]
            ncols = min(4, len(cols))
            nrows = (len(cols) + ncols - 1) // ncols
            fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 3.5, nrows * 3))
            fig.patch.set_facecolor("#0D0D14")
            fig.suptitle(f"{name} — Distributions", fontsize=14, color="#E0E0F0", y=1.01)
            axes = np.array(axes).flatten() if nrows * ncols > 1 else [axes]
            for i, col in enumerate(cols):
                ax = axes[i]
                ax.set_facecolor("#13131F")
                color = PALETTE[i % len(PALETTE)]
                sns.histplot(num_df[col].dropna(), ax=ax, color=color, kde=True,
                            line_kws={"lw": 2}, alpha=0.6, bins=30)
                ax.set_title(col, fontsize=9, color="#C0C0D8")
                ax.set_xlabel("")
            for j in range(len(cols), len(axes)):
                axes[j].set_visible(False)
            plt.tight_layout()
            charts.append({"title": f"{name} — Distributions", "img": fig_to_b64(fig)})

            # ── 3. Correlation heatmap ───────────────────────────────────────
            if num_df.shape[1] >= 2:
                fig, ax = plt.subplots(figsize=(min(10, num_df.shape[1] + 2),
                                                min(8, num_df.shape[1] + 1)))
                fig.patch.set_facecolor("#0D0D14")
                corr = num_df.corr()
                mask = np.triu(np.ones_like(corr, dtype=bool))
                cmap = sns.diverging_palette(240, 10, as_cmap=True)
                sns.heatmap(corr, mask=mask, cmap=cmap, center=0, ax=ax,
                            annot=num_df.shape[1] <= 12, fmt=".2f",
                            linewidths=0.5, square=True,
                            cbar_kws={"shrink": 0.8})
                ax.set_title(f"{name} — Correlations", fontsize=13, color="#E0E0F0", pad=12)
                charts.append({"title": f"{name} — Correlations", "img": fig_to_b64(fig)})

            # ── 4. Box plots ─────────────────────────────────────────────────
            if len(cols) > 0:
                fig, ax = plt.subplots(figsize=(max(8, len(cols) * 1.2), 5))
                fig.patch.set_facecolor("#0D0D14")
                ax.set_facecolor("#13131F")
                bp = ax.boxplot([num_df[c].dropna().values for c in cols],
                                patch_artist=True, notch=False,
                                medianprops=dict(color="#FFD166", lw=2),
                                whiskerprops=dict(color="#888899"),
                                capprops=dict(color="#888899"),
                                flierprops=dict(marker="o", color="#FF6B6B", alpha=0.4, ms=3))
                for patch, color in zip(bp["boxes"], PALETTE * 10):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.6)
                ax.set_xticks(range(1, len(cols) + 1))
                ax.set_xticklabels(cols, rotation=30, ha="right", fontsize=9)
                ax.set_title(f"{name} — Box Plots", fontsize=13, color="#E0E0F0", pad=12)
                plt.tight_layout()
                charts.append({"title": f"{name} — Box Plots", "img": fig_to_b64(fig)})

            # ── 5. Top categorical bar charts ────────────────────────────────
            for cat_col in cat_df.columns[:2]:
                vc = df[cat_col].value_counts().head(15)
                fig, ax = plt.subplots(figsize=(8, max(3, len(vc) * 0.45)))
                fig.patch.set_facecolor("#0D0D14")
                ax.set_facecolor("#13131F")
                bars = ax.barh(vc.index.astype(str), vc.values,
                            color=[PALETTE[i % len(PALETTE)] for i in range(len(vc))],
                            alpha=0.85)
                ax.set_xlabel("Count", color="#C0C0D8")
                ax.set_title(f"{name} — {cat_col} (top {len(vc)})", fontsize=12, color="#E0E0F0", pad=10)
                ax.invert_yaxis()
                plt.tight_layout()
                charts.append({"title": f"{name} — {cat_col}", "img": fig_to_b64(fig)})

            self.log(f"  ✓ {name}: {len(charts)} charts generated so far")

        return charts

    def step_summary(self,dfs):
        """Build summary statistics dataframes."""
        self.log("Computing summary statistics…")
        summaries = []
        for name, df in dfs.items():
            desc = df.describe(include="all").round(4).reset_index()
            desc.rename(columns={"index": "stat"}, inplace=True)
            summaries.append({"name": name, "shape": list(df.shape),
                            "columns": list(df.columns),
                            "dtypes": {c: str(t) for c, t in df.dtypes.items()},
                            "describe": desc.to_dict(orient="records")})
            self.log(f"  ✓ {name}: summary ready")
        return summaries