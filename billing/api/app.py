# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Set up the API server application instance
"""

import flask

from billing.openstack.common import cfg
from billing import db
from billing.api import v1
from billing.agent import price

app = flask.Flask('billing.api')
app.register_blueprint(v1.blueprint, url_prefix='/v1')


@app.before_request
def attach_config():
    flask.request.cfg = cfg.CONF
    db_api = db.get_api()
    db_api.configure_db()
    flask.request.db_api = db_api
