import urllib.request

_URL = "https://raw.githubusercontent.com/liadmusai-cell/seasonality-dashboard2/6fdd675faf7cd2873987911bafd2f95dd9f18ce8/app.py"
_src = urllib.request.urlopen(_URL, timeout=60).read().decode("utf-8")

# Only value rounding — same trick that fixed the heatmap hover.
_src = _src.replace("z = matrix.values * 100", "z = __import__('numpy').round(matrix.values * 100, 2)")
_src = _src.replace('y=df["avg_return"] * 100,', 'y=__import__("numpy").round(df["avg_return"] * 100, 2),')
_src = _src.replace('y=stats["win_rate"] * 100,', 'y=__import__("numpy").round(stats["win_rate"] * 100, 2),')
_src = _src.replace('x=data["ret"] * 100,', 'x=__import__("numpy").round(data["ret"] * 100, 2),')
_src = _src.replace(
    'hovertemplate="Week %{x}<br>Win rate: %{y:.1f}%<extra></extra>"',
    'hovertemplate="Week %{x}<br>Win rate: %{y:.2f}%<extra></extra>"',
)

exec(compile(_src, "app.py", "exec"), globals())
