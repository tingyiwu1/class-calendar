import asyncio
import pickle
import pytz
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import studentlink
from studentlink.util import normalize, Abbr, PageParseError
from studentlink.data.class_ import ScheduleClassView, Weekday, Event, Building

from icalendar import Calendar, Event as IEvent
import datetime
from contextlib import asynccontextmanager
from bs4.element import Tag

import re

TZ = pytz.timezone("US/Eastern")
BEGIN = datetime.datetime(2024, 1, 18, tzinfo=TZ)
END = datetime.datetime(2024, 5, 1, tzinfo=TZ)

INPUT = "page.html"

WEEKDAY_ABBRS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def save():
    page = open(INPUT, encoding="ISO-8859-1")
    print("opened")
    page = page.read()
    soup = BeautifulSoup(page, "html5lib")
    data_rows: list[Tag]
    _, *data_rows = (
        soup.find_all(string=re.compile(r"Spring|Summer|Fall|Winter"))[0]
        .find_parent("table")
        .find_all("tr")
    )
    result: dict[str, list[ScheduleClassView]] = {}
    semester = None
    for tr in data_rows:
        match tr.find_all("td"):
            case [
                Tag(
                    name="td",
                    attrs={"rowspan": _},
                    contents=[Tag(name="font", contents=[semester, *_]), *_],
                ),
                *rest,
            ]:
                if not isinstance(semester, str):  # skip divider rows
                    continue
                semester = normalize(semester).split("\n")[0]
                result[semester] = []
            case [*rest]:
                pass
            case _:
                raise PageParseError(f"Invalid row: \n{tr}\nin page:\n{page}")
        if semester is None:
            raise PageParseError(
                f"tr does not start with td that specifies a semester: \n{tr}\n{page}"
            )
        match rest:
            case [
                Tag(name="td", text=abbreviation),
                Tag(name="td"),
                Tag(name="td", text=status),
                Tag(name="td", text=cr_hrs),
                Tag(
                    name="td",
                    contents=[
                        Tag(name="font", contents=[title, _, instructor]),
                        *_,
                    ],
                ),
                Tag(name="td", text=topic),
                Tag(name="td", text=type),
                Tag(
                    name="td",
                    contents=[Tag(name="font", contents=[*events_buildings]), *_],
                ),
                Tag(
                    name="td",
                    contents=[Tag(name="font", contents=[*events_rooms]), *_],
                ),
                Tag(
                    name="td",
                    contents=[Tag(name="font", contents=[*events_days]), *_],
                ),
                Tag(
                    name="td",
                    contents=[Tag(name="font", contents=[*events_starts]), *_],
                ),
                Tag(
                    name="td",
                    contents=[Tag(name="font", contents=[*events_stops]), *_],
                ),
                Tag(name="td", text=notes),
            ]:
                result[semester].append(
                    create_schedule_class_view(
                        semester,
                        abbreviation,
                        status,
                        cr_hrs,
                        title,
                        instructor,
                        topic,
                        type,
                        notes,
                        events_buildings,
                        events_rooms,
                        events_days,
                        events_starts,
                        events_stops,
                    )
                )
            case [Tag(name="td", text="no\xa0reg\xa0activity"), *_]:
                continue
            case _:
                raise PageParseError(f"Invalid row: \n{tr}\nin page:\n{page}")
    return result


def create_schedule_class_view(
    semester,
    abbreviation,
    status,
    cr_hrs,
    title,
    instructor,
    topic,
    type,
    notes,
    events_buildings,
    events_rooms,
    events_days,
    events_starts,
    events_stops,
):
    schedule = []
    for building, room, days, start, stop in zip(
        events_buildings,
        events_rooms,
        events_days,
        events_starts,
        events_stops,
    ):
        match building, room:
            case Tag(name="a", text=abbr), _:
                building = Building(abbreviation=abbr)
                room = normalize(room).split("\n")[0]
            case "NO", "ROOM":
                building = room = None
            case Tag(name="br"), Tag(name="br"):  # skip line breaks
                continue
            case _:
                raise PageParseError(f"Invalid building or room: {building}, {room}")
        days = [Weekday[day] for day in days.split(",")]
        start = datetime.datetime.strptime(normalize(start), "%I:%M%p").time()
        stop = datetime.datetime.strptime(normalize(stop), "%I:%M%p").time()
        schedule += [
            Event(
                building=building,
                room=room,
                day=day,
                start=start,
                stop=stop,
            )
            for day in days
        ]
    return ScheduleClassView(
        abbr=Abbr(normalize(abbreviation)),
        semester=semester,
        status=normalize(status),
        cr_hrs=normalize(cr_hrs),
        title=normalize(title),
        instructor=normalize(instructor),
        topic=normalize(topic),
        type=normalize(type),
        schedule=schedule,
        notes=normalize(notes),
    )


def generate(schedule: dict[str, list[ScheduleClassView]]):
    for k, v in schedule.items():
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
                calendar_event = IEvent()
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
                        event.building.abbreviation + " " + event.room,
                    )
                cal.add_component(calendar_event)
        with open(k + ".ics", "wb") as f:
            f.write(cal.to_ical())


if __name__ == "__main__":
    schedule = save()
    generate(schedule)
