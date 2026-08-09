# last update: 2026-08-09 17:34
FROM python:3.11-slim

WORKDIR /app

# 安装依赖（用清华镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制全部文件
COPY backend/ backend/
COPY frontend/ frontend/
COPY audio/ audio/

# 云托管默认端口
ENV PORT=8080

# 启动 Flask
CMD ["python", "backend/app.py"]