#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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

from nova import flags

from billing.openstack.common import log
from billing.openstack.common import cfg

cfg.CONF.register_opts([
    cfg.IntOpt('periodic_interval',
               default=60,
               help='seconds between running periodic tasks')
])


def prepare_service(argv=[]):
    cfg.CONF(argv[1:])
    # FIXME(dhellmann): We must set up the nova.flags module in order
    # to have the RPC and DB access work correctly because we are
    # still using the Service object out of nova directly. We need to
    # move that into openstack.common.
    flags.FLAGS(argv[1:])
    log.setup('billing')
