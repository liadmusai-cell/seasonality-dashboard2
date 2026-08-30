from pathlib import Path

_here = Path(__file__).resolve().parent
_src = "".join((_here / f"lab_{i}.py").read_text(encoding="utf-8") for i in (1, 2, 3))
exec(compile(_src, "app.py", "exec"), globals())
