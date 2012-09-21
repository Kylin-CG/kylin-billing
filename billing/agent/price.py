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
Price controller.
"""

import datetime
import math

from billing.common import timeutils
from billing import exception
from billing.openstack import nova as nova_client
from billing.openstack.common import cfg
from billing.openstack.common import log

LOG = log.getLogger(__name__)

price_opts = [
    cfg.ListOpt('supported_items',
                default=['cpu', 'memory'],
                help='List of items supported for record.'),
    cfg.StrOpt('cpu_price', default=1,
               help='Per cpu price per minute'),
    cfg.StrOpt('memory_price', default=1,
               help='512M memory price per minute'),
]

CONF = cfg.CONF
CONF.register_opts(price_opts)


class PriceList(object):
    def __init__(self):
        self.value = None
        self.seconds = None
        self.price = None

    def get_price(self, item, value, seconds, price=None):
        self.value = value
        self.seconds = seconds
        self.price = price
        if item == 'cpu':
            return self.cpu_price()
        if item == 'memory':
            return self.memory_price()
        else:
            return 0

    def cpu_price(self):
        # A cpu per minute consume 1 vdollar.
        price = self.price or CONF.cpu_price
        if self.seconds < 60:
            self.seconds = 60
        return (self.value*self.seconds*self.price) / 60

    def memory_price(self):
        # A memory unit is 512.
        price = self.price or CONF.memory_price
        if self.seconds < 60:
            self.seconds = 60
        return (math.floor(self.value/512)*self.seconds*self.price) / 60

    def get_project_item_price(self, db_api, item_name, project_id):
        try:
            item = db_api.item_get_by_name(item_name)
            if item:
                resource = db_api.item_record_get_for_project(
                                                            project_id,
                                                            item.id)
                if resource:
                    created_at = \
                        resource.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    return resource.price, created_at

            return CONF.get('%s_price' % item_name, 0), None
        except exception.ProjectItemRecordNotFound:
            return CONF.get('%s_price' % item_name, 0), None


class PriceCounter(object):
    def __init__(self, db_api):
        self.db_api = db_api
        self.price_list = PriceList()

    def get_project_item_price(self, item_name, project_id):
        try:
            item = self.db_api.item_get_by_name(item_name)
            if item:
                resource = self.db_api.item_record_get_for_project(
                                                            project_id,
                                                            item.id)
                if resource:
                    created_at = \
                        resource.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    return resource.price or \
                           CONF.get('%s_price' % item_name, 0), created_at

            return CONF.get('%s_price' % item_name, 0), None
        except exception.ProjectItemRecordNotFound:
            return CONF.get('%s_price' % item_name, 0), None

    def item_usage(self, item_name, project_id, created_at, updated_at, value):
        start = created_at
        end = updated_at
        price, item_created_at = self.get_project_item_price(item_name,
                                                             project_id)
        if item_created_at and end < item_created_at:
            return 0

        if item_created_at and start < item_created_at and \
           end > item_created_at:
            start = item_created_at
        used_seconds = timeutils.parse_interval(start, strend=end)

        usage = self.price_list.get_price(item_name, value,
                                          used_seconds, price=price)
        return usage


class Items(object):
    def __init__(self, db_api, project_id, resources, values, user_id=None):
        """
        :param db_api: APIs access to database.
        :param project_id: Id of the project.
        :param resources: supported item list.
        :param values: Item billing record dict for a project,
                 { item:
                   {
                     "used":
                     "updated_at":
                   }
                 }
        """
        self.db_api = db_api
        self.project_id = project_id
        self.user_id = user_id
        self.resources = resources
        self.values = values

    def project_item_record_update(self):
        for item in self.resources:
            if not self.db_api.item_get_by_name(item):
                self.db_api.item_create(item)

            resource = self.db_api.item_get_by_name(item)
            value = {}
            if item in self.values:
                value = self.values[item]
                # Only suport integer billing.
                value['used'] = int(value['used'])
                value['item_id'] = resource.id
                try:
                    self.db_api.item_record_update_for_project(self.project_id,
                                                               value)
                    LOG.info("Used bill for item: %s updated: %s" % \
                                            (value["item_id"], value["used"]))
                except exception.ProjectItemRecordNotFound:
                    # Default vlaue:
                    # Dead time: 1 day
                    # Item Price: 1/min
                    value["until"] = datetime.datetime.utcnow() + \
                                     datetime.timedelta(days=1)
                    value["price"] = CONF.get('%s_price' % item, 0)
                    self.db_api.item_record_create_for_project(self.project_id,
                                                               value)
                    LOG.info("Used item bill for %s created: %s" % \
                                            (value["item_id"], value["used"]))


class TotalProjectRecord(object):
    def __init__(self, db_api, cred, project_id, values):
        """
        :param db_api: APIs access to database.
        :param cred: Credential for keystone authentication.
        :param project_id: Id of a project.
        :param values: Total billing record dict for a project,
                 {
                   "used":
                   "updated_at":
                 }
        """
        self.db_api = db_api
        self.cred = cred
        self.project_id = project_id
        self.values = values

    def _handle_project_billing_exhausted(self):
        # Set user quotas of the project to 0.
        project_users = nova_client.user_list(self.cred,
                                              tenant_id=self.project_id)
        for user in project_users:
            user_quotas = nova_client.user_quota_get(self.cred,
                                                     self.project_id, user.id)
            if user_quotas.cores == 0 and user_quotas.ram == 0:
                pass
            else:
                LOG.info("Setting quotas for user to 0.")
                nova_client.user_quota_update(self.cred,
                                              self.project_id,
                                              user.id,
                                              ram=0,
                                              cores=0)
        # 1. Set project quotas to 0.
        # 2. Halt all instances of the project.
        project_quotas = nova_client.tenant_quota_get(self.cred,
                                                      self.project_id)
        if project_quotas.cores == 0 and project_quotas.ram ==0:
            pass
        else:
            LOG.info("Setting quotas for project: %s to 0.", self.project_id)
            nova_client.tenant_quota_update(self.cred,
                                            self.project_id,
                                            ram=0,
                                            cores=0)

        servers = nova_client.server_list(self.cred, self.project_id)
        for server in servers:
            LOG.info('Deleting server: %s, which belongs to %s' % \
                     (server.id, self.project_id))
            #nova_client.server_delete(self.cred, server.id)

    def project_account_update(self):
        try:
            # Write data to database
            self.db_api.record_update_for_project(self.project_id,
                                                  self.values)
            LOG.info("Used project bill updated: %s" % self.values["used"])
        except exception.ProjectRecordNotFound:
            until = datetime.datetime.utcnow() + datetime.timedelta(days=1)
            values = {"amount": 1000,
                      "used": 0,
                      "description": "Initial vdollar for project is 1000",
                      "until": until}
            self.db_api.record_create_for_project(self.project_id, values)
            LOG.info("Project bill created: %s" % values["amount"])

        record = self.db_api.record_get_for_project(self.project_id)
        if record.amount < self.values["used"] or \
           datetime.datetime.utcnow() > record.until:
           # NOTE(lyj): Handle event while vDollar used up,
           #            or bill expired.
            LOG.info("Handling billing exhausted event...")
            self._handle_project_billing_exhausted()
