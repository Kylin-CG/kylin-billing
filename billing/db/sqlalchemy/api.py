#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 Kylinos <kylin7.sg@gmail.com>
#
# Author: Liyingjun <liyingjun1988gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Defines interface for DB access."""

import datetime
import logging
import time

import sqlalchemy
from sqlalchemy import asc, create_engine, desc
from sqlalchemy.exc import (IntegrityError, OperationalError, DBAPIError,
                            DisconnectionError)
from sqlalchemy.orm import exc
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import or_, and_
from sqlalchemy.orm import relationship, backref, object_mapper
from sqlalchemy.pool import NullPool, StaticPool
from sqlalchemy import Column, Integer, String, BigInteger
from sqlalchemy import ForeignKey, DateTime, Boolean, Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base

from billing.db.sqlalchemy import migration
from billing.db.sqlalchemy import models
from billing import exception

from billing.openstack.common import cfg

_ENGINE = None
_MAKER = None
_MAX_RETRIES = None
_RETRY_INTERVAL = None
BASE = declarative_base()
sa_logger = None
LOG = logging.getLogger(__name__)


db_opts = [
    cfg.IntOpt('sql_idle_timeout', default=3600),
    cfg.IntOpt('sql_max_retries', default=10),
    cfg.IntOpt('sql_retry_interval', default=1),
    cfg.BoolOpt('db_auto_create', default=False),
    ]

CONF = cfg.CONF
CONF.register_opts(db_opts)


class MySQLPingListener(object):

    """
    Ensures that MySQL connections checked out of the
    pool are alive.

    Borrowed from:
    http://groups.google.com/group/sqlalchemy/msg/a4ce563d802c929f
    """

    def checkout(self, dbapi_con, con_record, con_proxy):
        try:
            dbapi_con.cursor().execute('select 1')
        except dbapi_con.OperationalError, ex:
            if ex.args[0] in (2006, 2013, 2014, 2045, 2055):
                msg = 'Got mysql server has gone away: %s' % ex
                LOG.warn(msg)
                raise sqlalchemy.exc.DisconnectionError(msg)
            else:
                raise


def configure_db():
    """
    Establish the database, create an engine if needed, and
    register the models.
    """
    global _ENGINE, sa_logger, _MAX_RETRIES, _RETRY_INTERVAL
    if not _ENGINE:
        billing_sql_connection = CONF.billing_sql_connection
        _MAX_RETRIES = CONF.sql_max_retries
        _RETRY_INTERVAL = CONF.sql_retry_interval
        connection_dict = sqlalchemy.engine.url.make_url(billing_sql_connection)
        engine_args = {'pool_recycle': CONF.sql_idle_timeout,
                       'echo': False,
                       'convert_unicode': True
                       }
        if 'mysql' in connection_dict.drivername:
            engine_args['listeners'] = [MySQLPingListener()]

        try:
            _ENGINE = sqlalchemy.create_engine(billing_sql_connection, **engine_args)
            _ENGINE.connect = wrap_db_error(_ENGINE.connect)
            _ENGINE.connect()
        except Exception, err:
            msg = _("Error configuring registry database with supplied "
                    "billing_sql_connection '%(billing_sql_connection)s'. "
                    "Got error:\n%(err)s") % locals()
            LOG.error(msg)
            raise

        sa_logger = logging.getLogger('sqlalchemy.engine')
        if CONF.debug:
            sa_logger.setLevel(logging.DEBUG)

        if CONF.db_auto_create:
            LOG.info('auto-creating kylin-billing DB')
            models.register_models(_ENGINE)
            try:
                migration.version_control()
            except exception.DatabaseMigrationError:
                # only arises when the DB exists and is under version control
                pass
        else:
            LOG.info('not auto-creating kylin-billing DB')


def get_session(autocommit=True, expire_on_commit=False):
    """Helper method to grab session"""
    global _MAKER
    if not _MAKER:
        assert _ENGINE
        _MAKER = sqlalchemy.orm.sessionmaker(bind=_ENGINE,
                                             autocommit=autocommit,
                                             expire_on_commit=expire_on_commit)
    return _MAKER()


def is_db_connection_error(args):
    """Return True if error in connecting to db."""
    # NOTE(adam_g): This is currently MySQL specific and needs to be extended
    #               to support Postgres and others.
    conn_err_codes = ('2002', '2003', '2006')
    for err_code in conn_err_codes:
        if args.find(err_code) != -1:
            return True
    return False


def wrap_db_error(f):
    """Retry DB connection. Copied from nova and modified."""
    def _wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except sqlalchemy.exc.OperationalError, e:
            if not is_db_connection_error(e.args[0]):
                raise

            remaining_attempts = _MAX_RETRIES
            while True:
                LOG.warning(_('SQL connection failed. %d attempts left.'),
                                remaining_attempts)
                remaining_attempts -= 1
                time.sleep(_RETRY_INTERVAL)
                try:
                    return f(*args, **kwargs)
                except sqlalchemy.exc.OperationalError, e:
                    if (remaining_attempts == 0 or
                        not is_db_connection_error(e.args[0])):
                        raise
                except sqlalchemy.exc.DBAPIError:
                    raise
        except sqlalchemy.exc.DBAPIError:
            raise
    _wrap.func_name = f.func_name
    return _wrap


# Project account record


def get_project_record_by_id(record_id, session=None):
    session = session or get_session()
    result = session.query(models.ProjectAccountRecord).\
                    filter_by(id=record_id).\
                    first()

    if not result:
        raise exception.ProjectRecordNotFound()

    return result


def get_all_project_record(deleted=False):
    """Get all project record."""
    session = get_session()
    query = session.query(models.ProjectAccountRecord).\
                    filter_by(deleted=deleted).\
                    all()

    return query


def record_get_for_project(project_id, deleted=False, session=None):
    """Get account record for project."""
    session = session or get_session()
    result = session.query(models.ProjectAccountRecord).\
                    filter_by(project_id=project_id).\
                    filter_by(deleted=deleted).\
                    first()

    if not result:
        raise exception.ProjectRecordNotFound()

    return result


def record_create_for_project(project_id, values):
    """Create account record for project."""
    values['project_id'] = project_id
    values['created_at'] = datetime.datetime.utcnow()
    values['updated_at'] = datetime.datetime.utcnow()

    session = get_session()
    with session.begin():
        record_ref = models.ProjectAccountRecord()
        record_ref.update(values)
        record_ref.save(session=session)

    return record_ref


def record_update_for_project(project_id, values):
    """Update account record for project."""
    values['updated_at'] = datetime.datetime.utcnow()

    session = get_session()
    with session.begin():
        record_ref = record_get_for_project(project_id, session=session)
        record_ref.update(values)
        record_ref.save(session=session)

    return record_ref


def record_update_for_project_by_id(record_id, values):
    """Update account record by record_id."""
    values['updated_at'] = datetime.datetime.utcnow()

    session = get_session()
    with session.begin():
        record_ref = get_project_record_by_id(record_id, session=session)
        record_ref.update(values)
        record_ref.save(session=session)

    return record_ref


def record_destroy_for_project(project_id):
    """Destroy account record for project."""
    session = get_session()
    with session.begin():
        session.query(models.ProjectAccountRecord).\
                filter_by(project_id=project_id).\
                update({'deleted': True,
                        'deleted_at': datetime.datetime.utcnow(),
                        'updated_at': datetime.datetime.utcnow()})


def destroy_project_record_by_id(record_id):
    """Destroy account record for project by record id."""
    session = get_session()
    with session.begin():
        record_ref = get_project_record_by_id(record_id, session=session)
        record_ref.delete(session=session)


# Items


def get_all_item():
    session = get_session()
    result = session.query(models.Items).\
                    filter_by(deleted=False).\
                    all()

    return result
    

def item_get_by_id(item_id, session=None):
    session = session or get_session()
    result = session.query(models.Items).\
                    filter_by(id=item_id).\
                    first()

    return result


def item_get_by_name(name, session=None):
    session = session or get_session()
    result = session.query(models.Items).\
                    filter_by(name=name).\
                    first()

    return result


def item_create(name, session=None):
    session = session or get_session()

    with session.begin():
        item_ref = models.Items()
        item_ref.update({'name': name})
        item_ref.save(session=session)


def item_destroy(item_id):
    session = get_session()
    with session.begin():
        session.query(models.Items).\
                filter_by(id=item_id).\
                update({'deleted': True,
                        'deleted_at': datetime.datetime.utcnow(),
                        'updated_at': datetime.datetime.utcnow()})


# Project item record


def get_project_item_record(record_id, deleted=False, session=None):
    session = session or get_session()
    result = session.query(models.ProjectItemRecord).\
                    filter_by(id=record_id).\
                    filter_by(deleted=deleted).\
                    first()

    if not result:
        raise exception.ProjectItemRecordNotFound()

    return result


def get_all_item_record_for_project(project_id, deleted=False, session=None):
    """Get all item record for project by project id."""
    session = session or get_session()
    result = session.query(models.ProjectItemRecord).\
                    filter_by(project_id=project_id).\
                    filter_by(deleted=deleted).\
                    all()

    if not result:
        raise exception.ProjectItemRecordNotFound()

    return result


def item_record_get_for_project(project_id, item_id,
                                deleted=False, session=None):
    """Get item record for project by item id."""
    session = session or get_session()
    result = session.query(models.ProjectItemRecord).\
                    filter_by(project_id=project_id).\
                    filter_by(item_id=item_id).\
                    filter_by(deleted=deleted).\
                    first()

    if not result:
        raise exception.ProjectItemRecordNotFound()

    return result


def get_project_item_record_by_name(project_id, item_name,
                                    deleted=False, session=None):
    """Get item record for a project by item name."""
    session = session or get_session()
    if not item_get_by_name(item_name, session=session):
        item_create(item_name, session=session)

    item = item_get_by_name(item_name, session=session)

    result = session.query(models.ProjectItemRecord).\
                    filter_by(project_id=project_id).\
                    filter_by(item_id=item.id).\
                    filter_by(deleted=deleted).\
                    all()

    if not result:
        raise exception.ProjectItemRecordNotFound()

    return result


def item_record_create_for_project(project_id, values, session=None):
    """Create item record for project."""
    values['created_at'] = datetime.datetime.utcnow()
    values['project_id'] = project_id
    values['used'] = 0

    if 'price' in values:
        values['price'] = int(values['price'])

    session = session or get_session()
    with session.begin():
        record_ref = models.ProjectItemRecord()
        record_ref.update(values)
        record_ref.save(session=session)

    return record_ref


def item_record_update_for_project(project_id, values):
    """Create item record for project."""
    values['updated_at'] = datetime.datetime.utcnow()

    session = get_session()
    with session.begin():
        record_ref = item_record_get_for_project(project_id, values["item_id"],
                                                 session=session)
        price = values.get('price', None)
        if price and price != record_ref.price:
            # Destroy item record.
            item_record_destroy_for_project(record_ref.id)
            # Create a new item record with a different price.
            record = item_record_create_for_project(project_id, values)

            return record
        else:
            record_ref.update(values)
            record_ref.save(session=session)

            return record_ref


def update_project_item_record_by_id(record_id, values):
    """Update item record by item record_id."""
    values['updated_at'] = datetime.datetime.utcnow()

    session = get_session()
    with session.begin():
        record_ref = get_project_item_record(record_id, session=session)

        price = values.get('price', None)
        if price and price != record_ref.price:
            # Destroy item record.
            item_record_destroy_for_project(record_ref.id)

            # Create a new item record with a different price.
            values['item_id'] = record_ref.item_id
            project_id = record_ref.project_id
            record = item_record_create_for_project(project_id, values)

            return record
        else:
            record_ref.update(values)
            record_ref.save(session=session)

            return record_ref


def item_record_destroy_for_project(record_id, session=None):
    session = session or get_session()
    with session.begin():
        record_ref = session.query(models.ProjectItemRecord).\
                            filter_by(id=record_id).\
                            first()
        record_ref.delete(session=session)


# User account record


def get_user_record(record_id, session=None):
    session = session or get_session()
    result = session.query(models.UserAccountRecord).\
                    filter_by(id=record_id).\
                    first()

    if not result:
        raise exception.ProjectRecordNotFound()

    return result


def record_get_for_user(project_id, user_id, deleted=False):
    """Get account record for user."""
    session = get_session()
    query = session.query(models.UserAccountRecord).\
                    filter_by(project_id=project_id).\
                    filter_by(user_id=user_id).\
                    filter_by(deleted=deleted)

    return query.all()


def get_all_user_record(deleted=False):
    """Get all user record."""
    session = get_session()
    query = session.query(models.UserAccountRecord).\
                    filter_by(deleted=deleted).\
                    all()

    return query


def record_create_for_user(project_id, user_id, values):
    """Create account record for user."""
    values['project_id'] = project_id
    values['user_id'] = user_id

    session = get_session()
    with session.begin():
        record_ref = models.UserAccountRecord()
        record_ref.update(values)
        record_ref.save(session=session)


def record_update_for_user(record_id, values):
    """Create account record for user."""
    session = get_session()
    with session.begin():
        record_ref = get_user_record(record_id, session=session)
        record_ref.update(values)
        record_ref.save(session=session)


def record_destroy_for_user(project_id, user_id):
    """Destroy account record for user."""
    session = get_session()
    with session.begin():
        session.query(models.UserAccountRecord).\
                filter_by(project_id=project_id).\
                filter_by(user_id=user_id).\
                update({'deleted': True,
                        'deleted_at': datetime.datetime.utcnow(),
                        'updated_at': datetime.datetime.utcnow()})


def destroy_user_record_by_id(record_id):
    """Destroy account record for user by record id."""
    session = get_session()
    with session.begin():
        session.query(models.UserAccountRecord).\
                filter_by(id=record_id).\
                update({'deleted': True,
                        'deleted_at': datetime.datetime.utcnow(),
                        'updated_at': datetime.datetime.utcnow()})


# Event Log

def event_get(tenant_id, user_id=None):
    """Get event log for tenant or user."""


def event_create(tenant_id, user_id=None):
    """Create event log for tenant or user."""


def event_destroy(tenant_id, user_id=None):
    """Destroy event log for tenant or user."""
