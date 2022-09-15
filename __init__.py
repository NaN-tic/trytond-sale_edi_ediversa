# This file is part sale_edi_ediversa module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import sale_edi
from . import party


def register():
    Pool.register(
        party.Party,
        party.Address,
        sale_edi.Cron,
        sale_edi.EdiSaleReference,
        sale_edi.EdiSaleSale,
        sale_edi.PartyEdi,
        sale_edi.PIALIN,
        sale_edi.Sale,
        sale_edi.SaleDescription,
        sale_edi.SaleConfiguration,
        sale_edi.SaleEdi,
        sale_edi.SaleEdiDiscount,
        sale_edi.SaleEdiLine,
        sale_edi.SaleEdiLineQty,
        sale_edi.SaleEdiTax,
        module='sale_edi_ediversa', type_='model')
