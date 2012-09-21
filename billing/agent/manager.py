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

"""
Billing Service
"""

import datetime
import os
import json
import math

from billing.openstack.common import log
from billing.openstack.common import cfg
from ceilometer import storage

from nova import manager

from billing.openstack import nova as nova_client
from billing import db
from billing import exception
from billing.common import timeutils
from billing.agent import price

LOG = log.getLogger(__name__)

user_opts = [
    cfg.StrOpt('admin_user', default='admin',
               help=_('Username of keystone admin user')),
    cfg.StrOpt('admin_password', default='secrete',
                help=_('Password of keystone admin user')),
]

METER_STORAGE_OPTS = [
    cfg.StrOpt('metering_storage_engine',
               default='mongodb',
               help='The name of the storage engine to use',
               ),
    cfg.StrOpt('database_connection',
               default='mongodb://localhost:27017/ceilometer',
               help='Database connection string',
               ),
    ]

CONF = cfg.CONF
CONF.register_opts(user_opts)
CONF.register_opts(METER_STORAGE_OPTS)


class BillingManager(manager.Manager):

    def init_host(self):
        storage.register_opts(CONF)
        self.storage_engine = storage.get_engine(CONF)
        self.storage_conn = self.storage_engine.get_connection(CONF)
        self.price_list = price.PriceList() 
        self.items = CONF.supported_items
        self.db_api = db.get_api()
        self.db_api.configure_db()
        self.price_counter = price.PriceCounter(self.db_api)
        # Create scoped token for admin.
        unscoped_token = nova_client.token_create(CONF.admin_user,
                                                  CONF.admin_password)
        tenants = nova_client.tenant_list_for_token(unscoped_token.id)
        token = nova_client.token_create(CONF.admin_user,
                                         CONF.admin_password,
                                         tenants[0].id)
        self.cred = {"username": CONF.admin_user,
                     "password": CONF.admin_password,
                     "tenant_id": tenants[0].id,
                     "token": token}
        return

    def periodic_tasks(self, context, raise_on_error=False):
        LOG.debug("Running periodic task update_all_project_bill,"\
                 " %s seconds left until next run.", CONF.periodic_interval)
        self._check_all_project_bill()

    def _check_all_project_bill(self):
        """Update and check all project's bill record."""
        try:
            projects = self.storage_conn.get_projects()
            for project in projects:
                LOG.info("Check bill for project: %s" % project)
                self._check_project_bill(project)
        except Exception as e:
            LOG.error('Unspecified error in instance index', exc_info=True)
            messages.error(request, 'Unable to get instance list: %s' % \
                           e.message)

    def _check_project_bill(self, project):
        """
        Update the account record for a project.
        """
        values = {}
        for item in self.items:
            values[item] = {"used": 0}
        # Total using resources are used for counting interval price.
        resources = self.storage_conn.get_resources(project=project)
        for resource in resources:
            vcpus = resource['metadata'].get('vcpus', 0)
            memory = resource['metadata'].get('memory_mb', 0)
            created_at = resource['metadata'].get('created_at', None)
            if vcpus or memory:
              if created_at is None:
                  LOG.warn("Your need to add 'created_at' property to "
                           "compute/instance.py of ceilometer")
            updated_at = resource['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
            if created_at and updated_at:
                # Count price for the using resources.
                # Count used cpu bill.
                if "cpu" in values:
                    using = self.price_counter.item_usage('cpu', project, created_at,
                                                          updated_at, vcpus)
                    values['cpu']['used'] = values['cpu']['used'] + using
                        
                # Count used memory bill.
                if "memory" in values:
                    using = self.price_counter.item_usage('memory', project, created_at,
                                                          updated_at, memory)
                    values['memory']['used'] = values['memory']['used'] + using

        # Count total used bill.
        total_used = 0
        for item in self.items:
            used = 0
            # Add deleted item record to total used.
            try:
                deleted = self.db_api.get_project_item_record_by_name(project,
                                                                item,
                                                                deleted=True)
                for d in deleted:
                    used = used + d.used
            except exception.ProjectItemRecordNotFound:
                pass
            total_used = total_used + values[item]['used'] + used

        # Update item record.
        items = price.Items(self.db_api, project, self.items, values)
        items.project_item_record_update()

        # Update total account record.
        total_values = {"used": int(total_used)}
        project_record = price.TotalProjectRecord(self.db_api, self.cred,
                                                  project, total_values)
        project_record.project_account_update()
