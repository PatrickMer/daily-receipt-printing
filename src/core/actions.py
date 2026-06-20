"""ESC/POS printer action data model.

Typed dataclasses representing printer actions returned by widgets
and executed by the printer driver.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ESCPOSAction(ABC):
    """Base class for all ESC/POS printer actions."""

    action: str = field(init=False)

    @abstractmethod
    def __post_init__(self) -> None:
        """Subclasses must set self.action."""


@dataclass
class SetAction(ESCPOSAction):
    """Formatting action — maps to printer.set(...)."""

    align: Literal["left", "center", "right"] | None = None
    bold: bool | None = None
    underline: Literal[0, 1, 2] | None = None
    width: int | None = None
    height: int | None = None
    font: Literal["a", "b"] | None = None
    invert: bool | None = None

    def __post_init__(self) -> None:
        self.action = "set"


@dataclass
class TextAction(ESCPOSAction):
    """Print text content — maps to printer.text(txt)."""

    content: str

    def __post_init__(self) -> None:
        self.action = "text"


@dataclass
class FeedAction(ESCPOSAction):
    """Feed paper n lines — maps to printer.print_and_feed(n)."""

    lines: int = 1

    def __post_init__(self) -> None:
        self.action = "feed"


@dataclass
class ImageAction(ESCPOSAction):
    """Print an image from a file path — maps to printer.image(path, ...)."""

    path: str
    center: bool | None = None
    impl: Literal["bitImageRaster", "graphics", "bitImageColumn"] | None = None

    def __post_init__(self) -> None:
        self.action = "image"


@dataclass
class QRAction(ESCPOSAction):
    """Print a QR code — maps to printer.qr(content, ...)."""

    content: str
    size: int | None = None
    native: bool | None = None
    center: bool | None = None

    def __post_init__(self) -> None:
        self.action = "qr"


@dataclass
class BarcodeAction(ESCPOSAction):
    """Print a barcode — maps to printer.barcode(code, bc, ...)."""

    code: str
    bc_type: str
    height: int | None = None
    width: int | None = None
    pos: Literal["ABOVE", "BELOW", "BOTH", "OFF"] | None = None

    def __post_init__(self) -> None:
        self.action = "barcode"


@dataclass
class CutAction(ESCPOSAction):
    """Cut paper — maps to printer.cut(mode)."""

    mode: Literal["FULL", "PART"] = "FULL"

    def __post_init__(self) -> None:
        self.action = "cut"


ActionList = list[ESCPOSAction]
