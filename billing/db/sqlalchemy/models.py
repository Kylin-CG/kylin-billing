"""
SQLAlchemy models for billing data
"""

import datetime

from sqlalchemy import Column, Integer, String, BigInteger
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship, backref, object_mapper
from sqlalchemy import UniqueConstraint

from billing.common import utils

BASE = declarative_base()


@compiles(BigInteger, 'sqlite')
def compile_big_int_sqlite(type_, compiler, **kw):
    return 'INTEGER'


class ModelBase(object):
    """Base class for Models"""
    __table_args__ = {'mysql_engine': 'InnoDB'}
    __table_initialized__ = False
    __protected_attributes__ = set([
        "created_at", "updated_at", "deleted_at", "deleted"])

    created_at = Column(DateTime, default=datetime.datetime.utcnow(),
                        nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow(),
                        nullable=False, onupdate=datetime.datetime.utcnow())
    deleted_at = Column(DateTime)
    deleted = Column(Boolean, nullable=False, default=False)

    def save(self, session=None):
        """Save this object"""
        session = session
        session.add(self)
        session.flush()

    def delete(self, session=None):
        """Delete this object"""
        self.deleted = True
        self.deleted_at = datetime.datetime.utcnow()
        self.save(session=session)

    def update(self, values):
        """dict.update() behaviour."""
        for k, v in values.iteritems():
            self[k] = v

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def __iter__(self):
        self._i = iter(object_mapper(self).columns)
        return self

    def next(self):
        n = self._i.next().name
        return n, getattr(self, n)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def to_dict(self):
        return self.__dict__.copy()


class ProjectAccountRecord(BASE, ModelBase):
    """Represents ProjectAccountRecord in the datastore."""
    __tablename__ = 'project_account_record'

    id = Column(String(36), primary_key=True, default=utils.generate_uuid)
    project_id = Column(String(255), nullable=False)
    amount = Column(Integer)
    used = Column(Integer)
    description = Column(String(255))
    until = Column(DateTime)


class UserAccountRecord(BASE, ModelBase):
    """Represents UserAccountRecord in the datastore."""
    __tablename__ = 'user_account_record'

    id = Column(String(36), primary_key=True, default=utils.generate_uuid)
    project_id = Column(String(255), nullable=False)
    user_id = Column(String(255), nullable=False)
    amount = Column(Integer)
    used = Column(Integer)
    description = Column(String(255))
    until = Column(DateTime)


class Items(BASE, ModelBase):
    """Represents billable items in the datastore."""
    __tablename__ = 'items'

    id = Column(String(36), primary_key=True, default=utils.generate_uuid)
    name = Column(String(255), nullable=False)


class ProjectItemRecord(BASE, ModelBase):
    """Represents item record in the datastore."""
    __tablename__ = 'project_item_record'

    id = Column(String(36), primary_key=True, default=utils.generate_uuid)
    item_id = Column(String(36), ForeignKey('items.id'),
                     nullable=False)
    item = relationship(Items, backref=backref('items'))

    project_id = Column(String(255), nullable=False)
    used = Column(Integer)
    until = Column(DateTime)
    price = Column(Integer)


def register_models(engine):
    """
    Creates database tables for all models with the given engine
    """
    models = (ProjectAccountRecord, UserAccountRecord)
    for model in models:
        model.metadata.create_all(engine)


def unregister_models(engine):
    """
    Drops database tables for all models with the given engine
    """
    models = (ProjectAccountRecord, UserAccountRecord)
    for model in models:
        model.metadata.drop_all(engine)
