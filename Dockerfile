# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt /app/

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of your Django project into the container
COPY . /app/

# Expose the port Django will run on
EXPOSE 8000

# Run the application using Gunicorn
CMD ["gunicorn", "raadaa.wsgi:application", "--bind", "0.0.0.0:8000"]
