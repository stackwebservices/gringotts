"""
SQLAlchemy models for Gringotts data
"""

import json
from urllib.parse import urlparse
from oslo_config import cfg

from sqlalchemy import Column, Integer, String
from sqlalchemy import DateTime, Index, DECIMAL, Boolean, Text
from sqlalchemy.types import TypeDecorator
from sqlalchemy.ext.declarative import declarative_base

from gringotts.openstack.common import timeutils

sql_opts = [
    cfg.StrOpt('mysql_engine',
               default='InnoDB',
               help='MySQL engine')
]

cfg.CONF.register_opts(sql_opts)


def table_args():
    engine_name = urlparse(cfg.CONF.database.connection).scheme
    if engine_name == 'mysql':
        return {'mysql_engine': cfg.CONF.mysql_engine,
                'mysql_charset': "utf8"}
    return None


class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""

    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class GringottsBase(object):
    """Base class for Gringotts Models."""
    __table_args__ = table_args()
    __table_initialized__ = False

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def update(self, values):
        """Make the model object behave like a dict."""
        for k, v in values.iteritems():
            setattr(self, k, v)


Base = declarative_base(cls=GringottsBase)


class Product(Base):
    """Product DB Model of SQLAlchemy"""

    __tablename__ = 'product'
    __table_args__ = (
        Index('ix_product_product_id', 'product_id'),
    )

    id = Column(Integer, primary_key=True)

    product_id = Column(String(255))
    name = Column(String(255))
    service = Column(String(255))
    region_id = Column(String(255))
    description = Column(String(255))

    unit_price = Column(Text)
    deleted = Column(Boolean)

    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime)
    deleted_at = Column(DateTime)


class Order(Base):
    """Order DB Model of SQLAlchemy"""

    __tablename__ = 'order'
    __table_args__ = (
        Index('ix_order_order_id', 'order_id'),
        Index('ix_order_resource_id', 'resource_id'),
        Index('ix_order_project_id', 'project_id'),
    )

    id = Column(Integer, primary_key=True)

    order_id = Column(String(255))
    resource_id = Column(String(255))
    resource_name = Column(String(255))

    type = Column(String(255))
    status = Column(String(64))

    unit_price = Column(DECIMAL(20, 4))
    unit = Column(String(64))
    total_price = Column(DECIMAL(20, 4))
    cron_time = Column(DateTime)
    owed = Column(Boolean, default=False)
    charged = Column(Boolean, default=False)
    renew = Column(Boolean, default=False)
    renew_method = Column(String(64))
    renew_period = Column(Integer)
    date_time = Column(DateTime)

    user_id = Column(String(255))
    project_id = Column(String(255))
    region_id = Column(String(255))
    domain_id = Column(String(255))

    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime)


class Subscription(Base):
    """Subscription DB Model of SQLAlchemy"""

    __tablename__ = 'subscription'
    __table_args__ = (
        Index('ix_subscription_subscription_id', 'subscription_id'),
        Index('ix_subscription_product_id', 'product_id'),
        Index('ix_subscription_order_id', 'order_id'),
        Index('ix_subscription_project_id', 'project_id'),
    )

    id = Column(Integer, primary_key=True)

    subscription_id = Column(String(255))
    type = Column(String(64))

    product_id = Column(String(255))
    unit_price = Column(Text)
    quantity = Column(Integer)

    order_id = Column(String(255))
    user_id = Column(String(255))
    project_id = Column(String(255))
    region_id = Column(String(255))
    domain_id = Column(String(255))

    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime)


class Bill(Base):

    __tablename__ = 'bill'
    __table_args__ = (
        Index('ix_bill_bill_id', 'bill_id'),
        Index('ix_bill_start_end_time', 'start_time', 'end_time'),
        Index('ix_bill_order_id', 'order_id'),
        Index('ix_bill_project_id', 'project_id'),
    )

    id = Column(Integer, primary_key=True)

    bill_id = Column(String(255))

    start_time = Column(DateTime)
    end_time = Column(DateTime)

    type = Column(String(255))
    status = Column(String(64))

    unit_price = Column(DECIMAL(20, 4))
    unit = Column(String(64))
    total_price = Column(DECIMAL(20, 4))
    order_id = Column(String(255))
    resource_id = Column(String(255))

    remarks = Column(String(255))

    user_id = Column(String(255))
    project_id = Column(String(255))
    region_id = Column(String(255))
    domain_id = Column(String(255))

    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime)


class Account(Base):

    __tablename__ = 'account'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    domain_id = Column(String(255))
    balance = Column(DECIMAL(20, 4))
    frozen_balance = Column(DECIMAL(20, 4), default=0)
    consumption = Column(DECIMAL(20, 4))
    level = Column(Integer)
    owed = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)

    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime)
    deleted_at = Column(DateTime)


class Project(Base):

    __tablename__ = 'project'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    project_id = Column(String(255))
    consumption = Column(DECIMAL(20, 4))
    domain_id = Column(String(255))

    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime, default=timeutils.utcnow)


class UserProject(Base):

    __tablename__ = 'user_project'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    project_id = Column(String(255))
    consumption = Column(DECIMAL(20, 4))
    domain_id = Column(String(255))

    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime, default=timeutils.utcnow)


class Charge(Base):

    __tablename__ = 'charge'

    id = Column(Integer, primary_key=True)
    charge_id = Column(String(255))
    user_id = Column(String(255))
    domain_id = Column(String(255))
    value = Column(DECIMAL(20, 4))
    type = Column(String(64))
    come_from = Column(String(255))
    charge_time = Column(DateTime)
    trading_number = Column(String(255))
    operator = Column(String(64))
    remarks = Column(String(255))

    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime)


class PreCharge(Base):

    __tablename__ = 'precharge'

    id = Column(Integer, primary_key=True)

    code = Column(String(64))
    price = Column(DECIMAL(20, 4))

    created_at = Column(DateTime, default=timeutils.utcnow)
    expired_at = Column(DateTime)
    deleted_at = Column(DateTime)

    used = Column(Boolean, default=False)
    dispatched = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)

    operator_id = Column(String(255))
    user_id = Column(String(255))
    domain_id = Column(String(255))

    remarks = Column(String(255))


class Deduct(Base):

    __tablename__ = 'deduct'

    id = Column(Integer, primary_key=True)
    req_id = Column(String(255))
    deduct_id = Column(String(255))
    type = Column(String(64))
    money = Column(DECIMAL(20, 4))
    remark = Column(String(255))

    order_id = Column(String(255))
    created_at = Column(DateTime, default=timeutils.utcnow)
