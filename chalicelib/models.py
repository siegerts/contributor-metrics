from sqlalchemy import Boolean, Column, DateTime, Integer, String, Float, create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()


class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True)
    inserted_dt = Column(DateTime, default=func.now())
    inactive_dt = Column(DateTime)
    inactive = Column(Boolean, default=False)
    avatar_url = Column(String)
    events_url = Column(String)
    followers_url = Column(String)
    following_url = Column(String)
    gists_url = Column(String)
    gravatar_id = Column(String)
    html_url = Column(String)
    login = Column(String)
    node_id = Column(String)
    organizations_url = Column(String)
    received_events_url = Column(String)
    repos_url = Column(String)
    site_admin = Column(Boolean)
    starred_url = Column(String)
    subscriptions_url = Column(String)
    type = Column(String)
    url = Column(String)


class Issue(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True)
    active_lock_reason = Column(String)
    assignee = Column(JSON)
    assignees = Column(ARRAY(JSON))
    author_association = Column(String)
    body = Column(String)
    closed_at = Column(DateTime)
    comments = Column(Integer)
    comments_url = Column(String)
    created_at = Column(DateTime)
    events_url = Column(String)
    html_url = Column(String)
    labels = Column(ARRAY(JSON))
    labels_url = Column(String)
    locked = Column(Boolean)
    milestone = Column(JSON)
    node_id = Column(String)
    number = Column(Integer)
    org = Column(String)
    performed_via_github_app = Column(String)
    reactions = Column(JSON)
    repo = Column(String)
    repository_url = Column(String)
    score = Column(Float)
    state = Column(String)
    timeline_url = Column(String)
    title = Column(String)
    updated_at = Column(DateTime)
    url = Column(String)
    user = Column(JSON)
    username = Column(String)


class PullRequest(Base):
    __tablename__ = "pull_requests"
    id = Column(Integer, primary_key=True)
    url = Column(String)
    repo = Column(String)
    org = Column(String)
    repository_url = Column(String)
    labels_url = Column(String)
    comments_url = Column(String)
    events_url = Column(String)
    html_url = Column(String)
    node_id = Column(String)
    number = Column(Integer)
    title = Column(String)
    user = Column(JSON)
    username = Column(String)
    labels = Column(ARRAY(JSON))
    state = Column(String)
    merged = Column(Boolean, default=True)
    locked = Column(Boolean)
    assignee = Column(JSON)
    assignees = Column(ARRAY(JSON))
    milestone = Column(JSON)
    comments = Column(Integer)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    closed_at = Column(DateTime)
    author_association = Column(String)
    active_lock_reason = Column(String)
    draft = Column(Boolean)
    pull_request = Column(JSON)
    body = Column(String)
    reactions = Column(JSON)
    timeline_url = Column(String)
    performed_via_github_app = Column(String)
    score = Column(Integer)


def create_db_session(db_url):
    engine = create_engine(db_url)
    DBSession = sessionmaker(bind=engine)
    db = DBSession()
    return db


def create_all(db_url):
    engine = create_engine(db_url)
    Base.metadata.create_all(
        engine, tables=[PullRequest.__table__, Member.__table__, Issue.__table__]
    )
