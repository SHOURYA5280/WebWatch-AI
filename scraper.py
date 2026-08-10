import re
from bs4 import BeautifulSoup

with open("testpage.html", "r", encoding="utf-8") as file:
    html = file.read()

soup = BeautifulSoup(html, "html.parser")

products = soup.select(".product")

def get_text(element):
    return {"value": element.get_text(strip=True), "found": True} if element else {"value": "None", "found": False}

def looks_like_price(text):
    pattern = r"(₹|\$|€|£)\s*\d[\d,]*(\.\d{1,2})?"
    return bool(re.search(pattern, text))

def extract_price(product):
    price_element = product.select_one(".price")

    price_data = get_text(price_element)
    if not price_data["found"]:
        return {"value": "None", "found": False, "valid": False}

    valid = looks_like_price(price_data["value"])
    return {"value": price_data["value"], "found": True, "valid": valid}

def find_price_candidate(product):
    candidate_selectors = [
        ".price",
        ".current-price",
        ".product-price",
        ".sale-price",
        "[data-price]"
    ]

    for selector in candidate_selectors:
        element = product.select_one(selector)

        if element:
            text = element.get_text(strip=True)

            if looks_like_price(text):
                return {
                    "selector": selector,
                    "value": text,
                    "valid": True
                }

    return {
        "selector": None,
        "value": None,
        "valid": False
    }

for product in products:
    result = find_price_candidate(product)
    print(result)
