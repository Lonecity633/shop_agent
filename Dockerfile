# 1. 基础镜像：使用轻量级的 Python 环境
FROM python:3.12-slim

# 2. 设置容器内的工作目录
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. 先复制依赖文件并安装 (利用 Docker 缓存加速后续构建)
COPY requirements.txt .
# 使用国内清华源加速下载，并禁用缓存减小镜像体积
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 复制后端的 app 代码目录到容器内的 /workspace/app
COPY ./app ./app

# 5. 暴露后端端口 (FastAPI 默认通常是 8000)
EXPOSE 8000

# 6. 启动命令
# 注意：这里假设你的 FastAPI 实例在 app/main.py 里面，且变量名为 app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
