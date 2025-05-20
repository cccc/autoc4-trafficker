from pyhafas import HafasClient
from pyhafas.client import StationBoardLeg
from pyhafas.profile import  KVBProfile
import datetime
import time
import json
import sys

import asyncio

from typing import List, TypedDict, Dict, Any, Callable

import paho.mqtt.publish as publish 
import paho.mqtt.client as mqtt

# For typing purposes
class JsonLayout(TypedDict):
    departures: List[Dict[str, str]]
    srvtime: str # The srvtime, servertime, is the time when the server was accessed. As such, it describes how old the received information is.

class Trafficker:
    def __init__(self) -> None:
        # Clients
        self.client_kvb: HafasClient = HafasClient(KVBProfile())

        self.dirty_phrases: List[str] = [ "Köln Zollstock ", "Köln Nippes ", "Köln Junkersdorf ", "Köln Klettenberg ", "Köln Dellbrück ", "Köln Ehrenfeld ", "Kerpen ", "Leverkusen ", "Windeck " ]
        self.departures: List[StationBoardLeg] = self._get_departures()

        # Departure lists (because asyncio)
        self.ehrenfeld_departures: List[StationBoardLeg]
        self.venloerstr_departures: List[StationBoardLeg]

        self.json_list: JsonLayout = self._prepare_json()



    async def _gather_results(self):
        def make_ehrenfeld_call() -> None:
            self.ehrenfeld_departures = self.client_kvb.departures(
                station="900000835",
                date=datetime.datetime.now() - datetime.timedelta(minutes=15),
                products ={
                    "bus": True,
                    "stadtbahn": False,
                    "regionalverkehr": True,
                    "fernverkehr": True},
                max_trips=30
            )

        def make_venloerstr_call() -> None:
            self.venloerstr_departures = self.client_kvb.departures(
                station="900000251",
                date=datetime.datetime.now(),
                products={
                    "bus": False,
                    "stadtbahn": True,
                    "regionalverkehr": False,
                    "fernverkehr": False,
                },
                max_trips=30,
            )

        tasks = [
            asyncio.to_thread(make_ehrenfeld_call),
            asyncio.to_thread(make_venloerstr_call),
        ]

        await asyncio.gather(*tasks)

    # Collects all departures and gathers them in a big list, that is then returned
    def _get_departures(self) -> List[StationBoardLeg]:
        asyncio.run(self._gather_results())

        departures: List[StationBoardLeg] = self.ehrenfeld_departures + self.venloerstr_departures
        departures.sort(key=lambda dep: dep.dateTime)
        departures = self._clean_names_and_times(departures)
        departures = self._remove_invalid(departures)
        departures = self._remove_past_connections(departures)
        distance_from_sixteen: int = len(departures) - 16
        if distance_from_sixteen < 0:
            distance_from_sixteen = 0
        for _ in range(distance_from_sixteen):
            departures.pop()

        return departures
    
    def _remove_past_connections(self, departures: List[StationBoardLeg]) -> List[StationBoardLeg]:
        past_connections = 0
        for dpt in departures:
            if (dpt.dateTime + (dpt.delay if dpt.delay is not None else datetime.timedelta(seconds=0))).astimezone(datetime.timezone.utc) < datetime.datetime.now(datetime.timezone.utc):
                past_connections += 1
        if past_connections != 0:
            for _ in range(0,past_connections):
                departures.pop(0)
        return departures

    def _clean_names_and_times(self, departures: List[StationBoardLeg]) -> List[StationBoardLeg]:
        for dpt in departures:
            if dpt.name == "RE1RRX":
                dpt.name = "RE1"
            if dpt.name == "3" or dpt.name == "4":
                dpt.platform = "U"
            for phrase in self.dirty_phrases:
                dpt.direction = dpt.direction.replace("Hauptbahnhof", "Hbf") # pyright: ignore
                dpt.direction = dpt.direction.replace("Bahnhof", "")
                dpt.direction = dpt.direction.replace("Bf", "")
                if dpt.direction.find(phrase) != -1: # pyright: ignore
                    dpt.direction = dpt.direction.replace(phrase, "") # pyright: ignore
                    break

            if dpt.platform is None:
                dpt.platform = "X"
        return departures

    def _remove_invalid(self, departures: List[StationBoardLeg]) -> List[StationBoardLeg]:
        for dpt in departures:
            if dpt.cancelled:
                departures.remove(dpt)

            if dpt.direction == "Bf Ehrenfeld":
                departures.remove(dpt)
        return departures

    def _prepare_json(self) -> JsonLayout:
        json_output: JsonLayout = {"departures": [], "srvtime": "" }
        for dpt in self.departures:
            if dpt.delay is not None and dpt.delay.seconds != 0:
                delay = f"+{str((dpt.delay.seconds // 60))}"
            else:
                delay = ""
            departure = {
                "line": dpt.name,
                "direction": dpt.direction,
                "departure": dpt.dateTime.strftime("%H:%M"),
                "delay": delay,
                "platform": dpt.platform
            }
            json_output["departures"].append(departure)
        json_output["srvtime"] = datetime.datetime.now().strftime("%d.%m.%Y - %H:%M Uhr")
        return json_output

    def output_json(self) -> str:
        return json.dumps(self.json_list, indent=2)

if __name__ == "__main__":
    mqttc = mqtt.Client(client_id="trafficker")

    def on_connect(a, b, flags, rc):
        if rc != 0:
            sys.exit(1)
        else:
            mqttc.publish('heartbeat/trafficker', bytearray(b'\x01'), retain=True)

    mqttc.on_connect = on_connect
    mqttc.will_set('heartbeat/trafficker', bytearray(b'\x00'), 2, True)
    mqttc.connect("172.23.23.110",1883,60)
    mqttc.loop_start()

    while(True):
        json_output: str = Trafficker().output_json()
        publish.single('traffic/departures', payload=json_output, hostname="autoc4", port=1883, keepalive=60)
        time.sleep(5)

