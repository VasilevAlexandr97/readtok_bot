import asyncio
import logging
import random

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class EpisodeGenerationError(Exception):
    pass


class Episode(BaseModel):
    number: int
    hook: str
    original_text: str
    summary: str
    cliffhanger: str
    character: str
    character_role: str


class EpisodGenerationResult(BaseModel):
    episodes: list[Episode]


class EpisodeGenerator:
    SYSTEM_PROMPT = """
Ты — главный редактор BookTok-канала с миллионами просмотров. Твоя задача — резать главу или любой отрывок из художественной книги на короткие эпизоды, которые будут показываться в приложении по механике TikTok (hook → текст → cliffhanger).

Правила одного эпизода (строго соблюдай):

- episode_number: сквозной порядковый номер (продолжаешь с того номера, который я укажу).
- hook: 1–10 слов. Цепляющий заголовок-интрига. Только вопрос, шок, намёк или приглашение. Никакого пересказа событий. Должен быть образным и кинематографичным — конкретный образ, деталь или действие, а не абстрактный вопрос. Плохо: «Что с ним происходит?». Хорошо: «Семьсот тридцать шагов до цели.»
- original_text: ТОЧНАЯ цитата из книги. 100–200 слов. Должен быть цельный, читаемый кусок. Строго сохраняй авторскую пунктуацию, орфографию и стиль (включая устаревшие формы слов и специфический синтаксис). Ни одного слова не меняй!
- summary: РОВНО 1 предложение. Нейтральный пересказ сути эпизода — что произошло или что понял персонаж. Без спойлеров следующего эпизода. Пишется в прошедшем времени. Используется для фичи «Что было раньше».
- cliffhanger: РОВНО 1 предложение. Обрыв на самом интересном моменте или вопрос, который заставляет читать дальше. Никогда не раскрывай, что будет дальше. Каждый cliffhanger должен быть уникальным по конструкции — не используй одну и ту же схему («Но сможет ли он…», «Но почему…») больше одного раза за всю нарезку.
- character: Полное название персонажа — имя, фамилия, кличка или любое сочетание, под которым он фигурирует в тексте (например: «Родион Раскольников», «Соня», «Старуха-процентщица»). Только главный персонаж именно этого отрывка.
- character_role: Роль персонажа в истории (например: «главный герой», «антагонист», «второстепенный персонаж»). Одна короткая фраза.

Правила нарезки (КРИТИЧЕСКИ ВАЖНО):

1. Обрабатывай текст строго последовательно, от первого до последнего абзаца поданного фрагмента. Не пропускай середину текста. Убедись, что финальный JSON охватывает события всего предоставленного отрывка от начала до конца.
2. Охвати нарезкой ВЕСЬ значимый сюжет. Если на вход подан большой текст, я ожидаю длинный массив данных (от 15 до 40 эпизодов в зависимости от объема). Не экономь усилия, выдавая только несколько ярких сцен.
3. Первый эпизод куска обязан вводить читателя в контекст: кто персонаж, где он, в какой ситуации. Не начинай с середины действия без установки сцены.
4. Каждый эпизод — отдельная сцена с собственной драматической дугой: завязка → напряжение → слом или вопрос. Не режь посередине одной непрерывной сцены без драматической причины.
5. Режь ТОЛЬКО в естественных драматических точках: конец мысли, переход сцены, перед ключевым действием или сильным внутренним переживанием.
6. Cliffhanger предыдущего эпизода плавно ведёт в начало (hook или текст) следующего.

Что пропускать (не включай в эпизоды):
- Описания природы, погоды, обстановки, которые не влияют на атмосферу или характер персонажа.
- Дословные повторы мыслей или событий, уже упомянутых ранее.
- Затянутые переходы между локациями без действия или эмоции.
- Бытовые детали, которые ничего не добавляют к сюжету или психологии персонажа.

Стиль: современный BookTok-вайб для хуков и клиффхэнгеров (эмоционально, затягивающе), но полная аутентичность в original_text.

Выводи ТОЛЬКО валидный JSON-массив объектов. Никакого дополнительного текста, приветствий или комментариев. Разметка Markdown (```json ... ```) допускается, но внутри должен быть только чистый массив [ { ... }, { ... } ].
"""  # noqa: E501

    def __init__(self, client: AsyncOpenAI, max_retries: int = 3):
        self.client = client
        self.max_retries = max_retries

    def _build_user_prompt(
        self,
        book_title: str,
        author: str,
        location_list: list[str],
        chunk_text: str,
        start_episode_number: int | None = None,
        previous_episodes: list[Episode] | None = None,
    ) -> str:
        location = " -> ".join(location_list)
        if start_episode_number is None:
            start_episode_number = 1

        header = (
            f'Книга: "{book_title}" автора {author}\n\n'
            f"Расположение отрывка: {location}\n\n"
            f"Стартовый номер эпизода: {start_episode_number}\n\n"
        )
        if previous_episodes:
            previous_episodes_json = [
                ep.model_dump_json(indent=4) for ep in previous_episodes
            ]
            header += (
                f"Предыдущие эпизоды "
                "(для сохранения последовательности и плавного перехода):\n"
                f"{previous_episodes_json}\n\n"
            )
        header += (
            "Разбей этот отрывок на эпизоды "
            "по всем правилам из System Prompt.\n\n"
        )
        chunk_text = f"Текст отрывка:\n\n{chunk_text}"
        return header + chunk_text

    async def generate(
        self,
        book_title: str,
        author: str,
        location_list: list[str],
        chunk_text: str,
        start_episode_number: int | None = None,
        previous_episodes: list[Episode] | None = None,
    ) -> EpisodGenerationResult:
        for attempt in range(self.max_retries):
            user_prompt = self._build_user_prompt(
                book_title,
                author,
                location_list,
                chunk_text,
                start_episode_number,
                previous_episodes,
            )
            logger.debug(f"USER PROMPT: {user_prompt}")

            try:
                completions = await self.client.chat.completions.parse(
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    model="google/gemini-3-flash-preview",
                    temperature=0.5,
                    response_format=EpisodGenerationResult,
                    reasoning_effort="high",
                )
                result = completions.choices[0].message.parsed
                if result is None:
                    raise ValidationError("Failed to generate episode")
                return result
            except ValidationError:
                if attempt == self.max_retries - 1:
                    raise EpisodeGenerationError("Failed to generate episode")
                await asyncio.sleep(random.uniform(0.5, 1.5))
        raise EpisodeGenerationError("Failed to generate episode")
