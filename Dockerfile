FROM python:latest

# System update
RUN apt-get update -y && apt-get upgrade -y

# Install pip latest
RUN pip3 install -U pip

# Copy project
COPY . /app/
WORKDIR /app/

# Install Python deps
RUN pip3 install -U -r requirements.txt

# Download Montserrat fonts
RUN mkdir -p fonts && \
    wget -q -O fonts/Montserrat-Bold.ttf \
        https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf && \
    wget -q -O fonts/Montserrat-SemiBold.ttf \
        https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-SemiBold.ttf

# Start bot
CMD ["python3", "-m", "DURGESH"]
