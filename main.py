"""
KVB (as of 15.01.2025) does not support RE/RBs for some godforsaken reason
Because of that, we're using HAFAS provided by Verkehrsverbund Süd-Niedersachsen
I know what you're thinking. I hate it too. ~ fwam
"""

from pyhafas import HafasClient
from pyhafas.profile import VSNProfile, KVBProfile
import datetime
import json


client_vsn = HafasClient(VSNProfile())
client_kvb = HafasClient(KVBProfile())

departures_ehrenfeld = list()
departures_venloerstr = list()
departures_venloerstr_bus = list()
departures = list()
json_output = {"departures": list(), "srvtime": "" }

dirty_phrases = [ "Köln Zollstock ", "Köln Nippes ", "Köln Junkersdorf ", "Köln Klettenberg ", "Köln Dellbrück ", "Köln Ehrenfeld ", "Kerpen ", "Leverkusen "]
def get_departures():
    departures_ehrenfeld = client_vsn.arrivals(
        station="9406535", date=datetime.datetime.now() - datetime.timedelta(minutes=15), max_trips=10
    )
    departures_venloerstr = client_vsn.arrivals(
        station=client_vsn.locations("Köln Venloer Str")[0],
        products={"bus": True},
        date=datetime.datetime.now(),
        max_trips=10,
    )
    departures_venloerstr_bus = client_kvb.arrivals(
        station="900000251",
        date=datetime.datetime.now(),
        products={
            "bus": True,
            "stadtbahn": True,
            "regionalverkehr": False,
            "fernverkehr": False,
        },
        max_trips=10,
    )

    return departures_venloerstr + departures_ehrenfeld + departures_venloerstr_bus

departures = get_departures()
departures.sort(key=lambda dep: dep.dateTime)

for i in range(10):
    departures.pop()

for x in departures:
    for phrase in dirty_phrases:
        if x.direction.find(phrase) != -1:
            x.direction = x.direction.replace(phrase, "")
            print(x.direction)
        if x.direction.find("Bahnhof") != -1:
            x.direction = x.direction.replace("Hauptbahnhof", "Hbf")
            x.direction = x.direction.replace(" Bahnhof", "")
            break
    if x.cancelled:
        departures.remove(x)
    if x.direction == "Bf Ehrenfeld":
        departures.remove(x)
    if x.platform == None:
        x.platform = "X"

    if x.delay is not None and x.delay.seconds != 0:
        delay = str(x.delay.seconds // 60)
    else:
        delay = ""
    departure = {
        "line": x.name,
        "direction": x.direction,
        "departure": x.dateTime.strftime("%H:%M"),
        "delay": delay,
        "platform": x.platform
    }
    json_output["departures"].append(departure)

json_output["srvtime"] = datetime.datetime.now().strftime("%d.%m.%Y - %H:%M Uhr")

json_output = json.dumps(json_output, indent=2)
print(json_output)
print(len(departures))
