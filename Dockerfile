FROM python:3.12-alpine3.20

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY pball_pete.py .
COPY get_courts_lib.py .
COPY create_slash_command.py .

# Expose the port
EXPOSE 8181

# Register slash command and start with Gunicorn
# CMD python create_slash_command.py && gunicorn --bind 0.0.0.0:8181 --workers 1 --timeout 120 pball_pete:app
CMD ["sh", "-c", "python create_slash_command.py && gunicorn --bind 0.0.0.0:8181 --workers 1 --timeout 120 pball_pete:app"]
