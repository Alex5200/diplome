# ST3215 Frontend - Production Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

RUN echo 'server { listen 3000; root /usr/share/nginx/html; 
    location / { try_files $uri $uri/ /index.html; }
    location /api { proxy_pass http://robot-api:8000; }
    location /auth { proxy_pass http://robot-api:8000; }
    location /ws { proxy_pass http://robot-api:8000; 
        proxy_http_version 1.1; 
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]