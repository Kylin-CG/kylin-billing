# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2010-2012 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from billing.openstack.common import cfg
from billing.openstack.common import importutils

sql_connection_opt = [
    cfg.StrOpt('billing_sql_connection',
               default='sqlite:///billing.sqlite',
               metavar='CONNECTION',
               help='A valid SQLAlchemy connection '
                    'string for the registry database. '
                    'Default: %default'),
    cfg.StrOpt('data_api', default='billing.db.sqlalchemy.api',
                help='Python module path of data access API'),
]

CONF = cfg.CONF
CONF.register_opts(sql_connection_opt)


def add_cli_options():
    """
    Adds any configuration options that the db layer might have.

    :retval None
    """
    CONF.unregister_opt(sql_connection_opt[0])
    CONF.register_cli_opt(sql_connection_opt[0])


def get_api():
    return importutils.import_module(CONF.data_api)


# attributes common to all models
BASE_MODEL_ATTRS = set(['id', 'created_at', 'updated_at', 'deleted_at',
                        'deleted'])
