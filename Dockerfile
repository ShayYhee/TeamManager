FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    libreoffice \
    wkhtmltopdf \
    wget \
    gnupg \
    software-properties-common \
    xfonts-75dpi \
    xfonts-base \
    libxrender1 \
    libxtst6 \
    libjpeg62-turbo \
    libx11-dev \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libasound2 \
    libfontconfig1 \
    libfreetype6 \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install wkhtmltopdf
# RUN wget -q https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.bionic_amd64.deb && \
#     apt install -y ./wkhtmltox_0.12.6-1.bionic_amd64.deb && \
#     rm ./wkhtmltox_0.12.6-1.bionic_amd64.deb

# Set workdir
WORKDIR /app

# Copy files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Collect static files if needed
# RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Start the server
CMD ["gunicorn", "raadaa.wsgi:application", "--bind", "0.0.0.0:8000"]
