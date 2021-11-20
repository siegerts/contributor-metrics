from datetime import date, timedelta

import requests

try:
    from chalicelib.github import REPOS, GitHubAPI, GitHubAPIException, get_issues
except ModuleNotFoundError:
    from github import REPOS, GitHubAPI, GitHubAPIException, get_issues

try:
    from chalicelib.models import Event, EventPoll, create_all, create_db_session
except ModuleNotFoundError:
    from models import Event, EventPoll, create_all, create_db_session


class TimelineAPI(GitHubAPI):
    def get_timeline(self, url, etag=None, **params):
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": "token " + self.token,
        }

        # this needs to paginate...
        if etag:
            headers["If-None-Match"] = etag

        req = requests.get(url, headers=headers, params=params)

        if req.status_code == 304:
            # print("no updates")
            return None

        if req.status_code == 200:
            return req
        else:
            print(url, req.json())
            raise GitHubAPIException(req.status_code, req.json())


def update_issue_activity(db, gh, since_dt=None):
    """[summary]

    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        gh (GitHubAPI): instance of API helper with token
        db_model (sqlalchemy model): DB table model that corresponds with datatype
    """
    org = "aws-amplify"

    if not since_dt:
        raise Exception("since_dt is required.")

    for repo in REPOS:
        q = f"repo:{org}/{repo} updated:>={since_dt}"
        q += " is:issue "

        issues = get_issues(gh, query=q)
        issue_ids = [issue["id"] for issue in issues]

        # find existing issue timeline/page etags
        existing_recs = db.query(EventPoll).filter(EventPoll.id.in_(issue_ids)).all()
        existing_rec_ids = {f"{rec.id}-{rec.page_no}": rec for rec in existing_recs}

        # create hashid of issue + page
        # {
        #     12323242-1: <rec>,
        #     12323242-2: <rec>,
        # }
        for issue in issues:
            issue_id = issue["id"]
            issue_updated_at = issue["updated_at"]

            # chunk events reqs
            next = True
            params = {"page": 0, "per_page": 100}
            events = []

            while next:
                params["page"] += 1
                page_no = params["page"]

                etag_id = f"{issue_id}-{page_no}"
                cached_etag = None

                if existing_rec_ids.get(etag_id, None):
                    try:
                        cached_etag = existing_rec_ids[etag_id].etag
                        print("cache hit")
                    except KeyError:
                        pass

                    # if (
                    #     issue_updated_at
                    #     == existing_rec_ids[etag_id].issue_updated_at.isoformat() + "Z"
                    # ):
                    #     continue

                    # check for timeline etag cache

                gh.check_rate("core")
                req = gh.get_timeline(issue["timeline_url"], etag=cached_etag, **params)

                # print(issue_id, issue["timeline_url"], page_no, cached_etag, sep=" ")

                if not req:
                    print("no res")
                    next = False
                    continue

                events += req.json()
                next = len(req.json()) == params["per_page"]

                print("evts: ", len(req.json()))

                etag = req.headers["ETag"]
                if etag:
                    if cached_etag:
                        db.query(EventPoll).filter(
                            EventPoll.id == issue_id,
                            EventPoll.page_no == page_no,
                        ).update(dict(etag=etag))
                    else:
                        poll_event = EventPoll(
                            **dict(
                                id=issue_id,
                                page_no=page_no,
                                issue_updated_at=issue_updated_at,
                                etag=etag,
                            )
                        )
                        db.add(poll_event)
                        db.commit()

            if not events:
                print("no events.")
            else:
                # evt ids from api
                evt_ids = [
                    evt["id"] for evt in events if evt["event"] != "cross-referenced"
                ]

                # determine new
                existing_issue_evts = (
                    db.query(Event)
                    .filter(Event.id.in_(evt_ids), Event.issue_id == issue_id)
                    .all()
                )
                existing_evts_ids = [rec.id for rec in existing_issue_evts]

                evts_to_add = []
                for event in events:
                    # need to skip for now since no event_id
                    # TODO: figure this out, gen a unique event_id
                    if event["event"] == "cross-referenced":
                        continue

                    if event["id"] not in existing_evts_ids:
                        username = None
                        if not event.get("actor", None):
                            username = None
                        else:
                            username = event["actor"]["login"]

                        evts_to_add.append(
                            {
                                "id": event["id"],
                                "issue_id": issue_id,
                                "org": org,
                                "repo": repo,
                                "event": event["event"],
                                "body": event.get("body", None),
                                "label": event.get("label", None),
                                "reactions": event.get("reactions", None),
                                "created_at": event["created_at"],
                                "node_id": event.get("node_id", None),
                                "user": event["actor"],
                                "username": username,
                            }
                        )

                print("Number of events to add: ", len(evts_to_add))
                if not evts_to_add:
                    continue
                else:
                    print("UPDATE ", issue_id)
                    recs = [Event(**rec) for rec in evts_to_add]
                    db.add_all(recs)
                    db.commit()

    db.close()


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()

    token = os.getenv("GH_TOKEN")
    db_url = os.getenv("DB_URL")

    # ---
    gh = TimelineAPI(token=token)
    db = create_db_session(db_url)

    # create_all(db_url)

    today = date.today()
    # backfill
    # since_dt = today - timedelta(weeks=8)

    since_dt = today - timedelta(days=1)
    update_issue_activity(db, gh, since_dt)
