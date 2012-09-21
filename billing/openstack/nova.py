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

from billing.openstack.base import url_for

from billing.openstack.common import cfg

from novaclient.v1_1 import client as nova_client

from keystoneclient import service_catalog
from keystoneclient.v2_0 import client as keystone_client


keystone_urls = [
        cfg.StrOpt('auth_url', default='http://127.0.0.1:5000/v2.0',
                   help='Keystone auth url'),
        cfg.StrOpt('admin_url', default='http://127.0.0.1:35357/v2.0',
                   help='Keystone admin url')
]

CONF = cfg.CONF
CONF.register_opts(keystone_urls)


def keystoneclient(username=None, password=None,
                   tenant_id=None, token_id=None, admin=False):
    if admin:
        auth_url = CONF.admin_url
    else:
        auth_url = CONF.auth_url
    c = keystone_client.Client(username=username,
                               password=password,
                               tenant_id=tenant_id,
                               token=token_id,
                               auth_url=auth_url,
                               endpoint=auth_url)
    c.managment_url = auth_url
    return c


def token_create(username, password, tenant=None):
    c = keystoneclient(username=username,
                       password=password,
                       tenant_id=tenant)

    token = c.tokens.authenticate(username=username,
                                  password=password,
                                  tenant_id=tenant)
    return token


def user_list(cred, tenant_id=None):
    c = keystoneclient(username=cred["username"],
                       password=cred["password"],
                       token_id=cred["token"].id,
                       admin=True)

    return c.users.list(tenant_id=tenant_id)


def tenant_list_for_token(token):
    c = keystoneclient(token_id=token)

    return c.tenants.list()


def novaclient(cred):
    if cred.get("token", None) and cred.get("tenant_id", None):
        token = cred["token"]
        tenant_id = cred["tenant_id"]
    else:
        # Create scoped token for admin.
        unscoped_token = token_create(cred['username'], cred['password'])
        tenants = tenant_list_for_token(unscoped_token.id)
        tenant_id = tenants[0].id
        token = token_create(cred['username'], cred['password'], tenant_id)

    # Get service catalog
    catalog = service_catalog.ServiceCatalog(token)
    s_catalog = catalog.catalog.serviceCatalog

    management_url = url_for(s_catalog, 'compute')

    c = nova_client.Client(cred['username'],
                           token.id,
                           tenant_id,
                           management_url)
    c.client.auth_token = token.id
    c.client.management_url = management_url
    return c


def tenant_quota_get(cred, tenant_id):
    return novaclient(cred).quotas.get(tenant_id)


def tenant_quota_update(cred, tenant_id, **kwargs):
    novaclient(cred).quotas.update(tenant_id, **kwargs)


def user_quota_get(cred, tenant_id, user_id):
    return novaclient(cred).quotas.get(tenant_id, user_id)


def user_quota_update(cred, tenant_id, user_id, **kwargs):
    novaclient(cred).quotas.update(tenant_id, user_id, **kwargs)


def server_list(cred, tenant_id, user_id=None):
    search_opts = {}
    search_opts['all_tenants'] = True
    search_opts['project_id'] = tenant_id
    if user_id:
        search_opts['user_id'] = user_id
    return novaclient(cred).servers.list(True, search_opts)


def server_delete(cred, instance):
    novaclient(cred).servers.delete(instance)
