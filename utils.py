import io
import base64
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

PALETTE = ["#5B7FFF", "#FF6B6B", "#6BCB77", "#FFD166", "#A685E2", "#06D6A0"]

def fig_to_b64(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        return encoded

