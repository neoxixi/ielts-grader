FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目代码
COPY ielts_grader/ /app/ielts_grader/
COPY backend/ /app/backend/
COPY pyproject.toml /app/
RUN pip install --no-cache-dir -e /app

# 完整知识库（通过挂载卷或构建时复制）
# COPY private/band_profiles.json /root/.ielts-grader-private/
# COPY private/writing_strategies.json /root/.ielts-grader-private/
# COPY private/writing_roadmaps.json /root/.ielts-grader-private/

ENV PORT=8000
ENV ADMIN_API_KEY="change-me-in-production"
ENV PAYMENT_PROVIDER=manual

# 收款码图片（放在 backend/static/ 下，构建时或挂载卷传入）
# COPY backend/static/ /app/backend/static/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
