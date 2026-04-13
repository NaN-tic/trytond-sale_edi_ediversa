
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import shutil
from decimal import Decimal

from trytond.modules.account.tests import create_chart
from trytond.modules.company.tests import (
    CompanyTestMixin, create_company, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.exceptions import UserError, UserWarning



class SaleEdiEdiversaTestCase(CompanyTestMixin, ModuleTestCase):
    'Test SaleEdiEdiversa module'
    module = 'sale_edi_ediversa'

    @with_transaction()
    def test_import_aldi_orders_format(self):
        "Test ALDI ORDERS format"
        pool = Pool()
        EdiSale = pool.get('edi.sale')

        sale_edi = EdiSale.import_edi_file([], [
                'ORDERS_D_01B_UN_EAN010\n',
                'ORD|3500032980|220|9\n',
                'DTM|20200120|20200120\n',
                'NADBY|2345678234562||||ALDI GMBH CO. KG BEVERSTEDT'
                '|HEERSTEDTER MUEHLENWEG 22|BEVERSTEDT|27616|'
                'G78546758|DE|HRB-12345||9||||12345\n',
                'LIN|29040400|SRV|10\n',
                'PIALIN|IN|1000003244|||92|1\n',
                'IMDLIN|A|||MILCH SCHOKOLADE|DE\n',
                'QTYLIN|21|24|CT\n',
                'DTMLIN||||20200120||||||||||||100\n',
                'CNTRES|||24|1\n',
                ])

        self.assertIsNotNone(sale_edi)
        self.assertEqual(sale_edi.document_type, 'ORDERS_D_01B_UN_EAN010')
        self.assertEqual(sale_edi.number, '3500032980')
        self.assertEqual(sale_edi.document_date.isoformat(), '2020-01-20')
        self.assertEqual(sale_edi.delivery_date.isoformat(), '2020-01-20')
        self.assertEqual(len(sale_edi.lines), 1)
        self.assertEqual(sale_edi.lines[0].sequence, 10)
        self.assertEqual(sale_edi.lines[0].pialin[0].description,
            'MILCH SCHOKOLADE')
        self.assertEqual(sale_edi.lines[0].delivery_date.isoformat(),
            '2020-01-20')
        self.assertEqual(sale_edi.lines[0].expiration_days, 100)

    @with_transaction()
    def test_sale_edi(self):
        "Test sale edi"
        pool = Pool()
        Account = pool.get('account.account')
        Category = pool.get('product.category')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')
        Sale = pool.get('sale.sale')
        Party = pool.get('party.party')
        EdiSale = pool.get('edi.sale')
        Warning = pool.get('res.user.warning')

        company = create_company()
        with set_company(company):
            create_chart(company)

            customer1, customer2, customer3, = Party.create([{
                    'name': 'Customer',
                    'addresses': [('create', [])],
                    'identifiers': [('create', [{
                        'type': 'edi_head',
                        'code': 'EDI-CODE2',
                        }])],
                    },{
                    'name': 'Customer2',
                    'addresses': [('create', [])],
                    'identifiers': [('create', [{
                        'type': 'edi_head',
                        'code': 'EDI-CODE3',
                        }])],
                    },{
                    'name': 'Customer3',
                    'addresses': [('create', [])],
                    'identifiers': [('create', [{
                        'type': 'edi_head',
                        'code': 'EDI-CODE4',
                        }])],
                    },
                    ])

            account_receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ('closed', '!=', True),
                    ('company', '=', company.id),
                    ], limit=1)
            account_payable, = Account.search([
                    ('type.payable', '=', True),
                    ('closed', '!=', True),
                    ('company', '=', company.id),
                    ], limit=1)
            account_expense, = Account.search([
                    ('type.expense', '=', True),
                    ('closed', '!=', True),
                    ], limit=1)
            account_revenue, = Account.search([
                    ('type.revenue', '=', True),
                    ('closed', '!=', True),
                    ], limit=1)

            unit, = Uom.search([('name', '=', 'Unit')])

            account_category = Category()
            account_category.name = 'Account Category'
            account_category.accounting = True
            account_category.account_expense = account_expense
            account_category.account_revenue = account_revenue
            account_category.save()

            Template.create([{
                    'name': 'Product1',
                    'default_uom': unit.id,
                    'sale_uom': unit.id,
                    'list_price': Decimal(5),
                    'code': 'CODE1',
                    'salable': True,
                    'account_category': account_category,
                    'products': [('create', [{
                        'identifiers': [('create', [
                            {'type': 'ean', 'code': '1562683392128'}])],
                        }])],
                    }, {
                    'name': 'Product2',
                    'default_uom': unit.id,
                    'sale_uom': unit.id,
                    'list_price': Decimal(5),
                    'code': 'CODE2',
                    'salable': True,
                    'account_category': account_category,
                    'products': [('create', [{
                        'identifiers':  [('create', [
                            {'type': 'ean', 'code': '2165222621865'}])],
                        }])],
                    }, {
                    'name': 'Product3',
                    'default_uom': unit.id,
                    'sale_uom': unit.id,
                    'list_price': Decimal(5),
                    'code': 'CODE3',
                    'salable': True,
                    'account_category': account_category,
                    'products': [('create', [{
                        'identifiers':  [('create', [
                            {'type': 'ean', 'code': '8784511658814'}])],
                        }])],
                    }])

            edi_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'demo')
            for file_ in ('edi1.pla', 'edi2.pla', 'edi3.pla'):
                shutil.copy(os.path.join(edi_path, file_), '/tmp/')

            # import edi files and create sales from edi
            EdiSale.import_sales()
            edi1, edi2, edi3 = EdiSale.search([])
            EdiSale.create_sale([edi1])

            # Check user that edit sales related to edi (origins)
            with self.assertRaises(UserError):
                Sale.create([{
                    'party': customer1,
                    'origin': str(edi2),
                    }, {
                    'party': customer1,
                    'origin': str(edi2),
                    }])

            sale1, = Sale.create([{
                'party': customer1,
                'origin': str(edi2),
                }])

            # try create other sale and same edi1
            with self.assertRaises(UserError):
                Sale.create([{
                    'party': customer1,
                    'origin': str(edi2),
                    }])

            sale2, = Sale.create([{
                'party': customer1,
                'origin': str(edi3),
                }])

            self.assertEqual(edi3.state, 'done')
            self.assertEqual(sale2.is_edi, True)

            # try to write edi that is related to other sale
            with self.assertRaises(UserError):
                sale2.origin = edi2
                sale2.save()

            # sure origin sale2 is edi2
            sale2.origin = edi3
            sale2.save()

            # finally, set origin to None and check that edi is cancelled
            sale2 = Sale(sale2.id)
            with self.assertRaises(UserWarning):
                sale2.origin = None
                sale2.save()

            # confirm warning and try again
            Warning(user=Transaction().user, name='clean_origin_sale_%s' % sale2.id).save()
            sale2.origin = None
            sale2.save()

            # self.assertRaises(UserWarning, Sale.write, [sale])
            self.assertEqual(edi3.state, 'cancel')
            self.assertEqual(sale2.is_edi, False)

            # finally test when copy sale, origin is none
            sale3, sale4 = Sale.copy([sale1, sale2])
            self.assertEqual((sale3.origin, sale4.origin), (None, None))

            self.assertEqual(len(EdiSale.search([])), 3)
            self.assertEqual(
                len(EdiSale.search([('party.name', '=', 'Customer')])),
                3)
            self.assertEqual(
                len(EdiSale.search([('party.active', '=', True)])),
                3)

del ModuleTestCase
