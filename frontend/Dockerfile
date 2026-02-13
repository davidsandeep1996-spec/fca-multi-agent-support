
# Use lightweight Python
FROM python:3.11-slim

# Prevent python from generating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies directly (no requirements.txt needed for just 2 packages)
RUN pip install --default-timeout=100 --no-cache-dir streamlit requests
# Copy the app code
COPY streamlit_app.py .

# Expose Streamlit port
EXPOSE 8501

# Run the app
CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0"]
