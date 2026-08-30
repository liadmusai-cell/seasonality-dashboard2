import urllib.request
import numpy as np

_URL = "https://raw.githubusercontent.com/liadmusai-cell/seasonality-dashboard2/6fdd675faf7cd2873987911bafd2f95dd9f18ce8/app.py"
_src = urllib.request.urlopen(_URL, timeout=60).read().decode("utf-8")

# Heatmap values
_src = _src.replace("z = matrix.values * 100", "z = np.round(matrix.values * 100, 2)")

# Main seasonality bars
_src = _src.replace('y=df["avg_return"] * 100,', 'y=np.round(df["avg_return"] * 100, 2),')
_src = _src.replace(
    '"Win rate: %{customdata[3]:.1f}%<br>"',
    '"Win rate: %{customdata[3]:.2f}%<br>"',
)
_src = _src.replace(
    'yaxis=dict(title="Average return (%)", gridcolor="#1e293b", zeroline=False)',
    'yaxis=dict(title="Average return (%)", gridcolor="#1e293b", zeroline=False, hoverformat=".2f", tickformat=".2f")',
)

# Win-rate bars
_src = _src.replace('y=stats["win_rate"] * 100,', 'y=np.round(stats["win_rate"] * 100, 2),')
_src = _src.replace(
    'hovertemplate="Week %{x}<br>Win rate: %{y:.1f}%<extra></extra>"',
    'hovertemplate="Week %{x}<br>Win rate: %{y:.2f}%<extra></extra>"',
)
_src = _src.replace(
    'yaxis=dict(title="Win rate (%)", gridcolor="#1e293b", range=[0, 100])',
    'yaxis=dict(title="Win rate (%)", gridcolor="#1e293b", range=[0, 100], hoverformat=".2f", tickformat=".2f")',
)

# Return distribution histogram
_src = _src.replace('x=data["ret"] * 100,', 'x=np.round(data["ret"] * 100, 2),')
_src = _src.replace(
    '            name="Weekly return",',
    '            name="Weekly return",\n            hovertemplate="Return: %{x:+.2f}%<br>Count: %{y:.0f}<extra></extra>",',
)
_src = _src.replace(
    'xaxis=dict(title="Weekly return (%)", gridcolor="#1e293b")',
    'xaxis=dict(title="Weekly return (%)", gridcolor="#1e293b", hoverformat=".2f", tickformat=".2f")',
)

# Stop Plotly from also showing the raw unformatted y-value
_src = _src.replace(
    "fig.update_layout(\n        **PLOTLY_LAYOUT,",
    "fig.update_layout(\n        hovermode=\"closest\",\n        **PLOTLY_LAYOUT,",
)

exec(compile(_src, "app.py", "exec"), globals())
