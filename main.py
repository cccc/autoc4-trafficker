"""
KVB (as of 15.01.2025) does not support RE/RBs for some godforsaken reason
Because of that, we're using HAFAS provided by Verkehrsverbund Süd-Niedersachsen
I know what you're thinking. I hate it too. ~ fwam
"""

from pyhafas import HafasClient
from pyhafas.client import StationBoardLeg
from pyhafas.profile import VSNProfile, KVBProfile
import datetime
import json

from typing import List, TypedDict, Dict

# For typing purposes
class JsonLayout(TypedDict):
    departures: List[Dict[str, str]]
    srvtime: str # The srvtime, servertime, is the time when the server was accessed. As such, it describes how old the received information is.

class Trafficker:
    def __init__(self) -> None:
        # Clients
        self.client_vsn: HafasClient = HafasClient(VSNProfile())
        self.client_kvb: HafasClient = HafasClient(KVBProfile())

        self.dirty_phrases: List[str] = [ "Köln Zollstock ", "Köln Nippes ", "Köln Junkersdorf ", "Köln Klettenberg ", "Köln Dellbrück ", "Köln Ehrenfeld ", "Kerpen ", "Leverkusen "]
        self.departures: List[StationBoardLeg] = self._get_departures()

        self.json_list: JsonLayout = self._prepare_json()

    # Collects all departures and gathers them in a big list, that is then returned
    # TODO: Make the API requests asynchronously so that the required time gets down to a third.
    def _get_departures(self) -> List[StationBoardLeg]:
        departures_ehrenfeld: List[StationBoardLeg] = self.client_vsn.arrivals(
            station="9406535", date=datetime.datetime.now() - datetime.timedelta(minutes=15), max_trips=10
        )

        departures_venloerstr: List[StationBoardLeg] = self.client_vsn.arrivals(
            station=self.client_vsn.locations("Köln Venloer Str")[0],
            products={"bus": True},
            date=datetime.datetime.now(),
            max_trips=10,
        )

        departures_venloerstr_bus: List[StationBoardLeg] = self.client_kvb.arrivals(
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

        departures: List[StationBoardLeg] = departures_venloerstr + departures_ehrenfeld + departures_venloerstr_bus
        departures.sort(key=lambda dep: dep.dateTime)
        departures = self._clean_names_and_times(departures)
        departures = self._remove_invalid(departures)

        distance_from_twenty: int = len(departures) - 20
        if distance_from_twenty < 0:
            distance_from_twenty = 0
        for _ in range(distance_from_twenty):
            departures.pop()

        return departures

    def _clean_names_and_times(self, departures: List[StationBoardLeg]) -> List[StationBoardLeg]:
        for dpt in departures:
            for phrase in self.dirty_phrases:
                if dpt.direction.find("Bahnhof") != -1: # pyright: ignore
                    dpt.direction = dpt.direction.replace("Hauptbahnhof", "Hbf") # pyright: ignore
                    dpt.direction = dpt.direction.replace(" Bahnhof", "")
                if dpt.direction.find(phrase) != -1: # pyright: ignore
                    dpt.direction = dpt.direction.replace(phrase, "") # pyright: ignore
                    break

            if dpt.platform == None:
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
                delay = f"+{str(dpt.delay.seconds // 60)}"
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
    json_output: str = Trafficker().output_json()
    print(json_output)
