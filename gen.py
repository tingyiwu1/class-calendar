import asyncio
import aiohttp
import pytz
import os
from dotenv import load_dotenv

import studentlink
from studentlink.modules.allsched import AllSched

from icalendar import Calendar, Event
import datetime
from contextlib import asynccontextmanager

load_dotenv()

USERNAME, PASSWORD = os.getenv("USERNAME"), os.getenv("PASSWORD")

TZ = pytz.timezone("US/Eastern")
BEGIN = datetime.datetime(2023, 1, 19, tzinfo=TZ)
END = datetime.datetime(2023, 5, 3, tzinfo=TZ)

WEEKDAY_ABBRS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


@asynccontextmanager
async def PersistentCookieJar(filename):
    cookie_jar = aiohttp.CookieJar()
    try:
        cookie_jar.load(filename)
    except FileNotFoundError:
        pass
    yield cookie_jar
    cookie_jar.save(filename)


async def main():
    async with PersistentCookieJar(
        "cookies.pickle"
    ) as cookie_jar, aiohttp.ClientSession(
        cookie_jar=cookie_jar
    ) as session, studentlink.StudentLinkAuth(
        USERNAME, PASSWORD, session=session
    ) as sl:
        s = await sl.module(AllSched).get_schedule(True)
        for k, v in s.items():
            cal = Calendar()
            cal.add("prodid", "-//something")
            cal.add("version", "2.0")
            # buildings = {
            #     event.building.abbreviation: event.building
            #     for _class in v
            #     for event in _class.schedule
            #     if event.building is not None
            # }
            # for building in await asyncio.gather(
            #     *[sl.module(Bldg).get_building(bldg) for bldg in buildings.keys()]
            # ):
            #     buildings[building.abbreviation] = building
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
                            event.room + " " + event.building.description,
                        )
                    cal.add_component(calendar_event)
            with open(k + ".ics", "wb") as f:
                f.write(cal.to_ical())


if __name__ == "__main__":
    asyncio.run(main())
