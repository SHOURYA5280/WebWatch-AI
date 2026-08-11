import re
from bs4 import BeautifulSoup

# ---------- Utility Functions ----------

def get_text(element):
    """Safely extract text from a BeautifulSoup element."""
    if element:
        return {
            "value": element.get_text(strip=True),
            "found": True
        }

    return {
        "value": None,
        "found": False
    }


def looks_like_price(text):
    """Check whether text contains a currency-based price."""
    pattern = r"(₹|\$|€|£)\s*\d[\d,]*(\.\d{1,2})?"
    return bool(re.search(pattern, text))


# ---------- Price Extraction ----------

def extract_price(product):
    """Try to extract a price using the expected selector."""
    price_element = product.select_one(".price")

    price_data = get_text(price_element)

    if not price_data["found"]:
        return {
            "value": None,
            "found": False,
            "valid": False
        }

    valid = looks_like_price(price_data["value"])

    return {
        "value": price_data["value"],
        "found": True,
        "valid": valid
    }


# ---------- Candidate Discovery ----------

def find_price_candidates(product):
    """Find HTML elements whose text looks like a price."""
    candidates = []

    for element in product.find_all():
        text = element.get_text(strip=True)

        if looks_like_price(text):
            candidates.append(element)

    return candidates


# ---------- Candidate Scoring ----------

def score_price_candidate(element):
    """Give a score to a possible price element."""
    score = 0

    text = element.get_text(strip=True)

    # Price-like text
    if looks_like_price(text):
        score += 5

    # Currency symbol
    if any(symbol in text for symbol in ["₹", "$", "€", "£"]):
        score += 2

    # Class name
    classes = element.get("class", [])
    class_text = " ".join(classes).lower()

    if "price" in class_text:
        score += 3

    # ID
    element_id = element.get("id", "").lower()

    if "price" in element_id:
        score += 3

    # Shorter text is more likely to be a dedicated value
    if len(text) <= 20:
        score += 1

    # Penalize mixed text containing alphabetic characters
    if any(char.isalpha() for char in text):
        score -= 4

    return score


# ---------- Best Candidate ----------

def find_best_price_candidate(product):
    """Find and return the highest-scoring price candidate."""
    candidates = find_price_candidates(product)

    if not candidates:
        return None

    best_candidate = None
    best_score = -1

    for candidate in candidates:
        score = score_price_candidate(candidate)

        if score > best_score:
            best_score = score
            best_candidate = candidate

    return {
        "element": best_candidate,
        "score": best_score,
        "value": best_candidate.get_text(strip=True)
    }


# ---------- Selector Generation ----------

def generate_selector(element):
    """Generate a CSS selector for an HTML element."""

    element_id = element.get("id")

    if element_id:
        return f"#{element_id}"

    classes = element.get("class", [])

    if classes:
        return element.name + "." + ".".join(classes)

    return element.name


# ---------- Self-Healing ----------

def repair_price_selector(product):
    """Find, generate and verify a replacement price selector."""

    result = find_best_price_candidate(product)

    if result is None:
        return None

    selector = generate_selector(result["element"])

    # Verify that the generated selector finds an element
    element = product.select_one(selector)

    if element is None:
        return None

    value = element.get_text(strip=True)

    # Verify that the extracted value actually looks like a price
    if not looks_like_price(value):
        return None

    return {
        "selector": selector,
        "value": value,
        "score": result["score"]
    }


# ---------- Main Program ----------

with open("testpage.html", "r", encoding="utf-8") as file:
    html = file.read()

soup = BeautifulSoup(html, "html.parser")

products = soup.select(".product")


for product in products:

    price_data = extract_price(product)

    if price_data["found"] and price_data["valid"]:
        print("Price:", price_data["value"])

    else:
        print("⚠️ Original price selector failed.")

        repair = repair_price_selector(product)

        if repair:
            print("✅ Repaired!")
            print("New selector:", repair["selector"])
            print("Price:", repair["value"])
            print("Score:", repair["score"])
        else:
            print("❌ Could not repair price selector.")

    print()

