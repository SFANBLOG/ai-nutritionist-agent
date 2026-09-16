# ============================================
# AI 营养师 Agent - 后端镜像
# 含 BGE 向量化(sentence-transformers + torch)、pymilvus、minio
# ============================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    TOKENIZERS_PARALLELISM=false \
    HF_ENDPOINT=https://hf-mirror.com \
    HF_HOME=/root/.cache/huggingface

WORKDIR /app

# 系统依赖(编译部分 python 包 & 运行时需要)
# 使用国内 Debian 镜像加速 apt(基础镜像为 Debian,兼容 deb822 新格式与旧 sources.list)
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ curl gnupg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖(利用层缓存)
COPY requirements.txt .
# 关键:先安装 CPU 版 torch。否则 pip 会从 PyPI 拉取 CUDA 版 torch,并连带下载
# cudnn/cublas/nccl/cuda-toolkit 等数 GB 的 NVIDIA 依赖(容器为纯 CPU 场景,BGE 推理不需要 CUDA)。
RUN pip install --upgrade pip \
 && pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt

# 预下载 BGE 模型,保证容器内离线可用(失败不阻断构建,运行时可回退哈希向量)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')" \
    || echo "BGE 模型预下载失败,容器首次调用时将尝试在线下载或使用哈希兜底"

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
