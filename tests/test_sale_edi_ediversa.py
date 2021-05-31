# This file is part sale_edi_ediversa module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest


from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite


class SaleEdiEdiversaTestCase(ModuleTestCase):
    'Test Sale Edi Ediversa module'
    module = 'sale_edi_ediversa'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            SaleEdiEdiversaTestCase))
    return suite
