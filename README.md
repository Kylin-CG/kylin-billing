Kylin-billing
=============

Openstack billing system

Depends on ceilometer, python-novaclient, python-keystoneclient, nova

#### INSTALL ####
    git clone https://github.com/Kylin-CG/kylin-billing
    cd kylin-billing
    python setup.py install
    cp etc/billing-agent.conf.sample /etc/billing-agent.conf
    # Create mysql database `billing`
    billing-manage db_sync
    # Start agent manager
    billing-agent
    # Start API server
    billing-api
