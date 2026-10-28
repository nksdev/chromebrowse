"""Offline tests for table and JSON-LD extraction helpers.

The JavaScript collectors run in a browser, so these tests exercise the
pure-Python halves: ``tables_from_raw`` and ``parse_jsonld``. The DOM-side
behaviour is covered by ``tests/test_live.py``.
"""

from __future__ import annotations

from chromebrowse.extract import parse_jsonld, tables_from_raw
from chromebrowse.models import JsonLdBlock, Table, TableCell


# --------------------------------------------------------------------- tables


def test_tables_from_raw_builds_cells():
    raw = [
        {
            "index": 0,
            "caption": "Prices",
            "headers": ["Name", "Cost"],
            "columns": 2,
            "rows": [
                [
                    {"text": "Name", "header": True, "colspan": 1, "rowspan": 1},
                    {"text": "Cost", "header": True, "colspan": 1, "rowspan": 1},
                ],
                [
                    {"text": "a", "header": False, "colspan": 1, "rowspan": 1},
                    {"text": "1", "header": False, "colspan": 2, "rowspan": 1},
                ],
            ],
        }
    ]
    tables = tables_from_raw(raw)
    assert len(tables) == 1
    table = tables[0]
    assert isinstance(table, Table)
    assert table.caption == "Prices"
    assert table.headers == ["Name", "Cost"]
    assert table.columns == 2
    assert table.rows[0][0] == TableCell(text="Name", header=True, colspan=1, rowspan=1)
    assert table.rows[1][1].colspan == 2


def test_table_data_rows_drops_detected_header():
    raw = [
        {
            "index": 0,
            "headers": ["h"],
            "columns": 1,
            "rows": [
                [{"text": "h", "header": True}],
                [{"text": "v", "header": False}],
            ],
        }
    ]
    table = tables_from_raw(raw)[0]
    assert len(table.data_rows) == 1
    assert table.data_rows[0][0].text == "v"


def test_table_without_header_keeps_all_rows():
    raw = [
        {
            "index": 0,
            "headers": [],
            "columns": 1,
            "rows": [[{"text": "a", "header": False}], [{"text": "b", "header": False}]],
        }
    ]
    table = tables_from_raw(raw)[0]
    assert table.headers == []
    assert len(table.data_rows) == 2


def test_tables_from_raw_tolerates_missing_fields():
    tables = tables_from_raw([{"index": 3, "rows": [[{"text": "x"}]]}])
    assert tables[0].caption == ""
    assert tables[0].columns == 0
    assert tables[0].rows[0][0].colspan == 1


def test_tables_from_raw_empty():
    assert tables_from_raw([]) == []
    assert tables_from_raw(None) == []


def test_table_as_dict_is_json_ready():
    table = tables_from_raw([{"index": 0, "rows": [[{"text": "x", "header": True}]]}])[0]
    payload = table.as_dict()
    assert payload["rows"][0][0]["text"] == "x"
    assert payload["rows"][0][0]["header"] is True


# --------------------------------------------------------------------- jsonld


def test_parse_jsonld_valid_block():
    blocks = parse_jsonld([{"index": 0, "text": '{"@type": "Article", "name": "x"}'}])
    assert len(blocks) == 1
    assert blocks[0].data["@type"] == "Article"
    assert blocks[0].error is None
    assert blocks[0].types == ["Article"]


def test_parse_jsonld_list_of_types():
    blocks = parse_jsonld([{"index": 0, "text": '{"@type": ["A", "B"]}'}])
    assert blocks[0].types == ["A", "B"]


def test_parse_jsonld_array_root_flattens_types():
    raw = '[{"@type": "A"}, {"@type": "B"}]'
    blocks = parse_jsonld([{"index": 0, "text": raw}])
    assert blocks[0].types == ["A", "B"]


def test_parse_jsonld_invalid_block_records_error():
    blocks = parse_jsonld([{"index": 0, "text": "{not json"}])
    assert len(blocks) == 1
    assert blocks[0].data is None
    assert blocks[0].error is not None


def test_parse_jsonld_skips_blank_blocks():
    assert parse_jsonld([{"index": 0, "text": "   "}]) == []


def test_parse_jsonld_keeps_good_blocks_after_bad():
    blocks = parse_jsonld(
        [
            {"index": 0, "text": "{bad"},
            {"index": 1, "text": '{"@type": "Good"}'},
        ]
    )
    assert len(blocks) == 2
    assert blocks[0].error is not None
    assert blocks[1].types == ["Good"]


def test_parse_jsonld_handles_none():
    assert parse_jsonld(None) == []


def test_jsonld_block_as_dict():
    block = JsonLdBlock(index=2, data={"a": 1})
    assert block.as_dict() == {"index": 2, "data": {"a": 1}, "error": None}
