FROM python:latest

# System update
RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ttf-mscorefonts-installer \
        wget \
        unzip && \
    fc-cache -fv

# Install pip latest
RUN pip3 install --no-cache-dir -U pip

# Copy project
COPY . /app/
WORKDIR /app/

# Install Python dependencies
RUN pip3 install --no-cache-dir -U -r requirements.txt

# Create fonts directory and download Impact + Montserrat
RUN mkdir -p fonts && \
    wget -q -O fonts/Montserrat-Bold.ttf \
        https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf && \
    wget -q -O fonts/Impact.ttf \
        https://github.com/cosmicoptima/fonts/raw/main/impact.ttf

# Start bot
CMD ["python3", "-m", "DURGESH"]
