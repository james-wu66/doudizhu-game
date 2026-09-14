# last update: 2026-09-14 23:20 触发重建（106曾复用旧镜像，带入b783903双通道+a9da0bc max_tokens修复）
FROM python:3.11-slim

WORKDIR /app

# 安装依赖（用清华镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm curl && rm -rf /var/lib/apt/lists/*
RUN npm install -g @cloudbase/cli

# TASK-016 路线丙：向量模型（bge-small-zh-v1.5，共91MB）构建时从对象存储拉取进镜像。
# 模型文件为公开开源数据（BAAI bge），已设对象级公有读；运行时零下载，根治线上问答504。
# 布局与本地 KB_MODEL_DIR 一致：kb_models/fast-bge-small-zh-v1.5/
ENV KB_MODEL_DIR=/app/kb_models
# HF_HUB_OFFLINE=1：强制 fastembed/huggingface_hub 离线加载（模型已在镜像内）。
# 不加它容器会联网校验模型，境内云访问 hf.co 被墙挂死 → 线上问答 504（本机同款坑，交接文档§5）。
ENV HF_HUB_OFFLINE=1
ENV HF_HUB_DISABLE_TELEMETRY=1
RUN mkdir -p $KB_MODEL_DIR/fast-bge-small-zh-v1.5 && \
    for f in model_optimized.onnx tokenizer.json vocab.txt tokenizer_config.json special_tokens_map.json ort_config.json config.json; do \
        curl -fsSL -o "$KB_MODEL_DIR/fast-bge-small-zh-v1.5/$f" \
          "https://6a61-james-wu-d2gcojd404e6b8137-1420872702.cos.ap-shanghai.myqcloud.com/doudizhu-backup/fast-bge-small-zh-v1.5/$f" \
          || exit 1; \
    done

# 复制全部文件
COPY backend/ backend/
COPY frontend/ frontend/
COPY audio/ audio/

# 云托管默认端口
ENV PORT=8080

# 启动 Flask
CMD ["python", "backend/app.py"]