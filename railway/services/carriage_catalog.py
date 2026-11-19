"""Illustrative carriage layouts retained from the original project.

These are synthetic UI fixtures, not certified operator seating or fleet data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class ElementDef:
    nazwa: str
    rzad_od: int
    rzad_do: int
    kolumna_od: int
    kolumna_do: int


@dataclass
class SeatDef:
    numer: str
    rzad: int
    kolumna: int
    numer_przedzialu: int | None
    lokalizacja: str
    czy_przy_stoliku: bool = False
    czy_dla_niepelnosprawnych: bool = False
    czy_dla_rowerzystow: bool = False
    czy_przodem: bool | None = None


@dataclass
class TypWagonuDef:
    id_typu: int
    nazwa: str
    liczba_rzedow: int
    liczba_kolumn: int
    czy_przedzialowy: bool
    builder: Callable[[], tuple[list[ElementDef], list[SeatDef]]]


def _build_open_seats(
    rzad_od: int,
    rzad_do: int,
    kolumny: list[int],
    klasa: int,
    start_comp: int = 1,
    lokalizacja: str = "",
) -> list[SeatDef]:
    """Generuje bezprzedziałowy układ miejsc z wirtualnymi przedziałami PKP IC."""
    seats = []
    comp = start_comp
    for r in range(rzad_od, rzad_do + 1, 2):
        # Rząd A (przodem do kierunku / środek wagonu)
        if r <= rzad_do:
            if klasa == 2 and len(kolumny) >= 4:
                seats.append(
                    SeatDef(
                        f"{comp}5", r, kolumny[0], None, lokalizacja or "okno", czy_przodem=True
                    )
                )
                seats.append(
                    SeatDef(
                        f"{comp}1", r, kolumny[1], None, lokalizacja or "korytarz", czy_przodem=True
                    )
                )
                seats.append(
                    SeatDef(
                        f"{comp}2", r, kolumny[2], None, lokalizacja or "korytarz", czy_przodem=True
                    )
                )
                seats.append(
                    SeatDef(
                        f"{comp}6", r, kolumny[3], None, lokalizacja or "okno", czy_przodem=True
                    )
                )
            else:
                seats.append(
                    SeatDef(
                        f"{comp}5", r, kolumny[0], None, lokalizacja or "okno", czy_przodem=True
                    )
                )
                seats.append(
                    SeatDef(
                        f"{comp}1", r, kolumny[1], None, lokalizacja or "korytarz", czy_przodem=True
                    )
                )
                if len(kolumny) > 2:
                    seats.append(
                        SeatDef(
                            f"{comp}3",
                            r,
                            kolumny[2],
                            None,
                            lokalizacja or "środek",
                            czy_przodem=True,
                        )
                    )

        # Rząd B (tyłem do kierunku)
        r2 = r + 1
        if r2 <= rzad_do:
            if klasa == 2 and len(kolumny) >= 4:
                seats.append(
                    SeatDef(
                        f"{comp}7", r2, kolumny[0], None, lokalizacja or "okno", czy_przodem=False
                    )
                )
                seats.append(
                    SeatDef(
                        f"{comp}3",
                        r2,
                        kolumny[1],
                        None,
                        lokalizacja or "korytarz",
                        czy_przodem=False,
                    )
                )
                seats.append(
                    SeatDef(
                        f"{comp}4",
                        r2,
                        kolumny[2],
                        None,
                        lokalizacja or "korytarz",
                        czy_przodem=False,
                    )
                )
                seats.append(
                    SeatDef(
                        f"{comp}8", r2, kolumny[3], None, lokalizacja or "okno", czy_przodem=False
                    )
                )
            else:
                seats.append(
                    SeatDef(
                        f"{comp}7", r2, kolumny[0], None, lokalizacja or "okno", czy_przodem=False
                    )
                )
                seats.append(
                    SeatDef(
                        f"{comp}2",
                        r2,
                        kolumny[1],
                        None,
                        lokalizacja or "korytarz",
                        czy_przodem=False,
                    )
                )
                if len(kolumny) > 2:
                    seats.append(
                        SeatDef(
                            f"{comp}4",
                            r2,
                            kolumny[2],
                            None,
                            lokalizacja or "środek",
                            czy_przodem=False,
                        )
                    )
        comp += 1
    return seats


def _build_comp_seats(
    rzad_od: int,
    rzad_do: int,
    kolumny: list[int],
    seats_per_comp: int,
    start_comp: int = 1,
    lokalizacja: str = "",
) -> list[SeatDef]:
    """Generuje fizyczne przedziały z 2, 4 lub 6 miejscami w układzie PKP IC."""
    seats = []
    comp = start_comp
    for r in range(rzad_od, rzad_do + 1, 2):
        r1 = r
        r2 = r + 1
        if r2 > rzad_do:
            break  # Przedział wymaga pełnych 2 rzędów siatki

        if seats_per_comp == 6 and len(kolumny) >= 3:
            seats.append(
                SeatDef(
                    f"{comp}1", r1, kolumny[0], comp, lokalizacja or "korytarz", czy_przodem=True
                )
            )
            seats.append(
                SeatDef(f"{comp}3", r1, kolumny[1], comp, lokalizacja or "środek", czy_przodem=True)
            )
            seats.append(
                SeatDef(
                    f"{comp}5",
                    r1,
                    kolumny[2],
                    comp,
                    lokalizacja or "okno",
                    czy_przy_stoliku=True,
                    czy_przodem=True,
                )
            )

            seats.append(
                SeatDef(
                    f"{comp}2", r2, kolumny[0], comp, lokalizacja or "korytarz", czy_przodem=False
                )
            )
            seats.append(
                SeatDef(
                    f"{comp}4", r2, kolumny[1], comp, lokalizacja or "środek", czy_przodem=False
                )
            )
            seats.append(
                SeatDef(
                    f"{comp}6",
                    r2,
                    kolumny[2],
                    comp,
                    lokalizacja or "okno",
                    czy_przy_stoliku=True,
                    czy_przodem=False,
                )
            )

        elif seats_per_comp == 4 and len(kolumny) >= 2:
            seats.append(
                SeatDef(
                    f"{comp}1", r1, kolumny[0], comp, lokalizacja or "korytarz", czy_przodem=True
                )
            )
            seats.append(
                SeatDef(
                    f"{comp}3",
                    r1,
                    kolumny[1],
                    comp,
                    lokalizacja or "okno",
                    czy_przy_stoliku=True,
                    czy_przodem=True,
                )
            )

            seats.append(
                SeatDef(
                    f"{comp}2", r2, kolumny[0], comp, lokalizacja or "korytarz", czy_przodem=False
                )
            )
            seats.append(
                SeatDef(
                    f"{comp}4",
                    r2,
                    kolumny[1],
                    comp,
                    lokalizacja or "okno",
                    czy_przy_stoliku=True,
                    czy_przodem=False,
                )
            )

        elif seats_per_comp == 2 and len(kolumny) >= 1:
            seats.append(
                SeatDef(
                    f"{comp}1", r1, kolumny[0], comp, lokalizacja or "sypialny", czy_przodem=True
                )
            )
            seats.append(
                SeatDef(
                    f"{comp}2", r2, kolumny[0], comp, lokalizacja or "sypialny", czy_przodem=False
                )
            )

        comp += 1
    return seats


# --- BUILDERY WAGONÓW ---


def _build_bezprz_2kl() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 2), ElementDef("bagaż", 14, 15, 1, 2)]
    seats = _build_open_seats(2, 13, [1, 2, 4, 5], 2)
    stoliki = {
        "36",
        "38",
        "32",
        "34",
        "31",
        "33",
        "35",
        "37",
        "46",
        "48",
        "44",
        "42",
        "43",
        "41",
        "45",
        "47",
    }
    for s in seats:
        s.czy_przy_stoliku = s.numer in stoliki
    return el, seats


def _build_bezprz_1kl() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 1), ElementDef("bagaż", 12, 12, 4, 4)]
    seats = _build_open_seats(2, 11, [1, 2, 4], 1)
    stoliki = {"33", "31", "35", "34", "32", "37"}
    for s in seats:
        s.czy_przy_stoliku = s.numer in stoliki
    return el, seats


def _build_przedz_2kl() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [
        ElementDef("toaleta", 1, 1, 1, 1),
        ElementDef("toaleta", 18, 18, 5, 5),
        ElementDef("korytarz", 2, 17, 1, 2),
    ]
    seats = _build_comp_seats(2, 17, [3, 4, 5], 6)
    for s in seats:
        s.czy_przy_stoliku = False
    return el, seats


def _build_przedz_1kl_biz() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 1), ElementDef("korytarz", 2, 13, 1, 2)]
    seats = _build_comp_seats(2, 13, [3, 4], 4)
    for s in seats:
        s.czy_przy_stoliku = True
    return el, seats


def _build_wars() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("kuchnia", 1, 5, 1, 5), ElementDef("bar", 6, 7, 1, 5)]
    seats = _build_open_seats(8, 13, [1, 2, 4, 5], 2, start_comp=1, lokalizacja="stolik_wars")
    for s in seats:
        s.czy_przy_stoliku = True
        s.czy_przodem = None
    return el, seats


def _build_rowerowy() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 2), ElementDef("rowery", 12, 15, 1, 5)]
    seats = _build_open_seats(2, 11, [1, 2, 4, 5], 2)
    for s in seats:
        if s.kolumna in {1, 5}:
            s.czy_dla_rowerzystow = True
    return el, seats


def _build_cisza() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 2)]
    seats = _build_open_seats(2, 15, [1, 2, 4, 5], 2)
    for s in seats:
        s.czy_przodem = None
    return el, seats


def _build_prm() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta_PRM", 1, 3, 1, 5), ElementDef("strefa_PRM", 10, 12, 1, 5)]
    seats = _build_open_seats(4, 9, [1, 2, 4, 5], 2, lokalizacja="prm")
    for s in seats:
        s.czy_dla_niepelnosprawnych = True
    return el, seats


def _build_vip() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [
        ElementDef("toaleta", 1, 1, 1, 1),
        ElementDef("lounge", 10, 10, 1, 4),
        ElementDef("korytarz", 2, 9, 1, 2),
    ]
    seats = _build_comp_seats(2, 9, [3, 4], 4, lokalizacja="vip")
    for s in seats:
        s.czy_przy_stoliku = True
    return el, seats


def _build_rodzinny() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("strefa_dzieci", 1, 3, 1, 5)]
    seats = _build_open_seats(4, 15, [1, 2, 4, 5], 2, lokalizacja="rodzinne")
    for s in seats:
        s.czy_przy_stoliku = True
    return el, seats


def _build_sleeper_couchette() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 5), ElementDef("korytarz", 2, 11, 1, 3)]
    seats = _build_comp_seats(2, 11, [4, 5], 4, lokalizacja="kuszetka")
    for s in seats:
        s.czy_przy_stoliku = False
    return el, seats


def _build_sleeper_wagon() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("prysznic", 1, 2, 1, 4), ElementDef("korytarz", 3, 10, 1, 2)]
    seats = _build_comp_seats(3, 10, [3, 4], 2, lokalizacja="sypialny")
    return el, seats


def _build_minibar() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("minibar", 1, 2, 1, 5), ElementDef("toaleta", 13, 13, 1, 2)]
    seats = _build_open_seats(3, 12, [1, 2, 4, 5], 2)
    for s in seats:
        s.czy_przy_stoliku = s.numer.startswith("3")
    return el, seats


def _build_sleeper_6() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 1), ElementDef("korytarz", 2, 13, 1, 2)]
    seats = _build_comp_seats(2, 13, [3, 4, 5], 6, lokalizacja="kuszetka")
    for s in seats:
        s.czy_przy_stoliku = False
    return el, seats


def _build_bezprz_2kl_klim() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [
        ElementDef("toaleta", 1, 1, 1, 2),
        ElementDef("bagaż", 8, 8, 1, 2),
        ElementDef("bagaż", 8, 8, 4, 5),
    ]
    seats_p1 = _build_open_seats(2, 7, [1, 2, 4, 5], 2, start_comp=1)
    seats_p2 = _build_open_seats(9, 14, [1, 2, 4, 5], 2, start_comp=4)
    seats = seats_p1 + seats_p2
    for s in seats:
        if s.rzad in {6, 7, 9, 10}:
            s.czy_przy_stoliku = True
    return el, seats


def _build_przedz_1kl_open() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 1)]
    seats = _build_open_seats(2, 11, [1, 2, 4], 1)
    return el, seats


def _build_eip_1kl() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 1), ElementDef("przedział menedżerski", 2, 4, 1, 4)]
    seats = _build_open_seats(5, 12, [1, 2, 4], 1, start_comp=3)
    for s in seats:
        if s.rzad in {5, 6, 7, 8}:
            s.czy_przy_stoliku = True
    return el, seats


def _build_eip_2kl() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 2), ElementDef("bagaż", 14, 15, 1, 5)]
    seats = _build_open_seats(2, 13, [1, 2, 4, 5], 2)
    return el, seats


def _build_tlk_2kl() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [
        ElementDef("toaleta", 1, 1, 1, 1),
        ElementDef("bagaż", 17, 18, 1, 5),
        ElementDef("korytarz", 2, 16, 1, 2),
    ]
    seats = _build_comp_seats(2, 15, [3, 4, 5], 6)
    for s in seats:
        s.czy_przy_stoliku = False
    return el, seats


def _build_bezprz_2kl_legacy() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 2)]
    seats = _build_open_seats(2, 15, [1, 2, 4, 5], 2)
    return el, seats


def _build_barowy_siedzący() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("bar", 1, 8, 1, 5)]
    seats = _build_open_seats(9, 12, [1, 2, 4, 5], 2, start_comp=5, lokalizacja="bar")
    for s in seats:
        s.czy_przodem = None
    return el, seats


def _build_kombinowany_rower() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("rowery", 10, 14, 1, 5), ElementDef("toaleta", 1, 1, 4, 5)]
    seats = _build_open_seats(2, 9, [1, 2, 4, 5], 2)
    for s in seats:
        if s.kolumna in {1}:
            s.czy_dla_rowerzystow = True
    return el, seats


def _build_ic_night_seat() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 2), ElementDef("korytarz", 2, 15, 1, 2)]
    seats = _build_comp_seats(2, 15, [3, 4, 5], 6, lokalizacja="siedzący_nocny")
    for s in seats:
        s.czy_przy_stoliku = False
    return el, seats


def _build_ec_1kl() -> tuple[list[ElementDef], list[SeatDef]]:
    el = [ElementDef("toaleta", 1, 1, 1, 1)]  # USUNIĘTO: Kompartiment
    seats = _build_open_seats(2, 11, [1, 2, 4], 1)
    return el, seats


# --- LISTA WAGONÓW ---
TYPY_WAGONOW: list[TypWagonuDef] = [
    TypWagonuDef(1, "Bezprzedziałowy 2 kl. (standard)", 15, 5, False, _build_bezprz_2kl),
    TypWagonuDef(2, "Bezprzedziałowy 1 kl. (komfort)", 12, 4, False, _build_bezprz_1kl),
    TypWagonuDef(3, "Przedziałowy 2 kl. (klasyczny)", 18, 5, True, _build_przedz_2kl),
    TypWagonuDef(4, "Przedziałowy 1 kl. (biznes)", 14, 4, True, _build_przedz_1kl_biz),
    TypWagonuDef(5, "Wagon restauracyjny (WARS)", 14, 5, False, _build_wars),
    TypWagonuDef(6, "Bezprzedziałowy 2 kl. + rowery", 15, 5, False, _build_rowerowy),
    TypWagonuDef(7, "Strefa ciszy", 16, 5, False, _build_cisza),
    TypWagonuDef(8, "Wagon PRM", 12, 5, False, _build_prm),
    TypWagonuDef(9, "Przedziałowy premium (1 kl.)", 10, 4, True, _build_vip),
    TypWagonuDef(10, "Strefa rodzinna", 16, 5, False, _build_rodzinny),
    TypWagonuDef(11, "Kuszetka 4-os.", 12, 5, True, _build_sleeper_couchette),
    TypWagonuDef(12, "Sypialny 1-os.", 10, 4, True, _build_sleeper_wagon),
    TypWagonuDef(13, "Bezprzedziałowy 1 kl. + minibar", 13, 5, False, _build_minibar),
    TypWagonuDef(14, "Kuszetka 6-os.", 14, 5, True, _build_sleeper_6),
    TypWagonuDef(15, "Bezprzedziałowy 2 kl. (klimatyzacja)", 15, 5, False, _build_bezprz_2kl_klim),
    TypWagonuDef(16, "1 kl. open space", 11, 4, False, _build_przedz_1kl_open),
    TypWagonuDef(17, "EIP – 1 kl.", 12, 4, False, _build_eip_1kl),
    TypWagonuDef(18, "EIP – 2 kl.", 15, 5, False, _build_eip_2kl),
    TypWagonuDef(20, "TLK – przedziałowy 2 kl.", 18, 5, True, _build_tlk_2kl),
    TypWagonuDef(21, "TLK – bezprzedziałowy 2 kl.", 16, 5, False, _build_bezprz_2kl_legacy),
    TypWagonuDef(22, "Wagon barowy (siedzący)", 12, 5, False, _build_barowy_siedzący),
    TypWagonuDef(23, "Kombinowany rowerowy", 14, 5, False, _build_kombinowany_rower),
    TypWagonuDef(24, "Nocny siedzący IC", 16, 5, True, _build_ic_night_seat),
    TypWagonuDef(25, "EuroCity – 1 kl.", 12, 4, False, _build_ec_1kl),
]

TYPY_BY_ID = {t.id_typu: t for t in TYPY_WAGONOW}

SZABLONY_SKLADOW: dict[str, list[list[int]]] = {
    "EIP": [[18, 18, 17, 7, 5, 18, 17], [18, 17, 5, 7, 18, 18], [18, 18, 17, 17, 5, 18]],
    "EIC": [[25, 4, 5, 3, 3, 2], [25, 4, 5, 7, 3, 2, 1], [4, 5, 3, 3, 2, 9]],
    "IC": [[2, 8, 5, 6, 1, 10], [15, 8, 5, 6, 3, 1], [2, 7, 5, 6, 6, 1, 10], [2, 8, 13, 5, 1]],
    "TLK": [[20, 20, 3, 3, 21], [21, 20, 3, 3, 3, 20], [20, 3, 3, 3, 21, 6]],
    "EC": [[25, 4, 5, 6, 1, 1], [25, 4, 5, 3, 3, 2]],
    "EN": [[4, 3, 3, 3, 11, 3], [11, 3, 3, 3, 4]],
    "ICN": [[24, 11, 3, 3, 1], [24, 11, 11, 3, 1]],
    "IC/MP": [[4, 5, 3, 3, 1, 8], [4, 5, 7, 3, 1]],
    "EN/IC": [[4, 3, 3, 11, 3], [11, 3, 3, 4]],
    "EC/IC/ICN": [[25, 4, 5, 3, 24, 1], [25, 4, 5, 3, 3, 1]],
    "IC+": [[17, 5, 1, 1, 18], [2, 5, 17, 1, 1]],
    "EC/EIC": [[25, 4, 5, 3, 3, 2], [25, 4, 5, 7, 3, 2]],
    "EC/IC": [[25, 4, 5, 3, 1, 8], [4, 5, 3, 3, 1]],
}

KATEGORIE_DOZWOLONE = set(SZABLONY_SKLADOW.keys())


def normalizuj_kategorie(kat_raw: str) -> str | None:
    if not kat_raw:
        return None
    kat = kat_raw.strip().upper()
    if kat in KATEGORIE_DOZWOLONE:
        return kat
    if "_" in kat:
        pierwsza = kat.split("_")[0]
        if pierwsza in KATEGORIE_DOZWOLONE:
            return pierwsza
    zamiany = {"IC_IC": "IC", "IC_TLK": "TLK", "TLK_IC": "TLK"}
    return zamiany.get(kat)


def wybierz_szablon_skladu(kategoria: str, seed: int) -> list[int]:
    warianty = SZABLONY_SKLADOW.get(kategoria, [[2, 3, 3, 3, 1]])
    return warianty[seed % len(warianty)]
