from bs4 import BeautifulSoup

with open("testpage.html", "r", encoding="utf-8") as file:
    html = file.read()

soup = BeautifulSoup(html, "html.parser")

products = soup.select(".product")

for product in products:
    name = product.select_one("h2")
    price = product.select_one(".price")
    rating = product.select_one(".rating")

    if price:
        price_text = price.get_text(strip=True)
    else:
        price_text = "Not Available"

    print(name.get_text(strip=True))
    print(price_text)
    print(rating.get_text(strip=True))
    print()