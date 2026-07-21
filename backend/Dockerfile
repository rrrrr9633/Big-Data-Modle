FROM python:3.13-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG DEBIAN_MIRROR=mirrors.tuna.tsinghua.edu.cn

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120

WORKDIR /app/backend

COPY backend/requirements.prod.txt ./requirements.prod.txt
RUN sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && ldconfig \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --index-url "$PIP_INDEX_URL" --retries 5 --upgrade pip \
    && pip install --index-url "$PIP_INDEX_URL" --retries 5 -r requirements.prod.txt \
    && python -c "from lightgbm import LGBMClassifier, LGBMRegressor"

COPY backend ./
COPY ai4i2020.csv /app/ai4i2020.csv
COPY infra /app/infra

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
