import asyncio
import pytz
import os
from dotenv import load_dotenv

import studentlink
from studentlink.modules.allsched import AllSched
from studentlink.modules.bldg import Bldg
from studentlink.data.class_ import Building
import aiohttp

from icalendar import Calendar, Event
import datetime

load_dotenv()

USERNAME, PASSWORD = os.getenv("USERNAME"), os.getenv("PASSWORD")

TZ = pytz.timezone("US/Eastern")
BEGIN = datetime.datetime(2023, 1, 19, tzinfo=TZ)
END = datetime.datetime(2023, 5, 3, tzinfo=TZ)

WEEKDAY_ABBRS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


async def main():
    cookie_jar = aiohttp.CookieJar()
    try:
        cookie_jar.load("cookies.pickle")
    except FileNotFoundError:
        pass
    async with aiohttp.ClientSession(
        cookie_jar=cookie_jar
    ) as session, studentlink.StudentLinkAuth(
        USERNAME, PASSWORD, session=session
    ) as sl:
        s = await sl.module(AllSched).get_schedule()
        for k, v in s.items():
            print(k, v)
            cal = Calendar()
            cal.add("prodid", "-//something")
            cal.add("version", "2.0")
            buildings: dict[str, Building] = {}
            for _class in v:
                for event in _class.schedule:
                    if event.building is not None:
                        buildings[event.building.abbreviation] = event.building
            for building in await asyncio.gather(
                *[sl.module(Bldg).get_building(bldg) for bldg in buildings.keys()]
            ):
                buildings[building.abbreviation] = building
            for _class in v:
                for event in _class.schedule:
                    calendar_event = Event()
                    calendar_event.add("summary", _class.abbr)
                    first_date = BEGIN + datetime.timedelta(
                        days=((event.day - 1) % 7 - BEGIN.weekday()) % 7
                    )
                    last_date = END - datetime.timedelta(
                        days=(END.weekday() - (event.day - 1) % 7) % 7
                    )
                    calendar_event.add(
                        "dtstart",
                        datetime.datetime.combine(first_date, event.start, TZ),
                    )
                    calendar_event.add(
                        "dtend", datetime.datetime.combine(first_date, event.stop, TZ)
                    )
                    calendar_event.add(
                        "rrule",
                        {
                            "freq": "weekly",
                            "until": last_date,
                            "byday": WEEKDAY_ABBRS[event.day - 1],
                        },
                    )
                    if event.building is not None:
                        calendar_event.add(
                            "location",
                            event.room
                            + " "
                            + buildings[event.building.abbreviation].description,
                        )
                    cal.add_component(calendar_event)
            with open(k + ".ics", "wb") as f:
                f.write(cal.to_ical())

    cookie_jar.save("cookies.pickle")


if __name__ == "__main__":
    asyncio.run(main())
