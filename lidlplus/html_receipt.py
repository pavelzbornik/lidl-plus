from typing import Any
import re

import lxml.html as html


VAT_TYPE_LINE_ENDING_PATTERN = re.compile(r" [A-Z]$")


def parse_html_receipt(date: str, html_receipt: str) -> dict[str, Any]:
    parser = html.HTMLParser(encoding='utf-8')
    dom = html.fromstring(html_receipt.encode('utf-8'), parser=parser)

    receipt = {
        "date": date,
        "itemsLine": [],
        "currency": None,
    }
    last_item = None

    # This XPath correctly selects all relevant <span> elements in the order they appear.
    for node in dom.xpath(r".//span[starts-with(@id, 'purchase_list_line_')]"):
        node_class = node.attrib.get("class", "")
        # Get the full text content of the node, including text from child nodes
        node_text = "".join(node.itertext()).strip()

        # Skip empty or whitespace-only lines
        if not node_text:
            continue
        
        # Currency line
        if node_class == "currency":
            currency_val = node.attrib.get("data-currency")
            if currency_val:
                # Fix: Use the reliable 'data-currency' attribute for both code and symbol.
                receipt["currency"] = {"code": currency_val, "symbol": currency_val}
        
        # Article line
        elif "article" in node_class:
            # Fix (Duplicate Items): Check for the weight breakdown line, which is a descriptor
            # for the previous item, not a new item itself.
            if "kg x" in node_text:
                if last_item:
                    last_item["weightBreakdown"] = node_text
                continue  # Skip to the next node

            # --- START: ENCODING ISSUE RESOLUTION ---
            # The item name is extracted from the node's text content, which is correctly
            # encoded with HTML entities, unlike the corrupted 'data-art-description' attribute.
            # The name is the initial part of the string, ending before two or more spaces.
            name_match = re.match(r"^(.*?)\s{2,}", node_text)
            
            # Use the matched name. Fall back to the (corrupt) attribute if the pattern fails,
            # ensuring the parser remains robust.
            item_name = name_match.group(1).strip() if name_match else node.attrib.get("data-art-description")
            # --- END: ENCODING ISSUE RESOLUTION ---

            # This is a regular article, so create a new item.
            item = {
                "artId": node.attrib.get("data-art-id"),
                "name": item_name,
                "currentUnitPrice": node.attrib.get("data-unit-price"),
                "taxGroupName": node.attrib.get("data-tax-type"),
                "quantity": node.attrib.get("data-art-quantity", "1"), # Default to 1 if not present
                "discounts": [],
            }
            item["isWeight"] = "," in item["quantity"] or "." in item["quantity"]

            # Extract the total price for the item from the text line.
            # e.g., 'Eau de coco 1,49 2 2,98 A T' -> extract '2,98'
            match = re.search(r'(\d+,\d{2})\s+[A-Z]', node_text)
            if match:
                item["originalAmount"] = match.group(1)
            else:
                # Fallback if the pattern doesn't match
                floats = re.findall(r'\d+,\d+', node_text)
                if floats:
                    item["originalAmount"] = floats[-1]
                else:
                    item["originalAmount"] = None

            receipt["itemsLine"].append(item)
            last_item = item

        # Discount line
        elif "discount" in node_class:
            # A discount must be associated with the last item parsed.
            if not last_item:
                continue

            # Fix (Discount Parsing): Consolidate discount description and amount.
            # Check if the text is a discount amount (e.g., "-0,60").
            if re.match(r"-?\d+,\d+", node_text):
                amount_str = node_text.replace("-", "").strip()
                # If the last discount entry has a description but no amount, add the amount.
                if last_item["discounts"] and "amount" not in last_item["discounts"][-1]:
                    last_item["discounts"][-1]["amount"] = amount_str
                else:
                    # Fallback: create a new discount if the order is unexpected.
                    last_item["discounts"].append({"amount": amount_str})
            
            # Otherwise, the text is a discount description (e.g., "Rem Eau de coco").
            elif node_text:
                # A new discount starts with its description.
                last_item["discounts"].append({"description": node_text})

    return receipt

def parse_float(text: str) -> float:
    """Converts a comma-decimal string to a float."""
    return float(text.replace(",", "."))