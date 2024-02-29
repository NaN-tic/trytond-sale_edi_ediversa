
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.modules.account.tests import create_chart
from trytond.modules.company.tests import (
    CompanyTestMixin, PartyCompanyCheckEraseMixin, create_company, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.exceptions import UserError, UserWarning



class SaleEdiEdiversaTestCase(CompanyTestMixin, ModuleTestCase):
    'Test SaleEdiEdiversa module'
    module = 'sale_edi_ediversa'

    @with_transaction()
    def test_sale_edi(self):
        "Test sale edi"
        pool = Pool()
        Sale = pool.get('sale.sale')
        Party = pool.get('party.party')
        EdiSale = pool.get('edi.sale')
        Warning = pool.get('res.user.warning')

        company = create_company()
        with set_company(company):
            create_chart(company)

            customer, = Party.create([{
                'name': 'customer',
                }])

            # TODO create edi.sale from file source
            edi1 = EdiSale()
            edi1.save()
            edi2 = EdiSale()
            edi2.save()

            with self.assertRaises(UserError):
                Sale.create([{
                    'party': customer,
                    'origin': str(edi1),
                    }, {
                    'party': customer,
                    'origin': str(edi1),
                    }])

            sale1, = Sale.create([{
                'party': customer,
                'origin': str(edi1),
                }])

            # try create other sale and same edi1
            with self.assertRaises(UserError):
                Sale.create([{
                    'party': customer,
                    'origin': str(edi1),
                    }])

            sale2, = Sale.create([{
                'party': customer,
                'origin': str(edi2),
                }])

            self.assertEqual(edi2.state, 'done')
            self.assertEqual(sale2.is_edi, True)

            # try to write edi that is related to other sale
            with self.assertRaises(UserError):
                sale2.origin = edi1
                sale2.save()

            # sure origin sale2 is edi2
            sale2.origin = edi2
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
            self.assertEqual(edi2.state, 'cancel')
            self.assertEqual(sale2.is_edi, False)

            # finally test when copy sale, origin is none
            sale3, sale4 = Sale.copy([sale1, sale2])
            self.assertEqual((sale3.origin, sale4.origin), (None, None))

del ModuleTestCase
