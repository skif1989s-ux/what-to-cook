import base64
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Читаем .env из корня проекта
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BOTHUB_KEY = os.getenv("BOTHUB_KEY")

ai = AsyncOpenAI(
    base_url="https://openai.bothub.chat/v1",
    api_key=BOTHUB_KEY
) if BOTHUB_KEY else None

# Дешёвая модель с vision — для всех задач
MODEL = "gpt-4.1-mini"


async def parse_food_image(image_bytes: bytes) -> list:
    """📷 Распознаёт продукты на фото холодильника"""
    if not ai:
        raise Exception("BOTHUB_KEY не задан в .env!")

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    resp = await ai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content":
             "Ты шеф-повар. Перечисли ВСЕ видимые продукты на фото "
             "(овощи, мясо, молочку, крупы и т.д.). "
             "Ответ — ТОЛЬКО список названий через запятую на русском языке, без лишних слов. "
             "Пример: курица, помидор, лук, сыр, молоко"},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]}
        ]
    )
    text = resp.choices[0].message.content
    return [i.strip().lower() for i in text.replace("\n", ",").split(",") if i.strip()]


async def parse_food_text(text: str) -> list:
    """✏️ Извлекает продукты из свободного текста"""
    if not ai:
        raise Exception("BOTHUB_KEY не задан в .env!")

    resp = await ai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content":
             "Извлеки названия продуктов из текста. Ответ — список через запятую на русском."},
            {"role": "user", "content": text}
        ]
    )
    answer = resp.choices[0].message.content
    return [i.strip().lower() for i in answer.replace("\n", ",").split(",") if i.strip()]


async def generate_recipe(ingredients: list, preferences: str = "") -> dict:
    """✨ Генерирует простой рецепт из ингредиентов (скрытно от пользователя)"""
    if not ai:
        raise Exception("BOTHUB_KEY не задан в .env!")

    prompt = (
        f"У пользователя есть продукты: {', '.join(ingredients)}.\n"
        + (f"Его пожелания: {preferences}\n" if preferences else "")
        + """
Придумай простой вкусный рецепт из этих продуктов.
Верни СТРОГО JSON без пояснений:
{"title": str, "ingredients": [str], "steps": [str], "time_min": int, "calories": int}

Требования: рецепт простой (5-7 шагов), на русском языке, из доступных продуктов."""
    )

    resp = await ai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Ты шеф-повар. Придумывай простые вкусные рецепты на русском."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    text = resp.choices[0].message.content
    text = re.sub(r"```json|```", "", text).strip()
    try:
        data = json.loads(text)
        return {
            "title": data.get("title", "Домашнее блюдо"),
            "ingredients": data.get("ingredients", ingredients),
            "steps": data.get("steps", ["Смешайте ингредиенты", "Приготовьте по вкусу"]),
            "time_min": int(data.get("time_min", 30)),
            "calories": int(data.get("calories", 400)),
        }
    except json.JSONDecodeError:
        return {
            "title": "Домашнее блюдо",
            "ingredients": ingredients,
            "steps": ["Смешайте все ингредиенты", "Приготовьте по вкусу"],
            "time_min": 30,
            "calories": 400,
        }