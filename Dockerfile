FROM python:latest

# System update
RUN apt-get update -y && apt-get upgrade -y

# Install Microsoft Core Fonts (includes Impact)
# --no-install-recommends taki bina zarurat ke fonts na aaye
RUN apt-get install -y --no-install-recommends ttf-mscorefonts-installer

# Install pip latest
RUN pip3 install -U pip

# Copy project
COPY . /app/
WORKDIR /app/

# Install Python deps
RUN pip3 install -U -r requirements.txt

# Download Montserrat font
RUN mkdir -p fonts && \
    wget -q -O fonts/Montserrat-Bold.ttf \
        https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf

# Optional: Verify fonts are installed
RUN fc-list | grep -i impact || echo "Impact font may not be available"

# Start bot
CMD ["python3", "-m", "DURGESH"]
