import re
from bs4 import BeautifulSoup


# ============================================================
# 1. PRICE DETECTION
# ============================================================

def looks_like_price(text):
    """
    Check whether text looks like a price.

    Examples:
        ₹39,999   -> True
        $299.99   -> True
        39999     -> True
        4.5 stars -> False
    """

    # Prices should not normally contain letters.
    if any(char.isalpha() for char in text):
        return False

    pattern = r"(₹|\$|€|£)?\s*\d[\d,]*(\.\d{1,2})?"

    return bool(re.search(pattern, text))


# ============================================================
# 2. PRICE CANDIDATE SCORING
# ============================================================

def score_price_candidate(element):
    """
    Give a score to a possible price element.

    Higher score = more likely to be the actual price.
    """

    score = 0
    text = element.get_text(strip=True)

    # Price-like text
    if looks_like_price(text):
        score += 5

    # Currency symbol
    if any(symbol in text for symbol in ["₹", "$", "€", "£"]):
        score += 2

    # Class contains 'price'
    classes = element.get("class", [])
    class_text = " ".join(classes).lower()

    if "price" in class_text:
        score += 3

    # ID contains 'price'
    element_id = element.get("id", "").lower()

    if "price" in element_id:
        score += 3

    # Short text is more likely to be a price.
    if len(text) <= 20:
        score += 1

    # Penalize text containing letters.
    if any(char.isalpha() for char in text):
        score -= 4

    # Check HTML attributes for price-related clues.
    for attribute, value in element.attrs.items():

        attribute_text = str(attribute).lower()
        value_text = str(value).lower()

        if "price" in attribute_text:
            score += 2

        if "price" in value_text:
            score += 2

    # Penalize old/non-current prices.
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
# 3. FIND ONE PRICE ELEMENT
# ============================================================

def get_price_element(product):
    """
    Find the most likely current price element
    inside a product.
    """

    best_element = None
    best_score = -1

    for element in product.find_all():

        text = element.get_text(strip=True)

        # Ignore elements that don't look like prices.
        if not looks_like_price(text):
            continue

        score = score_price_candidate(element)

        if score > best_score:
            best_score = score
            best_element = element

    return best_element


# ============================================================
# 4. CREATE ELEMENT SIGNATURE
# ============================================================

def get_element_signature(element):
    """
    Create a structural fingerprint of an HTML element.

    This helps us compare an old element with
    an element in the new HTML.
    """

    parent = element.parent

    siblings = []

    if parent:

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

        "position": (
            list(
                parent.find_all(recursive=False)
            ).index(element)
            if parent else None
        ),

        "siblings": siblings
    }


# ============================================================
# 5. COMPARE ELEMENT STRUCTURES
# ============================================================

def compare_signatures(old, new):
    """
    Compare the structure of an old element
    with a new element.

    Higher score = stronger structural similarity.
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

    # Price-related attributes are useful clues.
    for attribute, value in new["attributes"].items():

        if "price" in attribute.lower():
            score += 2

        if "price" in value.lower():
            score += 2

    # Avoid old/MRP prices.
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
# 6. FIND BEST PRICE STRUCTURAL MATCH
# ============================================================

def find_best_structural_match(old_price, product):
    """
    Find the price element in the new product
    that most closely resembles the old price element.
    """

    old_signature = get_element_signature(old_price)

    best_element = None
    best_score = -1

    for element in product.find_all():

        text = element.get_text(strip=True)

        # Only compare price-like elements.
        if not looks_like_price(text):
            continue

        new_signature = get_element_signature(element)

        negative_words = [
            "old-price",
            "original-price",
            "previous-price",
            "was-price",
            "mrp"
        ]

        classes = element.get("class", [])
        class_text = " ".join(classes).lower()

        if any(word in class_text for word in negative_words):
            continue

        score = compare_signatures(
            old_signature,
            new_signature
        )

        if score > best_score:

            best_score = score
            best_element = element

    if best_element is None:
        return None

    # Reject the result if the score is too low
    if best_score < 5:
        return None

    return {
        "element": best_element,
        "score": best_score,
        "value": best_element.get_text(strip=True)
    }


# ============================================================
# 7. PRODUCT STRUCTURE
# ============================================================

def get_product_signature(product):
    """
    Create a structural fingerprint for a product.
    """

    price_element = get_price_element(product)

    return {
        "tag": product.name,

        "classes": product.get("class", []),

        "child_tags": [
            child.name
            for child in product.find_all(
                recursive=False
            )
        ],

        "child_classes": [
            child.get("class", [])
            for child in product.find_all(
                recursive=False
            )
        ],

        "has_price": price_element is not None,

        "has_rating": (
            product.select_one(".rating")
            is not None
        )
    }


# ============================================================
# 8. COMPARE PRODUCT STRUCTURES
# ============================================================

def compare_product_signatures(old, new):
    """
    Compare the structure of two products.

    Product names are intentionally NOT used here.
    """

    score = 0

    # Same main HTML tag
    if old["tag"] == new["tag"]:
        score += 2

    # Same classes
    if old["classes"] == new["classes"]:
        score += 3

    # Same direct child tags
    if old["child_tags"] == new["child_tags"]:
        score += 3

    # Same direct child classes
    if old["child_classes"] == new["child_classes"]:
        score += 2

    # Both contain a price
    if old["has_price"] == new["has_price"]:
        score += 2

    # Both contain a rating
    if old["has_rating"] == new["has_rating"]:
        score += 1

    return score


# ============================================================
# 9. PRODUCT POSITION
# ============================================================

def get_product_position(product, products):
    """
    Return the position of a product in the product list.
    """

    for index, item in enumerate(products):

        if item == product:
            return index

    return None


def compare_product_positions(old_position, new_position):
    """
    Give a score based on how close two products are
    in the product list.
    """

    if old_position is None or new_position is None:
        return 0

    difference = abs(old_position - new_position)

    if difference == 0:
        return 5

    if difference == 1:
        return 2

    return 0


# ============================================================
# 10. FIND MATCHING PRODUCT
# ============================================================

def find_matching_product(
    old_product,
    new_products,
    old_products
):
    """
    Find the most likely matching product.

    We mainly use:
        1. Position
        2. Product structure

    Product name is NOT used as the main signal.
    """

    old_position = get_product_position(
        old_product,
        old_products
    )

    old_signature = get_product_signature(
        old_product
    )

    best_product = None
    best_score = 0

    for product in new_products:

        new_position = get_product_position(
            product,
            new_products
        )

        new_signature = get_product_signature(
            product
        )

        # Structural similarity
        structure_score = compare_product_signatures(
            old_signature,
            new_signature
        )

        # Position similarity
        position_score = compare_product_positions(
            old_position,
            new_position
        )

        total_score = (
            structure_score
            + position_score
        )

        print(
            product.get_text(" ", strip=True)[:40],
            "→ Structure:",
            structure_score,
            "| Position:",
            position_score,
            "| Total:",
            total_score
        )

        if total_score > best_score:

            best_score = total_score
            best_product = product

    # Require reasonable structural evidence.
    if best_product is None:
        return None

    if best_score < 10:
        return None

    return best_product

def find_product_by_position(old_product, old_products, new_products):
    """
    Try to find the corresponding product using its
    position in the product list.

    This is useful when websites keep products
    in approximately the same order.
    """

    old_position = get_product_position(
        old_product,
        old_products
    )

    if old_position is None:
        return None

    # Make sure the same position exists
    if old_position >= len(new_products):
        return None

    return new_products[old_position]
def is_product_match(old_product, new_product):
    """
    Check whether two product elements have
    sufficiently similar HTML structures.
    """

    old_signature = get_product_signature(old_product)
    new_signature = get_product_signature(new_product)

    score = compare_product_signatures(
        old_signature,
        new_signature
    )

    print("Structural score:", score)

    # Our current structure score can reach 13.
    if score >= 10:
        return True

    return False

def find_matching_product_by_structure(old_product, new_products):
    """Find the strongest structural match."""

    old_signature = get_product_signature(old_product)

    best_product = None
    best_score = -1
    second_best_score = -1

    for product in new_products:

        new_signature = get_product_signature(product)

        score = compare_product_signatures(
            old_signature,
            new_signature
        )

        print("Candidate structural score:", score)

        if score > best_score:
            second_best_score = best_score
            best_score = score
            best_product = product

        elif score > second_best_score:
            second_best_score = score

    # Not enough structural similarity
    if best_score < 10:
        return None

    # If multiple candidates are equally good,
    # we cannot confidently identify the product.
    if best_score == second_best_score:
        return None

    return {
        "product": best_product,
        "score": best_score
    }

# ============================================================
# 11. LOAD HTML FILES
# ============================================================

with open(
    "oldpage.html",
    "r",
    encoding="utf-8"
) as file:

    old_html = file.read()


with open(
    "testpage.html",
    "r",
    encoding="utf-8"
) as file:

    new_html = file.read()


old_soup = BeautifulSoup(
    old_html,
    "html.parser"
)

new_soup = BeautifulSoup(
    new_html,
    "html.parser"
)


# ============================================================
# 12. GET PRODUCTS
# ============================================================

old_products = old_soup.select(".product")
new_products = new_soup.select(".product")


# ============================================================
# 13. SELECT OLD PRODUCT
# ============================================================

# Temporary for our testing.
# Later we will make this automatic.
old_product = old_products[0]

print(
    "Old product:",
    old_product.get_text(" ", strip=True)
)


# ============================================================
# 14. GET OLD PRICE
# ============================================================

old_price = old_product.select_one(".price")

if old_price is None:

    print("❌ Old price element not found.")

else:

    print(
        "Old price:",
        old_price.get_text(strip=True)
    )


    # ========================================================
    # 15. FIND MATCHING PRODUCT
    # ========================================================

    matching_product = find_matching_product(
        old_product,
        new_products,
        old_products
    )


    if matching_product is None:

        print("❌ No matching product found.")

    else:

        print(
            "Matched product."
        )


        # ====================================================
        # 16. FIND NEW PRICE
        # ====================================================

        result = find_best_structural_match(
            old_price,
            matching_product
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

            print(
                "❌ Could not find a suitable price."
            )

## Main Pipeline
print("Main Pipeline")
for old_product in old_products:

    old_position = get_product_position(
        old_product,
        old_products
    )

    if old_position >= len(new_products):

        print("❌ Product removed.")
        continue

    new_product = new_products[old_position]

    if not is_product_match(old_product, new_product):

        print("⚠️ Product structure changed.")
        continue

    print("✅ Product found.")

    old_price = get_price_element(old_product)

    result = find_best_structural_match(
        old_price,
        new_product
    )

    if result:

        print("New price:", result["value"])

    else:

        print("❌ Price not found.")