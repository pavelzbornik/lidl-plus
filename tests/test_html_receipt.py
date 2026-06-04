"""Tests for the HTML receipt parser (lidlplus.html_receipt). All offline."""

from lidlplus.html_receipt import parse_float, parse_html_receipt

# A single article with a coupon discount. The currency span needs visible text
# (empty spans are skipped) and the article name is the text before two+ spaces.
BASIC_HTML = """
<html><body>
  <span id="purchase_list_line_0" class="currency" data-currency="EUR">EUR</span>
  <span id="purchase_list_line_1" class="article"
        data-art-id="123" data-unit-price="2,19" data-tax-type="A"
        data-art-quantity="1">Vegane Frikadellen   2,19 A</span>
  <span id="purchase_list_line_2" class="discount">5&#8364; Coupon</span>
  <span id="purchase_list_line_3" class="discount">-0,21</span>
</body></html>
"""

# A weight article: the second "kg x" line is a breakdown of the previous item,
# not a new item, and the comma in the quantity marks it as weight-priced.
WEIGHT_HTML = """
<html><body>
  <span id="purchase_list_line_0" class="currency" data-currency="EUR">EUR</span>
  <span id="purchase_list_line_1" class="article"
        data-art-id="999" data-unit-price="1,99" data-tax-type="B"
        data-art-quantity="0,500">Bananen   0,99 B</span>
  <span id="purchase_list_line_2" class="article">0,500 kg x 1,99 EUR/kg</span>
</body></html>
"""


def test_parse_float_converts_comma_decimal():
    assert parse_float("2,19") == 2.19
    assert parse_float("0,5") == 0.5


def test_parse_basic_receipt():
    receipt = parse_html_receipt("2026-06-04", BASIC_HTML)
    assert receipt["date"] == "2026-06-04"
    assert receipt["currency"] == {"code": "EUR", "symbol": "EUR"}
    assert len(receipt["itemsLine"]) == 1

    item = receipt["itemsLine"][0]
    assert item["artId"] == "123"
    assert item["name"] == "Vegane Frikadellen"
    assert item["currentUnitPrice"] == "2,19"
    assert item["taxGroupName"] == "A"
    assert item["quantity"] == "1"
    assert item["isWeight"] is False
    assert item["originalAmount"] == "2,19"
    assert item["discounts"] == [{"description": "5€ Coupon", "amount": "0,21"}]


def test_parse_weight_item_attaches_breakdown():
    receipt = parse_html_receipt("2026-06-04", WEIGHT_HTML)
    # the "kg x" line must NOT become its own item
    assert len(receipt["itemsLine"]) == 1

    item = receipt["itemsLine"][0]
    assert item["name"] == "Bananen"
    assert item["isWeight"] is True
    assert item["weightBreakdown"] == "0,500 kg x 1,99 EUR/kg"


def test_empty_receipt_has_no_items():
    receipt = parse_html_receipt("2026-06-04", "<html><body></body></html>")
    assert receipt["itemsLine"] == []
    assert receipt["currency"] is None
