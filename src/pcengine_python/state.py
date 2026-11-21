"""Save states: the whole console between two instructions, as bytes, and back.

The same design as famicom-python's `state.py` (the family's first), adapted to this board and
its add-ons.

A save state is everything that changes as the console runs: the CPU (huc6280-python's
`CPUState`), the board's clock and lines, the VDCs, the VCE, the PSG, the timer and the interrupt
registers, work RAM, the card's mapper and its RAM, the capture and the mixer, and whatever an
add-on has plugged in (the SuperGrafx's VPC, the CD unit). It is *not* the wiring: a state is
loaded into a `System` built the same way (the same machine row, the same card, the same add-on),
which already holds the configuration, the callables that connect the parts and the references
between them. Loading writes the saved values into that system's objects, in place, so the
references stay as they were built.

**What is saved**, by walking the object graph from the board: every attribute of an object whose
class belongs to a registered package (`pcengine_python`; an add-on calls `register_package` when
it is imported), depth first in attribute order, as plain data. Not saved:

- callables (the hold line, the interrupt callbacks, a frame observer): wiring;
- objects whose class sets `STATE_FIXED = True` (media: a disc and its open files); if such an
  object has `state_identity()`, that string is saved in its place and loading refuses a system
  whose object there answers otherwise (a state of another disc);
- the CPU object (its `capture_state` is saved instead);
- (a frozen dataclass is saved by value: a line's `VideoTiming` is state; the `Machine` row is
  not, but it is small, and loading keeps the system's own object where the value is equal);
- a second path to an object already saved (the page table names every device; `Board.vdc` is
  `Board.vdcs[0]`): it is written as a reference;
- ROM bytes: an immutable `bytes` attribute of `ROM_BYTES` or more is written as its SHA-1 and
  length only, and loading refuses a system whose attribute there holds other bytes. That is how a
  state of another card (or another System Card) is recognised: BYOR, no ROM byte is in a state.

**The format** is zlib-compressed JSON: a header (format, version, the machine's name, the
packages whose classes the state names) and the encoded graph, each value tagged by type. It holds
no code: loading creates nothing but the registered packages' own classes and plain data.

**Equivalence** is the test (tests/test_state.py, scripts/state_roundtrip.py): a run saved at
some instruction boundary and loaded into a fresh system continues exactly as the run that was
never interrupted, bus cycle for bus cycle.
"""

from __future__ import annotations

import base64
import dataclasses
import enum
import hashlib
import importlib
import json
import zlib
from array import array
from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pcengine_python.system import System

FORMAT = "pcengine-python state"
VERSION = 1
#: Top-level packages whose objects are part of the state. Add-ons add theirs (register_package).
PACKAGES = {"pcengine_python"}
#: Attributes that are not state, by name (none needed so far beyond the rules above).
SKIPPED: set[str] = set()
#: An immutable `bytes` at least this long is a ROM image: saved as its SHA-1, never its content.
ROM_BYTES = 0x2000


class StateError(ValueError):
    """A state that cannot be loaded into this system."""


def register_package(name: str) -> None:
    """Make an add-on's classes part of the state (call it from the add-on's `__init__`)."""
    PACKAGES.add(name)


def _ours(value: object) -> bool:
    return type(value).__module__.split(".", 1)[0] in PACKAGES


def _fixed(value: object) -> bool:
    """Media or wiring that is an object: its class says STATE_FIXED."""
    return bool(getattr(type(value), "STATE_FIXED", False))


def _frozen(value: object) -> bool:
    """A frozen dataclass: an immutable value (a line's `VideoTiming`, the `Machine` row)."""
    params = getattr(type(value), "__dataclass_params__", None)
    return dataclasses.is_dataclass(value) and params is not None and params.frozen


def _wiring(value: object) -> bool:
    return callable(value) and not _ours(value)  # a function, a lambda or a bound method


def _attributes(value: object) -> dict[str, Any]:
    """An object's instance attributes: `__dict__`, or the slots of a slotted class."""
    if hasattr(value, "__dict__"):
        return vars(value)
    names = [name for cls in type(value).__mro__ for name in getattr(cls, "__slots__", ())]
    return {name: getattr(value, name) for name in names if hasattr(value, name)}


def _qualified(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def _rom(value: bytes) -> dict:
    return {"rom": hashlib.sha1(value).hexdigest(), "length": len(value)}


class _Encoder:
    def __init__(self, cpu: object) -> None:
        self.seen: dict[int, str] = {}
        self.cpu = cpu
        self.packages: set[str] = set()  # the registered packages the state names

    def value(self, value: Any, path: str) -> Any:
        if value is None or isinstance(value, (bool, str, float)):
            return value
        if isinstance(value, enum.Enum):
            self.packages.add(type(value).__module__.split(".", 1)[0])
            return {"enum": _qualified(type(value)), "name": value.name}
        if isinstance(value, int):
            return value
        if isinstance(value, bytes):
            if len(value) >= ROM_BYTES:
                return _rom(value)
            return {"bytes": base64.b64encode(value).decode()}
        if isinstance(value, bytearray):
            return {"bytearray": base64.b64encode(value).decode()}
        if isinstance(value, array):
            return {"array": value.typecode, "data": base64.b64encode(value.tobytes()).decode()}
        if isinstance(value, list):
            return [self.value(item, f"{path}[{i}]") for i, item in enumerate(value)]
        if isinstance(value, deque):
            items = [self.value(item, f"{path}[{i}]") for i, item in enumerate(value)]
            return {"deque": items, "maxlen": value.maxlen}
        if isinstance(value, tuple):
            return {"tuple": [self.value(item, f"{path}[{i}]") for i, item in enumerate(value)]}
        if isinstance(value, (set, frozenset)):
            return {"set": sorted(self.value(item, path) for item in value)}
        if isinstance(value, dict):
            pairs = [
                [self.value(k, path), self.value(v, f"{path}[{k!r}]")] for k, v in value.items()
            ]
            return {"dict": pairs}
        if _ours(value) and _frozen(value):
            self.packages.add(type(value).__module__.split(".", 1)[0])
            fields = {
                f.name: self.value(getattr(value, f.name), f"{path}.{f.name}")
                for f in dataclasses.fields(value)  # type: ignore[arg-type]
            }
            return {"value": _qualified(type(value)), "fields": fields}
        if _ours(value) and not _fixed(value):
            if id(value) in self.seen:
                return {"ref": self.seen[id(value)]}
            self.seen[id(value)] = path
            return self.object(value, path)
        raise StateError(f"{path}: cannot save a {type(value).__qualname__}")

    def object(self, value: object, path: str) -> dict:
        fields = {}
        wired = False  # it holds wiring a state cannot give back: only an existing object will do
        for name, attribute in _attributes(value).items():
            if name in SKIPPED:
                continue
            if _fixed(attribute) and hasattr(attribute, "state_identity"):
                fields[name] = {"fixed": attribute.state_identity()}
                continue
            if attribute is self.cpu or _fixed(attribute) or _wiring(attribute):
                wired = True
                continue
            if isinstance(attribute, type):
                continue
            if (
                isinstance(attribute, (list, tuple))
                and attribute
                and all(_wiring(item) for item in attribute)
            ):
                wired = True
                continue  # a list of callables: wiring
            fields[name] = self.value(attribute, f"{path}.{name}")
        self.packages.add(type(value).__module__.split(".", 1)[0])
        out = {"object": _qualified(type(value)), "fields": fields}
        if wired:
            out["wired"] = True
        return out


def save_state(system: System) -> bytes:
    """The state of `system` as bytes (between two of its steps)."""
    board = system.board
    encoder = _Encoder(system.cpu)
    encoded = encoder.value(board, "board")
    body = {
        "format": FORMAT,
        "version": VERSION,
        "machine": board.machine.name,
        "packages": sorted(encoder.packages),
        "cpu": dataclasses.asdict(system.cpu.capture_state()),  # type: ignore[attr-defined]
        "board": encoded,
    }
    return zlib.compress(json.dumps(body, separators=(",", ":")).encode(), 6)


class _Decoder:
    """Applies an encoded graph to a system, in place where it can.

    The encoder writes each object once, at the first path that reaches it, and a reference at
    every later one. The decoder walks in the same order, keeps each object it restores by that
    path, and gives a reference the object restored there, so sharing is as it was saved. An
    existing object is updated in place only by the first path that claims it; another path saved
    with an object of its own gets a new one. A new object is only ever a value, which here
    means a dataclass without wiring (a captured frame, a mixer lane): any other object the system
    does not already hold at that place means it was built another way (no Arcade Card, no CD
    unit), and the state is refused.
    """

    def __init__(self) -> None:
        self.objects: dict[str, object] = {}  # restored objects by their saved path
        self.claimed: set[int] = set()  # existing objects already updated
        self.created: set[int] = set()  # objects built here: values with no wiring

    def fresh(self, encoded: Any, path: str) -> Any:
        """A value built from `encoded` with nothing to update in place."""
        if encoded is None or isinstance(encoded, (bool, int, str, float)):
            return encoded
        if isinstance(encoded, list):
            return [self.fresh(item, f"{path}[{i}]") for i, item in enumerate(encoded)]
        if "ref" in encoded:
            return self.reference(encoded)
        if "enum" in encoded:
            return _class(encoded["enum"])[encoded["name"]]
        if "bytes" in encoded:
            return base64.b64decode(encoded["bytes"])
        if "bytearray" in encoded:
            return bytearray(base64.b64decode(encoded["bytearray"]))
        if "array" in encoded:
            out = array(encoded["array"])
            out.frombytes(base64.b64decode(encoded["data"]))
            return out
        if "rom" in encoded:
            raise StateError(f"{path}: the state names ROM bytes this system does not hold there")
        if "deque" in encoded:
            items = [self.fresh(item, f"{path}[{i}]") for i, item in enumerate(encoded["deque"])]
            return deque(items, encoded["maxlen"])
        if "tuple" in encoded:
            items = encoded["tuple"]
            return tuple(self.fresh(item, f"{path}[{i}]") for i, item in enumerate(items))
        if "set" in encoded:
            return {self.fresh(item, path) for item in encoded["set"]}
        if "dict" in encoded:
            out = {}
            for k, v in encoded["dict"]:
                key = self.fresh(k, path)
                out[key] = self.fresh(v, f"{path}[{key!r}]")
            return out
        if "value" in encoded:
            fields = {k: self.fresh(v, f"{path}.{k}") for k, v in encoded["fields"].items()}
            return _class(encoded["value"])(**fields)
        if "object" in encoded:
            cls = _class(encoded["object"])
            if encoded.get("wired") or not dataclasses.is_dataclass(cls):
                raise StateError(
                    f"{path}: the state has a {cls.__qualname__} there and this system does not "
                    "(a machine built another way?)"
                )
            obj = cls.__new__(cls)
            self.created.add(id(obj))
            self.objects[path] = obj
            for name, value in encoded["fields"].items():
                setattr(obj, name, self.fresh(value, f"{path}.{name}"))
            return obj
        raise StateError(f"cannot load {str(encoded)[:80]}")

    def reference(self, encoded: dict) -> object:
        try:
            return self.objects[encoded["ref"]]
        except KeyError:
            raise StateError(f"a reference to nothing saved: {encoded['ref']}") from None

    def into(self, current: Any, encoded: Any, path: str) -> Any:
        """`encoded` applied to `current`: updated in place where it is an object (or a container
        of objects) of the same shape not yet claimed, else built fresh. Returns the value the
        attribute should hold."""
        if isinstance(encoded, dict) and "ref" in encoded:
            target = self.reference(encoded)
            if id(target) in self.created and _ours(current) and type(current) is not type(target):
                raise StateError(
                    f"{path}: the state has a {type(target).__qualname__} there and this system a "
                    f"{type(current).__qualname__} (a machine built another way?)"
                )
            return target
        if isinstance(encoded, dict) and "rom" in encoded:
            if not isinstance(current, bytes) or _rom(current) != encoded:
                raise StateError(f"{path}: a state of another ROM image (another card?)")
            return current
        if isinstance(encoded, dict) and "fixed" in encoded:
            identity = getattr(current, "state_identity", lambda: None)()
            if identity != encoded["fixed"]:
                raise StateError(f"{path}: a state made with other media (another disc?)")
            return current
        if isinstance(encoded, dict) and "value" in encoded:
            value = self.fresh(encoded, path)
            return current if value == current else value  # an equal value keeps its identity
        if isinstance(encoded, dict) and "object" in encoded:
            if (
                _ours(current)
                and _qualified(type(current)) == encoded["object"]
                and id(current) not in self.claimed
            ):
                self.claimed.add(id(current))
                self.objects[path] = current
                self.apply(current, encoded["fields"], path)
                return current
            return self.fresh(encoded, path)
        if isinstance(encoded, list) and isinstance(current, list) and len(current) == len(encoded):
            for i, item in enumerate(encoded):
                current[i] = self.into(current[i], item, f"{path}[{i}]")
            return current
        if isinstance(encoded, dict) and "tuple" in encoded and isinstance(current, tuple):
            items = encoded["tuple"]
            if len(items) == len(current):
                return tuple(
                    self.into(c, e, f"{path}[{i}]")
                    for i, (c, e) in enumerate(zip(current, items, strict=True))
                )
        if isinstance(encoded, dict) and "dict" in encoded and isinstance(current, dict):
            out = {}
            for k, v in encoded["dict"]:
                key = self.fresh(k, path)
                out[key] = self.into(current.get(key), v, f"{path}[{key!r}]")
            return out
        return self.fresh(encoded, path)

    def apply(self, obj: object, fields: dict, path: str) -> None:
        for name, encoded in fields.items():
            setattr(obj, name, self.into(getattr(obj, name, None), encoded, f"{path}.{name}"))


def _class(name: str) -> type:
    """A class of a registered package by its qualified name."""
    module, _, qualname = name.rpartition(".")
    while module and module.split(".", 1)[0] in PACKAGES:
        try:
            found: Any = importlib.import_module(module)
        except ModuleNotFoundError:
            module, _, outer = module.rpartition(".")
            qualname = f"{outer}.{qualname}"
            continue
        for part in qualname.split("."):
            found = getattr(found, part)
        if isinstance(found, type):
            return found
        break
    raise StateError(f"not a class a state may hold: {name}")


def load_state(system: System, data: bytes) -> None:
    """Put `system` in the state `data` was saved from (the same machine, card and add-on).

    A state that is refused for its header leaves the system untouched; one refused further in
    (another card's ROM) may have written part of itself, and the system should be rebuilt."""
    try:
        body = json.loads(zlib.decompress(data))
    except (zlib.error, ValueError) as error:
        raise StateError(f"not a save state: {error}") from None
    if not isinstance(body, dict) or body.get("format") != FORMAT:
        raise StateError(f"not a {FORMAT}")
    if body.get("version") != VERSION:
        raise StateError(f"a {FORMAT} of version {body.get('version')}, not {VERSION}")
    board = system.board
    if body["machine"] != board.machine.name:
        raise StateError(f"a state of the {body['machine']}, not the {board.machine.name}")
    missing = set(body["packages"]) - PACKAGES
    if missing:
        raise StateError(f"a state that needs {', '.join(sorted(missing))}: import the add-on")
    cpu: Any = system.cpu
    cpu_state = type(cpu.capture_state())(**body["cpu"])
    _Decoder().into(board, body["board"], "board")
    cpu.restore_state(cpu_state)
