from pathlib import Path

_here = Path(__file__).resolve().parent
_src = "\n\n".join((_here / "lab_{}.py".format(i)).read_text(encoding="utf-8") for i in (1, 2, 3, 4))
exec(compile(_src, str(_here / "app.py"), "exec"), globals())
