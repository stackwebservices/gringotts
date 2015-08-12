import datetime
import decimal
import wsme
from wsme import types as wtypes
from gringotts.openstack.common import log
from gringotts.openstack.common import timeutils


LOG = log.getLogger(__name__)


operation_kind = wtypes.Enum(str, 'lt', 'le', 'eq', 'ne', 'ge', 'gt')


class APIBase(wtypes.Base):
    """Inherit from wsme Base class to handle complex types
    """
    def __init__(self, **kw):
        for k, v in kw.items():
            if isinstance(v, datetime.datetime):
                kw[k] = timeutils.isotime(at=v)
        super(APIBase, self).__init__(**kw)

    @classmethod
    def from_db_model(cls, m):
        return cls(**(m.as_dict()))

    @classmethod
    def transform(cls, **kwargs):
        return cls(**kwargs)

    def as_dict(self):
        return dict((k.name, getattr(self, k.name))
                    for k in wtypes.inspect_class(self.__class__)
                    if getattr(self, k.name) != wsme.Unset)

    # NOTE(suo): these two methods are to ensure the APIBase object can
    # be pickled by python-memcache client.
    def __getstate__(self):
        return self.as_dict()

    def __setstate__(self, state):
        for key in state:
            setattr(self, key, state[key])

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)


class Query(APIBase):
    """Sample query filter."""

    _op = None  # provide a default

    def get_op(self):
        return self._op or 'eq'

    def set_op(self, value):
        self._op = value

    # The name of the field to test
    field = wtypes.text

    # op = wsme.wsattr(operation_kind, default='eq')
    # this ^ doesn't seem to work.
    # The comparison operator. Defaults to 'eq'.
    op = wsme.wsproperty(operation_kind, get_op, set_op)

    # The value to compare against the stored data
    value = wtypes.text

    def __repr__(self):
        # for logging calls
        return '<Query %r %s %r>' % (self.field, self.op, self.value)

    @classmethod
    def sample(cls):
        return cls(field='resource_id',
                   op='eq',
                   value='bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
                   )


class Version(APIBase):
    """The version model."""
    version = wtypes.text


class Product(APIBase):
    """A product represents a rule which is applied to a billing resource."""
    product_id = wtypes.text
    name = wtypes.text
    service = wtypes.text
    region_id = wtypes.text
    description = wtypes.text

    type = wtypes.text
    unit_price = decimal.Decimal
    unit = wtypes.text

    reset = bool

    created_at = wtypes.text
    updated_at = wtypes.text

    extra = wsme.wsattr(wtypes.text, mandatory=False)


class Products(APIBase):
    total_count = int
    products = [Product]


class SimpleProduct(APIBase):
    """A product represents a rule which is applied to a billing resource."""
    name = wtypes.text
    service = wtypes.text

    unit_price = decimal.Decimal
    currency = wtypes.text
    unit = wtypes.text
    extra = wtypes.text


class Purchase(APIBase):
    """A purchase."""
    product_name = wtypes.text
    service = wtypes.text
    region_id = wtypes.text
    quantity = int


class Price(APIBase):
    """Price represents some products collection."""
    unit_price = decimal.Decimal
    hourly_price = decimal.Decimal
    monthly_price = decimal.Decimal
    unit = wtypes.text


class Sale(APIBase):
    """Statisttics Model for one single product."""
    product_id = wtypes.text
    product_name = wtypes.text
    service = wtypes.text
    region_id = wtypes.text

    quantity = int
    unit = wtypes.text
    total_price = decimal.Decimal

    @classmethod
    def sample(cls):
        return cls(product_id='product-xxx',
                   product_name='product-1',
                   service='Compute',
                   region_id='region-xxx',
                   quantity=1000,
                   unit='hour',
                   total_price=1234.7996)


class Sales(APIBase):
    """Statistics for all products."""
    total_price = decimal.Decimal
    sales = [Sale]


class Subscription(APIBase):
    """Represent model for a subscription to a product."""
    unit_price = decimal.Decimal
    quantity = int
    unit = wtypes.text
    total_price = decimal.Decimal
    user_id = wtypes.text
    project_id = wtypes.text
    created_at = wtypes.text
    type = wtypes.text
    extra = wtypes.text


class SubscriptionPostBody(APIBase):
    product_name = wtypes.text
    service = wtypes.text
    region_id = wtypes.text
    resource_volume = int
    order_id = wtypes.text
    type = wtypes.text
    user_id = wtypes.text
    project_id = wtypes.text


class SubscriptionPutBody(APIBase):
    order_id = wtypes.text
    quantity = int
    change_to = wtypes.text
    new_flavor = wtypes.text
    old_flavor = wtypes.text
    service = wtypes.text
    region_id = wtypes.text


class OrderPostBody(APIBase):
    """One single order."""
    order_id = wtypes.text
    unit_price = decimal.Decimal
    unit = wtypes.text
    resource_id = wtypes.text
    resource_name = wtypes.text
    user_id = wtypes.text
    project_id = wtypes.text
    region_id = wtypes.text
    type = wtypes.text
    status = wtypes.text


class OrderPutBody(APIBase):
    order_id = wtypes.text
    change_to = wtypes.text
    cron_time = datetime.datetime
    change_order_status = bool
    first_change_to = wtypes.text


class OrderIds(APIBase):
    order_ids = [wtypes.text]


class Order(APIBase):
    """One single order."""
    order_id = wtypes.text
    resource_id = wtypes.text
    resource_name = wtypes.text
    status = wtypes.text
    unit_price = decimal.Decimal
    total_price = decimal.Decimal
    type = wtypes.text
    cron_time = wtypes.text
    date_time = wtypes.text
    created_at = wtypes.text
    user_id = wtypes.text
    project_id = wtypes.text
    domain_id = wtypes.text
    region_id = wtypes.text
    owed = bool

    @classmethod
    def sample1(cls):
        return cls(order_id='31d25817-2ece-4f25-8b7b-9af8dac1a70f',
                   resource_id='31d25817-2ece-4f25-8b7b-9af8dac1a70f',
                   resource_name='vm1',
                   status='running',
                   unit_price=0.48,
                   total_price=12.55,
                   type='instance',
                   created_at=datetime.datetime(2013, 12, 29, 03, 00, 00))

    @classmethod
    def sample2(cls):
        return cls(order_id='31d25817-2ece-4f25-8b7b-9af8dac1a70f',
                   resource_id='31d25817-2ece-4f25-8b7b-9af8dac1a70f',
                   resource_name='vm2',
                   status='running',
                   unit_price=0.48,
                   total_price=1234.55,
                   type='instance',
                   created_at=datetime.datetime(2013, 12, 29, 04, 00, 00))


class Orders(APIBase):
    """Collection of orders."""
    total_count = int
    orders = [Order]

    @classmethod
    def sample(cls):
        return cls(total_count=13,
                   orders=[Order.sample1(),
                           Order.sample2()])


class BillBody(APIBase):
    order_id = wtypes.text
    action_time = datetime.datetime
    remarks = wtypes.text
    end_time = datetime.datetime


class BillResult(APIBase):
    type = int
    user_id = wtypes.text
    project_id = wtypes.text
    resource_type = wtypes.text
    resource_name = wtypes.text
    resource_id = wtypes.text
    region_id = wtypes.text
    resource_owed = bool
    date_time = wtypes.text


class Bill(APIBase):
    """Detail of an order."""
    resource_id = wtypes.text
    start_time = wtypes.text
    end_time = wtypes.text
    total_price = decimal.Decimal
    unit_price = decimal.Decimal
    remarks = wtypes.text

    @classmethod
    def sample1(cls):
        return cls(resource_id='resource-id-xxx',
                   start_time=datetime.datetime(2013, 12, 29, 03, 00, 00),
                   end_time=datetime.datetime(2013, 12, 29, 04, 00, 00),
                   total_price=12.34,
                   unit_price=0.48,
                   remarks='Instance has been created')

    @classmethod
    def sample2(cls):
        return cls(resource_id='resource-id-yyy',
                   start_time=datetime.datetime(2013, 12, 29, 04, 00, 00),
                   end_time=datetime.datetime(2013, 12, 29, 05, 00, 00),
                   total_price=12.34,
                   unit_price=0.48,
                   remarks='Instance has been stopped')


class Bills(APIBase):
    """Collection of bills."""
    total_count = int
    total_price = decimal.Decimal
    bills = [Bill]


class UserAccount(APIBase):
    """Account for a tenant."""
    balance = decimal.Decimal
    consumption = decimal.Decimal
    currency = wtypes.text
    owed = bool
    level = int


class Invitee(APIBase):
    user_id = wtypes.text
    user_name = wtypes.text
    user_email = wtypes.text
    created_at = wtypes.text
    charged = bool
    reward_value = decimal.Decimal


class Invitees(APIBase):
    total_count = int
    invitees = [Invitee]


class AdminAccount(APIBase):
    """Account Detail for a tenant."""
    balance = decimal.Decimal
    consumption = decimal.Decimal
    level = int
    user_id = wtypes.text
    project_id = wtypes.text
    domain_id = wtypes.text
    sales_id = wtypes.text
    owed = bool
    inviter = wtypes.text
    created_at = wtypes.text


class AdminAccounts(APIBase):
    total_count = int
    accounts = [AdminAccount]


class AccountSalesPersonPutBody(APIBase):
    sales_id = wtypes.text


class SalesPerson(APIBase):
    user_id = wtypes.text
    user_name = wtypes.text
    user_email = wtypes.text
    real_name = wtypes.text
    mobile_number = wtypes.text
    company = wtypes.text


class SalesPersonAmount(APIBase):
    sales_amount = decimal.Decimal
    accounts_number = int


class SalesPersonAccount(APIBase):
    user_id = wtypes.text
    user_name = wtypes.text
    user_email = wtypes.text
    real_name = wtypes.text
    mobile_number = wtypes.text
    company = wtypes.text
    balance = decimal.Decimal
    consumption = decimal.Decimal
    owed = bool


class SalesPersonAccounts(APIBase):
    total_count = int
    accounts = [SalesPersonAccount]


class SalesPersonAccountsPutBody(APIBase):
    user_ids = [wtypes.text]


class Summary(APIBase):
    """Summary of one single kind of order."""
    total_price = decimal.Decimal
    total_count = int
    order_type = wtypes.text


class Summaries(APIBase):
    """Summary of all kind of orders."""
    total_price = decimal.Decimal
    total_count = int
    summaries = [Summary]


class Trend(APIBase):
    """Total cunsumption in one period."""
    start_time = wtypes.text
    end_time = wtypes.text
    consumption = decimal.Decimal


class User(APIBase):
    """UOS user model."""
    user_id = wtypes.text
    user_name = wtypes.text


class SimpleProject(APIBase):
    """UOS project model."""
    project_id = wtypes.text
    project_name = wtypes.text


class Charge(APIBase):
    """Charge to account."""
    charge_id = wtypes.text
    value = decimal.Decimal
    type = wtypes.text
    come_from = wtypes.text
    charge_time = wtypes.text
    target = User
    actor = User
    remarks = wtypes.text


class Charges(APIBase):
    total_price = decimal.Decimal
    total_count = int
    charges = [Charge]


class PreChargeBody(APIBase):
    number = int
    price = decimal.Decimal
    expired_at = datetime.datetime


class PreChargeDispatched(APIBase):
    remarks = wtypes.text


class PreChargeUsed(APIBase):
    user_id = wtypes.text
    domain_id = wtypes.text


class PreCharge(APIBase):
    code = wtypes.text
    price = decimal.Decimal
    used = bool
    dispatched = bool
    user_id = wtypes.text
    project_id = wtypes.text
    created_at = wtypes.text
    expired_at = wtypes.text
    remarks = wtypes.text


class PreChargeSimple(APIBase):
    price = decimal.Decimal
    ret_code = int
    left_count = int
    lock_time = int


class Project(APIBase):
    user_id = wtypes.text
    project_id = wtypes.text
    domain_id = wtypes.text
    consumption = decimal.Decimal
    created_at = wtypes.text


class Projects(APIBase):
    projects = [Project]
    total_count = int


class UserProject(APIBase):
    user_id = wtypes.text
    project_id = wtypes.text
    domain_id = wtypes.text
    project_name = wtypes.text
    user_consumption = decimal.Decimal
    project_consumption = decimal.Decimal
    billing_owner = {wtypes.text: wtypes.text}
    project_owner = {wtypes.text: wtypes.text}
    project_creator = {wtypes.text: wtypes.text}
    is_historical = bool
    created_at = wtypes.text


class Resource(APIBase):
    region_name = wtypes.text
    resource_id = wtypes.text
    resource_name = wtypes.text
    resource_type = wtypes.text


class ComputeQuotaBody(APIBase):
    instances = int
    cores = int
    ram = int
    key_pairs = int


class VolumeQuotaBody(APIBase):
    volume_type = wtypes.text
    gigabytes = int
    snapshots = int
    volumes = int


class NetworkQuotaBody(APIBase):
    floatingip = int
    network = int
    router = int
    subnet = int
    loadbalancer = int
    listener = int
    pool = int
    security_group = int
    portforwardings = int


class QuotaBody(APIBase):
    project_id = wtypes.text
    user_id = wtypes.text
    region_name = wtypes.text
    compute = ComputeQuotaBody
    volume = [VolumeQuotaBody]
    network = NetworkQuotaBody


class QuotaItem(APIBase):
    limit = int
    used = int


class ComputeQuota(APIBase):
    instances = QuotaItem
    cores = QuotaItem
    ram = QuotaItem
    key_pairs = QuotaItem


class VolumeQuota(APIBase):
    volume_type = wtypes.text
    gigabytes = QuotaItem
    snapshots = QuotaItem
    volumes = QuotaItem


class NetworkQuota(APIBase):
    floatingip = QuotaItem
    network = QuotaItem
    router = QuotaItem
    subnet = QuotaItem
    loadbalancer = QuotaItem
    listener = QuotaItem
    pool = QuotaItem
    security_group = QuotaItem
    portforwardings = QuotaItem


class Quota(APIBase):
    project_id = wtypes.text
    user_id = wtypes.text
    region_name = wtypes.text
    compute = ComputeQuota
    volume = [VolumeQuota]
    network = NetworkQuota


class Estimate(APIBase):
    price_per_day = decimal.Decimal
    remaining_day = int


class ExtData(APIBase):
    resource_id = wtypes.text
    resource_name = wtypes.text
    resource_type = wtypes.text
    region_id = wtypes.text
    order_id = wtypes.text


class PayRequest(APIBase):
    reqId = wtypes.text
    accountNum = wtypes.text
    money = decimal.Decimal
    type = wtypes.text
    remark = wtypes.text
    extData = ExtData

    # flag to determine deduct the account actually or not
    deduct = wsme.wsattr(bool, default=True)


class Response(APIBase):
    code = wtypes.text
    total = wtypes.text
    message = wtypes.text


class Pay(APIBase):
    transactionNum = wtypes.text
    money = decimal.Decimal
    createDate = wtypes.text


class GetBalance(APIBase):
    money = decimal.Decimal


class CheckReq(APIBase):
    status = wtypes.text


class PayResponse(Response):
    data = [Pay]


class GetBalanceResponse(Response):
    data = [GetBalance]


class CheckReqResponse(Response):
    data = [CheckReq]


class TransferMoneyBody(APIBase):
    user_id_to = wtypes.text
    user_id_from = wtypes.text
    money = decimal.Decimal
    remarks = wtypes.text


class AccountsSales(APIBase):
    accounts = [wtypes.text]
    sales_id = wtypes.text
