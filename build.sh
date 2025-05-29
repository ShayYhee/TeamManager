if [[ $DJANGO_SUPERUSER_USERNAME && $DJANGO_SUPERUSER_EMAIL && $DJANGO_SUPERUSER_PASSWORD ]]; then
    python manage.py createsuperuser --noinput --username "$DJANGO_SUPERUSER_USERNAME" --email "$DJANGO_SUPERUSER_EMAIL"
else
    echo "Superuser environment variables not set. Skipping superuser creation."
fi