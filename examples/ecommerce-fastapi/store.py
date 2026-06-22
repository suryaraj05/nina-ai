"""In-memory product database: 20 clothing products for the Indian market."""


def _p(pid, name, category, price, tags, sizes, in_stock=True):
    return {"id": pid, "name": name, "category": category, "price": price,
            "tags": tags, "sizes": sizes, "in_stock": in_stock}


PRODUCTS = [
    # tops
    _p("p01", "Classic Navy Hoodie", "tops", 1999,
       ["casual", "winter", "athleisure", "streetwear"], ["S", "M", "L", "XL"]),
    _p("p02", "White Cotton Kurta", "tops", 1299,
       ["summer", "casual", "ethnic", "breathable"], ["S", "M", "L", "XL", "XXL"]),
    _p("p03", "Linen Half-Sleeve Shirt", "tops", 1499,
       ["summer", "casual", "breathable", "officewear"], ["M", "L", "XL"]),
    _p("p04", "Graphic Cotton Tee", "tops", 699,
       ["summer", "casual", "streetwear"], ["S", "M", "L", "XL"]),
    _p("p05", "Silk Festive Kurta", "tops", 2999,
       ["formal", "festive", "ethnic", "wedding"], ["M", "L", "XL"]),
    # bottoms
    _p("p06", "Slim-Fit Blue Jeans", "bottoms", 2199,
       ["casual", "all-season", "denim"], ["30", "32", "34", "36"]),
    _p("p07", "Rayon Palazzo Pants", "bottoms", 999,
       ["summer", "casual", "ethnic", "breathable"], ["S", "M", "L", "XL"]),
    _p("p08", "Athletic Joggers", "bottoms", 1299,
       ["athletic", "casual", "gym"], ["S", "M", "L", "XL"]),
    _p("p09", "Cotton Chino Shorts", "bottoms", 899,
       ["summer", "casual"], ["30", "32", "34", "36"]),
    _p("p10", "Churidar Pyjama", "bottoms", 799,
       ["ethnic", "casual", "summer"], ["S", "M", "L", "XL", "XXL"]),
    # outerwear
    _p("p11", "Textured Nehru Jacket", "outerwear", 2499,
       ["formal", "festive", "ethnic", "wedding"], ["M", "L", "XL"]),
    _p("p12", "Washed Denim Jacket", "outerwear", 2799,
       ["casual", "winter", "streetwear", "denim"], ["S", "M", "L", "XL"]),
    _p("p13", "Quilted Puffer Jacket", "outerwear", 3999,
       ["winter", "casual", "warm"], ["M", "L", "XL"], in_stock=False),
    _p("p14", "Bandhgala Blazer", "outerwear", 4999,
       ["formal", "wedding", "ethnic"], ["38", "40", "42", "44"]),
    # footwear
    _p("p15", "White Low-Top Sneakers", "footwear", 2499,
       ["casual", "summer", "streetwear"], ["7", "8", "9", "10", "11"]),
    _p("p16", "Punjabi Leather Juttis", "footwear", 1599,
       ["ethnic", "festive", "wedding"], ["7", "8", "9", "10"]),
    _p("p17", "Kolhapuri Sandals", "footwear", 1199,
       ["summer", "casual", "ethnic"], ["7", "8", "9", "10", "11"]),
    _p("p18", "Cushioned Running Shoes", "footwear", 3499,
       ["athletic", "gym"], ["7", "8", "9", "10", "11"]),
    # accessories
    _p("p19", "Banarasi Silk Dupatta", "accessories", 1899,
       ["festive", "ethnic", "wedding", "formal"], ["One Size"]),
    _p("p20", "Pashmina Wool Shawl", "accessories", 3299,
       ["winter", "formal", "warm"], ["One Size"]),
]

BY_ID = {p["id"]: p for p in PRODUCTS}
