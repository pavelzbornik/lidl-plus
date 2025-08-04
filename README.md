**This python package is unofficial and is not related in any way to Lidl. It was developed by reversed engineered requests and can stop working at anytime!**

# Python Lidl Plus API
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/Andre0512/lidl-plus/python-check.yml?branch=main&label=checks)](https://github.com/Andre0512/lidl-plus/actions/workflows/python-check.yml)
[![PyPI - Status](https://img.shields.io/pypi/status/lidl-plus)](https://pypi.org/project/lidl-plus)
[![PyPI](https://img.shields.io/pypi/v/lidl-plus?color=blue)](https://pypi.org/project/lidl-plus)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/lidl-plus)](https://www.python.org/)
[![PyPI - License](https://img.shields.io/pypi/l/lidl-plus)](https://github.com/Andre0512/lidl-plus/blob/main/LICENCE)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/lidl-plus)](https://pypistats.org/packages/lidl-plus)
[![Buy Me a Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-orange.svg)](https://www.buymeacoffee.com/andre0512)  


Fetch receipts and more from Lidl Plus.
## Installation
```bash
pip install lidl-plus
```

## Authentication
To login in Lidl Plus we need to simulate the app login.
This is a bit complicated, we need a web browser and some additional python packages.
After we have received the token once, we can use it for further requestes and we don't need a browser anymore.

#### Prerequisites
* Check you have installed one of the supported web browser
  - Chromium
  - Google Chrome
  - Mozilla Firefox
  - Microsoft Edge
* Install additional python packages
  ```bash
  pip install "lidl-plus[auth]"
  ```

#### Using a .env File

You can store your Lidl Plus credentials and settings in a `.env` file in your project root. This keeps sensitive information out of your code and makes configuration easier.

**Example `.env` file:**
```env
LIDL_LANGUAGE=de
LIDL_COUNTRY=AT
LIDL_EMAIL=your_email@example.com
LIDL_PASSWORD=your_password
LIDL_REFRESH_TOKEN=your_refresh_token
```

If you have [`python-dotenv`](https://pypi.org/project/python-dotenv/) installed (it is included in the dependencies), these variables will be loaded automatically for both the CLI and Python usage.

**In Python code:**
```python
import os
language = os.environ["LIDL_LANGUAGE"]
country = os.environ["LIDL_COUNTRY"]
email = os.environ["LIDL_EMAIL"]
password = os.environ["LIDL_PASSWORD"]
refresh_token = os.environ["LIDL_REFRESH_TOKEN"]
```

#### Commandline-Tool

**Without a `.env` file:**  
You will be prompted for all required information:
```bash
$ lidl-plus auth
Enter your language (de, en, ...): de
Enter your country (DE, AT, ...): AT
Enter your lidl plus email: your_email@example.com
Enter your lidl plus password:
Enter the verify code you received via phone: 590287
------------------------- refresh token ------------------------
2D4FC2A699AC703CAB8D017012658234917651203746021A4AA3F735C8A53B7F
----------------------------------------------------------------
```

**With a `.env` file:**  
All required information is loaded automatically and you will only be prompted for the 2FA code:
```bash
$ lidl-plus auth
Enter the verify code you received via phone: 590287
------------------------- refresh token ------------------------
2D4FC2A699AC703CAB8D017012658234917651203746021A4AA3F735C8A53B7F
----------------------------------------------------------------
```

#### Python
```python
from lidlplus import LidlPlusApi

lidl = LidlPlusApi(language="de", country="AT")
lidl.login(email="your_email@example.com", password="password", verify_token_func=lambda: input("Insert code: "))
print(lidl.refresh_token)
```
## Usage
Currently, the only features are fetching receipts and activating coupons
### Receipts
for receipt in lidl.tickets():
### Receipts

#### API v3 Breaking Changes

Due to a change in the Lidl Plus API from v2 to v3, receipt data is no longer provided as structured JSON. Instead, receipts are now returned as HTML, which is parsed to reconstruct a schema as close as possible to the previous version. However, there are breaking changes:


- **Removed fields:** The following fields that were present in the previous (v2) JSON API are no longer available in the v3 HTML-based response:

    - `taxGroup`
    - `codeInput` (barcode)
    - `deposit`
    - `giftSerialNumber`

- **Data is parsed from HTML:** The receipt parser extracts as much information as possible from the HTML, but some details may be missing or less reliable than before.
- **Schema compatibility:** The output format aims to be compatible with the previous JSON structure, but some fields may be absent or have different values.

#### Example Output
The parsed receipt data now looks like this (note: some fields may be missing or null):
```json
{
    "currentUnitPrice": "2,19",
    "quantity": "1",
    "isWeight": false,
    "originalAmount": "2,19",
    "name": "Vegane Frikadellen",
    "taxGroupName": "A",
    "discounts": [
        {
            "description": "5€ Coupon",
            "amount": "0,21"
        }
    ]
}
```

#### Commandline-Tool
```bash
$ lidl-plus --language=de --country=AT --refresh-token=XXXXX receipt --all > data.json
```

#### Python
```python
from lidlplus import LidlPlusApi

lidl = LidlPlusApi("de", "AT", refresh_token="XXXXXXXXXX")
for receipt in lidl.tickets():
    pprint(lidl.ticket(receipt["id"]))
```

### Coupons

You can list all coupons and activate/deactivate them by id
```json
{
    "sections": [
        {
            "name": "FavoriteStore",
            "coupons": []
        },
        {
            "name": "AllStores",
            "coupons": [
                {
                    "id": "2c9b3554-a09c-412c-8be4-d41cbff13572",
                    "image": "https://lidlplusprod.blob.core.windows.net/images/coupons/LT/IDISC0000254911.png?t=1695452076",
                    "type": "Standard",
                    "offerTitle": "1 + 1",
                    "title": "👨🏻‍🍳 Frozen 👨🏻‍🍳",
                    "offerDescriptionShort": "FREE",
                    "isSegmented": false,
                    "startValidityDate": "2023-09-24T21:00:00Z",
                    "endValidityDate": "2023-10-01T20:59:59Z",
                    "isActivated": false,
                    "apologizeText": "Xxxxxxxxxxxxxxxxx",
                    "apologizeStatus": false,
                    "apologizeTitle": "Xxxxxxxxxxxxxxxxxxx",
                    "promotionId": "DISC0000254911",
                    "tagSpecial": "",
                    "firstColor": "#ffc700",
                    "secondaryColor": null,
                    "firstFontColor": "#4a4a4a",
                    "secondaryFontColor": null,
                    "isSpecial": false,
                    "hasAsterisk": false,
                    "isHappyHour": false,
                    "stores": []
                },
                .......
            ]
        },
        {
            "name": "OtherStores",
            "coupons": []
        }
    ]
}
```

#### Commandline-Tool

Activate all available coupons

```bash
$ lidl-plus --language=de --country=AT --refresh-token=XXXXX coupon --all
```

#### Python
```python
from lidlplus import LidlPlusApi

lidl = LidlPlusApi("de", "AT", refresh_token="XXXXXXXXXX")
for section in lidl.coupons()["sections"]:
  for coupon in section["coupons"]:
    print("found coupon: ", coupon["title"], coupon["id"])
```

## Help
#### Commandline-Tool
```commandline
Lidl Plus API

options:
  -h, --help                show this help message and exit
  -c CC, --country CC       country (DE, BE, NL, AT, ...)
  -l LANG, --language LANG  language (de, en, fr, it, ...)
  -e EMAIL, --email EMAIL   Lidl Plus login email
  -p XXX, --password XXX    Lidl Plus login password
  --2fa {phone,email}       choose two factor auth method
  -r TOKEN, --refresh-token TOKEN
                            refresh token to authenticate
  --skip-verify             skip ssl verification
  --not-accept-legal-terms  not auto accept legal terms updates
  -d, --debug               debug mode

commands:
  auth                      authenticate and get token
  receipt                   output last receipts as json
  coupon                    activate coupons
```

## Support
If you find this project helpful and would like to support its development, you can buy me a coffee! ☕

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/andre0512)

Don't forget to star the repository if you found it useful! ⭐
