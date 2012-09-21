# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

from sqlalchemy.schema import (Column, MetaData, Table)

from billing.db.sqlalchemy.migrate_repo.schema import (
    Boolean, DateTime, Integer, String, Text, create_tables, drop_tables)

from billing.common import utils


def define_project_record_table(meta):
    project_account_record = Table('project_account_record', meta,
        Column('id', Integer(), primary_key=True, default=utils.generate_uuid),
        Column('project_id', String(255), nullable=False),
        Column('amount', Integer()),
        Column('used', Integer()),
        Column('description', Text()),
        Column('until', DateTime()),
        Column('created_at', DateTime(), nullable=False),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()),
        Column('deleted', Boolean(), nullable=False, default=False,
               index=True),
        mysql_engine='InnoDB',
        extend_existing=True)

    return project_account_record


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_project_record_table(meta)]
    create_tables(tables)


def downgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_project_record_table(meta)]
    drop_tables(tables)
