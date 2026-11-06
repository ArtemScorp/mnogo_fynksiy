import os
import io
import json
import random
import re
import threading
import tempfile

import numpy as np
import requests
import pyttsx3
from googletrans import Translator
from telebot import TeleBot

engine = pyttsx3.init()

API_TOKEN = os.getenv("BOT_TOKEN", "8776055802:AAFmJ7MCcjB-fq6AsICpqYbnIsDnSWFsLNw")
bot = TeleBot(API_TOKEN)

# Состояния игры для пользователей: chat_id -> dict
user_game_state = {}


def normalize(text):
    """Приводит слово к единому виду: нижний регистр, без ударений и пунктуации."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    remove_accents = {
        ord("á"): "a",
        ord("à"): "a",
        ord("ä"): "a",
        ord("é"): "e",
        ord("è"): "e",
        ord("ë"): "e",
        ord("í"): "i",
        ord("ì"): "i",
        ord("ï"): "i",
        ord("ó"): "o",
        ord("ò"): "o",
        ord("ö"): "o",
        ord("ú"): "u",
        ord("ù"): "u",
        ord("ü"): "u",
        ord("ñ"): "n",
    }
    text = text.translate(remove_accents)
    text = re.sub(r"[^a-zñ\-]", "", text)
    return text.strip()


def get_news(type="random") -> str:
    base_url = f"https://uselessfacts.jsph.pl/{type}.json"
    response = requests.get(base_url)
    if response.status_code == 200:
        return response.text.strip()
    else:
        return "Не удалось получить данные. Попробуйте позже."


def speak(text: str) -> io.BytesIO:
    """
    Озвучивает текст и возвращает аудиоданные в виде файлоподобного объекта.
    Временный файл создаётся внутри функции и удаляется после чтения.
    """
    engine_local = pyttsx3.init()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_path = tmp.name
    tmp.close()
    try:
        engine_local.save_to_file(text, tmp_path)
        engine_local.runAndWait()
        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        try:
            engine_local.stop()
        except Exception:
            pass
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    audio_io = io.BytesIO(data)
    audio_io.name = "speech.wav"
    return audio_io


@bot.message_handler(commands=["start"])
def start_message(message):
    bot.send_message(message.chat.id, "Привет, я многофункциональный бот!")
    bot.send_message(
        message.chat.id,
        "Выбери, что хочешь сделать. Чтобы написать задачу, напиши /one, /two и т.п.",
    )
    bot.send_message(message.chat.id, "1 – послушать твою фразу")
    bot.send_message(message.chat.id, "2 – поиграть в игру «Английский словарик»")
    bot.send_message(message.chat.id, "3 – узнать интересные факты")
    bot.send_message(
        message.chat.id,
        "5 – узнать своё количество враз для озвучки, сколько раз можно поиграть в словарик и сколько можно послушать фактов",
    )


@bot.message_handler(commands=["one"])
def one_message(message):
    sent = bot.send_message(message.chat.id, "Что сказать?")
    bot.register_next_step_handler(sent, speak_text)


def speak_text(message):
    engine.setProperty("rate", 100)
    engine.setProperty("volume", 1)
    voices = engine.getProperty("voices")
    if voices:
        engine.setProperty("voice", voices[0].id)
    engine.say(message.text)
    threading.Thread(target=engine.runAndWait).start()


WORDS = {
    "dog": "собака",
    "cat": "кот",
    "house": "дом",
    "water": "вода",
    "apple": "яблоко",
    "bread": "хлеб",
    "sun": "солнце",
    "moon": "луна",
    "mom": "мать",
    "dad": "отец",
    "city": "город",
    "mouse": "мышь",
    "bag": "сумка",
    "bug": "жук",
    "bed": "кровать",
    "bomb": "бомба",
    "country": "страна",
    "number": "число",
    "titan": "титан",
    "book": "книга",
    "friend": "друг",
    "flower": "цветок",
    "tree": "дерево",
}


@bot.message_handler(commands=["two"])
def two_message(message):
    chat_id = message.chat.id
    items = list(WORDS.items())
    random.shuffle(items)
    selected = items[:5]

    user_game_state[chat_id] = {
        "words": selected,
        "index": 0,
        "score": 0,
    }

    bot.send_message(
        chat_id,
        "Добро пожаловать в игру «Английский словарик»!\n"
        "Я показываю слово по-русски, а ты пишешь его перевод по-английски.\n"
        "В конце скажу, сколько слов ты угадал.",
    )
    send_next_round(chat_id)


def send_next_round(chat_id):
    state = user_game_state.get(chat_id)
    if not state:
        return

    index = state["index"]
    words = state["words"]

    if index >= len(words):
        score = state["score"]
        total = len(words)
        bot.send_message(chat_id, f"\n{'—' * 40}\nИгра окончена! Результат: {score} из {total}")
        if score == total:
            bot.send_message(chat_id, "🏆 Отлично, все слова верны!")
        elif score >= total // 2:
            bot.send_message(chat_id, "👍 Неплохо! Потренируйся ещё немного.")
        else:
            bot.send_message(chat_id, "💪 Тренируйся дальше — всё получится!")
        user_game_state.pop(chat_id, None)
        return

    word_en, word_ru = words[index]
    bot.send_message(chat_id, f"\n{'=' * 40}\nРаунд {index + 1}\n{'=' * 40}")
    bot.send_message(chat_id, f"Напиши по-английски слово: «{word_ru}»")
    state["current_word_en"] = word_en
    state["current_word_ru"] = word_ru


@bot.message_handler(func=lambda message: message.chat.id in user_game_state)
def game_answer_handler(message):
    chat_id = message.chat.id
    state = user_game_state.get(chat_id)
    if not state:
        return

    user_answer = message.text.strip()
    correct_en = state.get("current_word_en", "")
    correct_ru = state.get("current_word_ru", "")

    if normalize(user_answer) == normalize(correct_en):
        bot.send_message(chat_id, f"✅ Верно! «{correct_en}» = «{correct_ru}»")
        state["score"] += 1
    else:
        bot.send_message(chat_id, f"❌ Не совсем. Правильно: «{correct_en}» = «{correct_ru}»")

    state["index"] += 1
    send_next_round(chat_id)


@bot.message_handler(commands=["thee"])
def thee_message(message):
    new = json.loads(get_news())
    text = new["text"]
    print(text)
    translator = Translator(service_urls=["translate.google.com"])
    result = translator.translate(text, dest="ru")

    bot.reply_to(message, result.text)

    audio = speak(result.text)
    bot.send_audio(message.chat.id, audio)


if __name__ == "__main__":
    print("Бот запущен.")

    bot.infinity_polling(
        #    skip_pending=True,
        #    timeout=30,
        #    long_polling_timeout=30,
    )
