import difflib
from contextlib import asynccontextmanager
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import (
    init_db, fetch_all, create_user,
    save_generated_recipe, add_favorite, remove_favorite, get_favorites
)
from ai_parser import parse_food_image, parse_food_text, generate_recipe


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="What To Cook API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SYNONYMS = {
    "помидорки": "помидор", "томат": "помидор", "томаты": "помидор",
    "яиц": "яйцо", "яйца": "яйцо",
    "картошки": "картофель", "картошка": "картофель",
    "куриное филе": "курица", "филе куриное": "курица",
    "луковица": "лук", "лучок": "лук",
}


def normalize(text: str) -> str:
    return SYNONYMS.get(text.lower().strip(), text.lower().strip())


CATEGORIES = [
    {"id": "breakfast", "name": "Завтраки", "emoji": "🍳"},
    {"id": "dinner",    "name": "Ужины",    "emoji": "🍽️"},
    {"id": "healthy",   "name": "ПП",       "emoji": "🥦"},
    {"id": "salads",    "name": "Салаты",   "emoji": "🥗"},
    {"id": "soups",     "name": "Супы",     "emoji": "🍜"},
    {"id": "desserts",  "name": "Десерты",  "emoji": "🍰"},
    {"id": "vegan",     "name": "Веган",    "emoji": "🌱"},
    {"id": "generated", "name": "✨ Мои",   "emoji": "✨"},
]

ALL_TAGS = ["просто", "на каждый день", "бюджетно", "быстро", "пп", "правильное питание", "детям", "веган", "выпечка", "острое"]

CUISINE_FLAGS = {
    "Русская": "🇷", "Украинская": "🇺🇦", "Итальянская": "🇮🇹",
    "Французская": "🇫🇷", "Испанская": "🇪🇸", "Греческая": "🇬🇷",
    "Турецкая": "🇹🇷", "Американская": "🇺🇸", "Мексиканская": "🇲🇽",
    "Китайская": "🇨🇳", "Японская": "🇯🇵", "Тайская": "🇹🇭",
    "Индийская": "🇮🇳", "Польская": "🇵🇱", "Британская": "🇬🇧",
    "Марокканская": "🇲🇦", "Вьетнамская": "🇻🇳",
    "Домашняя": "🏠", "Другая": "🌍",
}


class SearchRequest(BaseModel):
    ingredients: List[str]
    max_time: Optional[int] = 60
    user_id: Optional[int] = None


@app.get("/")
async def root():
    return {"status": "ok", "service": "What To Cook API"}


@app.get("/api/categories")
async def get_categories():
    return {"categories": CATEGORIES, "tags": ALL_TAGS}


@app.get("/api/cuisines")
async def get_cuisines():
    recipes = await fetch_all()
    found = sorted(set(r["cuisine"] for r in recipes if r.get("cuisine")))
    return {"cuisines": [{"id": c, "name": c, "flag": CUISINE_FLAGS.get(c, "🌍")} for c in found]}


@app.get("/api/recipes")
async def list_recipes(category: str = None, tag: str = None, search: str = None, cuisine: str = None):
    recipes = await fetch_all()
    if category:
        recipes = [r for r in recipes if r["category"] == category]
    if tag:
        recipes = [r for r in recipes if tag in r["tags"]]
    if cuisine:
        recipes = [r for r in recipes if r.get("cuisine") == cuisine]
    if search:
        q = search.lower()
        recipes = [r for r in recipes if q in r["title"].lower()]
    return {"recipes": recipes}


@app.post("/api/recipes/search")
async def search_by_ingredients(req: SearchRequest):
    user_ings = [normalize(i) for i in req.ingredients]
    all_recipes = await fetch_all()
    results = []

    for recipe in all_recipes:
        recipe_ings = [normalize(i) for i in recipe["ingredients"]]
        if not recipe_ings:
            continue

        matched = 0
        for ri in recipe_ings:
            for ui in user_ings:
                if difflib.SequenceMatcher(None, ri, ui).ratio() > 0.7:
                    matched += 1
                    break

        ratio = matched / len(recipe_ings)
        if ratio >= 0.6 and recipe["time_min"] <= (req.max_time or 999):
            missing = [
                ri for ri in recipe_ings
                if not any(difflib.SequenceMatcher(None, ri, ui).ratio() > 0.7 for ui in user_ings)
            ]
            results.append({**recipe, "match_percent": round(ratio * 100), "missing": missing})

    results.sort(key=lambda x: (-x["match_percent"], x["time_min"]))
    return {"recipes": results[:10]}


@app.post("/api/recipes/smart-search")
async def smart_search(data: dict):
    """Умный поиск: сначала база, если мало — скрытно генерирует рецепт"""
    ingredients = [normalize(i) for i in data.get("ingredients", [])]
    max_time = data.get("max_time", 90)

    if not ingredients:
        return {"recipes": []}

    all_recipes = await fetch_all()
    results = []

    for recipe in all_recipes:
        recipe_ings = [normalize(i) for i in recipe["ingredients"]]
        if not recipe_ings:
            continue

        matched = sum(1 for ri in recipe_ings
                      if any(difflib.SequenceMatcher(None, ri, ui).ratio() > 0.7 for ui in ingredients))

        ratio = matched / len(recipe_ings)
        if ratio >= 0.6 and recipe["time_min"] <= max_time:
            missing = [ri for ri in recipe_ings
                       if not any(difflib.SequenceMatcher(None, ri, ui).ratio() > 0.7 for ui in ingredients)]
            results.append({**recipe, "match_percent": round(ratio * 100), "missing": missing})

    results.sort(key=lambda x: (-x["match_percent"], x["time_min"]))
    found = results[:5]

    # Если нашли мало — скрытно генерируем рецепт и выдаём как «найденный»
    if len(found) < 3:
        try:
            generated = await generate_recipe(ingredients)
            recipe_id = await save_generated_recipe(generated)
            generated["id"] = recipe_id
            generated["category"] = "generated"
            generated["cuisine"] = "Домашняя"
            generated["tags"] = ["сгенерировано"]
            generated["image_url"] = None
            generated["video_url"] = None
            generated["match_percent"] = 100
            generated["missing"] = []
            found.append(generated)
        except Exception as e:
            print(f"Generation error: {e}")

    return {"recipes": found}


@app.post("/api/recipes/generate")
async def generate_recipe_endpoint(data: dict):
    """Прямая генерация рецепта"""
    ingredients = data.get("ingredients", [])
    preferences = data.get("preferences", "")

    if not ingredients:
        return {"error": "Нет ингредиентов"}

    recipe = await generate_recipe(ingredients, preferences)
    recipe_id = await save_generated_recipe(recipe)
    recipe["id"] = recipe_id
    return {"recipe": recipe}


@app.post("/api/parse/image")
async def parse_image(file: UploadFile = File(...)):
    contents = await file.read()
    ingredients = await parse_food_image(contents)
    return {"ingredients": ingredients}


@app.post("/api/parse/text")
async def parse_text(data: dict):
    ingredients = await parse_food_text(data.get("text", ""))
    return {"ingredients": ingredients}


@app.post("/api/users/register")
async def register_user(data: dict):
    await create_user(int(data["user_id"]), data.get("username", ""))
    return {"status": "ok"}


@app.post("/api/favorites/add")
async def add_favorite_endpoint(data: dict):
    await add_favorite(int(data["user_id"]), int(data["recipe_id"]))
    return {"status": "ok"}


@app.post("/api/favorites/remove")
async def remove_favorite_endpoint(data: dict):
    await remove_favorite(int(data["user_id"]), int(data["recipe_id"]))
    return {"status": "ok"}


@app.get("/api/favorites/list")
async def list_favorites(user_id: int):
    favorites = await get_favorites(user_id)
    return {"recipes": favorites}