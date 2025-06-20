# Use Python 3.10 as the base image
FROM python:3.10

# Set the working directory inside the container
WORKDIR /app

# Copy all files from the current directory into the container
COPY . /app

# Get chrome dependencies
RUN apt-get update && apt-get install -y unzip xvfb libxi6 libgconf-2-4

# Get chrome installed for selenium to run on
RUN apt-get install -y --no-install-recommends gnupg wget curl unzip && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/* && \
    CHROME_VERSION=$(google-chrome --product-version) && \
    wget -q --continue -P /chromedriver "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$CHROME_VERSION/linux64/chromedriver-linux64.zip" && \
    unzip /chromedriver/chromedriver* -d /usr/local/bin/ && \
    rm -rf /chromedriver && \
    mv /usr/bin/google-chrome /app/google-chrome && \
    mv /usr/local/bin/chromedriver-linux64 /app/chromedriver

# Create a user dir for chrome data
RUN mkdir -p /app/chrome-user-data

# Make sure that we can use the chromedriver
RUN chmod +x /app/google-chrome && chmod +x /app/chromedriver/chromedriver

# Upgrade pip before installing dependencies
RUN python -m pip install --upgrade pip

# Do pytorch installation separately
RUN pip install --timeout=120 --resume-retries=5 torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the default Streamlit port (8501)
EXPOSE 8501

# Command to run the Streamlit app
ENTRYPOINT ["streamlit", "run", "streamlit-dash.py"]
CMD ["--server.port=8501", "--server.address=0.0.0.0"]