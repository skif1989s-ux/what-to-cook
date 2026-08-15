import aiosqlite
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "recipes.db")
JSON_PATH = os.path.join(os.path.dirname(__file__), "recipes_data.json")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, ingredients TEXT, time_min INTEGER, calories INTEGER,
                category TEXT, cuisine TEXT, tags TEXT,
                image_url TEXT, video_url TEXT, steps TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                premium INTEGER DEFAULT 0,
                requests_left INTEGER DEFAULT 3
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                recipe_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, recipe_id)
            )
        """)
        await db.commit()

        count = (await db.execute_fetchall("SELECT COUNT(*) FROM recipes"))[0][0]
        if count == 0 and os.path.exists(JSON_PATH):
            with open(JSON_PATH, encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
            for r in data:
                await db.execute(
                    """INSERT INTO recipes
                       (title, ingredients, time_min, calories, category, cuisine, tags, image_url, video_url, steps)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        r.get("title", ""),
                        json.dumps(r.get("ingredients", []), ensure_ascii=False),
                        r.get("time_min", 30),
                        r.get("calories", 300),
                        r.get("category", "dinner"),
                        r.get("cuisine", "Другая"),
                        json.dumps(r.get("tags", []), ensure_ascii=False),
                        r.get("image_url"),
                        r.get("video_url"),
                        json.dumps(r.get("steps", []), ensure_ascii=False),
                    )
                )
            await db.commit()


async def fetch_all():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM recipes")
        rows = await cursor.fetchall()
        return [{
            "id": row["id"],
            "title": row["title"],
            "ingredients": json.loads(row["ingredients"]),
            "time_min": row["time_min"],
            "calories": row["calories"],
            "category": row["category"],
            "cuisine": row["cuisine"],
            "tags": json.loads(row["tags"]),
            "image_url": row["image_url"],
            "video_url": row["video_url"],
            "steps": json.loads(row["steps"]),
        } for row in rows]


async def create_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()


async def save_generated_recipe(recipe: dict) -> int:
    """Сохраняет сгенерированный ИИ рецепт в общую базу (как «найденный»)"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO recipes
               (title, ingredients, time_min, calories, category, cuisine, tags, image_url, video_url, steps)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                recipe.get("title", "Домашнее блюдо"),
                json.dumps(recipe.get("ingredients", []), ensure_ascii=False),
                recipe.get("time_min", 30),
                recipe.get("calories", 400),
                "generated",
                "Домашняя",
                json.dumps(["сгенерировано"], ensure_ascii=False),
                None,
                None,
                json.dumps(recipe.get("steps", []), ensure_ascii=False),
            )
        )
        await db.commit()
        return cursor.lastrowid


async def add_favorite(user_id: int, recipe_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO favorites (user_id, recipe_id) VALUES (?, ?)",
            (user_id, recipe_id)
        )
        await db.commit()


async def remove_favorite(user_id: int, recipe_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM favorites WHERE user_id = ? AND recipe_id = ?",
            (user_id, recipe_id)
        )
        await db.commit()


async def get_favorites(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT r.* FROM recipes r
            JOIN favorites f ON r.id = f.recipe_id
            WHERE f.user_id = ?
            ORDER BY f.created_at DESC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [{
            "id": row["id"],
            "title": row["title"],
            "ingredients": json.loads(row["ingredients"]),
            "time_min": row["time_min"],
            "calories": row["calories"],
            "category": row["category"],
            "cuisine": row["cuisine"],
            "tags": json.loads(row["tags"]),
            "image_url": row["image_url"],
            "video_url": row["video_url"],
            "steps": json.loads(row["steps"]),
        } for row in rows]