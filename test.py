# python imports
import asyncio
import json
import logging
import requests
import sys
import urllib.parse
from requests.packages import urllib3

# 3rd. libraries imports
from aiotg import TgBot

with open("config.json") as cfg:
    config = json.load(cfg)

# logging config
# ###############################
logger = logging.getLogger("EMT_MadridBot")
logger.setLevel(logging.INFO)
logger.propagate = False

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s|%(levelname)s|%(name)s|%(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
# ###############################
urllib3.disable_warnings()

bot = TgBot(**config)

with open("config_emt.json") as cfg:
    emt_credentials = json.load(cfg)

EMT_URL = "https://openbus.emtmadrid.es:9443/emt-proxy-server/last/"


def make_request(uri, fields):
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = emt_credentials
    payload.update(fields)

    raw = urllib.parse.urlencode(payload)
    logger.info("SEND|{}|{}".format(uri, fields))
    response = requests.post(EMT_URL + uri,
                             data=raw,
                             verify=False,
                             headers=headers,)
    content = response.content.decode('utf-8')
    return json.loads(content)


# STOPS BY LOCATION
@bot.handle("location")
def location_stops(chat, location):
    # TODO Add NDC
    logger.info("location_stops|{}|{}|{},{}".format(
        chat.sender.get("id"),
        chat.sender.get("username"),
        location["latitude"],
        location["longitude"]))
    text, keyboard = get_stops_from_x_y(location)
    return chat.send_text(text,
                          reply_markup=json.dumps({"keyboard": keyboard,
                                                   "resize_keyboard": True}))


def get_stops_from_x_y(location):
    # utm_tuple = utm.from_latlon(location["latitude"], location["longitude"])
    # payload.update({"coordinateX": int(utm_tuple[0]),
    #                 "coordinateY": int(utm_tuple[1]),
    #                 "Radius": 200})
    content = make_request('geo/GetStopsFromXY.php',
                           {"latitude": location["latitude"],
                            "longitude": location["longitude"],
                            "Radius": 100})

    if "stop" not in content:
        return "No encuentro paradas alrededor", []

    # Process text message and keyboard
    text = ""
    keyboard = []
    if isinstance(content["stop"], dict):
        text += parse_stop(content["stop"])
        keyboard.append(["Parada {}".format(content["stop"]["stopId"])])
    else:
        kb_row = []
        by_row = 2
        for stop in content["stop"]:
            text += parse_stop(stop)
            if len(kb_row) == by_row:
                keyboard.append(kb_row)
                kb_row = ["Parada {}".format(stop["stopId"])]
            else:
                kb_row.append("Parada {}".format(stop["stopId"]))
        if kb_row:
            keyboard.append(kb_row)

    return text, keyboard


def parse_stop(stop):
    text = stop["stopId"] + " " + stop["name"] + "\n"
    text += "líneas: "
    if isinstance(stop["line"], dict):
        text += stop["line"]["line"]
    elif isinstance(stop["line"], list):
        text += ", ".join([line["line"] for line in stop["line"]])

    text += "\n"
    return text


@bot.command(r"/about")
def about(chat, match):
    logger.info("about|{}|{}".format(
        chat.sender.get("id"),
        chat.sender.get("username")))
    return chat.reply("https://twitter.com/VITIMan")


@bot.command("(/start|/?help)")
def usage(chat, match):
    text = """
Hola!

Bienvenido al servicio básico de encontrar una parada y saber lo que le queda a tu bus. Esperamos que lo disfrutes!

Cómo se usa:

- Paradas cercanas a tu ubicación:
    Simplemente manda tu ubicación
- Tiempo para que llegue un autobús a una parada concreta:
    /stop ID_PARADA
    """
    return chat.reply(text)


# ###### MINUTES LEFT FOR A BUS GIVEN A STOP
@bot.command("/stop (\d{1,5})")
def minutes_left(chat, match):
    try:
        stop = match.group(1)
    except IndexError:
        return chat.reply("No encuentro la parada")
    except AttributeError:
        return chat.reply("Introduce un número")

    logger.info("minutes_left|{}|{}|{}".format(
        chat.sender.get("id"),
        chat.sender.get("username"),
        stop))
    return arrive_stop(chat, stop)


@bot.command(r"parada (\d{1,5})")
def check_stop_and_location(chat, match):
    try:
        stop = match.group(1)
    except IndexError:
        return chat.reply("No encuentro la parada")
    except AttributeError:
        return chat.reply("Introduce un número")
    logger.info("check_stop_and_location|{}|{}|{}".format(
        chat.sender.get("id"),
        chat.sender.get("username"),
        stop))
    return arrive_stop_and_location(chat, stop)


def arrive_stop(chat, stop):
    """
    """
    content = make_request('geo/GetArriveStop.php', {"idStop": stop})
    return chat.reply(parse_stop_response(content))


@asyncio.coroutine
def arrive_stop_and_location(chat, stop):
    content = make_request('geo/GetArriveStop.php', {"idStop": stop})
    yield from chat.reply(parse_stop_response(content))
    try:
        content = make_request('bus/GetNodesLines.php', {"Nodes": stop})
        yield from chat.send_locaton(
            latitude=content["resultValues"]["latitude"],
            longitude=content["resultValues"]["longitude"])
    except KeyError:
        logger.warn("The stop does not exists")


def parse_stop_response(content):
    if "arrives" not in content:
        return "No encuentro la parada"

    buses = content["arrives"]
    for bus in buses:
        if bus["busTimeLeft"] == 999999:
            bus["busTimeLeft"] = 20
        else:
            bus["busTimeLeft"] = bus["busTimeLeft"] / 60

    text = ""
    for bus in buses:
        text += "{:4s} {:15s} {:3d}m\n".format(
            bus["lineId"], bus["destination"], int(bus["busTimeLeft"]))
    return text


if __name__ == '__main__':
    bot.run()
    # arrive_stop("", "1000")
    # location_stop("", "1000")
    # get_stops_from_x_y({'latitude': 40.449461, 'longitude': -3.677823})
