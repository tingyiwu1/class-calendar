import asyncio
import aiohttp
import os
from dotenv import load_dotenv

import studentlink
from studentlink.util import Semester
from studentlink.modules.allsched import AllSched
from studentlink.modules.bldg import Bldg
from studentlink.modules.reg import Add
from studentlink.modules.browse_schedule import BrowseSchedule
from studentlink.data.class_ import Building

import pickle

from contextlib import asynccontextmanager

from gen import PersistentCookieJar

load_dotenv()

USERNAME, PASSWORD = os.getenv("USERNAME"), os.getenv("PASSWORD")

SEMESTER = Semester.from_str("fall 2023")


async def main():
    async with PersistentCookieJar(
        "cookies.pickle"
    ) as cookie_jar, aiohttp.ClientSession(
        cookie_jar=cookie_jar
    ) as session, studentlink.StudentLinkAuth(
        USERNAME, PASSWORD, session=session
    ) as sl:
        college_codes = await sl.module(Add).get_college_codes(SEMESTER)

        async def get_all_classes_in_college(college_code: str):
            result = []
            query = (college_code,)
            # query = ['CAS', 'XL', '386', 'A1']
            while query:
                print(query)
                classes, query = await sl.module(BrowseSchedule).search_class(
                    SEMESTER, *query, include_next_query=True
                )
                result.extend(classes)
            return result
        res = dict(zip(college_codes, await asyncio.gather(*[get_all_classes_in_college(college_code) for college_code in college_codes])))
        with open("classes.pickle", "wb") as f:
            pickle.dump(res, f)


if __name__ == "__main__":
    asyncio.run(main())
