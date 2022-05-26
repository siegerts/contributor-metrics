"""
    add_inactive_members.py
    ~~~~~~~~~~~~~~~~~~~~~~~

    Update inactive team members.



"""
import os
from dotenv import load_dotenv
from chalicelib.models import Member, create_db_session

load_dotenv()

db_url = os.getenv("DB_URL")  # or remote var
db = create_db_session(db_url)

default_cols = [
    "inactive_dt",
    "avatar_url",
    "events_url",
    "followers_url",
    "following_url",
    "gists_url",
    "gravatar_id",
    "html_url",
    "node_id",
    "organizations_url",
    "received_events_url",
    "repos_url",
    "site_admin",
    "starred_url",
    "subscriptions_url",
    "url",
]


def update_members(users):
    member_ids = [mem[1] for mem in users]
    existing_recs = db.query(Member).filter(Member.id.in_(member_ids)).all()
    existing_rec_ids = [rec.id for rec in existing_recs]
    for (login, mem_id) in users:
        if mem_id not in existing_rec_ids:
            mem = {"id": mem_id, "login": login, "inactive": True, "type": "User"}
            cols = {col: None for col in default_cols}
            new_rec = Member(**{**mem, **cols})
            db.add(new_rec)
            db.commit()

            print(f"Inactive member saved: {login}")
    db.close()


if __name__ == "__main__":

    # SELECT distinct("user"), "user"->>'id' as _id, "user"->>'login' as login
    # FROM public.issues where
    # username in ('');

    previous_mems = [
        # login, id
        ("",),
    ]

    update_members(previous_mems)
