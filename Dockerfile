# Dockerfile

# Etapa 1: Use uma imagem base oficial do Python.
FROM python:3.11-slim

# Etapa 2: Defina o diretório de trabalho dentro do container.
WORKDIR /app

# Etapa 3: Copie o arquivo de dependências e instale-as.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Etapa 4: Copie o código da sua aplicação para dentro do container.
COPY . .

# Etapa 5: Comando para iniciar a aplicação usando um servidor de produção (Gunicorn).
# O Traefik irá se comunicar com a aplicação nesta porta 5000.
CMD ["gunicorn", "-k", "gevent", "--workers", "3", "--bind", "0.0.0.0:5000", "app:app"]