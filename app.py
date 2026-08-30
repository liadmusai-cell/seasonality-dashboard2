import urllib.request

_URL = "https://raw.githubusercontent.com/liadmusai-cell/seasonality-dashboard2/6fdd675faf7cd2873987911bafd2f95dd9f18ce8/app.py"
_src = urllib.request.urlopen(_URL, timeout=60).read().decode("utf-8")
exec(compile(_src, "app.py", "exec"), globals())
