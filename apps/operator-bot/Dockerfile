FROM python:3.11-slim
WORKDIR /bot
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY apps/operator-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home bot \
    && mkdir /state && chown bot:bot /state
COPY apps/operator-bot/bot.py .
COPY apps/operator-bot/journal.py .
COPY apps/api/app /reference/apps/api/app
COPY apps/web/app /reference/apps/web/app
COPY apps/web/components /reference/apps/web/components
COPY apps/web/lib /reference/apps/web/lib
USER 10001:10001
CMD ["python", "bot.py"]
