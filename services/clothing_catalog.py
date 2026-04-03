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


CLOTHING_VARIANT_CATALOG = {
    "tops": {
        "hot": [
            _pngimg("polo_shirt", "polo_shirt_PNG8161.png", "https://pngimg.com/image/8161", "White polo", "A polo keeps the outfit cleaner than a plain tee while staying breathable in hot weather.", ["Breathable", "Collared"]),
            _pngimg("polo_shirt", "polo_shirt_PNG8153.png", "https://pngimg.com/image/8153", "Grey polo", "A neutral polo works well when you want a warm-weather top that still looks structured.", ["Lightweight", "Easy pairing"]),
            _pngimg("polo_shirt", "polo_shirt_PNG8154.png", "https://pngimg.com/image/8154", "Sky polo", "A softer color keeps the outfit feeling lighter when the temperature is high.", ["Airy", "Warm-weather"]),
            _pngimg("polo_shirt", "polo_shirt_PNG8155.png", "https://pngimg.com/image/8155", "Navy polo", "A darker polo still works in the heat if you want something sharper than a casual tee.", ["Structured", "Summer smart"]),
            _pngimg("polo_shirt", "polo_shirt_PNG8143.png", "https://pngimg.com/image/8143", "Blue polo", "This kind of short-sleeve polo is an easy option when the day stays warm but active.", ["Short sleeve", "Clean finish"]),
            _pngimg("polo_shirt", "polo_shirt_PNG8144.png", "https://pngimg.com/image/8144", "Red polo", "A stronger color still fits hot weather as long as the fabric stays light and breathable.", ["Breathable", "Statement color"]),
        ],
        "mild": [
            _pngimg("tshirt", "tshirt_PNG5437.png", "https://pngimg.com/image/5437", "White tee", "A plain tee is still one of the easiest balanced-weather tops when you do not need heavy layering.", ["Minimal", "Everyday"]),
            _pngimg("tshirt", "tshirt_PNG5436.png", "https://pngimg.com/image/5436", "Black tee", "A darker tee works well in mild temperatures when comfort is the priority.", ["Versatile", "Clean look"]),
            _pngimg("tshirt", "tshirt_PNG5450.png", "https://pngimg.com/image/5450", "Grey tee", "A neutral tee is an easy middle-ground pick when the weather is stable.", ["Balanced", "Casual"]),
            _pngimg("dress_shirt", "dress_shirt_PNG8098.png", "https://pngimg.com/image/8098", "Blue dress shirt", "A long-sleeve shirt works once the weather is mild enough to support a cleaner silhouette.", ["Long sleeve", "Polished"]),
            _pngimg("dress_shirt", "dress_shirt_PNG8077.png", "https://pngimg.com/image/8077", "White dress shirt", "A crisp shirt gives you a sharper option for mild conditions without needing outerwear.", ["Smart casual", "Sharp finish"]),
            _pngimg("dress_shirt", "dress_shirt_PNG8083.png", "https://pngimg.com/image/8083", "Soft blue shirt", "A lighter dress shirt is useful when you want something tidier than a tee in balanced weather.", ["Lighter layer", "Structured"]),
        ],
        "cool": [
            _pngimg("dress_shirt", "dress_shirt_PNG8112.png", "https://pngimg.com/image/8112", "Layering shirt", "A full shirt becomes more useful once the air cools down and bare arms start feeling exposed.", ["Cool-weather", "Layer-ready"]),
            _pngimg("sweater", "sweater_PNG81.png", "https://pngimg.com/image/11670", "Blue sweater", "A sweater is the better starting point when the day feels cool enough that a tee is no longer enough.", ["Knitwear", "Warmer fabric"]),
            _pngimg("hoodie", "hoodie_PNG46.png", "https://pngimg.com/image/104440", "Grey hoodie", "A hoodie gives you more warmth than a shirt while still staying casual and easy to wear.", ["Casual layer", "Soft warmth"]),
            _pngimg("hoodie", "hoodie_PNG45.png", "https://pngimg.com/image/104439", "Black hoodie", "A clean hoodie is an easy cool-weather layer if you want comfort without a jacket yet.", ["Pullover", "Everyday warmth"]),
            _pngimg("hoodie", "hoodie_PNG41.png", "https://pngimg.com/image/104435", "Cream hoodie", "A lighter hoodie is useful when the day is cool, not freezing, and you still want a softer look.", ["Comfort", "Midweight"]),
            _pngimg("hoodie", "hoodie_PNG44.png", "https://pngimg.com/image/104438", "Navy hoodie", "A fuller hoodie handles cooler air better when the temperature keeps dropping into the evening.", ["Covered up", "Casual warmth"]),
        ],
        "cold": [
            _pngimg("hoodie", "hoodie_PNG43.png", "https://pngimg.com/image/104437", "Heavy hoodie", "A heavier hoodie is the right move once the weather crosses from cool into properly cold.", ["Cold-ready", "Heavier fabric"]),
            _pngimg("hoodie", "hoodie_PNG44.png", "https://pngimg.com/image/104438", "Navy hoodie", "A denser hoodie keeps heat in better than a dress shirt or plain long-sleeve top.", ["Thicker layer", "Covered"]),
            _pngimg("hoodie", "hoodie_PNG45.png", "https://pngimg.com/image/104439", "Black hoodie", "A darker hoodie is a practical cold-weather layer if the style direction is casual.", ["Streetwear", "Warm"]),
            _pngimg("hoodie", "hoodie_PNG46.png", "https://pngimg.com/image/104440", "Grey hoodie", "A classic hoodie still works well in colder weather if you are layering under a jacket.", ["Layerable", "Soft lining"]),
            _pngimg("sweater", "sweater_PNG81.png", "https://pngimg.com/image/11670", "Blue sweater", "A sweater remains a strong option for colder days when you want warmth without a sporty hoodie feel.", ["Knit", "Winter-friendly"]),
            _pngimg("hoodie", "hoodie_PNG41.png", "https://pngimg.com/image/104435", "Cream hoodie", "A fuller pullover helps hold warmth more effectively once the air is properly cold.", ["Pullover", "High comfort"]),
        ],
    },
    "bottoms": {
        "hot": [
            _pngimg("jeans", "jeans_PNG5777.png", "https://pngimg.com/image/5777", "Denim shorts", "A shorter denim bottom is easier to tolerate in hotter weather than full trousers.", ["Short length", "Warm-weather"]),
            _pngimg("jeans", "jeans_PNG5776.png", "https://pngimg.com/image/5776", "Blue jeans", "If you still want full coverage, lighter jeans are the better fallback over heavy trousers.", ["Fallback option", "Covered"]),
            _pngimg("jeans", "jeans_PNG5779.png", "https://pngimg.com/image/5779", "Slim jeans", "Slim denim still works if the heat is manageable and you prefer full-length bottoms.", ["Slim fit", "Optional full length"]),
            _pngimg("jeans", "jeans_PNG5771.png", "https://pngimg.com/image/5771", "Straight jeans", "Straight denim is more wearable than heavier pants if the day is hot but not extreme.", ["Straight fit", "Casual"]),
        ],
        "mild": [
            _pngimg("jeans", "jeans_PNG5776.png", "https://pngimg.com/image/5776", "Blue jeans", "Jeans are the simplest balanced-weather base when shorts feel too exposed.", ["Everyday", "Full length"]),
            _pngimg("jeans", "jeans_PNG5779.png", "https://pngimg.com/image/5779", "Slim jeans", "Slim denim works well when the weather is stable and you want a neater look.", ["Clean profile", "Balanced"]),
            _pngimg("jeans", "jeans_PNG5771.png", "https://pngimg.com/image/5771", "Straight jeans", "A straight-leg jean is comfortable through a mild day and easy to pair with most tops.", ["Reliable", "Comfortable"]),
            _pngimg("jeans", "jeans_PNG5748.png", "https://pngimg.com/image/5748", "Stacked jeans", "A fuller jean works if the weather feels balanced but a little cooler than expected.", ["Relaxed fit", "Denim staple"]),
            _pngimg("jeans", "jeans_PNG5747.png", "https://pngimg.com/image/5747", "Deep blue jeans", "A darker jean keeps the outfit polished without moving into formal trousers.", ["Darker wash", "Polished casual"]),
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
            _pngimg("shoes", "shoes_PNG7465.png", "https://pngimg.com/image/7465", "Casual shoe", "A simple lightweight shoe still works if sandals are too open for the day.", ["Casual", "Warm-day option"]),
            _pngimg("shoes", "shoes_PNG7471.png", "https://pngimg.com/image/7471", "Grey low-top", "A lower-profile shoe helps the outfit feel lighter in hotter weather.", ["Low-top", "Easy wear"]),
        ],
        "default": [
            _pngimg("shoes", "shoes_PNG7460.png", "https://pngimg.com/image/7460", "Street sneaker", "A standard sneaker handles most moderate days with no extra thought required.", ["Versatile", "Everyday"]),
            _pngimg("shoes", "shoes_PNG7465.png", "https://pngimg.com/image/7465", "Casual sneaker", "A casual sneaker is still the safest all-day choice when conditions stay normal.", ["Reliable", "Daily wear"]),
            _pngimg("running_shoes", "running_shoes_PNG5809.png", "https://pngimg.com/image/5809", "Runner", "A running shoe still works well for general movement when the weather is balanced.", ["Comfort", "Movement"]),
            _pngimg("shoes", "shoes_PNG7471.png", "https://pngimg.com/image/7471", "Grey sneaker", "A cleaner sneaker helps keep the outfit easy and practical.", ["Clean look", "Covered"]),
        ],
        "wet": [
            _pngimg("boots", "boots_PNG7784.png", "https://pngimg.com/image/7784", "Boots", "Boots are safer once the ground is wet enough that lighter shoes lose grip.", ["Grip", "Wet-ready"]),
            _pngimg("shoes", "shoes_PNG7460.png", "https://pngimg.com/image/7460", "Protected sneaker", "A sturdier closed sneaker still works if you want something lighter than a boot.", ["Closed toe", "Protected"]),
            _pngimg("running_shoes", "running_shoes_PNG5812.png", "https://pngimg.com/image/5812", "Covered runner", "A covered athletic shoe is still usable if the wet conditions are manageable.", ["Covered", "Fallback"]),
            _pngimg("boots", "boots_PNG7787.png", "https://pngimg.com/image/7787", "Dark boots", "A darker boot is the stronger option if the surface looks slick or messy.", ["Traction", "Rain support"]),
        ],
    },
    "accessories": {
        "sunny": [
            _pngimg("sunglasses", "sunglasses_PNG47.png", "https://pngimg.com/image/54403", "Classic sunglasses", "Sunglasses are the easiest sun accessory when glare is the real problem.", ["Sun protection", "Glare control"]),
            _pngimg("sunglasses", "sunglasses_PNG61.png", "https://pngimg.com/image/54417", "Rounded sunglasses", "A lighter sunglasses shape still does the job if the sky stays bright.", ["Light carry", "Bright weather"]),
            _pngimg("sunglasses", "sunglasses_PNG62.png", "https://pngimg.com/image/54418", "Dark sunglasses", "A darker pair gives a stronger visual finish without adding bulk.", ["Sharp look", "UV support"]),
            _pngimg("sunglasses", "sunglasses_PNG66.png", "https://pngimg.com/image/54422", "Sport sunglasses", "A sportier pair works if the day is brighter and more active.", ["Active use", "Secure fit"]),
        ],
        "cold": [
            _pngimg("scarf", "scarf_PNG39.png", "https://pngimg.com/image/111339", "Grey scarf", "A scarf is one of the easiest ways to make a cold outfit feel more complete.", ["Warmth", "Neck cover"]),
            _pngimg("scarf", "scarf_PNG41.png", "https://pngimg.com/image/111341", "Brown scarf", "A scarf adds real comfort once colder air starts cutting through the outfit.", ["Cold-ready", "Wrapped"]),
            _pngimg("scarf", "scarf_PNG23.png", "https://pngimg.com/image/111323", "Long scarf", "A longer scarf works if the cold needs more coverage around the neck and chest.", ["Longline", "Extra warmth"]),
            _pngimg("scarf", "scarf_PNG45.png", "https://pngimg.com/image/111345", "Minimal scarf", "A simple scarf keeps the outfit warmer without complicating the look.", ["Minimal", "Winter add-on"]),
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
        ],
    },
    "weather_add_ons": {
        "rain": [
            _pngimg("umbrella", "umbrella_PNG69127.png", "https://pngimg.com/image/69127", "Classic umbrella", "An umbrella is still the most practical add-on when showers are part of the day.", ["Rain-ready", "Portable"]),
            _pngimg("umbrella", "umbrella_PNG69141.png", "https://pngimg.com/image/69141", "Compact umbrella", "A smaller umbrella is enough if rain looks more likely than severe.", ["Carry item", "Backup"]),
            _pngimg("umbrella", "umbrella_PNG69174.png", "https://pngimg.com/image/69174", "Dark umbrella", "A darker umbrella gives a stronger carry option when the rain risk is real.", ["Practical", "Shower cover"]),
            _pngimg("umbrella", "umbrella_PNG69198.png", "https://pngimg.com/image/69198", "Wide umbrella", "A wider umbrella makes more sense if rain looks steady rather than brief.", ["More coverage", "Wet weather"]),
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


def get_clothing_visual_bundle(slot_key, weather_to_show):
    current = weather_to_show["current"]
    today = weather_to_show["forecast"][0] if weather_to_show.get("forecast") else {}
    current_temp = current["temperature"]
    rain_chance = today.get("rain_chance", 0)
    uv_index = today.get("uv_index", 0)
    wind_speed = current["wind"]
    precipitation = current.get("precipitation", 0)
    condition = current.get("condition", "")

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

    return {
        "profile_key": f"{slot_key}-{pool_key}",
        "variants": deepcopy(CLOTHING_VARIANT_CATALOG.get(slot_key, {}).get(pool_key, [])),
    }
