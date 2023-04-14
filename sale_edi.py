# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import os
from datetime import datetime
from decimal import Decimal

from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError, UserWarning
from trytond.pyson import Eval
from sql import Cast
from sql.functions import Substring
from trytond.modules.party_edi.party import SUPPLIER_TYPE, SupplierEdiMixin
from trytond.modules.company.model import reset_employee

DEFAULT_FILES_LOCATION = '/tmp/'
MODULE_PATH = os.path.dirname(os.path.abspath(__file__))
KNOWN_EXTENSIONS = ['.txt', '.edi', '.pla']
DATE_FORMAT = '%Y%m%d'


def to_date(value):
    if value is None or value == '':
        return None
    if len(value) > 8:
        value = value[0:8]
    if value == '00000000':
        return
    return datetime.strptime(value, DATE_FORMAT)


def to_decimal(value, digits=2):
    if value is None or value == '':
        return None
    return Decimal(value).quantize(Decimal('10')**-digits)


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super(Cron, cls).__setup__()
        cls.method.selection.extend([
            ('edi.sale|import_sales',
            'Import EDI Orders')])


class SaleConfiguration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    inbox_path_edi = fields.Char('EDI Sale Inbox Path')


class PartyEdi(SupplierEdiMixin, ModelSQL, ModelView):
    'Party Edi'
    __name__ = 'edi.sale.party'

    edi_sale = fields.Many2One('edi.sale', 'Edi Sale')

    def read_NADMS(self, message):
        self.type_ = 'NADMS'
        self.edi_code = message.pop(0) if message else ''
        self.name = message.pop(0) if message else ''
        if message:
            self.street = message.pop(0)
        if message:
            self.city = message.pop(0)
        if message:
            self.zip = message.pop(0)

    def read_NADSU(self, message):
        self.type_ = 'NADSU'
        self.edi_code = message.pop(0) if message else ''
        if message:
            self.cip = message.pop(0)
        self.name = message.pop(0) if message else ''
        if message:
            self.street = message.pop(0)
        if message:
            self.city = message.pop(0)
        if message:
            self.zip = message.pop(0)
        if message:
            self.vat = message.pop(0)
        if message:
            text = message.pop(0)
            if not self.cip and text:
                self.cip = text
        if message:
            message.pop(0)
        if message:
            message.pop(0)
        if message:
            message.pop(0)
        if message:
            text = message.pop(0)
            if not self.cip and text:
                self.cip = text

    def read_NADBY(self, message):
        self.type_ = 'NADBY'
        self.edi_code = message.pop(0) if message else ''
        if message:
            self.section = message.pop(0)
        if message:
            message.pop(0)
        if message:
            message.pop(0)
        self.name = message.pop(0) if message else ''
        if message:
            self.street = message.pop(0)
        if message:
            self.city = message.pop(0)
        if message:
            self.zip = message.pop(0)
        if message:
            self.vat = message.pop(0)

    def read_NADDP(self, message):
        self.type_ = 'NADDP'
        self.edi_code = message.pop(0) if message else ''
        if message:
            message.pop(0)
        self.name = message.pop(0) if message else ''
        if message:
            self.street = message.pop(0)
        if message:
            self.city = message.pop(0)
        if message:
            self.zip = message.pop(0)

    def read_NADIV(self, message):
        self.type_ = 'NADIV'
        self.edi_code = message.pop(0) if message else ''
        if message:
            message.pop(0)
        self.name = message.pop(0) if message else ''
        if message:
            self.street = message.pop(0)
        if message:
            self.city = message.pop(0)
        if message:
            self.zip = message.pop(0)
        if message:
            self.vat = message.pop(0)

    def read_NAD(self, message):
        self.type_ = 'NAD'
        self.edi_code = message.pop(0) if message else ''
        if message:
            self.vat = message.pop(0)


class SaleDescription(ModelSQL, ModelView):
    'Sale Description'
    __name__ = 'edi.sale.description'

    description = fields.Text('Description', readonly=True)
    sale = fields.Many2One('edi.sale', 'Sale', readonly=True)
    type_ = fields.Selection([
        ('DEL', 'Delivery Information'),
        ('AAI', 'General Information'),
        ('PAC', 'Package Information'),
        ('PUR', 'Purchase Information'),
        ('TXD', 'Tax Information'),
        ('INV', 'Invoice Information'),
        ('MKS', 'Information about marks and numbers'),
        ('ZZZ', 'Mutual definition')],
        'Type', readonly=True)

    def read_FTX(self, message):
        self.type_ = message.pop(0)
        message.pop(0)
        self.description = message.pop(0) if message else ''


class EdiSaleReference(ModelSQL, ModelView):
    'Sale Reference'
    __name__ = 'edi.sale.reference'

    # RFF, RFFLIN
    type_ = fields.Selection([
        (None, ''),
        ('AN', 'Shipment Number'),
        ('F', 'Shipment Date'), ],
        'Reference Code', readonly=True)
    reference = fields.Char('Reference', readonly=True)
    reference_date = fields.Date('Reference Date', readonly=True)
    origin = fields.Reference('Reference', selection='get_resource')
    line = fields.Many2One('edi.sale.line', 'Line', readonly=True)
    edi_sale = fields.Many2One('edi.sale', 'Sale', readonly=True)

    @classmethod
    def get_resource(cls):
        'Return list of Model names for resource Reference'
        return [(None, ''),
                ('stock.shipment.out', 'Shipment'), ]

    def read_message(self, message):
        message.pop(0)
        self.type_ = message.pop(0) if message else ''
        self.value = message.pop(0) if message else ''

    def search_reference(self):
        model = None
        if self.type_ == 'AN':
            model = 'stock.shipment.out'
        if not model:
            return
        Model = Pool().get(model)
        res = Model.search([('number', '=', self.reference)], limit=1)
        self.origin = res[0] if res else None


class PIALIN(ModelSQL, ModelView):
    'Edi Sale Line PIALIN'
    __name__ = 'edi.sale.line.pialin'

    line = fields.Many2One('edi.sale.line', 'Edi Sale Line',
        ondelete='CASCADE')
    type = fields.Selection([
            (None, ''), ('SA', 'Supplier Code'),
            ('IN', 'Purchaser Code'), ('SN', 'Serial Number'),
            ('NB', 'Lot Number'), ('EN', 'Expedition'),
            ('GB', 'Internal Group'), ('MF', 'Manufacturer Code'),
            ('UA', 'Purchaser Code'), ('CNA', 'National Code'),
            ('BP', 'Purchase Part Number')
            ], 'Type', readonly=True)
    code = fields.Char('Code', readonly=True)
    qualifier = fields.Selection([
            (None, ''),
            ('F', 'Free Text'),
            ('C', 'Encoded Description'),
            ('E', 'Short Description'),
            ], 'Qualifier',
        readonly=True)
    description = fields.Char('Description', readonly=True)


class SaleEdiLineQty(ModelSQL, ModelView):
    'Invoice Edi Line Qty'
    __name__ = 'edi.sale.line.quantity'

    type_ = fields.Selection([('21', 'Purchased'), ('59', 'Expedition'),
        ('192', 'Free included'), ('15E', 'Without Charge')], 'Type',
        readonly=True)
    quantity = fields.Float('Quantity', digits=(16, 4), readonly=True)
    uom_char = fields.Char('Uom', readonly=True)
    line = fields.Many2One('edi.sale.line', 'Line', ondelete='CASCADE')
    conditions = fields.Selection([(None, ''), ('81E', 'Invoice but not send'),
        ('82E', 'Send but no Invoice'), ('83E', 'Send full sale')],
        'Especial Conditions', readonly=True)


class SaleEdiTax(ModelSQL, ModelView):
    'Edi Sale Tax'
    __name__ = 'edi.sale.tax'

    type_ = fields.Selection([('VAT', 'VAT'), ('EXT', 'Exempt'),
        ('RET', 'IRPF'), ('RE', 'Equivalence Surcharge'),
        ('ACT', 'Alcohol Tax'), ('IGIC', 'IGIC')], 'Type', readonly=True)
    percent = fields.Numeric('Percent', digits=(16, 2), readonly=True)
    tax_amount = fields.Numeric('Tax Amount', digits=(16, 2), readonly=True)
    line = fields.Many2One('edi.sale.line', 'Line', ondelete='CASCADE',
        readonly=True)

    def search_tax(self):
        # TODO: Not implementd, now use product tax
        pass


class SaleEdiDiscount(ModelSQL, ModelView):
    'Sale Edi discount'
    __name__ = 'edi.sale.discount'

    type_ = fields.Selection([('A', 'Discount'), ('C', 'Charge')], 'Type',
        readonly=True)
    sequence = fields.Integer('sequence', readonly=True)
    discount = fields.Selection([(None, ''), ('EAB', 'Prompt Payment'),
        ('TD', 'Commercial'), ('X40', 'Royal decree')], 'Discount Type',
        readonly=True)
    percent = fields.Numeric('Percent', digits=(16, 2), readonly=True)
    amount = fields.Numeric('Amount', digits=(16, 2), readonly=True)
    sale_edi = fields.Many2One('edi.sale', 'Sale Edi',
         ondelete='CASCADE', readonly=True)
    line = fields.Many2One('edi.sale.line', 'Edi sle Line', ondelete='CASCADE')


class SaleEdiLine(ModelSQL, ModelView):
    'Edi Sale Line'
    __name__ = 'edi.sale.line'

    edi_sale = fields.Many2One('edi.sale', 'Edi Sale', ondelete='CASCADE')
    code = fields.Char('code', readonly=True)
    code_type = fields.Selection([(None, ''), ('EAN', 'EAN'), ('EAN8', 'EAN8'),
            ('EAN13', 'EAN13'), ('EAN14', 'EAN14'), ('DUN14', 'DUN14'),
            ('EN', 'EN')], 'Code Type', readonly=True)
    sequence = fields.Integer('Sequence', readonly=True)
    pialin = fields.One2Many('edi.sale.line.pialin', 'line', 'Pialin',
        readonly=True)
    expiration_date = fields.Date('Expiration Date', readonly=True)
    delivery_date = fields.Date('Delivery Date', readonly=True)
    intervention_date = fields.Date('Intervention Date', readonly=True)
    expiration_days = fields.Integer('Expiration Days', readonly=True)
    base_amount = fields.Numeric('Base Amount', digits=(16, 2), readonly=True)
    total_amount = fields.Numeric('Total Amount', digits=(16, 2),
        readonly=True)
    unit_price = fields.Numeric('Unit Price', digits=(16, 4), readonly=True)
    gross_price = fields.Numeric('Gross Price', digits=(16, 4), readonly=True)
    taxes = fields.One2Many('edi.sale.tax', 'line', 'Taxes', readonly=True)
    quantities = fields.One2Many('edi.sale.line.quantity', 'line',
        'Quantities', readonly=True)
    discounts = fields.One2Many('edi.sale.discount', 'line', 'Discounts',
        readonly=True)
    product = fields.Many2One('product.product', 'Product')
    quantity = fields.Function(fields.Float('Quantity', digits=(16, 4)),
         'get_sale_quantity')
    sale_line = fields.Many2One('sale.line', 'sale Line', readonly=True,
        ondelete='RESTRICT')

    def get_sale_quantity(self, name=None):
        for q in self.quantities:
            if q.type_ == '21':
                return q.quantity
        return 0

    def read_PIALIN(self, message):
        if not getattr(self, 'pialin', False):
            Pialin = Pool().get('edi.sale.line.pialin')
            pialin = Pialin()
            self.pialin = (pialin,)
        pialin = self.pialin[-1]
        pialin.type = message.pop(0)
        pialin.code = message.pop(0)

    def read_IMDLIN(self, message):
        if not getattr(self, 'pialin', False):
            Pialin = Pool().get('edi.sale.line.pialin')
            pialin = Pialin()
            self.pialin = (pialin,)
        pialin = self.pialin[-1]
        pialin.qualifier = message.pop(0) if message else ''
        pialin.description = message[-1] if message else ''

    def read_QTYLIN(self, message):
        QTY = Pool().get('edi.sale.line.quantity')
        qty = QTY()
        qty.type_ = message.pop(0) if message else ''
        quantity = message.pop(0) if message else None
        qty.quantity = float(quantity) if quantity else 0
        if qty.type_ == '21':
            self.quantity = qty.quantity
        if message:
            qty.uom_char = message.pop(0)
        if not getattr(self, 'quantities', False):
            self.quantities = []
        self.quantities += (qty,)

    def read_ALILIN(self, message):
        if not self.pialin:
            return
        pialin = self.pialin[-1]
        pialin.qualifier = message.pop(0) if message else ''
        pialin.description = message[-1] if message else ''

    def read_DTMLIN(self, message):
        self.expiration_date = to_date(message.pop(0)) if message else None
        self.delivery_date = to_date(message.pop(0)) if message else None
        self.intervention_date = to_date(message.pop(0)) if message else None
        days = message.pop(0) if message else 0
        self.expiration_days = int(days if days else 0)

    def read_FTXLIN(self, message):
        pass

    def read_PRILIN(self, message):
        type_ = message.pop(0)
        if type_ == 'AAA':
            self.unit_price = to_decimal(message.pop(0), 4
                ) if message else Decimal(0)
        elif type_ == 'AAB':
            self.gross_price = to_decimal(message.pop(0), 4
                ) if message else Decimal(0)

    def read_RFFLIN(self, message):
        pass

    def read_TAXLIN(self, message):
        Tax = Pool().get('edi.sale.tax')
        tax = Tax()
        tax.type_ = message.pop(0) if message else ''
        tax.percent = to_decimal(message.pop(0)) if message else Decimal(0)
        if message:
            tax.tax_amount = to_decimal(message.pop(0))
        if not getattr(self, 'taxes', False):
            self.taxes = []
        self.taxes += (tax,)

    def read_LIN(self, message):
        self.code = message.pop(0) if message else ''
        self.code_type = message.pop(0) if message else ''
        self.sequence = message.pop(0) if message else None

    def read_MOALIN(self, message):
        self.base_amount = (to_decimal(message.pop(0)) if message else
            Decimal(0))
        self.total_amount = (to_decimal(message.pop(0)) if message else
            Decimal(0))

    def read_ALCLIN(self, message):
        Discount = Pool().get('edi.sale.discount')
        discount = Discount()
        discount.type_ = message.pop(0) if message else ''
        sequence = message.pop(0) if message else None
        discount.sequence = int(sequence) or None
        discount.discount = message.pop(0) if message else ''
        discount.percent = (to_decimal(message.pop(0)) if message else
            Decimal(0))
        discount.amount = to_decimal(message.pop(0)) if message else Decimal(0)
        if not getattr(self, 'discounts', False):
            self.discounts = []
        self.discounts += (discount,)

    def read_MEALIN(self, message):
        # Not implemented
        pass

    def search_related(self):
        pool = Pool()
        ProductIdentifier = pool.get('product.identifier')
        domain = [
            ('type', '=', 'ean'),
            ('code', '=', self.code)
            ]
        barcode = ProductIdentifier.search(domain, limit=1)
        if not barcode:
            return
        product = barcode[0].product
        self.product = product


class SaleEdi(ModelSQL, ModelView):
    'Edi Sale'
    __name__ = 'edi.sale'

    company = fields.Many2One('company.company', 'Company', readonly=True)
    number = fields.Char('Number', readonly=True)
    type_ = fields.Selection([
        (None, ''),
        ('220', 'Pedido normal'),
        ('226', 'Pedido parcial que cancela un pedido abierto'),
        ('227', 'Pedido consignacion')],
        'Document Type', readonly=True)
    function_ = fields.Selection([
        (None, ''),
        ('9', 'Original'),
        ('1', 'Cancel'),
        ('4', 'Modify'),
        ('5', 'Replazement'),
        ('31', 'Copy')],
        'Function Type', readonly=True)
    document_date = fields.Date('Document Date', readonly=True)
    delivery_date = fields.Date('Delivery Date', readonly=True)
    first_deliver_date = fields.Date('First Delivery Date', readonly=True)
    last_deliver_date = fields.Date('Last Delivery Date', readonly=True)
    special_condition = fields.Selection([
        (None, ''),
        ('81E', 'Facturar pero no reabastecer'),
        ('82E', 'Enviar pero no facturar'),
        ('83E', 'Entregar el pedido entero')], 'Special Condition',
        readonly=True)
    descriptions = fields.One2Many('edi.sale.description', 'sale',
        'Description', readonly=True)
    parties = fields.One2Many('edi.sale.party', 'edi_sale', 'Parties',
        readonly=True)
    currency_code = fields.Char('Currency', readonly=True)
    currency = fields.Many2One('currency.currency', 'Currency')
    lines = fields.One2Many('edi.sale.line', 'edi_sale', 'Lines')
    gross_amount = fields.Numeric('Gross Amount', digits=(16, 2),
        readonly=True)
    base_amount = fields.Numeric('Base Amount', digits=(16, 2), readonly=True)
    manual_party = fields.Many2One('party.party', 'Manual Party',
        context={
            'company': Eval('company'),
            },
        depends=['company'])
    party = fields.Function(fields.Many2One('party.party', 'Party',
            context={
                'company': Eval('company'),
            },
            depends=['company']),
         'get_party', searcher='search_party')
    references = fields.One2Many('edi.sale.reference',
        'edi_sale', 'References', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], 'State', readonly=True)
    sale = fields.Function(fields.Many2One('sale.sale', 'Sale'),
        'get_sale', searcher='search_sale')
    sale_pricelist_from_edi = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
        ('party', 'Party'),
        ], "Sale PriceList From EDI", sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'create_sale': {
                'invisible': Eval('state').in_(['cancel', 'done']),
                'depends': ['state'],
            },
            'search_references': {
                'invisible': Eval('state').in_(['cancel', 'done']),
                'depends': ['state']
            },
            'cancel_sale': {'invisible': Eval('state').in_(['cancel'])}
        })

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_sale_pricelist_from_edi():
        return 'party'

    def get_party(self, name):
        if self.manual_party:
            return self.manual_party.id
        for s in self.parties:
            if s.type_ == 'NADBY':
                return s.party and s.party.id

    @classmethod
    def search_party(cls, name, clause):
        return ['OR', ('manual_party', ) + tuple(clause[1:]),
                [('parties.type_', '=', 'NADBY'),
                    ('parties.party', ) + tuple(clause[1:])]]

    def get_sale(self, name=None):
        pool = Pool()
        Sale = pool.get('sale.sale')

        sales = Sale.search([
                ('origin', '=', self),
                ])
        if not sales:
            return
        elif len(sales) == 1:
            return sales[0].id
        else:
            raise UserError(gettext('sale_edi_ediversa.msg_to_many_sales',
                    sales=", ".join(s.number or s.id for s in sales)))

    @classmethod
    def search_sale(cls, name, clause):
        pool = Pool()
        Sale = pool.get('sale.sale')
        table = cls.__table__()
        sale = Sale.__table__()

        _, operator, value = clause
        if not value:
            # Without sales
            sql_where = sale.origin == None
        else:
            # By the moment it's not needed this control, becasue the field is
            # not searchable directly, only for the tab. But if in some place
            # try to search not rise an error.
            Operator = fields.SQL_OPERATORS[operator]
            sql_where = Operator(sale.number, value)
        query = table.join(sale, 'LEFT',
            condition=(sale.origin.like('edi.sale,%')
                & (table.id == Cast(Substring(sale.origin, 10), 'INTEGER')))
                ).select(table.id, where=sql_where)
        return [('id', 'in', query)]

    def read_ORD(self, message):
        self.number = message.pop(0)
        self.type_ = message.pop(0)
        if message:
            self.function_ = message.pop(0)

    def read_DTM(self, message):
        self.document_date = to_date(message.pop(0))
        if message:
            self.delivery_date = to_date(message.pop(0))
        if message:
            self.first_delivery_date = to_date(message.pop(0))
        if message:
            self.last_delivery_date = to_date(message.pop(0))

    def get_ALI(self, message):
        self.special_condition = message.pop(0)

    def read_CTA(self, message):
        # Not implemented
        pass

    def read_COM(self, message):
        # Not implemented
        pass

    def read_CUX(self, message):
        # Not implemented
        pass

    def read_RFF(self, message):
        pass

    def read_CNTRES(self, message):
        # Not implemented
        pass

    def read_MOARES(self, message):
        self.base_amount = (to_decimal(message.pop(0)) if message else
            Decimal(0))
        self.gross_amount = to_decimal(message.pop(0)
            ) if message else Decimal(0)

    @classmethod
    def import_edi_file(cls, sales, data):
        pool = Pool()
        EdiSaleDescription = pool.get('edi.sale.description')
        SaleEdi = pool.get('edi.sale')
        SaleLineEdi = pool.get('edi.sale.line')
        PartyEdi = pool.get('edi.sale.party')
        # Configuration = pool.get('stock.configuration')

        default_values = SaleEdi.default_get(SaleEdi._fields.keys(),
            with_rec_name=False)

        # config = Configuration(1)
        separator = '|'  # TODO config.separator

        sale_edi = None
        sale_line = None
        document_type = data.pop(0).replace('\n', '').replace('\r', '')
        if document_type != 'ORDERS_D_96A_UN_EAN008':
            return
        for line in data:
            line = line.replace('\n', '').replace('\r', '')
            line = line.split(separator)
            msg_id = line.pop(0)
            if msg_id == 'ORD':
                sale_edi = SaleEdi(**default_values)
                sale_edi.read_ORD(line)
            elif 'FTX' in msg_id:
                edi_sale_description = EdiSaleDescription()
                edi_sale_description.read_FTX(line)
                if not getattr(sale_edi, 'descriptions', False):
                    sale_edi.descriptions = []
                sale_edi.descriptions += (edi_sale_description,)
            elif 'CTA' in msg_id:
                # not implemented
                continue
            elif 'COM' in msg_id:
                # not implemented
                continue
            elif 'CUX' in msg_id:
                # not implemented
                continue
            elif 'PAT' in msg_id:
                # not implemented
                continue
            elif msg_id == 'LIN':
                if sale_line:
                    sale_line.search_related()
                sale_line = SaleLineEdi()
                sale_line.read_LIN(line)
                if not getattr(sale_edi, 'lines', False):
                    sale_edi.lines = []
                sale_edi.lines += (sale_line,)
            elif 'LIN' in msg_id:
                getattr(sale_line, 'read_%s' % msg_id)(line)
            elif msg_id in [x[0] for x in SUPPLIER_TYPE]:
                party = PartyEdi()
                getattr(party, 'read_%s' % msg_id)(line)
                party.search_party()
                if not getattr(sale_edi, 'parties', False):
                    sale_edi.parties = []
                sale_edi.parties += (party,)
            elif 'NAD' in msg_id:
                continue
            else:
                getattr(sale_edi, 'read_%s' % msg_id)(line)

        # look for reference for last line
        if sale_line:
            sale_line.search_related()
        return sale_edi

    def add_attachment(self, attachment, filename=None):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        if not filename:
            filename = datetime.now().strftime("%y/%m/%d %H:%M:%S")
        attach = Attachment(
            name=filename,
            type='data',
            data=attachment.encode('utf-8'),
            resource=self)
        attach.save()

    @classmethod
    def import_sales(cls, edi_sale=None):
        pool = Pool()
        Configuration = pool.get('sale.configuration')

        configuration = Configuration(1)
        source_path = os.path.abspath(configuration.inbox_path_edi
            or DEFAULT_FILES_LOCATION)

        files = [os.path.join(source_path, fp) for fp in
            os.listdir(source_path) if os.path.isfile(os.path.join(
                    source_path, fp))]
        files_to_delete = []
        to_save = []
        attachments = dict()
        for fname in files:
            if fname[-4:].lower() not in KNOWN_EXTENSIONS:
                continue
            with open(fname, 'r', encoding='latin-1') as fp:
                data = fp.readlines()
                sale_edi = cls.import_edi_file([], data)

            basename = os.path.basename(fname)
            if sale_edi:
                attachments[sale_edi] = ("\n".join(data), basename)
                to_save.append(sale_edi)
                files_to_delete.append(fname)

        if to_save:
            cls.save(to_save)

        with Transaction().set_user(0, set_context=True):
            for sale_edi, (data, basename) in attachments.items():
                sale_edi.add_attachment(data, basename)

        if files_to_delete:
            for file in files_to_delete:
                os.remove(file)

    @classmethod
    @ModelView.button
    def search_references(cls, edi_sales):
        pool = Pool()
        Line = pool.get('edi.sale.line')
        to_save = []
        for edi_sale in edi_sales:
            if edi_sale.sale:
                continue
            for eline in edi_sale.lines:
                eline.search_related()
                to_save.append(eline)
        Line.save(to_save)

    @classmethod
    @ModelView.button
    def cancel_sale(cls, edi_sales):
        to_save = []
        for esale in edi_sales:
            if esale.sale and esale.sale.state != 'cancel':
                raise UserError(gettext('sale_edi_ediversa.msg_no_cancel_sale',
                number=esale.number))
            esale.state = 'cancel'
            to_save.append(esale)
        cls.save(to_save)

    @classmethod
    @ModelView.button
    def create_sale(cls, edi_sales):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')

        default_values = Sale.default_get(Sale._fields.keys(),
                with_rec_name=False)
        to_save = []
        to_done = []
        for edi_sale in edi_sales:
            if edi_sale.sale:
                continue
            sale = Sale(**default_values)
            sale.sale_date = edi_sale.document_date
            sale.party = edi_sale.party
            sale.on_change_party()
            sale.reference = edi_sale.number

            for party in edi_sale.parties:
                if party.type_ == 'NADIV':
                    sale.invoice_party = party.party
                    sale.on_change_invoice_party()
                    sale.invoice_address = (party.address if party.address else
                        party.party.addresses[0])
                elif party.type_ == 'NADDP':
                    sale.shipment_party = party.party
                    sale.on_change_shipment_party()
                    sale.shipment_address = party.address

            sale.lines = []
            price_list = None
            if hasattr(sale, 'price_list'):
                price_list = sale.price_list.id if sale.price_list else None
            with Transaction().set_context(price_list=price_list):
                for eline in edi_sale.lines:
                    if not eline.product:
                        raise UserError(
                            gettext('sale_edi_ediversa.msg_no_product',
                                code=eline.code or ''))
                    if not eline.product.salable:
                        raise UserError(
                            gettext('sale_edi_ediversa.msg_no_product_salable',
                                code=eline.code or ''))
                    line = Line()
                    line.product = eline.product
                    line.on_change_product()
                    line.quantity = eline.quantity
                    line.on_change_quantity()

                    if edi_sale.sale_pricelist_from_edi == 'yes':
                        pricelist_from_edi = True
                    elif edi_sale.sale_pricelist_from_edi == 'party':
                        pricelist_from_edi = (
                            edi_sale.party.sale_pricelist_from_edi)
                    else:
                        pricelist_from_edi = False

                    if pricelist_from_edi:
                        if hasattr(line, 'gross_unit_price'):
                            line.gross_unit_price = eline.unit_price
                            line.on_change_gross_unit_price()
                        else:
                            line.unit_price = eline.unit_price
                    sale.lines += (line,)
            sale.is_edi = True
            sale.origin = str(edi_sale)
            sale.edi_sale = edi_sale
            to_save.append(sale)
            edi_sale.state = 'done'
            to_done.append(edi_sale)
        Sale.save(to_save)
        cls.save(to_done)

    @classmethod
    def copy(cls, edi_sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('state', 'draft')
        return super(SaleEdi, cls).copy(edi_sales, default=default)


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    is_edi = fields.Boolean('Is Edi',
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)

        # Field name change:
        if table.column_exist('edi'):
            table.column_rename('edi', 'is_edi')

        super().__register__(module_name)

    @staticmethod
    def default_is_edi():
        return False

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['edi.sale']

    @classmethod
    def get_origin(cls):
        res = super().get_origin()
        return res + [('edi.sale', 'Edi Sale')]

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, sales):
        pool = Pool()
        EdiSale = pool.get('edi.sale')

        edi_sales = []
        for sale in sales:
            if isinstance(sale.origin, EdiSale):
                sale.origin.state = 'cancel'
                edi_sales.append(sale.origin)
        EdiSale.save(edi_sales)
        super().cancel(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('quoted_by', 'confirmed_by')
    def draft(cls, sales):
        pool = Pool()
        EdiSale = pool.get('edi.sale')

        edi_sales = []
        for sale in sales:
            if isinstance(sale.origin, EdiSale):
                sale.origin.state = 'done'
                edi_sales.append(sale.origin)
        EdiSale.save(edi_sales)
        super().draft(sales)

    @classmethod
    def write(cls, *args):
        pool = Pool()
        EdiSale = pool.get('edi.sale')
        Warning = pool.get('res.user.warning')

        actions = iter(args)
        for sales, values in zip(actions, actions):
            if 'origin' in values:
                if (values.get('origin')
                        and values['origin'].startswith('edi.sale')):
                    values['is_edi'] = True
                    edi_sale = EdiSale(int(values['origin'].split(',')[1]))
                    edi_sale.state = 'done'
                    edi_sale.save()
                    if not edi_sale.sale:
                        continue
                    raise UserError(
                        gettext('sale_edi_ediversa.msg_edi_sale_with_sale',
                            edi_sale=edi_sale.number,
                            sale=(edi_sale.sale.number
                                or edi_sale.sale.reference
                                or edi_sale.sale.id)))
                elif not values.get('origin'):
                    edi_sales = [sale.origin for sale in sales
                            if sale.origin
                            and sale.origin.__name__ == 'edi.sale']
                    numbers = ", ".join([
                            edi_sale.number for edi_sale in edi_sales])
                    if edi_sales:
                        key = 'clean_origin_sale_%s' % sales[0].id
                        if Warning.check(key):
                            raise UserWarning(key,
                                gettext('sale_edi_ediversa.'
                                    'msg_cancel_sale_edi_ediversa',
                                    edi_sales=numbers))
                        values['is_edi'] = False
                        EdiSale.write(edi_sales, {'state': 'cancel'})
        super().write(*args)

    @fields.depends('origin', 'is_edi')
    def on_change_origin(self):
        pool = Pool()
        EdiSale = pool.get('edi.sale')

        if not self.origin and self.is_edi:
            self.is_edi = False
        elif isinstance(self.origin, EdiSale) and hasattr(self.origin, 'sale'):
            self.is_edi = True
