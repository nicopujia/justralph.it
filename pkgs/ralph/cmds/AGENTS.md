# Adding a command

1. Create a module in `cmds/` (e.g. `cmds/foo.py`).
   The filename becomes the subcommand name (`ralph foo`).
2. Define a class that subclasses `Command` (from `cmds/__init__.py`).
3. Set `help` (one-line description for `--help`).
4. If the command needs extra flags, define a config dataclass in the same
   module that inherits from `Config` and set `config = FooConfig` on the class.
5. Implement `run(self) -> None`. Access config via `self.cfg` (set by the
   CLI before `run()` is called).

The CLI auto-discovers every `Command` subclass at startup. No registration
needed.

```python
# cmds/foo.py
from dataclasses import dataclass, field
from ..config import Config
from . import Command

@dataclass
class FooConfig(Config):
    bar: int = field(default=42, metadata={"help": "The bar value"})

class Foo(Command):
    help = "Do the foo thing"
    config = FooConfig
    cfg: FooConfig

    def run(self) -> None:
        print(self.cfg.bar)
```
