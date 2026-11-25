FROM python:3.12-slim

WORKDIR /app

# Cài đặt dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn
COPY . .

# Tạo thư mục dữ liệu và logs
RUN mkdir -p data logs

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
