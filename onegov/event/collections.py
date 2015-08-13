from datetime import datetime, timedelta
from onegov.core.collection import Pagination
from onegov.event.models import Event, Occurrence
from sedate import replace_timezone, standardize_date
from sqlalchemy import or_


class EventCollectionPagination(Pagination):

    def __init__(self, session, page=0, state='submitted'):
        self.session = session
        self.page = page
        self.state = state

    def __eq__(self, other):
        return self.state == other.state and self.page == other.page

    def subset(self):
        query = self.query()
        query = query.order_by(Event.start)
        query = query.filter(Event.state == self.state)

        return query

    @property
    def page_index(self):
        return self.page

    def page_by_index(self, index):
        return self.__class__(self.session, index, self.state)


class EventCollection(EventCollectionPagination):

    def query(self):
        return self.session.query(Event)

    def add(self, title, start, end, timezone, **optional):
        event = Event(
            state='initiated',
            title=title,
            start=replace_timezone(start, timezone),
            end=replace_timezone(end, timezone),
            timezone=timezone,
            **optional
        )

        self.session.add(event)
        self.session.flush()

        self.remove_old_events()

        return event

    def delete(self, event):
        self.session.delete(event)
        self.session.flush()

    def remove_old_events(self, max_age=None):
        if max_age is None:
            max_age = datetime.utcnow() - timedelta(days=30)
            max_age = standardize_date(max_age, 'UTC')

        events = self.session.query(Event).filter(Event.start < max_age)
        events = list(filter(
            lambda x: max(x.occurrence_dates(limit=False)) < max_age, events
        ))
        for event in events:
            self.session.delete(event)

        self.session.flush()


class OccurrenceCollectionPagination(Pagination):

    def __init__(self, session, page=0, start=None, end=None, tags=None):
        self.session = session
        self.start = start
        self.end = end
        self.tags = tags
        self.page = page

    def __eq__(self, other):
        return self.page == other.page

    def subset(self):
        query = self.query(start=self.start, end=self.end, tags=self.tags)
        query = query.order_by(Occurrence.start)

        return query

    @property
    def page_index(self):
        return self.page

    def page_by_index(self, index):
        return self.__class__(self.session, index)


class OccurrenceCollection(OccurrenceCollectionPagination):

    def query(self, start=None, end=None, tags=None):
        query = self.session.query(Occurrence)

        if start is not None:
            query = query.filter(Occurrence.start >= start)

        if end is not None:
            query = query.filter(Occurrence.end <= end)

        if tags is not None:
            query = query.filter(or_(*(
                Occurrence.tags.like('%{0}%'.format(tag)) for tag in tags
            )))

        query = query.order_by(Occurrence.start)

        return query

    def by_id(self, id):
        return self.query().filter(Occurrence.id == id).first()

    @property
    def used_tags(self):
        # todo: optimize with hstore
        tags = []
        for occurrence in self.session.query(Occurrence):
            tags.extend([tag.strip() for tag in occurrence.tags.split(',')])

        return sorted(set(tags))
