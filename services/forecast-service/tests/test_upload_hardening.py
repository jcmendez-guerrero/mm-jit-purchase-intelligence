"""T097 (forecast side): file checks before any row is read."""

import io
import zipfile

import pytest
import seed_fixtures as sf
from seeds.storage import SeedFileError, detect_format, sha256_hex
from upload_settings import ParseLimits

L = ParseLimits()


def code(fn):
    with pytest.raises(SeedFileError) as e:
        fn()
    return e.value.code


def test_valid_csv_and_xlsx_are_recognised():
    assert detect_format("datos.csv", sf.static("valid.csv"), L) == "csv"
    assert detect_format("datos.xlsx", sf.valid_xlsx(), L) == "xlsx"


def test_an_oversized_file_is_refused_by_the_size_cap():
    assert code(lambda: detect_format("datos.csv", sf.oversized_csv(L.max_bytes), L)) == "import_file_too_large"


def test_a_file_whose_bytes_do_not_match_its_extension_is_refused():
    assert code(lambda: detect_format("datos.xlsx", sf.wrong_signature_xlsx(), L)) == "import_type_not_allowed"
    assert code(lambda: detect_format("datos.csv", sf.valid_xlsx(), L)) == "import_type_not_allowed"
    assert code(lambda: detect_format("datos.csv", b"a;b\x00\n1;2\n", L)) == "import_type_not_allowed"
    assert code(lambda: detect_format("datos.pdf", b"%PDF-1.4", L)) == "import_type_not_allowed"


def test_macro_workbooks_are_refused_by_part_and_by_extension():
    assert code(lambda: detect_format("datos.xlsx", sf.macro_workbook(), L)) == "import_type_not_allowed"
    assert code(lambda: detect_format("datos.xlsm", sf.valid_xlsx(), L)) == "import_type_not_allowed"
    assert code(lambda: detect_format("datos.xls", b"x", L)) == "import_type_not_allowed"


def test_a_decompression_bomb_is_refused():
    assert code(lambda: detect_format("datos.xlsx", sf.decompression_bomb_xlsx(64), ParseLimits(max_decompressed_bytes=10 * 1024 * 1024))) in ("import_decompression_limit", "import_type_not_allowed")
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/workbook.xml", "<workbook/>")
        zf.writestr("xl/worksheets/sheet1.xml", b"0" * (20 * 1024 * 1024))
    assert code(lambda: detect_format("datos.xlsx", z.getvalue(), L)) == "import_decompression_limit"


def test_the_checksum_is_stable():
    assert sha256_hex(b"abc") == sha256_hex(b"abc") != sha256_hex(b"abd") and len(sha256_hex(b"")) == 64


def _workbook_with(extra_name, extra_content=b"<externalLink/>"):
    import io
    import zipfile

    src = zipfile.ZipFile(io.BytesIO(sf.valid_xlsx()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in src.infolist():
            zf.writestr(item, src.read(item.filename))
        zf.writestr(extra_name, extra_content)
    return out.getvalue()


def test_workbooks_with_external_links_are_refused_by_part():          # MMI-7 FR-004
    assert code(lambda: detect_format("datos.xlsx", _workbook_with("xl/externalLinks/externalLink1.xml"), L)) == "import_type_not_allowed"
    assert code(lambda: detect_format("datos.xlsx", _workbook_with("xl/externalLinks/_rels/externalLink1.xml.rels", b"<Relationships/>"), L)) == "import_type_not_allowed"
    assert detect_format("datos.xlsx", sf.valid_xlsx(), L) == "xlsx"                  # a plain workbook still passes
