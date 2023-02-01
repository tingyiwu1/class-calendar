import os
from dotenv import load_dotenv

from studentlink.modules.browse_schedule import RegClassView
from studentlink.data.class_ import Weekday

import pickle
from typing import TypedDict
from collections import defaultdict
import datetime
from itertools import zip_longest
import pandas as pd

load_dotenv()

USERNAME, PASSWORD = os.getenv("USERNAME"), os.getenv("PASSWORD")


class ClassEvent(TypedDict):
    start: datetime.time
    end: datetime.time
    abbr: str


def main():
    with open("classes.pickle", "rb") as f:
        classes: dict[str, list[RegClassView]] = pickle.load(f)
    classroom_schedules: dict[
        str, dict[str, dict[Weekday, list[ClassEvent]]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for class_list in classes.values():
        for class_ in class_list:
            for event in class_.schedule:
                if event.building is None or event.room is None:
                    continue
                classroom_schedules[event.building.abbreviation][event.room.upper()][
                    event.day
                ].append({"start": event.start, "end": event.stop, "abbr": class_.abbr})

    for rooms in classroom_schedules.values():
        for days in rooms.values():
            for events in days.values():
                events.sort(key=lambda x: x["start"])

    sheets = {}
    for building, rooms in classroom_schedules.items():
        grid = [[room] for room in sorted(rooms.keys(), key=lambda x: (x[0] != "B", x))]
        day_sizes = {day: 0 for day in Weekday}
        for row in grid:
            for day in Weekday:
                if day in rooms[row[0]]:
                    day_sizes[day] = max(day_sizes[day], len(rooms[row[0]][day]))
        for row in grid:
            for day in Weekday:
                row.append(day.name)
                if day in rooms[row[0]]:
                    row += [
                        f'{event["start"].strftime("%H:%M")}-{event["end"].strftime("%H:%M")} {event["abbr"]}'
                        for event in rooms[row[0]][day]
                    ]
                row += [""] * (day_sizes[day] - len(rooms[row[0]].get(day, [])))
        sheets[building] = grid

    with pd.ExcelWriter("schedules.xlsx") as writer:
        for building, grid in sheets.items():
            df = pd.DataFrame(zip_longest(*grid))
            df.to_excel(writer, sheet_name=building, index=False, header=False)
            for column in df:
                col_idx = df.columns.get_loc(column)
                writer.sheets[building].set_column(col_idx, col_idx, 25)


if __name__ == "__main__":
    main()
