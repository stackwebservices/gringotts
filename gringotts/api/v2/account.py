import datetime

import pecan
from pecan import rest
from pecan import request
import wsme
from wsme import types as wtypes
from wsmeext.pecan import wsexpose
from oslo_config import cfg

from gringotts.api import acl
from gringotts.api import app
from gringotts.policy import check_policy
from gringotts import exception
from gringotts import utils as gringutils
from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.services import keystone
from gringotts.checker import notifier
from gringotts.openstack.common import log
from gringotts.openstack.common.gettextutils import _


cfg.CONF.import_opt('notifier_level', 'gringotts.checker.service', group='checker')
LOG = log.getLogger(__name__)


class AccountSalesPersonController(rest.RestController):

    def __init__(self, user_id):
        self.user_id = user_id

    @wsexpose(models.SalesPerson)
    def get(self):
        """Return salesperson of an account
        """
        context = pecan.request.context

        user_id = self.user_id
        conn = pecan.request.db_conn
        account = conn.get_account(context, user_id)
        sales_id = account.sales_id
        if not sales_id:
            # Only allow sales admin to know that an account
            # belongs to no salesperson.
            check_policy(context, 'uos_sales_admin')
            return models.SalesPerson()

        # Only allow salesperson to get account that
        # belongs to himself/herself.
        if not acl.limit_to_sales(context, sales_id):
            raise exception.NotAuthorized()

        try:
            sales_user = keystone.get_uos_user(sales_id)
            return models.SalesPerson(
                user_id=sales_id, user_name=sales_user['name'],
                user_email=sales_user.get('email', ''),
                real_name=sales_user.get('real_name', ''),
                mobile_number=sales_user.get('mobile_number', ''),
                company=sales_user.get('company', '')
            )
        except (exception.NotFound):
            msg = _('Could not find salesperson %s of account %s'
                    ' from keystone' % (sales_id, user_id))
            LOG.error(msg)
            raise exception.NotFound(msg)

    @wsexpose(None, body=models.AccountSalesPersonPutBody)
    def put(self, data):
        """Update salesperson of an account
        """
        context = pecan.request.context
        check_policy(context, 'uos_sales_admin')

        user_id = self.user_id
        conn = pecan.request.db_conn
        conn.set_accounts_salesperson(context, [user_id], data.sales_id)


class AccountController(rest.RestController):
    """Manages operations on account."""

    _custom_actions = {
        'level': ['PUT'],
        'charges': ['GET'],
        'estimate': ['GET'],
        'estimate_per_day': ['GET'],
        'invitees': ['GET'],
    }

    def __init__(self, user_id):
        self._id = user_id
        self.external_client = app.external_client()

    def _account(self, user_id=None):
        self.conn = pecan.request.db_conn
        _id = user_id or self._id
        try:
            account = self.conn.get_account(request.context, _id)
            if cfg.CONF.external_billing.enable:
                external_balance = self.external_client.get_external_balance(
                    _id)['data'][0]['money']
                external_balance = gringutils._quantize_decimal(
                    external_balance)
                account.balance = external_balance
        except exception.AccountNotFound:
            LOG.error("Account %s not found" % _id)
            raise
        except exception.GetExternalBalanceFailed:
            raise
        except (Exception):
            LOG.error("Fail to get account %s" % _id)
            raise exception.AccountGetFailed(user_id=_id)
        return account

    @pecan.expose()
    def _lookup(self, subpath, *remainder):
        if subpath == 'salesperson':
            return AccountSalesPersonController(self._id), remainder

    @wsexpose(models.Invitees, int, int)
    def invitees(self, limit=None, offset=None):
        """Get invitees of the inviter."""

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

        inviter = acl.get_limited_to_user(
            request.headers, 'referees_get') or self._id

        self.conn = pecan.request.db_conn
        try:
            _invitees, total_count = self.conn.get_invitees(request.context,
                                                            inviter,
                                                            limit=limit,
                                                            offset=offset)
        except Exception as e:
            LOG.exception('Fail to get invitees')
            raise exception.DBError(reason=e)

        invitees = []
        for invitee in _invitees:
            user = keystone.get_uos_user(invitee.user_id)
            if user:
                user_name = user.get(
                    'real_name') or user['email'].split('@')[0]
                user_email = user['email']
            else:
                user_name = ""
                user_email = ""
            invitees.append(models.Invitee(user_id=invitee.user_id,
                                           user_name=user_name,
                                           user_email=user_email,
                                           created_at=invitee.created_at,
                                           charged=invitee.charged,
                                           reward_value=invitee.reward_value))
        return models.Invitees(total_count=total_count,
                               invitees=invitees)

    @wsexpose(models.UserAccount, int)
    def level(self, level):
        """Update the account's level."""
        check_policy(request.context, "account:level")

        if not isinstance(level, int) or level < 0 or level > 9:
            raise exception.InvalidParameterValue(err="Invalid Level")

        self.conn = pecan.request.db_conn
        try:
            account = self.conn.change_account_level(
                request.context, self._id, level)
        except Exception as e:
            LOG.exception('Fail to change the account level of: %s' % self._id)
            raise exception.DBError(reason=e)

        return models.UserAccount.from_db_model(account)

    @wsexpose(models.UserAccount)
    def get(self):
        """Get this account."""
        user_id = acl.get_limited_to_user(
            request.headers, 'account_get') or self._id
        return models.UserAccount.from_db_model(self._account(user_id=user_id))

    @wsexpose(models.Charge, wtypes.text, body=models.Charge)
    def put(self, data):
        """Charge the account."""
        check_policy(request.context, "account:charge")

        # check uos_bill_account_charge_limited charge value
        if "uos_bill_account_charge_limited" in request.context.roles:
            lscv = int(cfg.CONF.limited_support_charge_value)
            if data.value < -lscv or data.value > lscv:
                raise exception.InvalidChargeValue(value=data.value)
        else:  # check accountant charge value
            lacv = int(cfg.CONF.limited_accountant_charge_value)
            if data.value < -lacv or data.value > lacv:
                raise exception.InvalidChargeValue(value=data.value)

        remarks = data.remarks if data.remarks != wsme.Unset else None
        operator = request.context.user_id

        self.conn = pecan.request.db_conn

        try:
            charge, is_first_charge = self.conn.update_account(
                request.context, self._id, operator=operator,
                **data.as_dict())
            has_bonus = False
            if cfg.CONF.enable_bonus and data['type'] != 'bonus':
                value = gringutils.calculate_bonus(data['value'])
                if value > 0:
                    bonus, _ = self.conn.update_account(request.context,
                                                        self._id,
                                                        type='bonus',
                                                        value=value,
                                                        come_from='system',
                                                        operator=operator,
                                                        remarks=remarks)
                    has_bonus = True

            if cfg.CONF.enable_invitation and is_first_charge:
                _account = self._account()
                min_charge_value = gringutils._quantize_decimal(
                    cfg.CONF.min_charge_value)
                reward_value = gringutils._quantize_decimal(
                    cfg.CONF.reward_value)

                if _account.inviter \
                        and data.value >= min_charge_value \
                        and reward_value > 0:
                    self.conn.update_account(
                        request.context, _account.inviter, type='bonus',
                        value=reward_value, come_from='system',
                        operator=operator,
                        remarks="reward because of invitation",
                        invitee=self._id)
                    if cfg.CONF.notify_account_charged:
                        inviter = self.conn.get_account(
                            request.context, _account.inviter).as_dict()
                        contact = keystone.get_uos_user(inviter['user_id'])
                        self.notifier = notifier.NotifierService(
                            cfg.CONF.checker.notifier_level)
                        self.notifier.notify_account_charged(
                            request.context, inviter, contact,
                            'bonus', reward_value, bonus=0,
                            operator=operator,
                            operator_name=request.context.user_name,
                            remarks="reward because of invitation")
            self.conn.set_charged_orders(request.context, self._id)
        except exception.NotAuthorized as e:
            LOG.exception('Fail to charge the account:%s '
                          'due to not authorization' % self._id)
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception('Fail to charge the account:%s, '
                          'charge value: %s' % (self._id, data.value))
            raise exception.DBError(reason=e)
        else:
            # Notifier account
            if cfg.CONF.notify_account_charged:
                account = self.conn.get_account(
                    request.context, self._id).as_dict()
                contact = keystone.get_uos_user(account['user_id'])
                country_code = contact.get("country_code") or "86"
                language = "en_US" if country_code != '86' else "zh_CN"
                self.notifier = notifier.NotifierService(
                    cfg.CONF.checker.notifier_level)
                self.notifier.notify_account_charged(
                    request.context, account, contact,
                    data['type'], charge.value,
                    bonus=bonus.value if has_bonus else 0,
                    operator=operator,
                    operator_name=request.context.user_name,
                    remarks=remarks, language=language)
        return models.Charge.from_db_model(charge)

    @wsexpose(models.Charges, wtypes.text, datetime.datetime,
              datetime.datetime, int, int)
    def charges(self, type=None, start_time=None,
                end_time=None, limit=None, offset=None):
        """Get this account's charge records."""

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

        user_id = acl.get_limited_to_user(
            request.headers, 'account_charge') or self._id

        self.conn = pecan.request.db_conn
        charges = self.conn.get_charges(request.context,
                                        user_id=user_id,
                                        type=type,
                                        limit=limit,
                                        offset=offset,
                                        start_time=start_time,
                                        end_time=end_time)
        charges_list = []
        for charge in charges:
            charges_list.append(models.Charge.from_db_model(charge))

        total_price, total_count = self.conn.get_charges_price_and_count(
            request.context, user_id=user_id, type=type,
            start_time=start_time, end_time=end_time)
        total_price = gringutils._quantize_decimal(total_price)

        return models.Charges.transform(total_price=total_price,
                                        total_count=total_count,
                                        charges=charges_list)

    @wsexpose(int)
    def estimate(self):
        """Estimate the hourly billing resources how many days to owed.
        """
        self.conn = pecan.request.db_conn

        if not cfg.CONF.enable_owe:
            return -1

        user_id = acl.get_limited_to_user(
            request.headers, 'account_estimate') or self._id

        account = self._account(user_id=user_id)
        if account.balance < 0:
            return -2

        orders = self.conn.get_active_orders(request.context,
                                             user_id=user_id,
                                             within_one_hour=True,
                                             bill_methods=['hour'])
        if not orders:
            return -1

        price_per_hour = 0
        for order in orders:
            price_per_hour += gringutils._quantize_decimal(order.unit_price)

        if price_per_hour == 0:
            return -1

        price_per_day = price_per_hour * 24
        days_to_owe_d = float(account.balance / price_per_day)
        days_to_owe = round(days_to_owe_d)
        if days_to_owe < days_to_owe_d:
            days_to_owe = days_to_owe + 1
        if days_to_owe > 7:
            return -1
        return days_to_owe

    @wsexpose(models.Estimate)
    def estimate_per_day(self):
        """Get the price per day and the remaining days that the
        balance can support.
        """
        self.conn = pecan.request.db_conn
        user_id = acl.get_limited_to_user(
            request.headers, 'account_estimate') or self._id

        account = self._account(user_id=user_id)
        orders = self.conn.get_active_orders(request.context,
                                             user_id=user_id,
                                             within_one_hour=True,
                                             bill_methods=['hour'])
        price_per_day = gringutils._quantize_decimal(0)
        remaining_day = -1
        if not orders:
            return models.Estimate(price_per_day=price_per_day,
                                   remaining_day=remaining_day)

        price_per_hour = 0
        for order in orders:
            price_per_hour += gringutils._quantize_decimal(order.unit_price)

        if price_per_hour == 0:
            return models.Estimate(price_per_day=price_per_day,
                                   remaining_day=remaining_day)

        price_per_day = price_per_hour * 24
        remaining_day = int(account.balance / price_per_day)

        return models.Estimate(price_per_day=price_per_day,
                               remaining_day=remaining_day)

    @wsexpose(None)
    def delete(self):
        """Delete the account including the projects that belong to it."""
        # only admin can delete account
        check_policy(request.context, "account:delete")

        try:
            self.conn = pecan.request.db_conn
            self.conn.delete_account(request.context, self._id)
        except (exception.NotFound):
            msg = _('Could not find account whose user_id is %s' % self._id)
            raise exception.NotFound(msg)
        except Exception as e:
            msg = _("failed to delete account whose user_id is %s." % self._id)
            LOG.warn(msg)
            raise exception.DBError(reason=e)


class ChargeController(rest.RestController):

    @wsexpose(models.Charges, wtypes.text, wtypes.text,
              datetime.datetime, datetime.datetime, int, int,
              wtypes.text, wtypes.text)
    def get(self, user_id=None, type=None, start_time=None,
            end_time=None, limit=None, offset=None,
            sort_key='created_at', sort_dir='desc'):
        """Get all charges of all account."""

        check_policy(request.context, "charges:all")

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

        users = {}

        def _get_user(user_id):
            user = users.get(user_id)
            if user:
                return user
            contact = keystone.get_uos_user(user_id) or {}
            user_name = contact.get('name')
            email = contact.get('email')
            real_name = contact.get('real_name')
            mobile = contact.get('mobile_number')
            company = contact.get('company')
            users[user_id] = models.User(user_id=user_id,
                                         user_name=user_name,
                                         email=email,
                                         real_name=real_name,
                                         mobile=mobile,
                                         company=company)
            return users[user_id]

        self.conn = pecan.request.db_conn
        charges = self.conn.get_charges(request.context,
                                        user_id=user_id,
                                        type=type,
                                        limit=limit,
                                        offset=offset,
                                        start_time=start_time,
                                        end_time=end_time,
                                        sort_key=sort_key,
                                        sort_dir=sort_dir)
        charges_list = []
        for charge in charges:
            acharge = models.Charge.from_db_model(charge)
            acharge.actor = _get_user(charge.operator)
            acharge.target = _get_user(charge.user_id)
            charges_list.append(acharge)

        total_price, total_count = self.conn.get_charges_price_and_count(
            request.context, user_id=user_id, type=type,
            start_time=start_time, end_time=end_time)
        total_price = gringutils._quantize_decimal(total_price)

        return models.Charges.transform(total_price=total_price,
                                        total_count=total_count,
                                        charges=charges_list)


class TransferMoneyController(rest.RestController):

    @wsexpose(None, body=models.TransferMoneyBody)
    def post(self, data):
        """Transfer money from one account to another.
        And only the domain owner can do the operation.
        """
        is_domain_owner = acl.context_is_domain_owner(request.headers)
        if not is_domain_owner:
            raise exception.NotAuthorized()

        conn = pecan.request.db_conn
        conn.transfer_money(request.context, data)


class DetailController(rest.RestController):

    def __init__(self):
        self.external_client = app.external_client()

    @wsexpose(models.AdminAccountsInDetail, wtypes.text, bool, int, int,
              wtypes.text, wtypes.text)
    def get_all(self, user_id=None, owed=None, limit=None, offset=None,
                sort_key='created_at', sort_dir='desc'):
        check_policy(request.context, "account:all")

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

        self.conn = pecan.request.db_conn

        try:
            accounts = self.conn.get_accounts(request.context,
                                              user_id=user_id,
                                              owed=owed,
                                              limit=limit,
                                              offset=offset,
                                              sort_key=sort_key,
                                              sort_dir=sort_dir)
            count = self.conn.get_accounts_count(request.context,
                                                 owed=owed,
                                                 user_id=user_id)
            pecan.response.headers['X-Total-Count'] = str(count)
        except exception.NotAuthorized as e:
            LOG.exception('Failed to get all accounts')
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception('Failed to get all accounts')
            raise exception.DBError(reason=e)

        results = []
        user_ids = []
        for account in accounts:
            user_ids.append(account.user_id)
            if account.sales_id:
                user_ids.append(account.sales_id)

            if cfg.CONF.external_billing.enable:
                try:
                    external_balance = \
                        self.external_client.get_external_balance(
                            account.user_id)['data'][0]['money']
                    external_balance = \
                        gringutils._quantize_decimal(
                            external_balance)
                    account.balance = external_balance
                except exception.GetExternalBalanceFailed:
                    msg = _('Fail to get %s\'s external balance' %
                            (account.user_id))
                    LOG.warn(msg)

            price_per_day, remaining_day = \
                self._estimate_per_day(account.user_id,
                                       account.balance)

            result = models.AdminAccountInDetail(
                user=None,
                user_id=account.user_id,
                salesperson=None,
                sales_id=account.sales_id,
                balance=account.balance,
                consumption=account.consumption,
                level=account.level,
                project_id=account.project_id,
                domain_id=account.domain_id,
                owed=owed,
                inviter=account.inviter,
                created_at=account.created_at,
                price_per_day=price_per_day,
                remaining_day=remaining_day
            )
            results.append(result)

        users = keystone.get_users_by_user_ids(user_ids)
        for result in results:
            user = users.get(result.user_id)
            salesperson = users.get(result.sales_id)
            if user:
                result.user = models.UserInDetail(**user)
            if salesperson:
                result.salesperson = models.UserInDetail(**salesperson)

        return models.AdminAccountsInDetail(total_count=count,
                                            accounts=results)

    def _estimate_per_day(self, user_id, balance):
        """Get the price per day and the remaining days that the
        balance can support.
        """
        self.conn = pecan.request.db_conn

        orders = self.conn.get_active_orders(request.context,
                                             user_id=user_id,
                                             within_one_hour=True,
                                             bill_methods=['hour'])
        price_per_day = gringutils._quantize_decimal(0)
        remaining_day = -1
        if not orders:
            return (price_per_day, remaining_day)

        price_per_hour = 0
        for order in orders:
            price_per_hour += gringutils._quantize_decimal(order.unit_price)

        if price_per_hour == 0:
            return (price_per_day, remaining_day)

        price_per_day = price_per_hour * 24
        remaining_day = int(balance / price_per_day)

        return (price_per_day, remaining_day)


class AccountsController(rest.RestController):
    """Manages operations on the accounts collection."""

    charges = ChargeController()
    transfer = TransferMoneyController()
    detail = DetailController()

    @pecan.expose()
    def _lookup(self, user_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        if len(user_id) == 32:
            return AccountController(user_id), remainder

    @wsexpose(models.AdminAccounts, bool, int, int, wtypes.text)
    def get_all(self, owed=None, limit=None, offset=None, duration=None):
        """Get all accounts."""

        check_policy(request.context, "account:all")

        if limit and limit < 0:
            raise exception.InvalidParameterValue(err="Invalid limit")
        if offset and offset < 0:
            raise exception.InvalidParameterValue(err="Invalid offset")

        self.conn = pecan.request.db_conn

        duration = gringutils.normalize_timedelta(duration)
        if duration:
            active_from = datetime.datetime.utcnow() - duration
        else:
            active_from = None

        try:
            accounts = self.conn.get_accounts(request.context, owed=owed,
                                              limit=limit, offset=offset,
                                              active_from=active_from)
            count = self.conn.get_accounts_count(request.context,
                                                 owed=owed,
                                                 active_from=active_from)
            pecan.response.headers['X-Total-Count'] = str(count)
        except exception.NotAuthorized as e:
            LOG.exception('Failed to get all accounts')
            raise exception.NotAuthorized()
        except Exception as e:
            LOG.exception('Failed to get all accounts')
            raise exception.DBError(reason=e)

        accounts = [models.AdminAccount.from_db_model(account)
                    for account in accounts]

        return models.AdminAccounts(total_count=count,
                                    accounts=accounts)

    @wsexpose(None, body=models.AdminAccount)
    def post(self, data):
        """Create a new account."""
        check_policy(request.context, "account:post")

        conn = pecan.request.db_conn
        try:
            account = db_models.Account(**data.as_dict())
            return conn.create_account(request.context, account)
        except Exception:
            LOG.exception('Fail to create account: %s' % data.as_dict())
            raise exception.AccountCreateFailed(user_id=data.user_id,
                                                domain_id=data.domain_id)
