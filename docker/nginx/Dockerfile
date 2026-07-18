# edu_rag 容灾 Nginx 镜像
# 构建: docker build -t edu-rag-nginx -f docker/nginx/Dockerfile .
# 运行: docker run -d --name nginx -p 80:80 -e LOCAL_HOST=your.local.ip edu-rag-nginx

FROM nginx:1.25-alpine

# 安装 envsubst（用于环境变量替换 nginx.conf 模板）
RUN apk add --no-cache gettext

# 复制配置模板
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf.template

# 启动脚本：替换环境变量后启动 Nginx
RUN echo '#!/bin/sh' > /docker-entrypoint-custom.sh && \
    echo 'set -e' >> /docker-entrypoint-custom.sh && \
    echo 'envsubst < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf' >> /docker-entrypoint-custom.sh && \
    echo 'echo "Nginx config generated with LOCAL_HOST=${LOCAL_HOST:-127.0.0.1}"' >> /docker-entrypoint-custom.sh && \
    echo 'nginx -t' >> /docker-entrypoint-custom.sh && \
    echo 'exec nginx -g "daemon off;"' >> /docker-entrypoint-custom.sh && \
    chmod +x /docker-entrypoint-custom.sh

ENV LOCAL_HOST=127.0.0.1

EXPOSE 80

CMD ["/docker-entrypoint-custom.sh"]
