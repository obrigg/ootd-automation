FROM python:3.7-slim-buster
RUN apt-get update && apt-get install -y git
WORKDIR /ootd-autoation/
COPY ./ ./
RUN pip install -r requirements.txt
ENTRYPOINT ["python", "room_change_teams.py"]