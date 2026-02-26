FROM python:3.12-slim

COPY . .
RUN pip install -r requirements.txt

EXPOSE 5050

CMD [ "python","app.py"]