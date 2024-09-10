# Utilizar una imagen base oficial de Python
FROM python:3.10-slim

# Establecer el directorio de trabajo en /app
WORKDIR /app

# Copiar los archivos de requisitos al contenedor
COPY requirements.txt .

# Instalar las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código fuente al contenedor
COPY . .

# Exponer el puerto 8080 (donde se ejecutará FastAPI)
EXPOSE 8080

# Comando para ejecutar la aplicación con Uvicorn
CMD ["uvicorn", "app.main2:app", "--host", "0.0.0.0", "--port", "8080"]
