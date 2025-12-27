from src.parser import parse_entry


def test_parse_company_entry() -> None:
    text = """
    Thielen Steuerberater Partnerschaftsgesellschaft
    mit beschraenkter Berufshaftung
    Bahnhofstr. 1
    47574 Goch

    Tel.: 02823 / 97020
    Email: info@thielen-stb.de
    Zustaendige Berufskammer:
    Steuerberaterkammer Duesseldorf
    """

    entry = parse_entry(text)

    assert entry.name.startswith("Thielen Steuerberater")
    assert entry.salutation == ""
    assert entry.role == ""
    assert entry.street == "Bahnhofstr. 1"
    assert entry.plz == "47574"
    assert entry.city == "Goch"
    assert entry.phone == "02823 / 97020"
    assert entry.mobile == ""
    assert entry.email == "info@thielen-stb.de"
    assert entry.chamber == "Steuerberaterkammer Duesseldorf"


def test_parse_person_entry() -> None:
    text = """
    Frau
    Erika Knops
    Steuerberaterin
    Emmericher Weg 10
    47574 Goch

    Tel.: 02823 / 971555
    Email: steuerinfo@stb-knops.de
    Zustaendige Berufskammer:
    Steuerberaterkammer Duesseldorf
    """

    entry = parse_entry(text)

    assert entry.name == "Erika Knops"
    assert entry.salutation == "Frau"
    assert entry.role == "Steuerberaterin"
    assert entry.street == "Emmericher Weg 10"
    assert entry.plz == "47574"
    assert entry.city == "Goch"
    assert entry.phone == "02823 / 971555"
    assert entry.mobile == ""
    assert entry.email == "steuerinfo@stb-knops.de"
    assert entry.chamber == "Steuerberaterkammer Duesseldorf"


def test_parse_entry_with_mobile() -> None:
    text = """
    Herr
    Max Mustermann
    Steuerberater
    Musterstrasse 123
    12345 Musterstadt

    Tel.: 0123 / 456789
    Mobil: 01517 / 2150719
    Email: max@mustermann.de
    Zustaendige Berufskammer:
    Steuerberaterkammer Musterland
    """

    entry = parse_entry(text)

    assert entry.name == "Max Mustermann"
    assert entry.salutation == "Herr"
    assert entry.role == "Steuerberater"
    assert entry.phone == "0123 / 456789"
    assert entry.mobile == "01517 / 2150719"
    assert entry.email == "max@mustermann.de"
