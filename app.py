import os
import io
import json
import base64
import threading
import traceback
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from flask import Flask, render_template, request, jsonify, send_file
from pipeline import Pipeline

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

# ─── Pipeline state ───────────────────────────────────────────────────────────
pipeline_state = {
    "status": "idle",
    "progress": 0,
    "log": [],
    "results": [],
    "dataframes": [],
    "error": None,
}
state_lock = threading.Lock()

sns.set_style("darkgrid")
plt.rcParams.update({
            "figure.facecolor": "#0D0D14",
            "axes.facecolor": "#13131F",
            "axes.edgecolor": "#2A2A3D",
            "grid.color": "#1E1E30",
            "text.color": "#E0E0F0",
            "axes.labelcolor": "#C0C0D8",
            "xtick.color": "#888899",
            "ytick.color": "#888899",
        })


pipeline=Pipeline(state_lock,pipeline_state)

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_pipeline():
    with state_lock:
        if pipeline_state["status"] == "running":
            return jsonify({"error": "Pipeline already running"}), 409
        pipeline_state.update(status="running", progress=0, log=[],
                               results=[], dataframes=[], error=None)

    files = json.loads(request.form.get("files", "[]"))
    params = json.loads(request.form.get("params", "{}"))

    def run():
        try:
            pipeline.set_progress(5);  
            pipeline.log("▶ Pipeline started")

            dfs = pipeline.step_load_files(files, params)
            if not dfs:
                raise ValueError("No valid files could be loaded.")
            pipeline.set_progress(25)

            dfs = pipeline.step_clean(dfs, params)
            pipeline.set_progress(45)

            dfs = pipeline.step_transform(dfs, params)
            pipeline.set_progress(60)

            charts = pipeline.step_visualise(dfs, params)
            pipeline.set_progress(80)

            summaries = pipeline.step_summary(dfs)
            pipeline.set_progress(95)

            with state_lock:
                pipeline.pipeline_state["results"] = charts
                pipeline.pipeline_state["dataframes"] = summaries
                pipeline.pipeline_state["status"] = "done"
                pipeline.pipeline_state["progress"] = 100
            pipeline.log("✅ Pipeline complete")
        except Exception as e:
            with state_lock:
                pipeline.pipeline_state["status"] = "error"
                pipeline.pipeline_state["error"] = str(e)
            pipeline.log(f"✗ Error: {e}")
            pipeline.log(traceback.format_exc())

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/status")
def status():
    with state_lock:
       
        return jsonify({k: v for k, v in pipeline.pipeline_state.items() if k != "results" and k != "dataframes"})

@app.route("/results")
def results():
    with state_lock:
        print(pipeline.pipeline_state["dataframes"])
        return jsonify({"charts": pipeline.pipeline_state["results"],
                        "dataframes": pipeline.pipeline_state["dataframes"]})

@app.route("/upload", methods=["POST"])
def upload():
    saved = []
    upload_dir = Path("/tmp/dataflow_uploads")
    upload_dir.mkdir(exist_ok=True)
    for f in request.files.getlist("files"):
        dest = upload_dir / f.filename
        f.save(str(dest))
        saved.append(str(dest))
    return jsonify({"paths": saved})

if __name__ == "__main__":
    app.run(debug=True, port=5050, use_reloader=False)
