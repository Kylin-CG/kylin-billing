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

import logging
import os

from migrate.versioning import api as versioning_api
# See LP bug #719834. sqlalchemy-migrate changed location of
# exceptions.py after 0.6.0.
try:
    from migrate.versioning import exceptions as versioning_exceptions
except ImportError:
    from migrate import exceptions as versioning_exceptions
from migrate.versioning import repository as versioning_repository

from billing import exception
from billing.openstack.common import cfg

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


def db_version():
    """
    Return the database's current migration number

    :retval version number
    """
    repo_path = get_migrate_repo_path()
    billing_sql_connection = CONF.billing_sql_connection
    try:
        return versioning_api.db_version(billing_sql_connection, repo_path)
    except versioning_exceptions.DatabaseNotControlledError, e:
        msg = (_("database '%(billing_sql_connection)s' is not under "
                 "migration control") % locals())
        raise exception.DatabaseMigrationError(msg)


def upgrade(version=None):
    """
    Upgrade the database's current migration level

    :param version: version to upgrade (defaults to latest)
    :retval version number
    """
    db_version()  # Ensure db is under migration control
    repo_path = get_migrate_repo_path()
    billing_sql_connection = CONF.billing_sql_connection
    version_str = version or 'latest'
    LOG.info(_("Upgrading %(billing_sql_connection)s to version %(version_str)s") %
             locals())
    return versioning_api.upgrade(billing_sql_connection, repo_path, version)


def downgrade(version):
    """
    Downgrade the database's current migration level

    :param version: version to downgrade to
    :retval version number
    """
    db_version()  # Ensure db is under migration control
    repo_path = get_migrate_repo_path()
    billing_sql_connection = CONF.billing_sql_connection
    LOG.info(_("Downgrading %(billing_sql_connection)s to version %(version)s") %
             locals())
    return versioning_api.downgrade(billing_sql_connection, repo_path, version)


def version_control(version=None):
    """
    Place a database under migration control
    """
    billing_sql_connection = CONF.billing_sql_connection
    try:
        _version_control(version)
    except versioning_exceptions.DatabaseAlreadyControlledError, e:
        msg = (_("database '%(billing_sql_connection)s' is already under migration "
               "control") % locals())
        raise exception.DatabaseMigrationError(msg)


def _version_control(version):
    """
    Place a database under migration control
    """
    repo_path = get_migrate_repo_path()
    billing_sql_connection = CONF.billing_sql_connection
    if version is None:
        version = versioning_repository.Repository(repo_path).latest
    return versioning_api.version_control(billing_sql_connection, repo_path, version)


def db_sync(version=None, current_version=None):
    """
    Place a database under migration control and perform an upgrade

    :retval version number
    """
    billing_sql_connection = CONF.billing_sql_connection
    try:
        _version_control(current_version)
    except versioning_exceptions.DatabaseAlreadyControlledError, e:
        if current_version is not None:
            msg = (_("database '%(billing_sql_connection)s' is already under "
                     "migration control") % locals())
            raise exception.DatabaseMigrationError(msg)

    upgrade(version=version)


def get_migrate_repo_path():
    """Get the path for the migrate repository."""
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                        'migrate_repo')
    assert os.path.exists(path)
    return path
