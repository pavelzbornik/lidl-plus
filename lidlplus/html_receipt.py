from typing import Any
import re

import lxml.html as html


VAT_TYPE_LINE_ENDING_PATTERN = re.compile(r" [A-Z]$")


def parse_html_receipt(date: str, html_receipt: str) -> dict[str, Any]:
    dom = html.document_fromstring(html_receipt)

    receipt = {
        "date": date,
        "itemsLine": [],
    }
    last_item = None
    for node in dom.xpath(r".//span[starts-with(@id, 'purchase_list_line_')]"):
        node_class = node.attrib.get("class", "")
        # Article line
        if node_class == "article":
            # Skip empty or whitespace-only lines
            if not node.text or node.text.strip() == "":
                continue

            art_id = node.attrib.get("data-art-id")
            art_desc = node.attrib.get("data-art-description")
            unit_price = node.attrib.get("data-unit-price")
            tax_type = node.attrib.get("data-tax-type")
            quantity_text = node.attrib.get("data-art-quantity")
            # Some lines (like weight breakdown) may not have all fields
            # Try to parse as much as possible
            item = {
                "artId": art_id,
                "name": art_desc,
                "currentUnitPrice": unit_price if unit_price else None,
                "taxGroupName": tax_type,
                "discounts": [],
            }
            # Quantity/weight
            if quantity_text is not None:
                if "," in quantity_text or "." in quantity_text:
                    item["isWeight"] = True
                    item["quantity"] = quantity_text
                else:
                    item["isWeight"] = False
                    item["quantity"] = quantity_text
            else:
                # Try to extract quantity from text if possible
                item["isWeight"] = False
                item["quantity"] = "1"

            # Try to extract total price from text (last number before tax type)
            text = node.text.strip()
            # e.g. 'Eau de coco            1,49  2    2,98 A T'
            # Only match numbers with at least one digit before and after comma
            m = re.search(r"(\d{1,3}(?:[.,]\d{2})+)\s*[A-Z]", text)
            if m and re.match(r"^\d+[.,]\d+$", m.group(1)):
                item["originalAmount"] = m.group(1).replace(".", ",")
            else:
                # fallback: try to get last float in text
                floats = re.findall(r"\d+,[\d]+", text)
                if floats:
                    item["originalAmount"] = floats[-1]
            last_item = item
            receipt["itemsLine"].append(item)
        # Discount line
        elif node_class.startswith("discount"):
            # Try to extract discount amount and label
            text = node.text.strip()
            # e.g. '-0,60' or 'Rem Eau de coco'
            if text.startswith("-") or text.endswith(",") or re.match(r"-?\d+,\d+", text):
                # Discount amount
                try:
                    amount = parse_float(text.replace("-", ""))
                    if last_item is not None:
                        last_item["discounts"].append({"amount": str(amount).replace(".", ",")})
                except Exception:
                    pass
            elif text:
                # Discount description
                if last_item is not None:
                    # Add as description to last discount if exists, else as new
                    if last_item["discounts"]:
                        last_item["discounts"][-1]["description"] = text
                    else:
                        last_item["discounts"].append({"description": text})
        # Currency line (header)
        elif node_class == "currency":
            receipt["currency"] = {"code": node.text.strip(), "symbol": node.attrib.get("data-currency")}
        # Weight breakdown line (e.g. '1,894 kg x 3,99   EUR/kg')
        elif node.attrib.get("data-art-id") and "kg x" in node.text:
            # Attach to last item if possible
            if last_item is not None:
                last_item["weightBreakdown"] = node.text.strip()
        # Fallback: try to parse lines with price at end and VAT type
        elif not node_class:
            if not node.text:
                continue
            if not VAT_TYPE_LINE_ENDING_PATTERN.search(node.text):
                continue
            # Try to parse name and price
            *name_parts, price = node.text[:-2].split()
            item = {
                "name": " ".join(name_parts),
                "originalAmount": price,
                "isWeight": True,
                "discounts": [],
            }
            last_item = item
            receipt["itemsLine"].append(item)
    return receipt


def parse_float(text: str) -> float:
    return float(text.replace(",", "."))
