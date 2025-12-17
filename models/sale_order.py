# -*- coding: utf-8 -*-

from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_pricelist_price(self):
        """
        Override pricelist price computation for bus tickets.
        Always return the manually set price_unit instead of computing from pricelist.
        """
        self.ensure_one()
        
        # Check if this is a bus ticket product
        if self.product_id and self.product_id.default_code == 'bus_ticket':
            # Return the manually set price_unit, don't use pricelist
            _logger.info(f"Bus ticket detected - preserving manual price {self.price_unit}")
            return self.price_unit
        
        # For other products, use standard pricelist logic
        return super()._get_pricelist_price()
    
    @api.onchange('product_id', 'product_uom_qty')
    def _onchange_product_id_warning(self):
        """
        Override product change handler for bus tickets.
        Prevent price recalculation on product/quantity change.
        """
        # Check if this is a bus ticket product
        if self.product_id and self.product_id.default_code == 'bus_ticket':
            # Skip the standard onchange that would recalculate price
            _logger.info(f"Bus ticket - skipping price recalculation on product change")
            return {}
        
        # For other products, use standard logic
        return super()._onchange_product_id_warning()
    
    def _prepare_invoice_line(self, **optional_values):
        """Preserve bus ticket price when creating invoice"""
        res = super()._prepare_invoice_line(**optional_values)
        
        if self.product_id and self.product_id.default_code == 'bus_ticket':
            # Force the correct price from the order line
            res['price_unit'] = self.price_unit
            _logger.info(f"Preserving bus ticket price {self.price_unit} in invoice line")
        
        return res

