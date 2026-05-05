# --- 第一阶段：编译 Vue 代码 ---
FROM node:20-alpine AS build-stage

WORKDIR /app

# 复制 package.json 并安装依赖 (使用淘宝镜像源加速)
COPY package*.json ./
RUN npm install --registry=https://registry.npmmirror.com

# 复制所有前端代码并执行打包
COPY . .
RUN npm run build


# --- 第二阶段：Nginx 部署 ---
FROM nginx:alpine AS production-stage
COPY nginx.conf /etc/nginx/conf.d/default.conf
# 将第一阶段打包生成的 dist 文件夹内容复制到 Nginx 的网页目录
# 注意：确认你的 Vue 项目打包出来的是 dist 文件夹
COPY --from=build-stage /app/dist /usr/share/nginx/html

# 暴露 80 端口
EXPOSE 80

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
