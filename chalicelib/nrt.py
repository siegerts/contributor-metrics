"""
    nrt.py
    ~~~~~~

    Near real-time GitHub issue timeline event updater.

    TODO: handle issues cross-references
    TODO: nrt for pull requests

"""

import time
from datetime import date, timedelta

import requests  # type: ignore


try:
    from chalicelib.github import (
        REPOS,
        GitHubAPI,
        GitHubAPIException,
        create_or_update_issue,
        get_issues,
    )
    from chalicelib.models import (
        Event,
        EventPoll,
        Issue,
        PullRequest,
        create_db_session,
    )
    from chalicelib.utils import send_plain_email

except ModuleNotFoundError:
    from github import (
        REPOS,
        GitHubAPI,
        GitHubAPIException,
        create_or_update_issue,
        get_issues,
    )
    from models import Event, EventPoll, Issue, PullRequest, create_db_session
    from utils import send_plain_email


class TimelineAPI(GitHubAPI):
    def get_timeline(self, url, etag=None, **params):
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": "token " + self.token,
            "X-GitHub-Api-Version": self.gh_api_version,
        }
        if etag:
            headers["If-None-Match"] = etag

        req = requests.get(url, headers=headers, params=params)

        if req.status_code == 304:
            # no hit on rate limit
            return None
        if req.status_code == 200:
            # check rate from headers
            if req.headers["x-ratelimit-remaining"] == 0:
                pause = (req.headers["x-ratelimit-reset"] - time.time()) + 3
                print(f"...waiting for {pause} seconds.")
                time.sleep(pause)
                print("...resuming.")
            return req
        else:
            print(url)
            send_plain_email(f"{url}: {req.status_code} : {req.json()}")
            raise GitHubAPIException(req.status_code, req.json())


def create_or_update_etag(db, etag, cached_etag, issue_id, page_no, issue_updated_at):
    """Update cache based on etag header from GitHub
    Timeline API response. The cache is at
    the timeline url + page number level.

    The etag will change when a reaction is added to
    a comment, and then need to check reactions == db.reactions

    The challenge is to know when reactions are just
    happening in the background?

    The assumption is that an issue will get comments as
    reactions are coming in. This will be caught as an
    issue updates and the new reactions reconciled when
    the events are processed.

    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        etag (str): etag from API response
        cached_etag (str): etag from previous request
        issue_id (int): GitHub issue id
        page_no (int): Issue Timeline API page number.
        issue_updated_at (datetime): Last update date of issue
    """
    if cached_etag:
        db.query(EventPoll).filter(
            EventPoll.id == issue_id,
            EventPoll.page_no == page_no,
        ).update(dict(etag=etag))
    else:
        timeline_etag = EventPoll(
            **dict(
                id=issue_id,
                page_no=page_no,
                issue_updated_at=issue_updated_at,
                etag=etag,
            )
        )
        db.add(timeline_etag)
        db.commit()


def create_or_update_events(db, events, issue_id, org, repo):
    """Find all related events in the DB and update
    accordingly based on reactions and updated_at values.
    This logic is only applied to these fields as other
    event types trigger net new records.

    If not in the DB, then create new records.

    Note: `cross-referenced` - need to skip for now since
    no `event_id`.


    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        events ([dict]): Events returned from the Timeline API for a given issue
        issue_id (int): Issue Id related to events
        org (str): GitHub organization
        repo (str): GitHub repo
    """
    if not events:
        return
    else:
        # evt ids from api
        evt_ids = [evt["id"] for evt in events if evt["event"] != "cross-referenced"]

        existing_issue_evts = (
            db.query(Event)
            .filter(Event.id.in_(evt_ids), Event.issue_id == issue_id)
            .all()
        )
        existing_evts_recs = {rec.id: rec for rec in existing_issue_evts}
        evts_to_add = []

        for event in events:
            # need to skip for now since no event_id
            # TODO: figure this out, gen a unique event_id?
            if event["event"] == "cross-referenced":
                continue
            event_id = event["id"]

            # determine new
            if event_id not in existing_evts_recs.keys():
                username = None
                if not event.get("actor", None):
                    username = None
                else:
                    username = event["actor"]["login"]

                evts_to_add.append(
                    {
                        "id": event_id,
                        "issue_id": issue_id,
                        "org": org,
                        "repo": repo,
                        "event": event["event"],
                        "body": event.get("body", None),
                        "label": event.get("label", None),
                        "reactions": event.get("reactions", None),
                        "created_at": event["created_at"],
                        "updated_at": event.get("updated_at", None),
                        "author_association": event.get("author_association", None),
                        "node_id": event.get("node_id", None),
                        "user": event["actor"],
                        "username": username,
                    }
                )
            # does it need updated in db
            # comparing updated_at and reactions here
            # want to make sure that all reaction updates
            # are caught
            else:
                if event.get("commented", None):
                    if (
                        existing_evts_recs[event_id].updated_at != event["updated_at"]
                        or existing_evts_recs[event_id].reactions != event["reactions"]
                    ):
                        updated_evt = {
                            "body": event.get("body", None),
                            "reactions": event.get("reactions", None),
                            "updated_at": event.get("updated_at", None),
                        }
                        db.query(Event).filter(Event.id == event_id).update(
                            dict(**updated_evt)
                        )
                        db.commit()

        print("Number of events to add: ", len(evts_to_add))
        if not evts_to_add:
            return
        else:
            print("UPDATE ", issue_id)
            recs = [Event(**rec) for rec in evts_to_add]
            db.add_all(recs)
            db.commit()


def get_timeline_events(
    db, gh, issue_id, existing_cache_ids, timeline_url, issue_updated_at
):
    """Retrieve paginated events from Issue Timeline API

    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        gh (GitHubAPI): instance of API helper with token
        issue_id (int): GitHub issue id
        existing_cache_ids ([{str:<rec>}]): Mapping of {issue-page_no: rec} of all existing cache ids
        timeline_url (str): Timeline API URL for GitHub issue
        issue_updated_at (datetime): [description]

    Returns:
        [dict]: List of timeline events for a GitHub issue
    """
    next = True
    params = {"page": 0, "per_page": 100}
    events = []

    # check rate through API first
    # subsequent rate checks are handled using req
    # headers after each req
    gh.check_rate("core")
    while next:
        params["page"] += 1
        page_no = params["page"]

        # existing_cache_ids structure
        # {
        #     12323242-1: <rec>,
        #     12323242-2: <rec>,
        # }
        etag_key = f"{issue_id}-{page_no}"
        cached_etag = None

        if existing_cache_ids.get(etag_key, None):
            try:
                cached_etag = existing_cache_ids[etag_key].etag
                # print("cache hit")
            except (KeyError, AttributeError):
                pass

        req = gh.get_timeline(timeline_url, etag=cached_etag, **params)

        if not req:
            # print("no res")
            next = False
            continue

        events += req.json()
        next = len(req.json()) == params["per_page"]

        print("evts: ", len(req.json()))

        etag = req.headers["ETag"]
        if etag:
            create_or_update_etag(
                db, etag, cached_etag, issue_id, page_no, issue_updated_at
            )

    return events


def update_issue_activity(db, gh, db_model, since_dt=None, prs=True):
    """Updates Timeline event activity for recently updated GitHub
    issues

    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        gh (GitHubAPI): instance of API helper with token
        db_model (sqlalchemy model): DB table model that corresponds with datatype
        prs (bool, optional): Flag to indicate whether to search
        PRs or issues. Defaults to True (i.e. search PRs).
    """
    org = "aws-amplify"

    if not since_dt:
        raise Exception("since_dt is required.")

    for repo in REPOS:
        q = f"repo:{org}/{repo} updated:>={since_dt}"

        if prs:
            q += " is:pr "
        else:
            q += " is:issue "

        issues = get_issues(gh, query=q)
        issue_ids = [issue["id"] for issue in issues]

        # find existing issue timeline/page etags
        cache_recs = db.query(EventPoll).filter(EventPoll.id.in_(issue_ids)).all()

        # create hashid of issue + page
        # {
        #     12323242-1: <rec>,
        #     12323242-2: <rec>,
        # }
        existing_cache_ids = {f"{rec.id}-{rec.page_no}": rec for rec in cache_recs}

        # find existing issues
        existing_recs = db.query(db_model).filter(db_model.id.in_(issue_ids)).all()
        existing_rec_ids = {rec.id: rec for rec in existing_recs}

        for issue in issues:
            issue_id = issue["id"]
            issue_updated_at = issue["updated_at"]
            timeline_url = issue["timeline_url"]

            create_or_update_issue(db, db_model, issue, existing_rec_ids)

            # TODO: adjust for prs
            if not prs:
                events = get_timeline_events(
                    db, gh, issue_id, existing_cache_ids, timeline_url, issue_updated_at
                )
                create_or_update_events(db, events, issue_id, org, repo)

    db.close()


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv  # type: ignore

    load_dotenv()

    token = os.getenv("GH_TOKEN")
    db_url = os.getenv("DB_URL")

    # ---
    gh = TimelineAPI(token=token)
    db = create_db_session(db_url)

    today = date.today()
    # backfill
    # since_dt = today - timedelta(weeks=8)

    since_dt = today - timedelta(days=1)

    update_issue_activity(db, gh, Issue, since_dt, prs=False)
    update_issue_activity(db, gh, PullRequest, since_dt, prs=True)
