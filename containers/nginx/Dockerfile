FROM nginx:latest

RUN rm /etc/nginx/conf.d/default.conf

COPY containers/nginx/custom.conf /etc/nginx/conf.d/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]