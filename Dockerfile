FROM python:3.5

ADD requirements.txt /bot/
ADD test.py /bot/

RUN pip install -r ./requirements.txt/

RUN pip install -r ./requirements.txt
