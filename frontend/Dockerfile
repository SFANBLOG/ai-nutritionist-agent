# ============================================
# AI 营养师 Agent - 前端镜像
# 多阶段构建:node 构建静态资源 -> nginx 托管并反向代理 /api
# ============================================
FROM node:20-alpine AS build

WORKDIR /app

# 使用国内 npm 镜像加速依赖安装
RUN npm config set registry https://registry.npmmirror.com

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine

# 反向代理后端 API 与文档
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
