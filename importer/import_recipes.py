import asyncio
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
import httpx
from openai import AsyncOpenAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BOTHUB_KEY = os.getenv("BOTHUB_KEY")
PEXELS_KEY = os.getenv("PEXELS_KEY")

ai = AsyncOpenAI(
    base_url="https://openai.bothub.chat/v1",
    api_key=BOTHUB_KEY
) if BOTHUB_KEY else None

MODEL = "gpt-4.1-mini"

# Перевод кухонь EN -> RU
CUISINE_RU = {
    "Russian": "Русская", "Ukrainian": "Украинская", "Italian": "Итальянская",
    "French": "Французская", "Spanish": "Испанская", "Greek": "Греческая",
    "Turkish": "Турецкая", "American": "Американская", "Mexican": "Мексиканская",
    "Chinese": "Китайская", "Japanese": "Японская", "Thai": "Тайская",
    "Indian": "Индийская", "Polish": "Польская", "British": "Британская",
    "Moroccan": "Марокканская", "Vietnamese": "Вьетнамская",
}

# ─── БЛОК 1: простые повседневные блюда (40 запросов) ───
QUERY_META = [
    {"q": "chicken",   "category": "dinner",    "tags": ["просто", "бюджетно", "на каждый день"]},
    {"q": "beef",      "category": "dinner",    "tags": ["бюджетно", "на каждый день"]},
    {"q": "pork",      "category": "dinner",    "tags": ["бюджетно", "на каждый день"]},
    {"q": "turkey",    "category": "dinner",    "tags": ["пп", "просто"]},
    {"q": "meatball",  "category": "dinner",    "tags": ["просто", "детям"]},
    {"q": "fish",      "category": "dinner",    "tags": ["пп", "просто"]},
    {"q": "tuna",      "category": "dinner",    "tags": ["быстро", "пп"]},
    {"q": "shrimp",    "category": "dinner",    "tags": ["быстро", "пп"]},
    {"q": "egg",       "category": "breakfast", "tags": ["быстро", "пп", "просто"]},
    {"q": "pancakes",  "category": "breakfast", "tags": ["детям", "выпечка", "просто"]},
    {"q": "oatmeal",   "category": "breakfast", "tags": ["пп", "быстро", "просто"]},
    {"q": "pasta",     "category": "dinner",    "tags": ["быстро", "бюджетно", "просто"]},
    {"q": "rice",      "category": "dinner",    "tags": ["бюджетно", "на каждый день"]},
    {"q": "noodle",    "category": "dinner",    "tags": ["быстро", "бюджетно"]},
    {"q": "soup",      "category": "soups",     "tags": ["бюджетно", "просто", "на каждый день"]},
    {"q": "salad",     "category": "salads",    "tags": ["пп", "быстро", "просто"]},
    {"q": "potato",    "category": "dinner",    "tags": ["бюджетно", "просто", "на каждый день"]},
    {"q": "mushroom",  "category": "dinner",    "tags": ["бюджетно", "веган"]},
    {"q": "cabbage",   "category": "dinner",    "tags": ["бюджетно", "веган"]},
    {"q": "broccoli",  "category": "dinner",    "tags": ["пп", "веган"]},
    {"q": "cake",      "category": "desserts",  "tags": ["детям", "выпечка", "просто"]},
    {"q": "cookie",    "category": "desserts",  "tags": ["детям", "выпечка", "просто"]},
    {"q": "pie",       "category": "desserts",  "tags": ["выпечка", "детям"]},
    {"q": "beans",     "category": "vegan",     "tags": ["бюджетно", "веган", "пп"]},
    {"q": "lentil",    "category": "vegan",     "tags": ["бюджетно", "веган", "пп"]},
    {"q": "cheese",    "category": "dinner",    "tags": ["быстро", "просто"]},
    {"q": "cottage",   "category": "breakfast", "tags": ["пп", "просто"]},
]

# ─── БЛОК 2: национальные кухни ───
CUISINE_QUERIES = [
    {"area": "Russian",   "count": 4},
    {"area": "Ukrainian", "count": 3},
    {"area": "Italian",   "count": 4},
    {"area": "French",    "count": 3},
    {"area": "Spanish",   "count": 3},
    {"area": "Greek",     "count": 3},
    {"area": "Turkish",   "count": 3},
    {"area": "American",  "count": 3},
    {"area": "Mexican",   "count": 3},
    {"area": "Chinese",   "count": 4},
    {"area": "Japanese",  "count": 3},
    {"area": "Thai",      "count": 3},
    {"area": "Indian",    "count": 3},
    {"area": "Polish",    "count": 3},
]

# ─── БЛОК 3: правильное питание ───
HEALTHY_QUERIES = [
    "grilled chicken", "steamed fish", "quinoa",
    "green smoothie", "chicken salad", "vegetable stir",
]


def guess_category(title: str) -> str:
    """Определяет категорию блюда по названию"""
    t = title.lower()
    if any(w in t for w in ["salad", "салат"]): return "salads"
    if any(w in t for w in ["soup", "суп", "broth", "бульон"]): return "soups"
    if any(w in t for w in ["cake", "pie", "cookie", "pudding", "dessert", "торт", "пирог"]): return "desserts"
    if any(w in t for w in ["pancake", "oatmeal", "porridge", "блин", "каша"]): return "breakfast"
    return "dinner"


async def translate_recipe(title, ingredients, steps) -> dict:
    resp = await ai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content":
             "Переведи рецепт на русский. Верни JSON: "
             '{"title": str, "ingredients": [str], "steps": [str]}'},
            {"role": "user", "content": json.dumps(
                {"title": title, "ingredients": ingredients, "steps": steps},
                ensure_ascii=False)}
        ],
        response_format={"type": "json_object"}
    )
    text = resp.choices[0].message.content
    text = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"title": title, "ingredients": ingredients, "steps": steps}


async def pexels_photo(query):
    if not PEXELS_KEY: return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get("https://api.pexels.com/v1/search",
                params={"query": query, "per_page": 1},
                headers={"Authorization": PEXELS_KEY})
            photos = r.json().get("photos", [])
            return photos[0]["src"]["large"] if photos else None
    except Exception:
        return None


async def pexels_video(query):
    if not PEXELS_KEY: return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get("https://api.pexels.com/videos/search",
                params={"query": f"cooking {query}", "per_page": 1},
                headers={"Authorization": PEXELS_KEY})
            videos = r.json().get("videos", [])
            if not videos: return None
            files = videos[0]["video_files"]
            sd = [f for f in files if (f.get("width") or 9999) <= 640]
            return (sd[0] or files[0])["link"]
    except Exception:
        return None


def extract_fields(meal):
    """Достаёт ингредиенты и шаги из meal"""
    ingredients = []
    for i in range(1, 21):
        ing = meal.get(f"strIngredient{i}")
        measure = meal.get(f"strMeasure{i}", "") or ""
        if ing and ing.strip():
            ingredients.append(f"{measure.strip()} {ing.strip()}".strip())
        if len(ingredients) >= 8: break

    instructions = meal.get("strInstructions", "") or ""
    steps = [s.strip() for s in instructions.replace("\r\n", ". ").split(".") if len(s.strip()) > 15][:6]
    if not steps:
        steps = [instructions[:200]] if instructions else ["Приготовить по вкусу"]
    return ingredients, steps


async def process_meal(meal, category, tags, cuisine, pexels_query, results, seen_ids, counter):
    """Общая обработка одного рецепта"""
    meal_id = meal.get("idMeal")
    if meal_id in seen_ids: return
    seen_ids.add(meal_id)

    ingredients, steps = extract_fields(meal)
    title = meal.get("strMeal", "Без названия")
    counter[0] += 1
    print(f"    [{counter[0]}] 📝 {title} ({cuisine})")
    print(f"         🌐 Перевод...")
    try:
        ru = await translate_recipe(title, ingredients, steps)
        print(f"         ✅ {ru['title']}")
    except Exception as e:
        print(f"         ⚠️ ошибка: {e}")
        ru = {"title": title, "ingredients": ingredients, "steps": steps}

    photo = meal.get("strMealThumb") or await pexels_photo(pexels_query)
    video = await pexels_video(pexels_query)

    results.append({
        "title": ru["title"],
        "ingredients": ru["ingredients"],
        "steps": ru["steps"],
        "time_min": 30,
        "calories": 400,
        "category": category,
        "cuisine": cuisine,
        "tags": tags,
        "image_url": photo,
        "video_url": video,
    })


async def main():
    if not BOTHUB_KEY:
        print("❌ BOTHUB_KEY не задан в .env!")
        return
    print(f"✅ Bothub: {BOTHUB_KEY[:8]}... | 💰 {MODEL}")
    print(f"📋 План: простые блюда + 14 кухонь + ПП ≈ 190 рецептов\n")

    results = []
    seen_ids = set()
    counter = [0]

    async with httpx.AsyncClient(timeout=30) as client:
        # ─── БЛОК 1: простые блюда ───
        print("═══ БЛОК 1: ПРОСТЫЕ БЛЮДА ═══")
        for meta in QUERY_META:
            print(f"🔍 [{meta['q']}]")
            try:
                r = await client.get(f"https://www.themealdb.com/api/json/v1/1/search.php?s={meta['q']}")
                meals = r.json().get("meals") or []
                print(f"    📦 {len(meals)} рецептов")
            except Exception as e:
                print(f"    ❌ {e}")
                continue
            for meal in meals[:4]:
                cuisine = CUISINE_RU.get(meal.get("strArea", ""), "Другая")
                await process_meal(meal, meta["category"], meta["tags"], cuisine, meta["q"], results, seen_ids, counter)

        # ─── БЛОК 2: национальные кухни ───
        print("\n═══ БЛОК 2: НАЦИОНАЛЬНЫЕ КУХНИ ═══")
        for cq in CUISINE_QUERIES:
            ru_name = CUISINE_RU.get(cq["area"], cq["area"])
            print(f"🌍 [{ru_name}]")
            try:
                r = await client.get(f"https://www.themealdb.com/api/json/v1/1/filter.php?a={cq['area']}")
                ids = [m["idMeal"] for m in (r.json().get("meals") or [])[:cq["count"]]]
            except Exception as e:
                print(f"    ❌ {e}")
                continue
            for rid in ids:
                d = await client.get(f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={rid}")
                meal = (d.json().get("meals") or [None])[0]
                if not meal: continue
                cat = guess_category(meal.get("strMeal", ""))
                tags = ["на каждый день"] if cat == "dinner" else []
                await process_meal(meal, cat, tags, ru_name, cq["area"].lower() + " food", results, seen_ids, counter)

        # ─── БЛОК 3: правильное питание ───
        print("\n═══ БЛОК 3: ПРАВИЛЬНОЕ ПИТАНИЕ ═══")
        for hq in HEALTHY_QUERIES:
            print(f"🥦 [{hq}]")
            try:
                r = await client.get(f"https://www.themealdb.com/api/json/v1/1/search.php?s={hq}")
                meals = r.json().get("meals") or []
            except Exception as e:
                print(f"    ❌ {e}")
                continue
            for meal in meals[:3]:
                cuisine = CUISINE_RU.get(meal.get("strArea", ""), "Другая")
                await process_meal(meal, "healthy", ["пп", "правильное питание"], cuisine, hq, results, seen_ids, counter)

    out_path = Path(__file__).parent.parent / "backend" / "recipes_data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n🎉 Готово! Всего рецептов: {len(results)} -> {out_path}")

    stats = {}
    for r in results:
        stats[r["category"]] = stats.get(r["category"], 0) + 1
    print("\n📊 По категориям:")
    for cat, n in stats.items():
        print(f"   {cat}: {n}")


if __name__ == "__main__":
    asyncio.run(main())