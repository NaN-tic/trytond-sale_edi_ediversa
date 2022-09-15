# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.modules.party_edi.party import SUPPLIER_TYPE

class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    sale_pricelist_from_edi = fields.Boolean("Sale PriceList From EDI")


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    last_edi_party = fields.Many2One('edi.sale.party', 'Last Edi Party')
    type_ = fields.Function(fields.Selection(SUPPLIER_TYPE, 'Type'),
        'get_type_')
    edi_code = fields.Function(fields.Char('Edi Code'),
        'get_edi_code')
    commercial_register = fields.Function(fields.Char('Comercial Register'),
        'get_commercial_register')
    country_code = fields.Function(fields.Char('Country_code'),
        'get_country_code')

    def get_type_(self, name=None):
        if self.last_edi_party and self.last_edi_party.type_:
            return self.last_edi_party.type_
        return None

    def get_edi_code(self, name=None):
        if self.last_edi_party:
            return self.last_edi_party.edi_code
        return None

    def get_commercial_register(self, name=None):
        if self.last_edi_party:
            return self.last_edi_party.commercial_register
        return None

    def get_country_code(self, name=None):
        if self.last_edi_party:
            return self.last_edi_party.country_code
        return None
