from copy import deepcopy


def _pngimg(category, filename, page_url, style_name, note, badges):
    return {
        "style_name": style_name,
        "image_url": f"https://pngimg.com/uploads/{category}/{filename}",
        "source_url": page_url,
        "source_label": "PNGIMG",
        "note": note,
        "badges": badges,
    }


def _with_tags(variant, *tags):
    enriched = dict(variant)
    enriched["tags"] = list(tags)
    return enriched


CLOTHING_VARIANT_CATALOG = {
    "tops": {
        "hot": [
            _with_tags(_pngimg("polo_shirt", "polo_shirt_PNG8161.png", "https://pngimg.com/image/8161", "White polo", "A polo keeps the outfit cleaner than a plain tee while staying breathable in hot weather.", ["Breathable", "Collared"]), "hot"),
            _with_tags(_pngimg("polo_shirt", "polo_shirt_PNG8153.png", "https://pngimg.com/image/8153", "Grey polo", "A neutral polo works well when you want a warm-weather top that still looks structured.", ["Lightweight", "Easy pairing"]), "hot"),
            _with_tags(_pngimg("polo_shirt", "polo_shirt_PNG8154.png", "https://pngimg.com/image/8154", "Sky polo", "A softer color keeps the outfit feeling lighter when the temperature is high.", ["Airy", "Warm-weather"]), "hot"),
            _with_tags(_pngimg("polo_shirt", "polo_shirt_PNG8155.png", "https://pngimg.com/image/8155", "Navy polo", "A darker polo still works in the heat if you want something sharper than a casual tee.", ["Structured", "Summer smart"]), "hot"),
            _with_tags(_pngimg("polo_shirt", "polo_shirt_PNG8143.png", "https://pngimg.com/image/8143", "Blue polo", "This kind of short-sleeve polo is an easy option when the day stays warm but active.", ["Short sleeve", "Clean finish"]), "hot"),
            _with_tags(_pngimg("polo_shirt", "polo_shirt_PNG8144.png", "https://pngimg.com/image/8144", "Red polo", "A stronger color still fits hot weather as long as the fabric stays light and breathable.", ["Breathable", "Statement color"]), "hot"),
            _with_tags(_pngimg("polo_shirt", "polo_shirt_PNG8142.png", "https://pngimg.com/image/8142", "Soft polo", "A lighter polo keeps the outfit clean without adding any unnecessary weight in the heat.", ["Soft tone", "Low bulk"]), "hot"),
        ],
        "mild": [
            _with_tags(_pngimg("tshirt", "tshirt_PNG5437.png", "https://pngimg.com/image/5437", "White tee", "A plain tee is still one of the easiest balanced-weather tops when you do not need heavy layering.", ["Minimal", "Everyday"]), "mild"),
            _with_tags(_pngimg("tshirt", "tshirt_PNG5435.png", "https://pngimg.com/image/5435", "Charcoal tee", "A darker tee still works well in mild weather when you want comfort with a slightly sharper finish.", ["Clean", "Versatile"]), "mild"),
            _with_tags(_pngimg("tshirt", "tshirt_PNG5436.png", "https://pngimg.com/image/5436", "Black tee", "A darker tee works well in mild temperatures when comfort is the priority.", ["Versatile", "Clean look"]), "mild"),
            _with_tags(_pngimg("tshirt", "tshirt_PNG5450.png", "https://pngimg.com/image/5450", "Grey tee", "A neutral tee is an easy middle-ground pick when the weather is stable.", ["Balanced", "Casual"]), "mild"),
            _with_tags(_pngimg("dress_shirt", "dress_shirt_PNG8098.png", "https://pngimg.com/image/8098", "Blue dress shirt", "A long-sleeve shirt works once the weather is mild enough to support a cleaner silhouette.", ["Long sleeve", "Polished"]), "mild"),
            _with_tags(_pngimg("dress_shirt", "dress_shirt_PNG8077.png", "https://pngimg.com/image/8077", "White dress shirt", "A crisp shirt gives you a sharper option for mild conditions without needing outerwear.", ["Smart casual", "Sharp finish"]), "mild"),
            _with_tags(_pngimg("dress_shirt", "dress_shirt_PNG8083.png", "https://pngimg.com/image/8083", "Soft blue shirt", "A lighter dress shirt is useful when you want something tidier than a tee in balanced weather.", ["Lighter layer", "Structured"]), "mild"),
        ],
        "cool": [
            _with_tags(_pngimg("dress_shirt", "dress_shirt_PNG8112.png", "https://pngimg.com/image/8112", "Layering shirt", "A full shirt becomes more useful once the air cools down and bare arms start feeling exposed.", ["Cool-weather", "Layer-ready"]), "cool"),
            _with_tags(_pngimg("sweater", "sweater_PNG81.png", "https://pngimg.com/image/11670", "Blue sweater", "A sweater is the better starting point when the day feels cool enough that a tee is no longer enough.", ["Knitwear", "Warmer fabric"]), "cool"),
            _with_tags(_pngimg("sweater", "sweater_PNG57.png", "https://pngimg.com/image/11646", "Neutral sweater", "A soft sweater is a cleaner cool-weather top when you want warmth without going straight to outerwear.", ["Soft knit", "Layerable"]), "cool"),
            _with_tags(_pngimg("sweater", "sweater_PNG48.png", "https://pngimg.com/image/11637", "Dark sweater", "A darker sweater works well once cooler air makes lighter shirts feel underpowered.", ["Dense knit", "Cool-day fit"]), "cool"),
            _with_tags(_pngimg("sweater", "sweater_PNG31.png", "https://pngimg.com/image/11620", "Classic sweater", "A classic knit gives the outfit more warmth than a shirt while staying visually simple.", ["Classic knit", "Balanced warmth"]), "cool"),
            _with_tags(_pngimg("hoodie", "hoodie_PNG46.png", "https://pngimg.com/image/104440", "Grey hoodie", "A hoodie gives you more warmth than a shirt while still staying casual and easy to wear.", ["Casual layer", "Soft warmth"]), "cool"),
            _with_tags(_pngimg("hoodie", "hoodie_PNG45.png", "https://pngimg.com/image/104439", "Black hoodie", "A clean hoodie is an easy cool-weather layer if you want comfort without a jacket yet.", ["Pullover", "Everyday warmth"]), "cool"),
            _with_tags(_pngimg("hoodie", "hoodie_PNG41.png", "https://pngimg.com/image/104435", "Cream hoodie", "A lighter hoodie is useful when the day is cool, not freezing, and you still want a softer look.", ["Comfort", "Midweight"]), "cool"),
            _with_tags(_pngimg("hoodie", "hoodie_PNG44.png", "https://pngimg.com/image/104438", "Navy hoodie", "A fuller hoodie handles cooler air better when the temperature keeps dropping into the evening.", ["Covered up", "Casual warmth"]), "cool"),
        ],
        "cold": [
            _with_tags(_pngimg("hoodie", "hoodie_PNG43.png", "https://pngimg.com/image/104437", "Heavy hoodie", "A heavier hoodie is the right move once the weather crosses from cool into properly cold.", ["Cold-ready", "Heavier fabric"]), "cold"),
            _with_tags(_pngimg("hoodie", "hoodie_PNG44.png", "https://pngimg.com/image/104438", "Navy hoodie", "A denser hoodie keeps heat in better than a dress shirt or plain long-sleeve top.", ["Thicker layer", "Covered"]), "cold"),
            _with_tags(_pngimg("hoodie", "hoodie_PNG45.png", "https://pngimg.com/image/104439", "Black hoodie", "A darker hoodie is a practical cold-weather layer if the style direction is casual.", ["Streetwear", "Warm"]), "cold"),
            _with_tags(_pngimg("hoodie", "hoodie_PNG46.png", "https://pngimg.com/image/104440", "Grey hoodie", "A classic hoodie still works well in colder weather if you are layering under a jacket.", ["Layerable", "Soft lining"]), "cold"),
            _with_tags(_pngimg("sweater", "sweater_PNG81.png", "https://pngimg.com/image/11670", "Blue sweater", "A sweater remains a strong option for colder days when you want warmth without a sporty hoodie feel.", ["Knit", "Winter-friendly"]), "cold"),
            _with_tags(_pngimg("sweater", "sweater_PNG57.png", "https://pngimg.com/image/11646", "Neutral winter sweater", "A denser sweater gives a cleaner cold-weather option when you want warmth without a bulky look.", ["Dense knit", "Winter"]), "cold"),
            _with_tags(_pngimg("sweater", "sweater_PNG48.png", "https://pngimg.com/image/11637", "Dark winter sweater", "A darker heavier sweater works well once the weather demands more than a shirt or tee.", ["Heavy knit", "Cold-day"]), "cold"),
            _with_tags(_pngimg("sweater", "sweater_PNG31.png", "https://pngimg.com/image/11620", "Classic winter knit", "A classic knit stays relevant in cold weather if the outfit is layered properly.", ["Classic", "Cold-ready"]), "cold"),
            _with_tags(_pngimg("hoodie", "hoodie_PNG41.png", "https://pngimg.com/image/104435", "Cream hoodie", "A fuller pullover helps hold warmth more effectively once the air is properly cold.", ["Pullover", "High comfort"]), "cold"),
        ],
    },
    "bottoms": {
        "hot": [
            _pngimg("jeans", "jeans_PNG5777.png", "https://pngimg.com/image/5777", "Denim shorts", "A shorter denim bottom is easier to tolerate in hotter weather than full trousers.", ["Short length", "Warm-weather"]),
            _pngimg("jeans", "jeans_PNG5776.png", "https://pngimg.com/image/5776", "Blue jeans", "If you still want full coverage, lighter jeans are the better fallback over heavy trousers.", ["Fallback option", "Covered"]),
            _pngimg("jeans", "jeans_PNG5779.png", "https://pngimg.com/image/5779", "Slim jeans", "Slim denim still works if the heat is manageable and you prefer full-length bottoms.", ["Slim fit", "Optional full length"]),
            _pngimg("jeans", "jeans_PNG5771.png", "https://pngimg.com/image/5771", "Straight jeans", "Straight denim is more wearable than heavier pants if the day is hot but not extreme.", ["Straight fit", "Casual"]),
            _pngimg("jeans", "jeans_PNG5768.png", "https://pngimg.com/image/5768", "Relaxed denim", "A lighter relaxed jean still works as a hotter-day fallback when you want more coverage.", ["Relaxed fit", "Fallback"]),
            _pngimg("jeans", "jeans_PNG5759.png", "https://pngimg.com/image/5759", "Soft blue denim", "A softer denim option keeps the outfit casual without feeling as heavy as denser pants.", ["Lighter wash", "Casual"]),
        ],
        "mild": [
            _pngimg("jeans", "jeans_PNG5776.png", "https://pngimg.com/image/5776", "Blue jeans", "Jeans are the simplest balanced-weather base when shorts feel too exposed.", ["Everyday", "Full length"]),
            _pngimg("jeans", "jeans_PNG5779.png", "https://pngimg.com/image/5779", "Slim jeans", "Slim denim works well when the weather is stable and you want a neater look.", ["Clean profile", "Balanced"]),
            _pngimg("jeans", "jeans_PNG5771.png", "https://pngimg.com/image/5771", "Straight jeans", "A straight-leg jean is comfortable through a mild day and easy to pair with most tops.", ["Reliable", "Comfortable"]),
            _pngimg("jeans", "jeans_PNG5748.png", "https://pngimg.com/image/5748", "Stacked jeans", "A fuller jean works if the weather feels balanced but a little cooler than expected.", ["Relaxed fit", "Denim staple"]),
            _pngimg("jeans", "jeans_PNG5747.png", "https://pngimg.com/image/5747", "Deep blue jeans", "A darker jean keeps the outfit polished without moving into formal trousers.", ["Darker wash", "Polished casual"]),
            _pngimg("jeans", "jeans_PNG5766.png", "https://pngimg.com/image/5766", "Classic mild denim", "Classic denim remains the easiest choice when the weather sits in the middle and you want reliability.", ["Classic", "Balanced weather"]),
            _pngimg("jeans", "jeans_PNG5745.png", "https://pngimg.com/image/5745", "Structured denim", "A more structured denim shape works when you want mild-weather polish without formal trousers.", ["Structured", "Smart casual"]),
        ],
        "cool": [
            _pngimg("jeans", "jeans_PNG5779.png", "https://pngimg.com/image/5779", "Slim jeans", "Once the weather cools down, full-length denim becomes the safer default base.", ["Covered", "Cool-weather"]),
            _pngimg("jeans", "jeans_PNG5771.png", "https://pngimg.com/image/5771", "Straight jeans", "Straight jeans are useful when cooler air makes lighter bottoms less comfortable.", ["Straight fit", "Reliable"]),
            _pngimg("jeans", "jeans_PNG5748.png", "https://pngimg.com/image/5748", "Stacked denim", "A denser jean works well if the day stays cool from morning into the evening.", ["Denser fabric", "Long day"]),
            _pngimg("jeans", "jeans_PNG5747.png", "https://pngimg.com/image/5747", "Dark denim", "Darker denim helps if you want something that feels a little warmer and more grounded.", ["Darker wash", "Covered"]),
            _pngimg("jeans", "jeans_PNG5745.png", "https://pngimg.com/image/5745", "Classic denim", "Classic denim remains the easiest cool-day bottom when you do not need technical fabrics.", ["Classic", "Casual"]),
        ],
        "cold": [
            _pngimg("jeans", "jeans_PNG5748.png", "https://pngimg.com/image/5748", "Stacked denim", "Heavier denim makes more sense once colder weather turns lighter pants into a weak choice.", ["Cold-ready", "Heavier"]),
            _pngimg("jeans", "jeans_PNG5747.png", "https://pngimg.com/image/5747", "Dark denim", "A dense dark jean gives better cold-weather balance than thin or cropped bottoms.", ["Dense", "Longline"]),
            _pngimg("jeans", "jeans_PNG5745.png", "https://pngimg.com/image/5745", "Classic denim", "A sturdy jean works better once cold air makes exposed ankles or thinner fabrics uncomfortable.", ["Warm enough", "Everyday"]),
            _pngimg("jeans", "jeans_PNG5779.png", "https://pngimg.com/image/5779", "Slim winter jean", "A slim jean is still fine in the cold if the rest of the outfit adds enough warmth.", ["Slim fit", "Layer-friendly"]),
        ],
    },
    "outerwear": {
        "light": [
            _pngimg("jacket", "jacket_PNG8044.png", "https://pngimg.com/image/8044", "Green jacket", "A lighter jacket is enough when the outer layer is mostly there for backup.", ["Light outerwear", "Transitional"]),
            _pngimg("jacket", "jacket_PNG8043.png", "https://pngimg.com/image/8043", "Brown jacket", "A compact jacket keeps the outfit practical without making it feel overbuilt.", ["Everyday", "Light cover"]),
            _pngimg("jacket", "jacket_PNG8047.png", "https://pngimg.com/image/8047", "Grey wind jacket", "A wind-friendly shell is useful when the temperature is okay but the breeze changes the feel.", ["Wind layer", "Shell feel"]),
            _pngimg("jacket", "jacket_PNG8049.png", "https://pngimg.com/image/8049", "Minimal jacket", "A simple jacket works well when you only need a little extra structure and coverage.", ["Minimal", "Backup layer"]),
            _pngimg("jacket", "jacket_PNG8034.png", "https://pngimg.com/image/8034", "Red jacket", "A lighter jacket is enough once the weather only calls for mild outer coverage.", ["Light warmth", "Statement color"]),
            _pngimg("jacket", "jacket_PNG8036.png", "https://pngimg.com/image/8036", "Compact jacket", "A shorter jacket works when the weather only needs a little extra cover, not a full coat.", ["Compact", "Low bulk"]),
        ],
        "mid": [
            _pngimg("jacket", "jacket_PNG8026.png", "https://pngimg.com/image/8026", "Leather jacket", "A medium-weight jacket makes more sense when cool air or wind starts affecting comfort.", ["Mid warmth", "Structured"]),
            _pngimg("jacket", "jacket_PNG8047.png", "https://pngimg.com/image/8047", "Grey shell jacket", "A shell-style jacket works if the day needs more protection than a soft overshirt.", ["Shell", "Weather-aware"]),
            _pngimg("raincoat", "raincoat_PNG7.png", "https://pngimg.com/image/113976", "Light raincoat", "A rain-ready outer layer helps once showers become part of the day.", ["Rain cover", "Mid layer"]),
            _pngimg("raincoat", "raincoat_PNG25.png", "https://pngimg.com/image/113994", "Field raincoat", "A longer coat is useful when cooler weather and light rain are both part of the picture.", ["Longer cut", "Protective"]),
            _pngimg("jacket", "jacket_PNG8044.png", "https://pngimg.com/image/8044", "Green shell jacket", "A structured jacket gives enough warmth and coverage for cooler mixed conditions.", ["Structured", "Cool-weather"]),
        ],
        "heavy": [
            _pngimg("raincoat", "raincoat_PNG61.png", "https://pngimg.com/image/114030", "Heavy raincoat", "A full outer layer is the right call when cold weather needs real protection.", ["High coverage", "Cold-weather"]),
            _pngimg("jacket", "jacket_PNG8026.png", "https://pngimg.com/image/8026", "Leather outer layer", "A denser jacket makes more sense once lighter outerwear stops being enough.", ["Dense layer", "Cold snap"]),
            _pngimg("raincoat", "raincoat_PNG25.png", "https://pngimg.com/image/113994", "Long coat", "A longer coat profile helps once wind and cold both need to be handled properly.", ["Longline", "Higher warmth"]),
            _pngimg("jacket", "jacket_PNG8047.png", "https://pngimg.com/image/8047", "Grey winter shell", "A heavier shell-style jacket keeps weather pressure off the rest of the outfit.", ["Weather shield", "Outer protection"]),
        ],
    },
    "shoes": {
        "hot": [
            _pngimg("running_shoes", "running_shoes_PNG5809.png", "https://pngimg.com/image/5809", "Light running shoe", "A breathable runner is the easiest hot-weather shoe when you still want support.", ["Breathable", "Active comfort"]),
            _pngimg("running_shoes", "running_shoes_PNG5812.png", "https://pngimg.com/image/5812", "Blue trainer", "A lighter trainer keeps walking comfortable without looking too heavy.", ["Light shoe", "Walking-ready"]),
            _pngimg("running_shoes", "running_shoes_PNG5806.png", "https://pngimg.com/image/5806", "Sport trainer", "A sportier trainer stays practical in hotter weather as long as it remains breathable.", ["Sporty", "Breathable"]),
            _pngimg("sandals", "sandals_PNG9681.png", "https://pngimg.com/image/9681", "Open sandals", "Sandals are the easiest warm-weather option when the ground is dry and the day is hot.", ["Open footwear", "Dry weather"]),
            _pngimg("sandals", "sandals_PNG9698.png", "https://pngimg.com/image/9698", "Simple sandals", "A lighter sandal works once the weather stays hot and the day is mostly easygoing.", ["Open fit", "Warm-day"]),
            _pngimg("sandals", "sandals_PNG9693.png", "https://pngimg.com/image/9693", "Strap sandals", "A strapped sandal works if you want a little more hold than a very minimal pair.", ["Airflow", "Secure straps"]),
            _pngimg("sandals", "sandals_PNG9701.png", "https://pngimg.com/image/9701", "Wide sandals", "A broader sandal shape still keeps the outfit light when the heat is doing most of the work.", ["Lightwear", "Warm-day"]),
            _pngimg("sandals", "sandals_PNG9709.png", "https://pngimg.com/image/9709", "Casual sandals", "A casual sandal keeps the whole outfit visually lighter in hotter conditions.", ["Low bulk", "Summer ready"]),
        ],
        "default": [
            _pngimg("running_shoes", "running_shoes_PNG5809.png", "https://pngimg.com/image/5809", "Runner", "A running shoe still works well for general movement when the weather is balanced.", ["Comfort", "Movement"]),
            _pngimg("running_shoes", "running_shoes_PNG5812.png", "https://pngimg.com/image/5812", "Blue runner", "A lighter trainer is still a solid everyday choice when the weather stays normal.", ["Everyday", "Easy wear"]),
            _pngimg("running_shoes", "running_shoes_PNG5817.png", "https://pngimg.com/image/5817", "White trainer", "A cleaner trainer works well as a balanced-weather everyday shoe.", ["Clean look", "Everyday"]),
            _pngimg("running_shoes", "running_shoes_PNG5780.png", "https://pngimg.com/image/5780", "Trail sneaker", "A chunkier sneaker is still fine when the weather is balanced but movement-heavy.", ["Movement-ready", "Covered"]),
            _pngimg("sandals", "sandals_PNG9681.png", "https://pngimg.com/image/9681", "Casual sandal", "If the weather leans warm and relaxed, a sandal can still be a reasonable everyday option.", ["Warm-leaning", "Casual"]),
            _pngimg("sandals", "sandals_PNG9709.png", "https://pngimg.com/image/9709", "Simple sandal", "A simple sandal works as a lighter option when the day stays dry and easy.", ["Dry ground", "Light option"]),
        ],
        "wet": [
            _pngimg("boots", "boots_PNG7815.png", "https://pngimg.com/image/7815", "Rain boots", "Boots are safer once the ground is wet enough that lighter shoes lose grip.", ["Grip", "Wet-ready"]),
            _pngimg("boots", "boots_PNG7813.png", "https://pngimg.com/image/7813", "Black boots", "A sturdier boot works better when the ground is damp and you need more protection.", ["Protected", "Wet streets"]),
            _pngimg("running_shoes", "running_shoes_PNG5812.png", "https://pngimg.com/image/5812", "Covered runner", "A covered athletic shoe is still usable if the wet conditions are manageable.", ["Covered", "Fallback"]),
            _pngimg("running_shoes", "running_shoes_PNG5809.png", "https://pngimg.com/image/5809", "Protected runner", "A runner with more coverage still works if the weather is wet but not severe.", ["Covered", "Fallback option"]),
        ],
    },
    "accessories": {
        "sunny": [
            _pngimg("sunglasses", "sunglasses_PNG47.png", "https://pngimg.com/image/54403", "Classic sunglasses", "Sunglasses are the easiest sun accessory when glare is the real problem.", ["Sun protection", "Glare control"]),
            _pngimg("sunglasses", "sunglasses_PNG61.png", "https://pngimg.com/image/54417", "Rounded sunglasses", "A lighter sunglasses shape still does the job if the sky stays bright.", ["Light carry", "Bright weather"]),
            _pngimg("sunglasses", "sunglasses_PNG62.png", "https://pngimg.com/image/54418", "Dark sunglasses", "A darker pair gives a stronger visual finish without adding bulk.", ["Sharp look", "UV support"]),
            _pngimg("sunglasses", "sunglasses_PNG66.png", "https://pngimg.com/image/54422", "Sport sunglasses", "A sportier pair works if the day is brighter and more active.", ["Active use", "Secure fit"]),
            _pngimg("cap", "cap_PNG5678.png", "https://pngimg.com/image/5678", "Baseball cap", "A cap is still a useful bright-weather accessory if you want shade without carrying much.", ["Shade", "Casual"]),
            _pngimg("cap", "cap_PNG5670.png", "https://pngimg.com/image/5670", "Dark cap", "A darker cap keeps things simple when the weather needs a small sun-blocking extra.", ["Sun cover", "Easy carry"]),
            _pngimg("cap", "cap_PNG5684.png", "https://pngimg.com/image/5684", "Rounded cap", "A second cap option gives you another bright-weather extra without changing the outfit too much.", ["Shade", "Light extra"]),
        ],
        "cold": [
            _pngimg("scarf", "scarf_PNG39.png", "https://pngimg.com/image/111339", "Grey scarf", "A scarf is one of the easiest ways to make a cold outfit feel more complete.", ["Warmth", "Neck cover"]),
            _pngimg("scarf", "scarf_PNG41.png", "https://pngimg.com/image/111341", "Brown scarf", "A scarf adds real comfort once colder air starts cutting through the outfit.", ["Cold-ready", "Wrapped"]),
            _pngimg("scarf", "scarf_PNG23.png", "https://pngimg.com/image/111323", "Long scarf", "A longer scarf works if the cold needs more coverage around the neck and chest.", ["Longline", "Extra warmth"]),
            _pngimg("scarf", "scarf_PNG45.png", "https://pngimg.com/image/111345", "Minimal scarf", "A simple scarf keeps the outfit warmer without complicating the look.", ["Minimal", "Winter add-on"]),
            _pngimg("scarf", "scarf_PNG63.png", "https://pngimg.com/image/43968", "Soft scarf", "A softer scarf still works well when the goal is warmth without a bulky finish.", ["Soft knit", "Cold-weather"]),
        ],
        "windy": [
            _pngimg("scarf", "scarf_PNG39.png", "https://pngimg.com/image/111339", "Wind scarf", "A wrapped scarf helps once the breeze turns manageable weather into something sharper.", ["Wind cover", "Secure fit"]),
            _pngimg("sunglasses", "sunglasses_PNG66.png", "https://pngimg.com/image/54422", "Sport sunglasses", "A more secure pair of sunglasses works better than anything loose in windy weather.", ["Secure", "Low bulk"]),
            _pngimg("scarf", "scarf_PNG45.png", "https://pngimg.com/image/111345", "Compact scarf", "A compact scarf is useful if you need weather protection without carrying too much.", ["Compact", "Practical"]),
            _pngimg("sunglasses", "sunglasses_PNG47.png", "https://pngimg.com/image/54403", "Classic shades", "A smaller accessory is still fine if it stays secure and easy to manage in the wind.", ["Stable", "Simple"]),
        ],
        "default": [
            _pngimg("sunglasses", "sunglasses_PNG47.png", "https://pngimg.com/image/54403", "Classic sunglasses", "A light accessory is enough when the weather is cooperative and you just want a finish.", ["Minimal", "Easy extra"]),
            _pngimg("sunglasses", "sunglasses_PNG61.png", "https://pngimg.com/image/54417", "Rounded sunglasses", "Sunglasses still work as a simple style-led extra even when the day is not especially bright.", ["Style-led", "Optional"]),
            _pngimg("sunglasses", "sunglasses_PNG62.png", "https://pngimg.com/image/54418", "Dark sunglasses", "A cleaner frame gives the outfit a practical accessory without changing the whole look.", ["Clean finish", "Low effort"]),
            _pngimg("sunglasses", "sunglasses_PNG66.png", "https://pngimg.com/image/54422", "Sport pair", "A sportier accessory still works if you want something more active-looking.", ["Active edge", "Simple carry"]),
            _pngimg("cap", "cap_PNG5678.png", "https://pngimg.com/image/5678", "Everyday cap", "A simple cap still works as a practical optional extra when nothing weather-specific stands out.", ["Optional", "Daily wear"]),
        ],
    },
    "weather_add_ons": {
        "rain": [
            _pngimg("umbrella", "umbrella_PNG69127.png", "https://pngimg.com/image/69127", "Classic umbrella", "An umbrella is still the most practical add-on when showers are part of the day.", ["Rain-ready", "Portable"]),
            _pngimg("umbrella", "umbrella_PNG69141.png", "https://pngimg.com/image/69141", "Compact umbrella", "A smaller umbrella is enough if rain looks more likely than severe.", ["Carry item", "Backup"]),
            _pngimg("umbrella", "umbrella_PNG69174.png", "https://pngimg.com/image/69174", "Dark umbrella", "A darker umbrella gives a stronger carry option when the rain risk is real.", ["Practical", "Shower cover"]),
            _pngimg("umbrella", "umbrella_PNG69198.png", "https://pngimg.com/image/69198", "Wide umbrella", "A wider umbrella makes more sense if rain looks steady rather than brief.", ["More coverage", "Wet weather"]),
            _pngimg("umbrella", "umbrella_PNG69176.png", "https://pngimg.com/image/69176", "Straight umbrella", "A straight umbrella works as a cleaner rain backup when you want a more compact carry.", ["Compact", "Rain shield"]),
            _pngimg("umbrella", "umbrella_PNG69167.png", "https://pngimg.com/image/69167", "Curved umbrella", "A curved-handle umbrella is still a useful rain add-on if showers look more likely than not.", ["Carry-ready", "Daily rain"]),
            _pngimg("umbrella", "umbrella_PNG69137.png", "https://pngimg.com/image/69137", "Slim umbrella", "A slimmer umbrella still works well when you want something easy to carry through light rain.", ["Slim carry", "Light rain"]),
            _pngimg("umbrella", "umbrella_PNG69213.png", "https://pngimg.com/image/69213", "Rounded umbrella", "A fuller umbrella shape gives you another practical wet-weather carry option.", ["Full canopy", "Rain cover"]),
            _pngimg("raincoat", "raincoat_PNG7.png", "https://pngimg.com/image/113976", "Raincoat", "A weather-ready layer becomes part of the add-on kit when rain is persistent.", ["Layer backup", "Rain protection"]),
        ],
        "sun": [
            _pngimg("sunglasses", "sunglasses_PNG47.png", "https://pngimg.com/image/54403", "Sun shades", "If the sun is the main issue, a practical add-on like sunglasses matters more than another layer.", ["Bright skies", "UV support"]),
            _pngimg("sunglasses", "sunglasses_PNG61.png", "https://pngimg.com/image/54417", "Rounded shades", "A second sunglasses option gives you a lighter bright-weather add-on.", ["Light carry", "Easy protection"]),
            _pngimg("sunglasses", "sunglasses_PNG62.png", "https://pngimg.com/image/54418", "Dark shades", "A darker pair works if the day is bright and more exposed than it first looks.", ["Glare control", "Sun-ready"]),
            _pngimg("sunglasses", "sunglasses_PNG66.png", "https://pngimg.com/image/54422", "Sport shades", "A sportier add-on is useful if the day involves more movement outdoors.", ["Outdoor use", "Secure fit"]),
        ],
        "wind": [
            _pngimg("scarf", "scarf_PNG39.png", "https://pngimg.com/image/111339", "Wind scarf", "A scarf is a smarter add-on than loose accessories when the wind is the main issue.", ["Wind block", "Compact"]),
            _pngimg("scarf", "scarf_PNG45.png", "https://pngimg.com/image/111345", "Compact scarf", "A shorter scarf is enough if you just need a small extra barrier against the air.", ["Compact", "Secure"]),
            _pngimg("umbrella", "umbrella_PNG69141.png", "https://pngimg.com/image/69141", "Weather backup", "A compact carry item still works as a backup if the weather looks mixed rather than purely windy.", ["Backup", "Carry-ready"]),
            _pngimg("raincoat", "raincoat_PNG25.png", "https://pngimg.com/image/113994", "Wind-ready coat", "A light weather coat becomes the more useful add-on once the breeze is persistent.", ["Outer backup", "Wind-aware"]),
        ],
        "default": [
            _pngimg("sunglasses", "sunglasses_PNG47.png", "https://pngimg.com/image/54403", "Optional shades", "Nothing looks mandatory, so a small optional extra is enough if you want one.", ["Optional", "Low bulk"]),
            _pngimg("umbrella", "umbrella_PNG69141.png", "https://pngimg.com/image/69141", "Compact umbrella", "A compact backup item is enough when the weather is mostly cooperative.", ["Emergency backup", "Portable"]),
            _pngimg("sunglasses", "sunglasses_PNG61.png", "https://pngimg.com/image/54417", "Simple sunglasses", "A small add-on like sunglasses still works if you want a little practical polish.", ["Simple", "Easy extra"]),
            _pngimg("scarf", "scarf_PNG45.png", "https://pngimg.com/image/111345", "Light scarf", "A lighter scarf is fine if you want one extra carry item without committing to something bulky.", ["Soft add-on", "Optional"]),
        ],
    },
}


TARGET_STYLE_COUNT = 10


def _collect_slot_variants(slot_key, primary_pool_key):
    slot_catalog = CLOTHING_VARIANT_CATALOG.get(slot_key, {})
    ordered_pool_keys = [primary_pool_key] + [
        pool_key for pool_key in slot_catalog.keys() if pool_key != primary_pool_key
    ]

    collected = []
    seen_urls = set()

    for pool_key in ordered_pool_keys:
        for variant in slot_catalog.get(pool_key, []):
            variant_url = str(variant.get("image_url") or "")
            if not variant_url or variant_url in seen_urls:
                continue
            seen_urls.add(variant_url)
            collected.append(deepcopy(variant))
            if len(collected) >= TARGET_STYLE_COUNT:
                return collected

    if collected and len(collected) < TARGET_STYLE_COUNT:
        fallback_variants = list(collected)
        fallback_index = 0
        while len(collected) < TARGET_STYLE_COUNT:
            collected.append(deepcopy(fallback_variants[fallback_index % len(fallback_variants)]))
            fallback_index += 1

    return collected


def _resolve_clothing_pool_key(slot_key, current_temp, rain_chance, uv_index, wind_speed, precipitation, condition):
    is_wet = rain_chance >= 45 or precipitation >= 0.2 or condition in {"Rainy", "Snowy", "Thunderstorm"}
    is_sunny = uv_index >= 6 or (condition == "Sunny" and rain_chance < 20)
    is_windy = wind_speed >= 25

    if current_temp >= 28:
        temp_band = "hot"
    elif current_temp >= 18:
        temp_band = "mild"
    elif current_temp >= 10:
        temp_band = "cool"
    else:
        temp_band = "cold"

    if slot_key in {"tops", "bottoms"}:
        pool_key = temp_band
    elif slot_key == "outerwear":
        if temp_band == "cold":
            pool_key = "heavy"
        elif temp_band == "cool" or is_wet or is_windy:
            pool_key = "mid"
        else:
            pool_key = "light"
    elif slot_key == "shoes":
        pool_key = "wet" if is_wet else ("hot" if temp_band == "hot" else "default")
    elif slot_key == "accessories":
        if temp_band == "cold":
            pool_key = "cold"
        elif is_sunny:
            pool_key = "sunny"
        elif is_windy:
            pool_key = "windy"
        else:
            pool_key = "default"
    else:
        if is_wet:
            pool_key = "rain"
        elif is_sunny:
            pool_key = "sun"
        elif is_windy:
            pool_key = "wind"
        else:
            pool_key = "default"

    return pool_key


def get_clothing_visual_bundle_for_conditions(
    slot_key,
    current_temp,
    rain_chance=0,
    uv_index=0,
    wind_speed=0,
    precipitation=0,
    condition="",
):
    pool_key = _resolve_clothing_pool_key(
        slot_key,
        current_temp,
        rain_chance,
        uv_index,
        wind_speed,
        precipitation,
        condition,
    )

    return {
        "profile_key": f"{slot_key}-{pool_key}",
        "variants": _collect_slot_variants(slot_key, pool_key),
    }


def get_clothing_visual_bundle(slot_key, weather_to_show):
    current = weather_to_show["current"]
    today = weather_to_show["forecast"][0] if weather_to_show.get("forecast") else {}
    return get_clothing_visual_bundle_for_conditions(
        slot_key,
        current["temperature"],
        today.get("rain_chance", 0),
        today.get("uv_index", 0),
        current["wind"],
        current.get("precipitation", 0),
        current.get("condition", ""),
    )
