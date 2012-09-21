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
    Boolean, DateTime, Integer, String, Text, create_tables, drop_tables,
    from_migration_import)

from billing.common import utils


def define_project_item_record_table(meta):
    (define_items_table,) = from_migration_import(
        '003_make_items_table', ['define_items_table'])

    items = define_items_table(meta)

    project_item_record = Table('project_item_record', meta,
        Column('id', String(36), primary_key=True, default=utils.generate_uuid),
        Column('item_id', String(36), ForeignKey('items.id'), nullable=False),
        Column('project_id', String(255), nullable=False),
        Column('used', Integer()),
        Column('until', DateTime()),
        Column('price', Integer()),
        Column('created_at', DateTime(), nullable=False),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()),
        Column('deleted', Boolean(), nullable=False, default=False,
               index=True),
        mysql_engine='InnoDB',
        extend_existing=True)

    return project_item_record


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_project_item_record_table(meta)]
    create_tables(tables)


def downgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_project_item_record_table(meta)]
    drop_tables(tables)
