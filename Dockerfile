# Dockerfile

# Etapa 1: Use uma imagem base oficial do Python.
FROM python:3.11-slim

# Etapa 2: Defina o diret�rio de trabalho dentro do container.
WORKDIR /app

# Etapa 3: Copie o arquivo de depend�ncias e instale-as.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Etapa 4: Copie o c�digo da sua aplica��o para dentro do container.
COPY . .

# Etapa 5: Comando para iniciar a aplica��o usando um servidor de produ��o (Gunicorn).
# O Traefik ir� se comunicar com a aplica��o nesta porta 5000.
CMD ["gunicorn", "-k", "gevent", "--workers", "3", "--bind", "0.0.0.0:5000", "app:app"]