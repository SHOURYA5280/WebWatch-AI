import re
from bs4 import BeautifulSoup


# ============================================================
# 1. BASIC UTILITY FUNCTIONS
# ============================================================

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
    """
    Check whether text looks like a price.

    Examples:
        ₹39,999     -> True
        $299.99     -> True
        39999       -> True
        4.5 stars   -> False
    """

    # Price should not normally contain alphabetic characters.
    if any(char.isalpha() for char in text):
        return False

    # Match optional currency symbol followed by a number.
    pattern = r"(₹|\$|€|£)?\s*\d[\d,]*(\.\d{1,2})?"

    return bool(re.search(pattern, text))


# ============================================================
# 2. PRICE EXTRACTION
# ============================================================

def extract_price(product):
    """
    Try to extract the price using the original '.price' selector.
    """

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


# ============================================================
# 3. PRICE CANDIDATE DISCOVERY
# ============================================================

def find_price_candidates(product):
    """
    Find all elements inside a product whose text
    looks like a price.
    """

    candidates = []

    for element in product.find_all():

        text = element.get_text(strip=True)

        if looks_like_price(text):
            candidates.append(element)

    return candidates


# ============================================================
# 4. PRICE CANDIDATE SCORING
# ============================================================

def score_price_candidate(element):
    """
    Give a score to a possible price element.

    Higher score = more likely to be the actual price.
    """

    score = 0

    text = element.get_text(strip=True)

    # --------------------------------------------------------
    # Price-like text
    # --------------------------------------------------------

    if looks_like_price(text):
        score += 5

    # --------------------------------------------------------
    # Currency symbol
    # --------------------------------------------------------

    if any(symbol in text for symbol in ["₹", "$", "€", "£"]):
        score += 2

    # --------------------------------------------------------
    # Class name containing 'price'
    # --------------------------------------------------------

    classes = element.get("class", [])
    class_text = " ".join(classes).lower()

    if "price" in class_text:
        score += 3

    # --------------------------------------------------------
    # ID containing 'price'
    # --------------------------------------------------------

    element_id = element.get("id", "").lower()

    if "price" in element_id:
        score += 3

    # --------------------------------------------------------
    # Short text is more likely to be a dedicated price value
    # --------------------------------------------------------

    if len(text) <= 20:
        score += 1

    # --------------------------------------------------------
    # Penalize alphabetic characters
    # --------------------------------------------------------

    if any(char.isalpha() for char in text):
        score -= 4

    # --------------------------------------------------------
    # Check HTML attributes for price-related clues
    # --------------------------------------------------------

    for attribute, value in element.attrs.items():

        attribute_text = str(attribute).lower()
        value_text = str(value).lower()

        if "price" in attribute_text:
            score += 2

        if "price" in value_text:
            score += 2

    # --------------------------------------------------------
    # Penalize attributes that suggest an old/non-current price
    # --------------------------------------------------------

    negative_words = [
        "old-price",
        "original-price",
        "previous-price",
        "was-price",
        "mrp"
    ]

    for value in element.attrs.values():

        value_text = str(value).lower()

        for word in negative_words:

            if word in value_text:
                score -= 4

    return score


# ============================================================
# 5. FIND BEST PRICE CANDIDATE
# ============================================================

def find_best_price_candidate(product):
    """
    Find the highest-scoring price candidate inside a product.
    """

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


# ============================================================
# 6. GENERATE CSS SELECTOR
# ============================================================

def generate_selector(element):
    """
    Generate a simple CSS selector for an element.

    Priority:
        1. ID
        2. Classes
        3. Tag name
    """

    # ID gives us the most specific simple selector.
    element_id = element.get("id")

    if element_id:
        return f"#{element_id}"

    # Use classes if there is no ID.
    classes = element.get("class", [])

    if classes:
        return element.name + "." + ".".join(classes)

    # Fall back to the tag name.
    return element.name


# ============================================================
# 7. REPAIR PRICE SELECTOR
# ============================================================

def repair_price_selector(product):
    """
    Find the best price candidate, generate a selector
    and verify that the selector works.
    """

    result = find_best_price_candidate(product)

    if result is None:
        return None

    selector = generate_selector(result["element"])

    # Check whether the generated selector actually works.
    element = product.select_one(selector)

    if element is None:
        return None

    value = element.get_text(strip=True)

    # Make sure the selected element still looks like a price.
    if not looks_like_price(value):
        return None

    return {
        "selector": selector,
        "value": value,
        "score": result["score"]
    }


# ============================================================
# 8. HTML ELEMENT SIGNATURE
# ============================================================

def get_element_signature(element):
    """
    Create a structural description of an HTML element.

    This allows us to compare an old element with
    a possible replacement in the new HTML.
    """

    parent = element.parent

    siblings = []

    if parent:

        # Look only at direct children of the parent.
        for child in parent.find_all(recursive=False):

            if child != element:

                siblings.append({
                    "tag": child.name,
                    "classes": child.get("class", [])
                })

    return {
        "tag": element.name,

        "classes": element.get("class", []),

        "id": element.get("id"),

        # Save all attributes for later comparison.
        "attributes": {
            key: str(value)
            for key, value in element.attrs.items()
        },

        "parent_tag": (
            parent.name
            if parent else None
        ),

        "parent_classes": (
            parent.get("class", [])
            if parent else []
        ),

        # Position among direct children.
        "position": (
            list(
                parent.find_all(recursive=False)
            ).index(element)
            if parent else None
        ),

        "siblings": siblings
    }


# ============================================================
# 9. COMPARE OLD AND NEW ELEMENTS
# ============================================================

def compare_signatures(old, new):
    """
    Compare the structure of an old element with a new element.

    A higher score means the new element is structurally
    more similar to the old element.
    """

    score = 0

    # Same HTML tag
    if old["tag"] == new["tag"]:
        score += 2

    # Same classes
    if old["classes"] == new["classes"]:
        score += 3

    # Same ID
    if old["id"] == new["id"] and old["id"] is not None:
        score += 3

    # Same parent tag
    if old["parent_tag"] == new["parent_tag"]:
        score += 1

    # Same parent classes
    if old["parent_classes"] == new["parent_classes"]:
        score += 2

    # Same position inside parent
    if old["position"] == new["position"]:
        score += 2

    # Same siblings
    if old["siblings"] == new["siblings"]:
        score += 3

    # --------------------------------------------------------
    # Attribute-based clues
    # --------------------------------------------------------

    for attribute, value in new["attributes"].items():

        if "price" in attribute.lower():
            score += 2

        if "price" in value.lower():
            score += 2

    # --------------------------------------------------------
    # Negative clues
    # --------------------------------------------------------

    negative_words = [
        "old-price",
        "original-price",
        "previous-price",
        "was-price",
        "mrp"
    ]

    for value in new["attributes"].values():

        value_text = str(value).lower()

        for word in negative_words:

            if word in value_text:
                score -= 4

    return score


# ============================================================
# 10. FIND BEST STRUCTURAL MATCH
# ============================================================

def find_best_structural_match(old_element, new_elements):
    """
    Find the price-like element in the new HTML
    that most closely resembles the old price element.
    """

    old_signature = get_element_signature(old_element)

    best_element = None
    best_score = -1

    for element in new_elements:

        text = element.get_text(strip=True)

        # Ignore elements that don't look like prices.
        if not looks_like_price(text):
            continue

        new_signature = get_element_signature(element)

        score = compare_signatures(
            old_signature,
            new_signature
        )

        print(
            element.name,
            element.get("class"),
            text,
            "→ Score:",
            score
        )

        if score > best_score:
            best_score = score
            best_element = element

    # No suitable candidate was found.
    if best_element is None:
        return None

    return {
        "element": best_element,
        "score": best_score,
        "value": best_element.get_text(strip=True)
    }


# ============================================================
# 11. PRODUCT MATCHING
# ============================================================

def get_product_name(product):
    """Extract the product name from its h2 element."""

    name_element = product.select_one("h2")

    if name_element:
        return name_element.get_text(strip=True)

    return None


def product_name_similarity(old_name, new_name):
    """
    Calculate a simple similarity score between two product names.

    The score is based on how many words from the old name
    are also present in the new name.

    Example:
        Power Phone
        Power Phone 5G

        Similarity = 1.0
    """

    old_words = set(old_name.lower().split())
    new_words = set(new_name.lower().split())

    if not old_words or not new_words:
        return 0

    common_words = old_words.intersection(new_words)

    return len(common_words) / len(old_words)


def find_matching_product(old_product, new_products):
    """
    Find the new product that is most similar to the old product.
    """

    old_name = get_product_name(old_product)

    if old_name is None:
        return None

    best_product = None
    best_score = 0

    for product in new_products:

        new_name = get_product_name(product)

        if new_name is None:
            continue

        score = product_name_similarity(
            old_name,
            new_name
        )

        print(
            new_name,
            "→ Similarity:",
            score
        )

        if score > best_score:
            best_score = score
            best_product = product

    return best_product


# ============================================================
# 12. LOAD HTML FILES
# ============================================================

with open("oldpage.html", "r", encoding="utf-8") as file:
    old_html = file.read()

with open("testpage.html", "r", encoding="utf-8") as file:
    new_html = file.read()


# Convert HTML strings into BeautifulSoup objects.
old_soup = BeautifulSoup(old_html, "html.parser")
new_soup = BeautifulSoup(new_html, "html.parser")


# ============================================================
# 13. FIND THE OLD PRODUCT
# ============================================================

old_products = old_soup.select(".product")

old_product = None

# For our current test, we are targeting Power Phone.
for product in old_products:

    if get_product_name(product) == "Power Phone":
        old_product = product
        break


if old_product is None:
    print("❌ Old product not found.")

else:

    print(
        "Old product:",
        get_product_name(old_product)
    )

    # Find the old price inside the selected product.
    old_price = old_product.select_one(".price")

    if old_price is None:

        print("❌ Old price element not found.")

    else:

        # ====================================================
        # 14. FIND MATCHING PRODUCT IN NEW HTML
        # ====================================================

        new_products = new_soup.select(".product")

        matching_product = find_matching_product(
            old_product,
            new_products
        )

        if matching_product is None:

            print("❌ No matching product found.")

        else:

            print(
                "Matched product:",
                get_product_name(matching_product)
            )

            # =================================================
            # 15. RECOVER THE NEW PRICE
            # =================================================

            new_elements = matching_product.find_all()

            result = find_best_structural_match(
                old_price,
                new_elements
            )

            if result:

                print(
                    "Best element:",
                    result["element"]
                )

                print(
                    "Best score:",
                    result["score"]
                )

                print(
                    "Price:",
                    result["value"]
                )

            else:

                print("❌ Could not find a suitable price.")