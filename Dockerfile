FROM python:3.12-slim

EXPOSE 16384
VOLUME /data

WORKDIR /app
COPY tnfsd.py /app/tnfsd.py

ENTRYPOINT ["python", "/app/tnfsd.py", "/data"]
